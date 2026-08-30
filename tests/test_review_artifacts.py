from __future__ import annotations

from pathlib import Path

import pytest

from core.errors import (
    ArtifactGenerationFailedError,
    ArtifactUnavailableError,
    StateInvalidError,
)
from core.llm import ScriptedLLM
from core.review_facade import ReviewFacade
from core.script_intake import SCRIPT_INTAKE_PROMPT_ID
from schemas.enums import AmountBracket
from schemas.reviews import (
    ConfirmedReviewDetails,
    IdeaOnly,
    ReviewArtifactType,
    ReviewState,
    StartReviewCommand,
    UploadedScript,
)


SCRIPT = """# English Working Title

### Episode 1 Scene 1: Police station
A community police officer checks a suspicious phone call.
社区民警在派出所核实一通可疑来电。
"""

INTAKE_REPLY = {
    "tags": {
        "value": ["public security", "family drama"],
        "origin": "suggested",
        "explanation": "The story combines public safety and family drama.",
    },
    "synopsis": {
        "value": "A community officer checks a suspicious call.",
        "origin": "suggested",
        "explanation": "This captures the central action.",
    },
    "episode_count": {
        "value": 10,
        "origin": "suggested",
        "explanation": "Ten short episodes suit the demo format.",
    },
    "episode_minutes": {
        "value": 3,
        "origin": "suggested",
        "explanation": "Three minutes is a concise episode length.",
    },
    "amount_bracket": {
        "value": "at_or_above_upper",
        "origin": "suggested",
        "explanation": "This is an editable planning estimate.",
    },
}


def facade(stores, snapshots, clock) -> ReviewFacade:
    return ReviewFacade(
        stores=stores,
        snapshots=snapshots,
        clock=clock,
        llm=ScriptedLLM({SCRIPT_INTAKE_PROMPT_ID: INTAKE_REPLY}),
    )


def details() -> ConfirmedReviewDetails:
    return ConfirmedReviewDetails(
        title="English Working Title",
        tags=["public security", "family drama"],
        synopsis="A community officer checks a suspicious call.",
        episode_count=10,
        episode_minutes=3,
        amount_bracket=AmountBracket.AT_OR_ABOVE_UPPER,
    )


def completed_script(service: ReviewFacade):
    started = service.start(
        StartReviewCommand(
            owner_uid="u_demo",
            source=UploadedScript(
                filename="e2e-30min-public-security.md",
                media_type="text/markdown",
                content=SCRIPT.encode(),
            ),
        )
    )
    return service.confirm(started.review_id, "u_demo", details())


def test_form_pdf_contains_confirmed_values_classification_and_placeholder(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock)
    review = completed_script(service)

    artifact = service.artifact(
        review.review_id, "u_demo", ReviewArtifactType.FORM
    )

    assert artifact.filename == "project-review-form.pdf"
    assert artifact.media_type == "application/pdf"
    assert artifact.content.startswith(b"%PDF-")
    assert b"Project Review Form" in artifact.content
    assert b"English Working Title" in artifact.content
    assert b"Class 1" in artifact.content
    assert b"To be supplied by filing institution" in artifact.content
    assert b"Routing authority" in artifact.content
    assert b"Review preparation only" in artifact.content
    assert b"at_or_above_upper" not in artifact.content


def test_summary_pdf_contains_stable_risks_evidence_boundary_and_semantic_status(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock)
    review = completed_script(service)

    artifact = service.artifact(
        review.review_id, "u_demo", ReviewArtifactType.SUMMARY
    )

    assert artifact.filename == "risk-summary.pdf"
    assert artifact.media_type == "application/pdf"
    assert artifact.content.startswith(b"%PDF-")
    assert b"Risk Summary" in artifact.content
    assert b"RISK-001" in artifact.content
    assert b"Needs human review" in artifact.content
    assert b"Evidence boundary" in artifact.content
    assert b"Semantic status: Pending" in artifact.content
    assert b"Counts by category" in artifact.content
    assert b"Counts by status" in artifact.content
    assert b"not legal advice" in artifact.content
    assert b"external review status unknown" in artifact.content
    assert b"public_security" not in artifact.content


def test_demo_fixture_provenance_is_bound_to_checksum_not_filename(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock)
    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "scripts"
        / "e2e-30min-public-security.md"
    )
    started = service.start(
        StartReviewCommand(
            owner_uid="u_demo",
            source=UploadedScript(
                filename="renamed-demo.md",
                media_type="text/markdown",
                content=fixture.read_bytes(),
            ),
        )
    )
    completed = service.confirm(started.review_id, "u_demo", details())
    summary = service.artifact(
        completed.review_id, "u_demo", ReviewArtifactType.SUMMARY
    )

    assert b"Synthetic and externally unreviewed" in summary.content


def test_annotated_script_preserves_every_source_line_and_adds_stable_notes(
    stores, review_snapshots, clock
) -> None:
    service = facade(stores, review_snapshots, clock)
    review = completed_script(service)

    artifact = service.artifact(
        review.review_id, "u_demo", ReviewArtifactType.ANNOTATED_SCRIPT
    )

    assert artifact.filename == "annotated-script.md"
    assert artifact.media_type == "text/markdown; charset=utf-8"
    rendered = artifact.content.decode()
    for line in SCRIPT.splitlines():
        assert line in rendered
    assert "<!-- RISK-001" in rendered
    assert "Needs human review" in rendered
    assert "explanation=" in rendered
    assert rendered.index("A community police officer") < rendered.index(
        "<!-- RISK-001"
    )


def test_idea_review_generates_only_the_form(stores, review_snapshots, clock) -> None:
    service = facade(stores, review_snapshots, clock)
    started = service.start(
        StartReviewCommand(owner_uid="u_demo", source=IdeaOnly())
    )
    review = service.confirm(started.review_id, "u_demo", details())

    form = service.artifact(
        review.review_id, "u_demo", ReviewArtifactType.FORM
    )
    assert form.content.startswith(b"%PDF-")
    with pytest.raises(ArtifactUnavailableError):
        service.artifact(
            review.review_id, "u_demo", ReviewArtifactType.SUMMARY
        )


def test_artifacts_require_a_completed_review(stores, review_snapshots, clock) -> None:
    service = facade(stores, review_snapshots, clock)
    started = service.start(
        StartReviewCommand(owner_uid="u_demo", source=IdeaOnly())
    )

    with pytest.raises(StateInvalidError):
        service.artifact(started.review_id, "u_demo", ReviewArtifactType.FORM)


def test_renderer_failure_does_not_corrupt_completed_session(
    stores, review_snapshots, clock, monkeypatch
) -> None:
    service = facade(stores, review_snapshots, clock)
    review = completed_script(service)

    def fail(*_args, **_kwargs):
        raise RuntimeError("renderer unavailable")

    monkeypatch.setattr(service._artifact_composer, "compose", fail)
    with pytest.raises(ArtifactGenerationFailedError, match="could not generate"):
        service.artifact(
            review.review_id, "u_demo", ReviewArtifactType.FORM
        )

    assert service.get(review.review_id, "u_demo").state is ReviewState.COMPLETE
