"""A subject-rule change reaches projects, and does not re-decide them.

`ImpactNode` had only `D1c` and `C1-a`. The subject match, `D1b`, had no node
at all -- so a snapshot could change the trigger vocabulary that decides whether
a project is a special subject, publish, and mark nobody stale. It was the one
impact the loop could not express, and it was recorded as an open gap for
months before this.

Adding the node is half of it. The other half is what must *not* happen:
`recalc_tier` re-runs the amount stage only, so using it to answer a subject
question would give a money answer to a question about content. A D1b change
marks a project stale and tells its creator; re-deciding the subject needs the
full chain and a human. These tests pin both halves.
"""

from __future__ import annotations

import pytest

from schemas.policy_snapshot import ImpactNode, PolicyUpdatedEvent
from workers.policy.adapters.fake_recalc import FakeRecalcClient
from workers.policy.adapters.memory_projects import (
    InMemoryProjectRepository,
    ProjectPolicyState,
)
from workers.policy.consumer import PolicyUpdatedConsumer


def _project(**overrides) -> ProjectPolicyState:
    base = {
        "project_id": "proj_1",
        "policy_snapshot_version": "v2",
        "impact_nodes": [ImpactNode.D1B, ImpactNode.D1C],
        "has_classification": True,
        "has_review": False,
        "tier": "T1",
        "tier_provisional": False,
        "workflow_status": "DRAFT",
        "policy_stale": False,
        "frozen_form_hash": None,
        "submitted_materials": [],
        "registration_number": None,
    }
    base.update(overrides)
    return ProjectPolicyState.model_validate(base)


def _event(impact: list[ImpactNode], thresholds_published: bool = False) -> PolicyUpdatedEvent:
    return PolicyUpdatedEvent(
        snapshot_version="v3",
        effective_from="2026-09-01T00:00:00+08:00",
        impact=impact,
        thresholds_published=thresholds_published,
        published_at="2026-08-28T12:00:00+00:00",
        idempotency_key="policy.updated:v3",
    )


@pytest.fixture
def repository() -> InMemoryProjectRepository:
    repo = InMemoryProjectRepository()
    repo.add_project(_project())
    return repo


@pytest.mark.asyncio
async def test_a_subject_rule_change_marks_a_project_stale(repository) -> None:
    """Before D1b existed this returned zero, silently."""

    recalc = FakeRecalcClient(repository, new_tier="T2")
    consumer = PolicyUpdatedConsumer(repository, recalc)

    result = await consumer.handle(_event([ImpactNode.D1B]))

    assert result.stale_marked == 1
    assert repository.get_project("proj_1").policy_stale is True


@pytest.mark.asyncio
async def test_a_subject_rule_change_never_recalculates_the_tier(repository) -> None:
    """`recalc_tier` redoes the amount stage. A subject change is not about money."""

    recalc = FakeRecalcClient(repository, new_tier="T3")
    consumer = PolicyUpdatedConsumer(repository, recalc)

    result = await consumer.handle(_event([ImpactNode.D1B], thresholds_published=True))

    assert result.recalculated == 0
    assert recalc.calls == [], "no recalc call may be made for a subject change"
    assert repository.get_project("proj_1").tier == "T1", "the tier is untouched"


@pytest.mark.asyncio
async def test_a_threshold_change_still_recalculates(repository) -> None:
    """The D1c path must keep working; adding D1b must not narrow it."""

    repository.mark_policy_stale("proj_1")
    provisional = InMemoryProjectRepository()
    provisional.add_project(_project(tier_provisional=True, policy_stale=False))
    recalc = FakeRecalcClient(provisional, new_tier="T2")
    consumer = PolicyUpdatedConsumer(provisional, recalc)

    result = await consumer.handle(_event([ImpactNode.D1C], thresholds_published=True))

    assert result.stale_marked == 1
    assert result.recalculated == 1
    assert provisional.get_project("proj_1").tier == "T2"


@pytest.mark.asyncio
async def test_a_project_not_exposed_to_the_node_is_left_alone(repository) -> None:
    untouched = InMemoryProjectRepository()
    untouched.add_project(_project(impact_nodes=[ImpactNode.C1A], has_review=True))
    consumer = PolicyUpdatedConsumer(
        untouched, FakeRecalcClient(untouched, new_tier="T2")
    )

    result = await consumer.handle(_event([ImpactNode.D1B]))

    assert result.stale_marked == 0
    assert untouched.get_project("proj_1").policy_stale is False


@pytest.mark.asyncio
async def test_redelivery_of_a_subject_change_is_idempotent(repository) -> None:
    """Pub/Sub delivers at least once; a creator gets told once."""

    consumer = PolicyUpdatedConsumer(
        repository, FakeRecalcClient(repository, new_tier="T2")
    )
    event = _event([ImpactNode.D1B])

    first = await consumer.handle(event)
    second = await consumer.handle(event)

    assert first.stale_marked == 1
    assert second.already_processed is True
    assert second.stale_marked == 0


@pytest.mark.asyncio
async def test_the_notice_names_the_version_that_was_published(repository) -> None:
    """Not the one the project is already pinned to.

    The dashboard read "Snapshot v2 was published" at the moment v3 was,
    because the adapter passed the project's current pinned version instead of
    the event's. A notice that names the version the creator already had is
    news about nothing.
    """

    seen: list[tuple[str, str | None]] = []

    class RecordingRepository:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def mark_policy_stale(self, project_id, snapshot_version=None):
            seen.append((project_id, snapshot_version))
            self._inner.mark_policy_stale(project_id, snapshot_version)

    recording = RecordingRepository(repository)
    consumer = PolicyUpdatedConsumer(
        recording, FakeRecalcClient(repository, new_tier="T2")
    )

    await consumer.handle(_event([ImpactNode.D1B]))

    assert seen == [("proj_1", "v3")], "the event's version, not the project's v2"
