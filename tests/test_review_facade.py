from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import replace
from pathlib import Path
import threading

import pytest

from core.errors import ForbiddenError, StateInvalidError, UpstreamLLMError
from core.llm import ScriptedLLM, UnavailableLLM
from core.review import SCRIPT_REVIEW_PROMPT_ID
from core.review_facade import ReviewFacade
from core.script_intake import SCRIPT_INTAKE_PROMPT_ID
from core.workflow_service import WorkflowService
from schemas.common import AuditEntry, Fact, SourceRef, TimelineEvent
from schemas.enums import (
    Actor,
    AmountBracket,
    FindingStatus,
    ProductionStage,
    ProjectState,
    SourceRefType,
    TaskStatus,
)
from schemas.policy_snapshot import PackName
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
from schemas.snapshot import SnapshotService
from store.memory import InMemoryStores
from store.sqlite import SqliteStores


SCRIPT = """# 《先挂电话》

- 目标时长：约 30 分钟
- 集数：1 集

### 第一集 场景一：派出所
社区民警帮助居民核实一通可疑来电。
"""

SEMANTIC_SCRIPT = """# 《便利店》

### 第一集 场景一：便利店
顾客买水。
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

EDGE_PACK = {
    "subject_rules": [
        {
            "rule_id": "SR-EDGE-REANALYSIS",
            "category": "public_security",
            "trigger_patterns": ["缉毒"],
            "is_edge_case": True,
            "clause_ref": "nrta-order-16-article-5",
        }
    ]
}


class EdgeReviewSnapshots(SnapshotService):
    def __init__(self, base: SnapshotService) -> None:
        self._base = base

    def latest_version(self, as_of=None) -> str:
        return self._base.latest_version(as_of)

    def get_pack(self, name: PackName, version: str | None = None) -> dict:
        if PackName(name) is PackName.P2_SUBJECT_RULES:
            return dict(EDGE_PACK)
        return self._base.get_pack(name, version)

    def clause(self, clause_id: str, version: str):
        return self._base.clause(clause_id, version)


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


def start_semantic_script(service: ReviewFacade):
    return service.start(
        StartReviewCommand(
            owner_uid="u_demo",
            source=UploadedScript(
                filename="semantic.md",
                media_type="text/markdown",
                content=SEMANTIC_SCRIPT.encode(),
            ),
        )
    )


def semantic_reply(reason: str | None = None) -> dict:
    return {
        "hits": [
            {
                "category": "public_security",
                "quote": "顾客买水。",
                "reason": reason,
            }
        ]
    }


def projection_snapshot(stores, project_id: str) -> dict:
    return {
        "project": stores.projects.get(project_id),
        "facts": stores.facts.list(project_id),
        "findings": stores.findings.list(project_id),
        "form": stores.forms.latest(project_id),
        "tasks": stores.tasks.list(project_id),
        "timeline": stores.timeline.list(project_id),
        "audit": stores.audit.list(project_id),
    }


class DelayedPublication:
    """Pause a bundle publish after it has started reading staged data."""

    def __init__(self, publication, entered: threading.Event, release: threading.Event):
        self._publication = publication
        self._entered = entered
        self._release = release

    @property
    def facts(self):
        self._entered.set()
        assert self._release.wait(timeout=5)
        return self._publication.facts

    def __getattr__(self, name):
        return getattr(self._publication, name)


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

    monkeypatch.setattr(WorkflowService, "apply_review_confirmation", fail)
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
    assert len(
        [
            finding
            for finding in stores.findings.list(after.project_id)
            if finding.active
        ]
    ) == counts["findings"]

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
    original = WorkflowService.apply_review_confirmation

    def controlled(workflow, *args, **kwargs):
        nonlocal calls
        with calls_lock:
            calls += 1
        entered.set()
        assert release.wait(timeout=5)
        return original(workflow, *args, **kwargs)

    monkeypatch.setattr(WorkflowService, "apply_review_confirmation", controlled)
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

    original = WorkflowService.apply_review_confirmation

    def counted(workflow, *args, **kwargs):
        nonlocal calls
        with calls_lock:
            calls += 1
        entered.set()
        assert release.wait(timeout=5)
        return original(workflow, *args, **kwargs)

    monkeypatch.setattr(WorkflowService, "apply_review_confirmation", counted)

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

    monkeypatch.setattr(WorkflowService, "run_classification", fail)
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


def _assert_stale_reanalysis_cannot_claim_after_complete_aba(
    first: ReviewFacade,
    second: ReviewFacade,
    stores,
) -> None:
    started = start_script(first)
    first.confirm(started.review_id, "u_demo", confirmed())
    stale_read = threading.Event()
    resume_stale = threading.Event()
    original_owned = first._owned
    paused = False

    def pause_after_read(review_id: str, actor_uid: str):
        nonlocal paused
        session = original_owned(review_id, actor_uid)
        if not paused and session.state is ReviewState.COMPLETE:
            paused = True
            stale_read.set()
            assert resume_stale.wait(timeout=5)
        return session

    first._owned = pause_after_read
    stale_details = confirmed(title="stale request A")
    fresh_details = confirmed(title="fresh request B")
    with ThreadPoolExecutor(max_workers=1) as pool:
        stale = pool.submit(
            first.reanalyze,
            started.review_id,
            "u_demo",
            stale_details,
        )
        assert stale_read.wait(timeout=5)
        fresh = second.reanalyze(
            started.review_id,
            "u_demo",
            fresh_details,
        )
        assert fresh.state is ReviewState.COMPLETE
        resume_stale.set()
        with pytest.raises(StateInvalidError):
            stale.result(timeout=5)

    current = stores.review_sessions.get(started.review_id)
    assert current is not None
    assert current.state is ReviewState.COMPLETE
    assert current.confirmed == fresh_details
    assert current.generation == 2


def test_memory_reanalysis_claim_rejects_complete_state_aba(
    review_snapshots, clock
) -> None:
    stores = InMemoryStores()
    _assert_stale_reanalysis_cannot_claim_after_complete_aba(
        facade(stores, review_snapshots, clock),
        facade(stores, review_snapshots, clock),
        stores,
    )


def test_sqlite_reanalysis_claim_rejects_complete_state_aba(
    tmp_path, review_snapshots, clock
) -> None:
    path = tmp_path / "review-reanalysis-aba.db"
    first_stores = SqliteStores.at(path)
    second_stores = SqliteStores.at(path)
    try:
        _assert_stale_reanalysis_cannot_claim_after_complete_aba(
            facade(first_stores, review_snapshots, clock),
            facade(second_stores, review_snapshots, clock),
            first_stores,
        )
    finally:
        first_stores.db.close()
        second_stores.db.close()


def test_late_failure_from_old_generation_cannot_overwrite_newer_completion(
    stores, review_snapshots, clock, monkeypatch
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())
    entered = threading.Event()
    release = threading.Event()

    def fail_late(*_args, **_kwargs):
        entered.set()
        assert release.wait(timeout=5)
        raise RuntimeError("old generation failed late")

    monkeypatch.setattr(WorkflowService, "run_classification", fail_late)
    with ThreadPoolExecutor(max_workers=1) as pool:
        old = pool.submit(
            service.reanalyze,
            started.review_id,
            "u_demo",
            confirmed(title="old generation"),
        )
        assert entered.wait(timeout=5)
        claimed = stores.review_sessions.get(started.review_id)
        assert claimed is not None
        newer = claimed.model_copy(
            update={
                "generation": claimed.generation + 1,
                "state": ReviewState.COMPLETE,
                "confirmed": confirmed(title="newer generation"),
            }
        )
        stores.review_sessions.put(newer)
        release.set()
        with pytest.raises(RuntimeError, match="old generation failed late"):
            old.result(timeout=5)

    assert stores.review_sessions.get(started.review_id) == newer


def test_same_asset_reanalysis_preserves_unavailable_semantic_pending(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock, UnavailableLLM())
    started = start_script(service)
    first = service.confirm(started.review_id, "u_demo", confirmed())
    assert first.semantic_status.value == "pending"

    rerun = service.reanalyze(
        started.review_id,
        "u_demo",
        confirmed(title="Pending semantic rerun"),
    )

    assert rerun.semantic_status.value == "pending"


def test_same_asset_reanalysis_calls_semantic_review_again(
    stores, review_snapshots, clock
) -> None:
    llm = ScriptedLLM(
        {
            SCRIPT_INTAKE_PROMPT_ID: INTAKE_REPLY,
            SCRIPT_REVIEW_PROMPT_ID: {"hits": []},
        }
    )
    service = facade(stores, review_snapshots, clock, llm)
    started = start_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())
    assert sum(call.prompt_id == SCRIPT_REVIEW_PROMPT_ID for call in llm.calls) == 1

    rerun = service.reanalyze(
        started.review_id,
        "u_demo",
        confirmed(title="Semantic rerun"),
    )

    assert rerun.semantic_status.value == "complete"
    assert sum(call.prompt_id == SCRIPT_REVIEW_PROMPT_ID for call in llm.calls) == 2


def test_reanalysis_hit_to_no_hit_hides_prior_script_finding(
    stores, review_snapshots, clock
) -> None:
    llm = ScriptedLLM(
        {
            SCRIPT_INTAKE_PROMPT_ID: INTAKE_REPLY,
            SCRIPT_REVIEW_PROMPT_ID: semantic_reply("initial reason"),
        }
    )
    service = facade(stores, review_snapshots, clock, llm)
    started = start_semantic_script(service)
    first = service.confirm(started.review_id, "u_demo", confirmed())
    assert len(first.findings) == 1

    llm._replies[SCRIPT_REVIEW_PROMPT_ID] = {"hits": []}
    rerun = service.reanalyze(
        started.review_id,
        "u_demo",
        confirmed(title="No semantic hit"),
    )

    assert rerun.findings == []
    session = stores.review_sessions.get(started.review_id)
    historical = [
        finding
        for finding in stores.findings.list(session.project_id)
        if finding.asset_version != "intent_profile"
    ]
    assert len(historical) == 1
    assert historical[0].analysis_generation == 1
    assert historical[0].active is False


def test_reanalysis_changed_hit_replaces_visible_script_finding(
    stores, review_snapshots, clock
) -> None:
    llm = ScriptedLLM(
        {
            SCRIPT_INTAKE_PROMPT_ID: INTAKE_REPLY,
            SCRIPT_REVIEW_PROMPT_ID: semantic_reply("first suggestion"),
        }
    )
    service = facade(stores, review_snapshots, clock, llm)
    started = start_semantic_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())
    llm._replies[SCRIPT_REVIEW_PROMPT_ID] = semantic_reply("revised suggestion")

    rerun = service.reanalyze(
        started.review_id,
        "u_demo",
        confirmed(title="Changed semantic hit"),
    )

    assert len(rerun.findings) == 1
    assert rerun.findings[0].suggestion == "revised suggestion"
    session = stores.review_sessions.get(started.review_id)
    historical = [
        finding
        for finding in stores.findings.list(session.project_id)
        if finding.asset_version != "intent_profile"
    ]
    assert len(historical) == 2
    assert [(item.analysis_generation, item.active) for item in historical] == [
        (1, False),
        (2, True),
    ]


def test_reanalysis_new_hit_appears_once_without_duplicate_on_next_generation(
    stores, review_snapshots, clock
) -> None:
    llm = ScriptedLLM(
        {
            SCRIPT_INTAKE_PROMPT_ID: INTAKE_REPLY,
            SCRIPT_REVIEW_PROMPT_ID: {"hits": []},
        }
    )
    service = facade(stores, review_snapshots, clock, llm)
    started = start_semantic_script(service)
    first = service.confirm(started.review_id, "u_demo", confirmed())
    assert first.findings == []
    llm._replies[SCRIPT_REVIEW_PROMPT_ID] = semantic_reply("new hit")

    second = service.reanalyze(
        started.review_id,
        "u_demo",
        confirmed(title="New hit"),
    )
    third = service.reanalyze(
        started.review_id,
        "u_demo",
        confirmed(title="Same hit next generation"),
    )

    assert len(second.findings) == 1
    assert len(third.findings) == 1
    session = stores.review_sessions.get(started.review_id)
    active = [
        finding
        for finding in stores.findings.list(session.project_id)
        if finding.asset_version != "intent_profile" and finding.active
    ]
    assert len(active) == 1
    assert active[0].analysis_generation == 3


def test_script_review_task_failure_terminalizes_without_false_semantic_success(
    stores, review_snapshots, clock, monkeypatch
) -> None:
    llm = ScriptedLLM(
        {
            SCRIPT_INTAKE_PROMPT_ID: INTAKE_REPLY,
            SCRIPT_REVIEW_PROMPT_ID: {"hits": []},
        }
    )
    service = facade(stores, review_snapshots, clock, llm)
    started = start_semantic_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())
    session = stores.review_sessions.get(started.review_id)
    before = projection_snapshot(stores, session.project_id)
    original = llm.structured

    def fail_script_review(request):
        if request.prompt_id == SCRIPT_REVIEW_PROMPT_ID:
            raise RuntimeError("private semantic worker crash")
        return original(request)

    monkeypatch.setattr(llm, "structured", fail_script_review)

    with pytest.raises(UpstreamLLMError):
        service.reanalyze(
            started.review_id,
            "u_demo",
            confirmed(title="Task failure"),
        )

    restored = service.get(started.review_id, "u_demo")
    assert restored.state is ReviewState.FAILED
    assert restored.semantic_status is None
    assert projection_snapshot(stores, session.project_id) == before


def test_reanalysis_replaces_then_hides_classification_alert_findings(
    stores, review_snapshots, clock
) -> None:
    service = facade(
        stores,
        EdgeReviewSnapshots(review_snapshots),
        clock,
        UnavailableLLM(),
    )
    started = service.start(
        StartReviewCommand(owner_uid="u_demo", source=IdeaOnly())
    )
    edge = confirmed(
        tags=["缉毒"],
        synopsis="一名缉毒警察在边境执行卧底任务。",
    )
    first = service.confirm(started.review_id, "u_demo", edge)
    session = stores.review_sessions.get(started.review_id)
    assert session is not None
    assert len([finding for finding in first.findings if finding.explanation]) == 1

    same_edge = service.reanalyze(
        started.review_id,
        "u_demo",
        edge.model_copy(update={"title": "缉毒项目修订版"}),
    )
    active_alerts = [finding for finding in same_edge.findings if finding.explanation]
    assert len(active_alerts) == 1
    stored_alerts = [
        finding
        for finding in stores.findings.list(session.project_id)
        if finding.alert is not None
    ]
    assert len(stored_alerts) == 1
    assert stored_alerts[0].analysis_generation == 2
    assert stored_alerts[0].active is True

    no_edge = service.reanalyze(
        started.review_id,
        "u_demo",
        confirmed(
            title="普通家庭故事",
            tags=["家庭"],
            synopsis="一家人在便利店里化解日常误会。",
        ),
    )
    assert [finding for finding in no_edge.findings if finding.explanation] == []
    stored = stores.findings.list(session.project_id)
    assert len([finding for finding in stored if finding.alert is not None]) == 1
    assert next(finding for finding in stored if finding.alert is not None).active is False


@pytest.mark.parametrize(
    "project_state",
    [
        ProjectState.FORM_FROZEN,
        ProjectState.INSTITUTION_REVIEW,
        ProjectState.INSTITUTION_RETURNED,
        ProjectState.READY_FOR_EXTERNAL_FILING,
        ProjectState.FILED,
        ProjectState.PRODUCTION,
    ],
)
def test_reanalysis_rejects_frozen_or_submitted_project_before_any_write(
    stores, review_snapshots, clock, project_state
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())
    session = stores.review_sessions.get(started.review_id)
    project = stores.projects.get(session.project_id)
    stores.projects.save(project.model_copy(update={"state": project_state}))
    if project_state is ProjectState.FORM_FROZEN:
        draft = stores.forms.latest(session.project_id)
        stores.forms.put(
            session.project_id,
            draft.model_copy(update={"frozen": True, "hash": "frozen-hash"}),
        )
    before_session = stores.review_sessions.get(started.review_id)
    before = projection_snapshot(stores, session.project_id)

    with pytest.raises(StateInvalidError):
        service.reanalyze(
            started.review_id,
            "u_demo",
            confirmed(title=f"Rejected in {project_state.value}"),
        )

    assert stores.review_sessions.get(started.review_id) == before_session
    assert projection_snapshot(stores, session.project_id) == before


@pytest.mark.parametrize("boundary", ["classification", "finding", "form", "event"])
def test_reanalysis_failure_boundaries_preserve_previous_complete_projection(
    stores, review_snapshots, clock, monkeypatch, boundary
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())
    session = stores.review_sessions.get(started.review_id)
    before = projection_snapshot(stores, session.project_id)

    def fail(*_args, **_kwargs):
        raise RuntimeError(f"{boundary} staging failure")

    if boundary == "classification":
        monkeypatch.setattr(WorkflowService, "run_classification", fail)
    elif boundary == "finding":
        monkeypatch.setattr(WorkflowService, "run_script_review", fail)
    elif boundary == "form":
        monkeypatch.setattr(WorkflowService, "form_draft", fail)
    else:
        original = WorkflowService.record_review_event

        def fail_package_event(self, project_id, event, detail):
            if event == "review.package_ready":
                raise RuntimeError("event staging failure")
            return original(self, project_id, event, detail)

        monkeypatch.setattr(
            WorkflowService,
            "record_review_event",
            fail_package_event,
        )

    with pytest.raises(RuntimeError, match=f"{boundary} staging failure"):
        service.reanalyze(
            started.review_id,
            "u_demo",
            confirmed(title=f"Failure at {boundary}"),
        )

    assert service.get(started.review_id, "u_demo").state is ReviewState.FAILED
    assert projection_snapshot(stores, session.project_id) == before
    assert not any(
        event.event == "review.package_ready"
        and event.detail.get("state") == ReviewState.COMPLETE.value
        and event.at > before["timeline"][-1].at
        for event in stores.timeline.list(session.project_id)
    )


def test_terminal_publication_failure_preserves_previous_complete_projection(
    stores, review_snapshots, clock, monkeypatch
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())
    session = stores.review_sessions.get(started.review_id)
    before = projection_snapshot(stores, session.project_id)
    monkeypatch.setattr(
        stores,
        "publish_review_analysis",
        lambda _publication: False,
        raising=False,
    )

    with pytest.raises(StateInvalidError):
        service.reanalyze(
            started.review_id,
            "u_demo",
            confirmed(title="Lost terminal publication"),
        )

    assert projection_snapshot(stores, session.project_id) == before
    assert not any(
        event.event == "review.package_ready"
        and event.at > before["timeline"][-1].at
        for event in stores.timeline.list(session.project_id)
    )


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_bundle_publish_serializes_unrelated_project_writes(
    tmp_path, review_snapshots, clock, monkeypatch, backend
) -> None:
    if backend == "memory":
        stores = InMemoryStores()
        concurrent = stores
    else:
        path = tmp_path / "review-unrelated-project.sqlite3"
        stores = SqliteStores.at(path)
        concurrent = SqliteStores.at(path)
    service = facade(stores, review_snapshots, clock)
    first = start_script(service)
    service.confirm(first.review_id, "u_demo", confirmed())
    second = start_script(service, owner="u_second")
    service.confirm(second.review_id, "u_second", confirmed(title="Project B"))
    second_session = stores.review_sessions.get(second.review_id)
    second_project = stores.projects.get(second_session.project_id)

    entered = threading.Event()
    release = threading.Event()
    write_entered = threading.Event()
    original_publish = stores.publish_review_analysis

    def delayed_publish(publication):
        return original_publish(DelayedPublication(publication, entered, release))

    def write_project():
        write_entered.set()
        return concurrent.projects.save(
            second_project.model_copy(
                update={"title_working": "Project B concurrent"}
            )
        )

    monkeypatch.setattr(stores, "publish_review_analysis", delayed_publish)
    with ThreadPoolExecutor(max_workers=2) as pool:
        publishing = pool.submit(
            service.reanalyze,
            first.review_id,
            "u_demo",
            confirmed(title="Project A reanalyzed"),
        )
        assert entered.wait(timeout=5)
        writing = pool.submit(write_project)
        assert write_entered.wait(timeout=5)
        write_was_blocked = not writing.done()
        release.set()
        publishing.result(timeout=5)
        writing.result(timeout=5)

    assert write_was_blocked
    assert stores.projects.get(second_session.project_id).title_working == (
        "Project B concurrent"
    )
    if backend == "sqlite":
        concurrent.db.close()
        stores.db.close()


def test_memory_bundle_publish_blocks_aggregate_readers_until_complete(
    stores, review_snapshots, clock, monkeypatch
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())
    session = stores.review_sessions.get(started.review_id)
    entered = threading.Event()
    release = threading.Event()
    read_entered = threading.Event()
    original_publish = stores.publish_review_analysis

    def delayed_publish(publication):
        return original_publish(DelayedPublication(publication, entered, release))

    def read_project():
        read_entered.set()
        return stores.projects.get(session.project_id)

    monkeypatch.setattr(stores, "publish_review_analysis", delayed_publish)
    with ThreadPoolExecutor(max_workers=2) as pool:
        publishing = pool.submit(
            service.reanalyze,
            started.review_id,
            "u_demo",
            confirmed(title="Reader atomicity"),
        )
        assert entered.wait(timeout=5)
        reading = pool.submit(read_project)
        assert read_entered.wait(timeout=5)
        read_was_blocked = not reading.done()
        release.set()
        publishing.result(timeout=5)
        assert reading.result(timeout=5).title_working == "Reader atomicity"

    assert read_was_blocked


def test_review_publication_rejects_cross_project_aggregate_identity(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())
    session = stores.review_sessions.get(started.review_id)
    stage = stores.stage_review_analysis(started.review_id, session.project_id)
    analyzing = session.model_copy(
        update={"state": ReviewState.ANALYZING, "generation": session.generation + 1}
    )
    assert stores.review_sessions.compare_and_put(
        session.review_id,
        ReviewState.COMPLETE,
        analyzing,
        expected_generation=session.generation,
    )
    publication = stores.prepare_review_analysis_publication(
        stage,
        analyzing.model_copy(update={"state": ReviewState.COMPLETE}),
    )
    invalid = replace(
        publication,
        project=publication.project.model_copy(update={"project_id": "proj_other"}),
    )

    with pytest.raises(ValueError, match="aggregate identities"):
        stores.publish_review_analysis(invalid)


def test_sqlite_stage_captures_one_consistent_aggregate_snapshot(
    tmp_path, review_snapshots, clock
) -> None:
    path = tmp_path / "review-consistent-stage.sqlite3"
    stores = SqliteStores.at(path)
    concurrent = SqliteStores.at(path)
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())
    session = stores.review_sessions.get(started.review_id)
    entered = threading.Event()
    release = threading.Event()

    def pause_after_snapshot_begins(statement: str) -> None:
        if (
            not entered.is_set()
            and "collection = 'projects'" in statement
            and session.project_id in statement
        ):
            entered.set()
            assert release.wait(timeout=5)

    stores.db._connection.set_trace_callback(pause_after_snapshot_begins)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            stores.stage_review_analysis,
            started.review_id,
            session.project_id,
        )
        assert entered.wait(timeout=5)
        concurrent.facts.add(
            session.project_id,
            Fact(
                fact_id="fact_after_sqlite_snapshot",
                key="after_snapshot",
                value="live only",
                source_ref=SourceRef(
                    type=SourceRefType.USER_ANSWER,
                    answer_id="after_sqlite_snapshot",
                ),
                created_at=clock.now(),
            ),
        )
        release.set()
        stage = future.result(timeout=5)
    stores.db._connection.set_trace_callback(None)

    assert not any(
        fact.fact_id == "fact_after_sqlite_snapshot" for fact in stage.baseline.facts
    )
    assert any(
        fact.fact_id == "fact_after_sqlite_snapshot"
        for fact in stores.facts.list(session.project_id)
    )
    concurrent.db.close()
    stores.db.close()


@pytest.mark.parametrize(
    "mutation",
    [
        "freeze",
        "submission",
        "form_update",
        "project_update",
        "finding_action",
        "fact",
        "task_completion",
        "timeline_audit",
    ],
)
@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_reanalysis_publish_rejects_concurrent_lifecycle_change(
    tmp_path, review_snapshots, clock, monkeypatch, backend, mutation
) -> None:
    if backend == "memory":
        stores = InMemoryStores()
        concurrent = stores
    else:
        path = tmp_path / f"review-lifecycle-{mutation}.sqlite3"
        stores = SqliteStores.at(path)
        concurrent = SqliteStores.at(path)
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())
    session = stores.review_sessions.get(started.review_id)
    previous_complete = session
    before_ready = len(
        [
            event
            for event in stores.timeline.list(session.project_id)
            if event.event == "review.package_ready"
        ]
    )
    entered = threading.Event()
    release = threading.Event()
    original_publish = stores.publish_review_analysis

    def pause_before_publish(publication):
        entered.set()
        assert release.wait(timeout=5)
        return original_publish(publication)

    monkeypatch.setattr(stores, "publish_review_analysis", pause_before_publish)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            service.reanalyze,
            started.review_id,
            "u_demo",
            confirmed(title=f"Concurrent {mutation}"),
        )
        assert entered.wait(timeout=5)
        live_project = concurrent.projects.get(session.project_id)
        if mutation == "freeze":
            concurrent.projects.save(
                live_project.model_copy(update={"state": ProjectState.FORM_FROZEN})
            )
            live_form = concurrent.forms.latest(session.project_id)
            concurrent.forms.put(
                session.project_id,
                live_form.model_copy(update={"frozen": True, "hash": "frozen-race"}),
            )
        elif mutation == "submission":
            concurrent.projects.save(
                live_project.model_copy(
                    update={
                        "state": ProjectState.INSTITUTION_REVIEW,
                        "title_working": "Downstream submitted title",
                    }
                )
            )
        elif mutation == "form_update":
            live_form = concurrent.forms.latest(session.project_id)
            concurrent.forms.put(
                session.project_id,
                live_form.model_copy(update={"hash": "concurrent-form-update"}),
            )
        elif mutation == "project_update":
            concurrent.projects.save(
                live_project.model_copy(
                    update={"title_working": "Concurrent title update"}
                )
            )
        elif mutation == "finding_action":
            finding = next(
                item
                for item in concurrent.findings.list(session.project_id)
                if item.alert is None
            )
            WorkflowService(
                concurrent, review_snapshots, clock
            ).act_on_finding(session.project_id, finding.finding_id, "resolve")
        elif mutation == "fact":
            concurrent.facts.add(
                session.project_id,
                Fact(
                    fact_id="fact_concurrent_reanalysis",
                    key="concurrent_note",
                    value="must survive",
                    source_ref=SourceRef(
                        type=SourceRefType.USER_ANSWER,
                        answer_id="concurrent_reanalysis",
                    ),
                    created_at=clock.now(),
                ),
            )
        elif mutation == "task_completion":
            task = concurrent.tasks.list(session.project_id)[-1]
            concurrent.tasks.save(
                task.model_copy(
                    update={
                        "status": TaskStatus.SUCCEEDED,
                        "result": {"concurrent_completion": True},
                    }
                )
            )
        else:
            concurrent.timeline.add(
                session.project_id,
                TimelineEvent(
                    event_id="event_concurrent_reanalysis",
                    at=clock.now(),
                    actor=Actor.SYSTEM,
                    event="concurrent.timeline",
                ),
            )
            concurrent.audit.add(
                session.project_id,
                AuditEntry(
                    at=clock.now(),
                    actor=Actor.SYSTEM,
                    from_state=live_project.state.value,
                    to_state=live_project.state.value,
                    reason="concurrent.audit",
                ),
            )
        release.set()
        with pytest.raises(StateInvalidError):
            future.result(timeout=5)

    stored_project = stores.projects.get(session.project_id)
    expected_state = {
        "freeze": ProjectState.FORM_FROZEN,
        "submission": ProjectState.INSTITUTION_REVIEW,
        "form_update": ProjectState.CLASSIFIED,
        "project_update": ProjectState.CLASSIFIED,
        "finding_action": ProjectState.CLASSIFIED,
        "fact": ProjectState.CLASSIFIED,
        "task_completion": ProjectState.CLASSIFIED,
        "timeline_audit": ProjectState.CLASSIFIED,
    }[mutation]
    assert stored_project.state is expected_state
    if mutation == "freeze":
        assert stores.forms.latest(session.project_id).frozen is True
        assert stores.forms.latest(session.project_id).hash == "frozen-race"
    elif mutation == "submission":
        assert stored_project.title_working == "Downstream submitted title"
    elif mutation == "form_update":
        assert stores.forms.latest(session.project_id).hash == "concurrent-form-update"
    elif mutation == "project_update":
        assert stored_project.title_working == "Concurrent title update"
    elif mutation == "finding_action":
        assert next(
            item
            for item in stores.findings.list(session.project_id)
            if item.alert is None
        ).status is FindingStatus.RESOLVED
    elif mutation == "fact":
        assert any(
            item.fact_id == "fact_concurrent_reanalysis"
            for item in stores.facts.list(session.project_id)
        )
    elif mutation == "task_completion":
        assert any(
            (item.result or {}).get("concurrent_completion") is True
            for item in stores.tasks.list(session.project_id)
        )
    else:
        assert any(
            item.event_id == "event_concurrent_reanalysis"
            for item in stores.timeline.list(session.project_id)
        )
        assert any(
            item.reason == "concurrent.audit"
            for item in stores.audit.list(session.project_id)
        )
    restored = stores.review_sessions.get(started.review_id)
    assert restored.state is ReviewState.COMPLETE
    assert restored.generation == previous_complete.generation + 1
    assert restored.confirmed == previous_complete.confirmed
    assert service.get(started.review_id, "u_demo").state is ReviewState.COMPLETE
    assert len(
        [
            event
            for event in stores.timeline.list(session.project_id)
            if event.event == "review.package_ready"
        ]
    ) == before_ready
    if mutation == "fact":
        retried = service.reanalyze(
            started.review_id,
            "u_demo",
            confirmed(title="Retry after aggregate conflict"),
        )
        assert retried.state is ReviewState.COMPLETE
        assert stores.review_sessions.get(started.review_id).generation == (
            previous_complete.generation + 2
        )
    if backend == "sqlite":
        concurrent.db.close()
        stores.db.close()


@pytest.mark.parametrize(
    "project_state",
    [
        ProjectState.CLASSIFIED,
        ProjectState.ROADMAP_CONFIRMED,
        ProjectState.COLLECTING_MATERIALS,
        ProjectState.REVIEW_RUNNING,
        ProjectState.REVISION_LOOP,
        ProjectState.GATE_D3_PASSED,
        ProjectState.NEEDS_HUMAN_SUBJECT,
        ProjectState.NEEDS_HUMAN_FORMTYPE,
        ProjectState.EXIT_NON_DRAMA,
        ProjectState.EXIT_T2,
        ProjectState.EXIT_T3,
        ProjectState.EXIT_SISTER_PATH,
    ],
)
def test_complete_review_outcome_states_can_reanalyze_from_fresh_intake_baseline(
    stores, review_snapshots, clock, project_state
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    service.confirm(started.review_id, "u_demo", confirmed())
    session = stores.review_sessions.get(started.review_id)
    project = stores.projects.get(session.project_id)
    stores.projects.save(project.model_copy(update={"state": project_state}))

    result = service.reanalyze(
        started.review_id,
        "u_demo",
        confirmed(title=f"Corrected from {project_state.value}"),
    )

    assert result.state is ReviewState.COMPLETE
    stored = stores.projects.get(session.project_id)
    assert stored.state is ProjectState.CLASSIFIED
    assert stored.title_working == f"Corrected from {project_state.value}"


def test_exit_duration_can_be_corrected_by_reanalysis(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock)
    started = start_script(service)
    service.confirm(
        started.review_id,
        "u_demo",
        confirmed(episode_minutes=25),
    )
    session = stores.review_sessions.get(started.review_id)
    assert stores.projects.get(session.project_id).state is ProjectState.EXIT_SISTER_PATH
    before_audit = stores.audit.list(session.project_id)

    corrected = service.reanalyze(
        started.review_id,
        "u_demo",
        confirmed(title="Corrected duration", episode_minutes=3),
    )

    assert corrected.state is ReviewState.COMPLETE
    stored = stores.projects.get(session.project_id)
    assert stored.state is ProjectState.CLASSIFIED
    assert stored.intent_profile.episode_minutes == 3
    audit = stores.audit.list(session.project_id)
    reset = audit[len(before_audit)]
    assert reset.from_state == ProjectState.EXIT_SISTER_PATH.value
    assert reset.to_state == ProjectState.DRAFT.value
    assert reset.reason == "review.reanalysis_reset"
    assert reset.detail["generation"] == 2
    assert all(
        previous.to_state == current.from_state
        for previous, current in zip(audit, audit[1:])
    )


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
