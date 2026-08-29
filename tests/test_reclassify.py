"""A stale project has a way to get a new answer.

A policy change marks a project stale and tells its creator. For a threshold
change the tier is recalculated automatically, because `recalc_tier` can answer
that from the amount alone. For a subject-rule change it deliberately is not
(D-050): re-deciding a subject match needs the whole chain and a human who
asked for it.

Which left the creator holding a notice saying their answer rested on rules
that had moved, and no way to get a new one. These tests pin the way out and,
more importantly, its limits: it refuses when there is nothing to redo, it
refuses once a form has been sent, and it keeps everything about the project
except the classification.
"""

from __future__ import annotations

import pytest

from core.errors import StateInvalidError
from schemas.enums import ProjectState


def _stale(workflow, project_id: str) -> None:
    project = workflow.get_project(project_id)
    workflow._stores.projects.save(project.model_copy(update={"policy_stale": True}))


def _at_state(workflow, project_id: str, state: ProjectState) -> None:
    project = workflow.get_project(project_id)
    workflow._stores.projects.save(project.model_copy(update={"state": state}))


@pytest.fixture
def classified(workflow, intent_romance) -> str:
    project_id = workflow.create_project("u_demo", "夏日便利店").project_id
    workflow.submit_intent(project_id, intent_romance.model_dump())
    workflow.run_classification(project_id)
    return project_id


def test_a_stale_project_can_be_re_decided(workflow, classified) -> None:
    _stale(workflow, classified)

    project, outcome = workflow.reclassify(classified)

    assert outcome.classification is not None
    assert project.policy_stale is False, "redoing it is what clears the flag"


def test_a_project_that_is_not_stale_is_refused(workflow, classified) -> None:
    """There is nothing to redo, and saying so is better than redoing it."""

    with pytest.raises(StateInvalidError):
        workflow.reclassify(classified)


def test_re_deciding_does_not_move_the_state(workflow, classified) -> None:
    """A project halfway through collection keeps its place in the journey."""

    _at_state(workflow, classified, ProjectState.COLLECTING_MATERIALS)
    _stale(workflow, classified)

    project, _ = workflow.reclassify(classified)

    assert project.state is ProjectState.COLLECTING_MATERIALS


@pytest.mark.parametrize(
    "state",
    [
        ProjectState.FORM_FROZEN,
        ProjectState.INSTITUTION_REVIEW,
        ProjectState.READY_FOR_EXTERNAL_FILING,
        ProjectState.FILED,
    ],
)
def test_a_sent_form_is_never_re_decided_in_place(workflow, classified, state) -> None:
    """Its class is part of what the filing company is holding.

    Changing it underneath them would make the locked document they are
    reviewing describe a different project than the one it names.
    """

    _at_state(workflow, classified, state)
    _stale(workflow, classified)

    with pytest.raises(StateInvalidError):
        workflow.reclassify(classified)


def test_the_change_is_recorded_in_the_timeline(workflow, classified) -> None:
    """A later reader must be able to see that the answer moved, and why."""

    _stale(workflow, classified)
    workflow.reclassify(classified)

    events = workflow._stores.timeline.list(classified)
    rerun = [e for e in events if e.event == "classification.rerun_after_policy_change"]
    assert len(rerun) == 1
    detail = rerun[0].detail
    assert "from_tier" in detail and "to_tier" in detail
    assert "from_snapshot" in detail and "to_snapshot" in detail


def test_re_deciding_twice_needs_a_second_reason(workflow, classified) -> None:
    """The flag is the reason. Once cleared, the door closes again."""

    _stale(workflow, classified)
    workflow.reclassify(classified)

    with pytest.raises(StateInvalidError):
        workflow.reclassify(classified)
