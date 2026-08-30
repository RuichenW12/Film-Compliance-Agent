from __future__ import annotations

import hashlib
from pathlib import Path

from core.demo_intake_llm import DemoIntakeLLM
from core.review_facade import ReviewFacade
from schemas.enums import AmountBracket
from schemas.reviews import (
    ConfirmedReviewDetails,
    ReviewArtifactType,
    ReviewState,
    StartReviewCommand,
    UploadedScript,
)


FIXTURE = (
    Path(__file__).parent / "fixtures" / "scripts" / "e2e-30min-public-security.md"
)

def test_public_security_fixture_reaches_confirmed_risk_package(
    stores, review_snapshots, clock
) -> None:
    raw = FIXTURE.read_bytes()
    service = ReviewFacade(
        stores=stores,
        snapshots=review_snapshots,
        clock=clock,
        llm=DemoIntakeLLM(),
    )

    started = service.start(
        StartReviewCommand(
            owner_uid="u_demo",
            source=UploadedScript(
                filename=FIXTURE.name,
                media_type="text/markdown",
                content=raw,
            ),
        )
    )

    assert started.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert started.candidates.title.value == "先挂电话"
    assert started.candidates.structure.source_episode_count == 1
    assert started.candidates.structure.source_total_minutes == 30
    assert started.candidates.structure.source_scene_count == 15
    assert started.candidates.episode_count.value == 10
    assert started.candidates.episode_minutes.value == 3

    result = service.confirm(
        started.review_id,
        "u_demo",
        ConfirmedReviewDetails(
            title="先挂电话",
            tags=["公安", "家庭现实"],
            synopsis="社区民警在派出所帮助居民识别可疑来电，修复父女关系。",
            episode_count=10,
            episode_minutes=3,
            amount_bracket=AmountBracket.AT_OR_ABOVE_UPPER,
        ),
    )

    assert result.state is ReviewState.COMPLETE
    assert result.classification.class_name == "Class 1"
    assert result.classification.co_review_required is True
    assert "Public security subject" in result.classification.subjects
    located_scenes = {finding.scene for finding in result.findings}
    assert {3, 4, 10, 11, 14} <= located_scenes
    assert {finding.status for finding in result.findings} == {
        "Needs human review"
    }
    assert not {
        "political",
        "military",
        "diplomatic",
        "national_security",
        "united_front",
        "ethnic",
        "religious",
        "judicial",
    } & {finding.category for finding in result.findings}
    assert result.semantic_status.value == "pending"
    assert "clean pass" not in result.model_dump_json().lower()

    form = service.artifact(
        result.review_id, "u_demo", ReviewArtifactType.FORM
    )
    summary = service.artifact(
        result.review_id, "u_demo", ReviewArtifactType.SUMMARY
    )
    annotated = service.artifact(
        result.review_id, "u_demo", ReviewArtifactType.ANNOTATED_SCRIPT
    )

    assert form.content.startswith(b"%PDF-")
    assert summary.content.startswith(b"%PDF-")
    annotated_text = annotated.content.decode("utf-8")
    for line in raw.decode("utf-8").splitlines():
        assert line in annotated_text
    for finding in result.findings:
        assert f"<!-- {finding.risk_id}" in annotated_text
