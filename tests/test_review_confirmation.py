from __future__ import annotations

import pytest

from schemas.enums import (
    AmountBracket,
    ClaimedFormType,
    ProductionStage,
    ProjectState,
    SourceRefType,
)
from schemas.reviews import ConfirmedReviewDetails, ReviewMode


def details(**updates) -> ConfirmedReviewDetails:
    values = {
        "title": "先挂电话",
        "tags": ["public security", "family drama"],
        "synopsis": "A family confronts the urgency and shame behind a scam call.",
        "episode_count": 10,
        "episode_minutes": 3,
        "amount_bracket": AmountBracket.AT_OR_ABOVE_UPPER,
    }
    values.update(updates)
    return ConfirmedReviewDetails(**values)


@pytest.mark.parametrize(
    ("mode", "expected_stage"),
    [
        (ReviewMode.SCRIPT, ProductionStage.SCRIPT_READY),
        (ReviewMode.IDEA, ProductionStage.IDEA),
    ],
)
def test_confirmation_writes_the_project_intent_in_one_workflow_operation(
    workflow, mode: ReviewMode, expected_stage: ProductionStage
) -> None:
    project = workflow.create_project("u_demo")

    updated = workflow.apply_review_confirmation(project.project_id, mode, details())

    assert updated.title_working == "先挂电话"
    assert updated.state is ProjectState.INTAKE_DONE
    assert updated.intent_profile.form_type_claimed is ClaimedFormType.MICRO_DRAMA
    assert updated.intent_profile.genre_keywords == [
        "public security",
        "family drama",
    ]
    assert updated.intent_profile.synopsis.startswith("A family")
    assert updated.intent_profile.episode_count == 10
    assert updated.intent_profile.episode_minutes == 3
    assert updated.intent_profile.amount_bracket is AmountBracket.AT_OR_ABOVE_UPPER
    assert updated.intent_profile.is_ai_generated is True
    assert updated.intent_profile.production_stage is expected_stage
    assert updated.intent_profile.source == "user_confirmed_review"


def test_confirmation_writes_only_user_answer_facts(workflow, stores) -> None:
    project = workflow.create_project("u_demo")
    workflow.apply_review_confirmation(project.project_id, ReviewMode.SCRIPT, details())

    facts = {fact.key: fact for fact in stores.facts.list(project.project_id)}
    assert set(facts) == {
        "title",
        "episode_count",
        "episode_minutes",
        "amount_bracket",
    }
    assert facts["title"].value == "先挂电话"
    assert facts["episode_count"].value == 10
    assert facts["episode_minutes"].value == 3
    assert facts["amount_bracket"].value == "at_or_above_upper"
    assert {fact.source_ref.type for fact in facts.values()} == {
        SourceRefType.USER_ANSWER
    }
    assert all(fact.source_ref.answer_id for fact in facts.values())


def test_repeating_the_same_confirmation_does_not_duplicate_facts(
    workflow, stores
) -> None:
    project = workflow.create_project("u_demo")
    workflow.apply_review_confirmation(project.project_id, ReviewMode.SCRIPT, details())
    workflow.apply_review_confirmation(project.project_id, ReviewMode.SCRIPT, details())
    assert len(stores.facts.list(project.project_id)) == 4


def test_confirmation_timeline_does_not_copy_story_text(workflow, stores) -> None:
    project = workflow.create_project("u_demo")
    confirmed = details()
    workflow.apply_review_confirmation(
        project.project_id, ReviewMode.SCRIPT, confirmed
    )

    events = stores.timeline.list(project.project_id)
    review_event = [event for event in events if event.event == "review.details_confirmed"]
    assert len(review_event) == 1
    assert confirmed.synopsis not in str(review_event[0].detail)
