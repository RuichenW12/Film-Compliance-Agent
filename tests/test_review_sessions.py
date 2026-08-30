from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from schemas.enums import AmountBracket
from schemas.reviews import (
    CandidateOrigin,
    CandidateValue,
    ConfirmedReviewDetails,
    IntakeStatus,
    ReviewMode,
    ReviewSession,
    ReviewState,
)


NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def confirmed_details(**updates) -> ConfirmedReviewDetails:
    values = {
        "title": "先挂电话",
        "tags": ["public security", "suspense"],
        "synopsis": "A caller races to stop a public-safety emergency.",
        "episode_count": 10,
        "episode_minutes": 3,
        "amount_bracket": AmountBracket.AT_OR_ABOVE_UPPER,
    }
    values.update(updates)
    return ConfirmedReviewDetails(**values)


def script_session(**updates) -> ReviewSession:
    values = {
        "review_id": "review_1",
        "owner_uid": "u_demo",
        "mode": ReviewMode.SCRIPT,
        "state": ReviewState.EXTRACTING,
        "project_id": "proj_1",
        "asset_version": "asset_1",
        "source_filename": "script.md",
        "source_sha256": "a" * 64,
        "normalized_text_uri": "blob://proj_1/script-text",
        "intake_status": IntakeStatus.RUNNING,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(updates)
    return ReviewSession(**values)


def test_confirmed_details_normalize_tags_without_inventing_values() -> None:
    details = confirmed_details(tags=[" public security ", "suspense", "suspense"])
    assert details.tags == ["public security", "suspense"]


@pytest.mark.parametrize("tags", [[], ["   "], ["x" * 41]])
def test_confirmed_details_reject_invalid_tags(tags: list[str]) -> None:
    with pytest.raises(ValidationError):
        confirmed_details(tags=tags)


def test_confirmed_details_require_a_known_amount_bracket() -> None:
    with pytest.raises(ValidationError, match="amount_bracket"):
        confirmed_details(amount_bracket=AmountBracket.UNKNOWN)


def test_suggested_candidates_require_an_explanation() -> None:
    with pytest.raises(ValidationError, match="explanation"):
        CandidateValue(value="suspense", origin=CandidateOrigin.SUGGESTED)


@pytest.mark.parametrize(
    "missing",
    ["asset_version", "source_filename", "source_sha256", "normalized_text_uri"],
)
def test_script_session_requires_source_references_once_extracting(
    missing: str,
) -> None:
    with pytest.raises(ValidationError, match=missing):
        script_session(**{missing: None})


def test_uploading_script_session_can_exist_before_source_is_committed() -> None:
    session = script_session(
        state=ReviewState.UPLOADING,
        asset_version=None,
        source_filename=None,
        source_sha256=None,
        normalized_text_uri=None,
        intake_status=IntakeStatus.NOT_STARTED,
    )
    assert session.state is ReviewState.UPLOADING


def test_idea_session_rejects_script_source_references() -> None:
    with pytest.raises(ValidationError, match="idea"):
        script_session(mode=ReviewMode.IDEA)


def test_failed_session_requires_an_error_code_and_message() -> None:
    with pytest.raises(ValidationError, match="error_code"):
        script_session(state=ReviewState.FAILED)


def test_complete_session_requires_confirmed_details() -> None:
    with pytest.raises(ValidationError, match="confirmed"):
        script_session(state=ReviewState.COMPLETE)


def test_complete_session_accepts_confirmed_details() -> None:
    session = script_session(
        state=ReviewState.COMPLETE,
        intake_status=IntakeStatus.COMPLETE,
        confirmed=confirmed_details(),
    )
    assert session.confirmed.title == "先挂电话"
