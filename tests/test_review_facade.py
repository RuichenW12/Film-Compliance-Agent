from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
import threading

import pytest

from core.errors import ForbiddenError, StateInvalidError
from core.llm import ScriptedLLM, UnavailableLLM
from core.review_facade import ReviewFacade
from core.script_intake import SCRIPT_INTAKE_PROMPT_ID
from schemas.enums import AmountBracket, ProductionStage
from schemas.reviews import (
    ConfirmedReviewDetails,
    IdeaOnly,
    IntakeStatus,
    ReviewArtifactType,
    ReviewMode,
    ReviewState,
    StartReviewCommand,
    UploadedScript,
)
from store.sqlite import SqliteStores


SCRIPT = """# 《先挂电话》

- 目标时长：约 30 分钟
- 集数：1 集

### 第一集 场景一：派出所
社区民警帮助居民核实一通可疑来电。
"""

INTAKE_REPLY = {
    "tags": {
        "value": ["public security", "family drama"],
        "origin": "suggested",
        "explanation": "The story joins scam prevention with family conflict.",
    },
    "synopsis": {
        "value": "A family and a community officer confront a suspicious call.",
        "origin": "suggested",
        "explanation": "This captures the central story conflict.",
    },
    "episode_count": {
        "value": 10,
        "origin": "suggested",
        "explanation": "Ten episodes preserve the source duration.",
    },
    "episode_minutes": {
        "value": 3,
        "origin": "suggested",
        "explanation": "Three minutes per episode makes ten episodes total thirty minutes.",
    },
    "amount_bracket": {
        "value": "at_or_above_upper",
        "origin": "suggested",
        "explanation": "A planning estimate from the supplied ranges.",
    },
}


def facade(stores, snapshots, clock, llm=None) -> ReviewFacade:
    return ReviewFacade(
        stores=stores,
        snapshots=snapshots,
        clock=clock,
        llm=llm or ScriptedLLM({SCRIPT_INTAKE_PROMPT_ID: INTAKE_REPLY}),
    )


def start_script(service: ReviewFacade, owner: str = "u_demo"):
    return service.start(
        StartReviewCommand(
            owner_uid=owner,
            source=UploadedScript(
                filename="script.md",
                media_type="text/markdown",
                content=SCRIPT.encode(),
            ),
        )
    )


def confirmed(**updates) -> ConfirmedReviewDetails:
    values = {
        "title": "先挂电话（确认版）",
        "tags": ["公安", "现实题材"],
        "synopsis": "社区民警在派出所帮助居民核实可疑来电。",
        "episode_count": 10,
        "episode_minutes": 3,
        "amount_bracket": AmountBracket.AT_OR_ABOVE_UPPER,
    }
    values.update(updates)
    return ConfirmedReviewDetails(**values)


def test_start_hides_upload_orchestration_and_waits_for_confirmation(
    stores, review_snapshots, clock
) -> None:
    view = start_script(facade(stores, review_snapshots, clock))

    assert view.state is ReviewState.AWAITING_CONFIRMATION
    assert view.mode is ReviewMode.SCRIPT
    assert view.intake_status is IntakeStatus.COMPLETE
    assert view.candidates.title.value == "先挂电话"
    assert view.candidates.episode_count.value == 10
    assert view.candidates.episode_minutes.value == 3
    assert view.source_sha256
    assert view.source_download_url.endswith("/source")
    assert [option.label for option in view.amount_options] == [
        "Below CNY 300,000",
        "CNY 300,000–800,000",
        "CNY 800,000 or above",
    ]
    assert stores.projects.list_all()[0].intent_profile.synopsis is None
    assert stores.facts.list(stores.projects.list_all()[0].project_id) == []


def test_source_bytes_and_normalized_text_are_stored_separately(
    stores, review_snapshots, clock
) -> None:
    view = start_script(facade(stores, review_snapshots, clock))
    project = stores.projects.list_all()[0]
    asset = stores.assets.list(project.project_id)[0]

    assert asset.sha256 == view.source_sha256
    assert stores.blobs.get(asset.storage_uri) == SCRIPT.encode()
    assert asset.text_storage_uri != asset.storage_uri
    assert stores.blobs.get(asset.text_storage_uri).decode() == SCRIPT


def test_source_download_returns_original_bytes_and_checks_owner(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock)
    view = start_script(service, owner="u_owner")

    source = service.source(view.review_id, "u_owner")

    assert source.filename == "script.md"
    assert source.media_type == "text/markdown"
    assert source.content == SCRIPT.encode()
    with pytest.raises(ForbiddenError):
        service.source(view.review_id, "u_other")


def test_confirm_uses_edited_values_then_runs_analysis(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)

    result = service.confirm(started.review_id, "u_demo", confirmed())

    assert result.state is ReviewState.COMPLETE
    assert result.confirmed.title == "先挂电话（确认版）"
    assert result.classification.class_name == "Class 1"
    assert result.classification.co_review_required is True
    assert result.semantic_status.value in {"complete", "pending"}
    assert result.findings
    assert {artifact.artifact_type for artifact in result.artifacts} == {
        ReviewArtifactType.FORM,
        ReviewArtifactType.SUMMARY,
        ReviewArtifactType.ANNOTATED_SCRIPT,
    }

    project = stores.projects.list_all()[0]
    assert project.title_working == "先挂电话（确认版）"
    assert project.intent_profile.production_stage is ProductionStage.SCRIPT_READY
    assert project.intent_profile.genre_keywords == ["公安", "现实题材"]
    assert stores.forms.latest(project.project_id) is not None


def test_failed_confirmation_exposes_safe_recovery_copy(
    stores, review_snapshots, clock, monkeypatch
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)

    def fail(*_args, **_kwargs):
        raise RuntimeError("private renderer hostname and stack detail")

    monkeypatch.setattr(service._workflow, "apply_review_confirmation", fail)
    with pytest.raises(RuntimeError):
        service.confirm(started.review_id, "u_demo", confirmed())

    restored = service.get(started.review_id, "u_demo")
    assert restored.state is ReviewState.FAILED
    assert "private renderer" not in (restored.failure_message or "")
    assert "Start a new review" in (restored.failure_message or "")


def test_failed_view_does_not_reload_the_broken_snapshot(
    stores, review_snapshots, clock, monkeypatch
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)

    def fail(*_args, **_kwargs):
        raise RuntimeError("snapshot pack unavailable")

    monkeypatch.setattr(service._snapshots, "get_pack", fail)
    with pytest.raises(RuntimeError, match="snapshot pack unavailable"):
        service.confirm(started.review_id, "u_demo", confirmed())

    restored = service.get(started.review_id, "u_demo")
    assert restored.state is ReviewState.FAILED
    assert restored.classification is None
    assert restored.amount_options == []


def test_upload_orchestration_failure_persists_failed_session(
    stores, review_snapshots, clock, monkeypatch
) -> None:
    service = facade(stores, review_snapshots, clock)

    def fail(*_args, **_kwargs):
        raise RuntimeError("blob store unavailable")

    monkeypatch.setattr(stores.blobs, "put", fail)
    with pytest.raises(RuntimeError, match="blob store unavailable"):
        start_script(service)

    sessions = list(stores.review_sessions._items.values())
    assert len(sessions) == 1
    assert sessions[0].state is ReviewState.FAILED
    assert service.get(sessions[0].review_id, "u_demo").failure_message


def test_duplicate_confirmation_returns_existing_result_without_new_findings(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    first = service.confirm(started.review_id, "u_demo", confirmed())
    project = stores.projects.list_all()[0]
    finding_count = len(stores.findings.list(project.project_id))

    second = service.confirm(started.review_id, "u_demo", confirmed())

    assert second == first
    assert len(stores.findings.list(project.project_id)) == finding_count


def test_different_confirmation_after_completion_is_a_state_conflict(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())

    with pytest.raises(StateInvalidError):
        service.confirm(
            started.review_id,
            "u_demo",
            confirmed(title="A different completed answer"),
        )


def test_reanalyze_updates_completed_review_without_duplicate_identity_or_storage(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    first = service.confirm(started.review_id, "u_demo", confirmed())
    before = stores.review_sessions.get(started.review_id)
    assert before is not None
    counts = {
        "projects": len(stores.projects.list_all()),
        "assets": len(stores.assets.list(before.project_id)),
        "sessions": len(stores.review_sessions._items),
        "findings": len(stores.findings.list(before.project_id)),
    }
    edited = confirmed(
        title="先挂电话（导演修订版）",
        tags=["家庭", "反诈"],
        synopsis="女儿和社区民警帮助父亲识破一通诈骗电话。",
        episode_count=12,
        episode_minutes=2,
        amount_bracket=AmountBracket.BETWEEN,
    )

    result = service.reanalyze(started.review_id, "u_demo", edited)

    after = stores.review_sessions.get(started.review_id)
    assert after is not None
    assert result.state is ReviewState.COMPLETE
    assert result.review_id == first.review_id
    assert result.confirmed == edited
    assert result.source_filename == first.source_filename
    assert result.source_sha256 == first.source_sha256
    assert after.project_id == before.project_id
    assert after.asset_version == before.asset_version
    assert after.normalized_text_uri == before.normalized_text_uri
    assert len(stores.projects.list_all()) == counts["projects"]
    assert len(stores.assets.list(after.project_id)) == counts["assets"]
    assert len(stores.review_sessions._items) == counts["sessions"]
    assert len(stores.findings.list(after.project_id)) == counts["findings"]

    project = stores.projects.get(after.project_id)
    assert project is not None
    assert project.title_working == edited.title
    assert project.intent_profile.genre_keywords == edited.tags
    assert project.intent_profile.synopsis == edited.synopsis
    assert project.intent_profile.episode_count == edited.episode_count
    assert project.intent_profile.episode_minutes == edited.episode_minutes
    assert project.intent_profile.amount_bracket is edited.amount_bracket
    assert project.classification is not None
    assert result.classification is not None
    assert stores.facts.get_by_key(after.project_id, "title").value == edited.title
    form = stores.forms.latest(after.project_id)
    assert form is not None
    assert form.fields["title"].value == edited.title
    assert form.fields["episode_count"].value == edited.episode_count
    assert form.fields["episode_minutes"].value == edited.episode_minutes


def test_reanalyze_identical_details_is_a_noop(
    stores, review_snapshots, clock, monkeypatch
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    first = service.confirm(started.review_id, "u_demo", confirmed())

    def unexpected(*_args, **_kwargs):
        raise AssertionError("identical details must not rerun analysis")

    monkeypatch.setattr(service._workflow, "apply_review_confirmation", unexpected)

    assert service.reanalyze(started.review_id, "u_demo", confirmed()) == first


def test_reanalyze_rejects_non_complete_review_and_wrong_owner(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock)
    awaiting = start_script(service, owner="u_owner")

    with pytest.raises(StateInvalidError):
        service.reanalyze(awaiting.review_id, "u_owner", confirmed())

    service.confirm(awaiting.review_id, "u_owner", confirmed())
    with pytest.raises(ForbiddenError):
        service.reanalyze(
            awaiting.review_id,
            "u_other",
            confirmed(title="Unauthorized edit"),
        )


def test_two_concurrent_reanalyses_only_one_claims_and_runs_analysis(
    stores, review_snapshots, clock, monkeypatch
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())
    edited = confirmed(title="Only one winner")
    entered = threading.Event()
    release = threading.Event()
    calls = 0
    calls_lock = threading.Lock()
    original = service._workflow.apply_review_confirmation

    def controlled(*args, **kwargs):
        nonlocal calls
        with calls_lock:
            calls += 1
        entered.set()
        assert release.wait(timeout=5)
        return original(*args, **kwargs)

    monkeypatch.setattr(service._workflow, "apply_review_confirmation", controlled)
    with ThreadPoolExecutor(max_workers=2) as pool:
        winner = pool.submit(
            service.reanalyze, started.review_id, "u_demo", edited
        )
        assert entered.wait(timeout=5)
        loser = pool.submit(
            service.reanalyze, started.review_id, "u_demo", edited
        )
        with pytest.raises(StateInvalidError):
            loser.result(timeout=5)
        release.set()
        assert winner.result(timeout=5).state is ReviewState.COMPLETE

    assert calls == 1


def test_sqlite_two_connections_allow_only_one_reanalysis_claim(
    tmp_path, review_snapshots, clock, monkeypatch
) -> None:
    path = tmp_path / "review-reanalysis-race.db"
    first_stores = SqliteStores.at(path)
    second_stores = SqliteStores.at(path)
    first = facade(first_stores, review_snapshots, clock)
    second = facade(second_stores, review_snapshots, clock)
    started = start_script(first)
    first.confirm(started.review_id, "u_demo", confirmed())
    edited = confirmed(title="SQLite winner")
    barrier = threading.Barrier(2)
    entered = threading.Event()
    release = threading.Event()
    calls = 0
    calls_lock = threading.Lock()

    def wrap(service):
        original = service._workflow.apply_review_confirmation

        def counted(*args, **kwargs):
            nonlocal calls
            with calls_lock:
                calls += 1
            entered.set()
            assert release.wait(timeout=5)
            return original(*args, **kwargs)

        monkeypatch.setattr(service._workflow, "apply_review_confirmation", counted)

    wrap(first)
    wrap(second)

    def run(service):
        barrier.wait(timeout=5)
        try:
            return service.reanalyze(started.review_id, "u_demo", edited)
        except StateInvalidError as exc:
            return exc

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, service) for service in (first, second)]
            assert entered.wait(timeout=5)
            done, _ = wait(futures, timeout=5, return_when=FIRST_COMPLETED)
            assert len(done) == 1
            release.set()
            results = [future.result(timeout=5) for future in futures]
        assert sum(isinstance(result, StateInvalidError) for result in results) == 1
        assert sum(
            getattr(result, "state", None) is ReviewState.COMPLETE
            for result in results
        ) == 1
        assert calls == 1
    finally:
        first_stores.db.close()
        second_stores.db.close()


def test_failed_reanalysis_terminalizes_the_claimed_session(
    stores, review_snapshots, clock, monkeypatch
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())

    def fail(*_args, **_kwargs):
        raise RuntimeError("private reanalysis worker detail")

    monkeypatch.setattr(service._workflow, "run_classification", fail)
    with pytest.raises(RuntimeError, match="private reanalysis worker detail"):
        service.reanalyze(
            started.review_id,
            "u_demo",
            confirmed(title="Failure-triggering edit"),
        )

    restored = service.get(started.review_id, "u_demo")
    assert restored.state is ReviewState.FAILED
    assert "private reanalysis" not in (restored.failure_message or "")
    assert "Start a new review" in (restored.failure_message or "")


def test_review_owner_isolated(stores, review_snapshots, clock) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service, owner="u_owner")

    with pytest.raises(ForbiddenError):
        service.get(started.review_id, "u_other")
    with pytest.raises(ForbiddenError):
        service.confirm(started.review_id, "u_other", confirmed())


def test_idea_mode_is_manual_and_skips_script_review(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = service.start(
        StartReviewCommand(owner_uid="u_demo", source=IdeaOnly())
    )

    assert started.state is ReviewState.AWAITING_CONFIRMATION
    assert started.mode is ReviewMode.IDEA
    assert started.candidates is not None
    assert started.source_download_url is None

    result = service.confirm(started.review_id, "u_demo", confirmed())
    project = stores.projects.list_all()[0]
    assert result.state is ReviewState.COMPLETE
    assert result.findings == []
    assert project.intent_profile.production_stage is ProductionStage.IDEA
    assert stores.assets.list(project.project_id) == []
    assert stores.tasks.list(project.project_id) == []
    assert [artifact.artifact_type for artifact in result.artifacts] == [
        ReviewArtifactType.FORM
    ]


def test_unavailable_intake_still_allows_manual_confirmation(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock, UnavailableLLM())
    started = start_script(service)

    assert started.state is ReviewState.AWAITING_CONFIRMATION
    assert started.intake_status is IntakeStatus.UNAVAILABLE
    assert started.candidates.title.value == "先挂电话"
    assert started.candidates.tags is None

    result = service.confirm(started.review_id, "u_demo", confirmed())
    assert result.state is ReviewState.COMPLETE


def test_retry_intake_reuses_saved_text(stores, review_snapshots, clock) -> None:
    unavailable = facade(stores, review_snapshots, clock, UnavailableLLM())
    started = start_script(unavailable)
    restored = facade(
        stores,
        review_snapshots,
        clock,
        ScriptedLLM({SCRIPT_INTAKE_PROMPT_ID: INTAKE_REPLY}),
    )

    retried = restored.retry_intake(started.review_id, "u_demo")

    assert retried.state is ReviewState.AWAITING_CONFIRMATION
    assert retried.intake_status is IntakeStatus.COMPLETE
    assert retried.candidates.episode_count.value == 10


def test_review_view_does_not_expose_internal_ids_or_raw_states(
    stores, review_snapshots, clock
) -> None:
    view = start_script(facade(stores, review_snapshots, clock))
    payload = view.model_dump_json()

    assert "project_id" not in payload
    assert "asset_version" not in payload
    assert "INTAKE_DONE" not in payload
    assert "script_intake_analysis" not in payload


def test_sqlite_facade_restores_the_confirmation_screen_after_restart(
    tmp_path, review_snapshots, clock
) -> None:
    path = tmp_path / "review-facade.db"
    first_stores = SqliteStores.at(path)
    started = start_script(facade(first_stores, review_snapshots, clock))
    first_stores.db.close()

    reopened = SqliteStores.at(path)
    try:
        restored = facade(reopened, review_snapshots, clock).get(
            started.review_id, "u_demo"
        )
        assert restored.state is ReviewState.AWAITING_CONFIRMATION
        assert restored.candidates.title.value == "先挂电话"
        assert restored.source_sha256 == started.source_sha256
    finally:
        reopened.db.close()
