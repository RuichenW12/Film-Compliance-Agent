from __future__ import annotations

from pathlib import Path

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
