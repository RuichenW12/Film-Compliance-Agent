import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from schemas.policy_snapshot import PolicyUpdatedEvent
from workers.policy.adapters.fake_recalc import FakeRecalcClient, FakeRecalcError
from workers.policy.adapters.memory_projects import (
    InMemoryProjectRepository,
    ProjectPolicyState,
)
from workers.policy.consumer import PolicyUpdatedConsumer


NOW = datetime(2026, 8, 23, 18, 0, tzinfo=timezone(timedelta(hours=8)))


def event() -> PolicyUpdatedEvent:
    return PolicyUpdatedEvent(
        snapshot_version="v2",
        impact=["D1c"],
        thresholds_published=True,
        effective_from=NOW,
        published_at=NOW,
        idempotency_key="policy.updated:v2",
    )


def provisional_project() -> ProjectPolicyState:
    return ProjectPolicyState(
        project_id="project_provisional",
        policy_snapshot_version="v1",
        impact_nodes=["D1c"],
        has_classification=True,
        has_review=False,
        tier="T3",
        tier_provisional=True,
        workflow_status="DRAFT",
        policy_stale=False,
        frozen_form_hash=None,
        submitted_materials=[],
        registration_number=None,
    )


def frozen_project() -> ProjectPolicyState:
    return ProjectPolicyState(
        project_id="project_frozen",
        policy_snapshot_version="v1",
        impact_nodes=["D1c"],
        has_classification=True,
        has_review=True,
        tier="T1",
        tier_provisional=False,
        workflow_status="FORM_FROZEN",
        policy_stale=False,
        frozen_form_hash="sha256:frozen-form",
        submitted_materials=["materials/frozen.pdf"],
        registration_number="REG-LOCKED-001",
    )


def build_consumer(*, fail_recalc: bool = False):
    repository = InMemoryProjectRepository()
    repository.add_project(provisional_project())
    repository.add_project(frozen_project())
    recalc = FakeRecalcClient(
        repository,
        new_tier="T2",
        fail_on={"project_provisional"} if fail_recalc else None,
    )
    return PolicyUpdatedConsumer(repository, recalc), repository, recalc


def test_update_recalculates_only_provisional_project() -> None:
    consumer, repository, recalc = build_consumer()

    result = asyncio.run(consumer.handle(event()))

    provisional = repository.get_project("project_provisional")
    frozen = repository.get_project("project_frozen")
    assert result.model_dump() == {
        "stale_marked": 2,
        "recalculated": 1,
        "already_processed": False,
    }
    assert recalc.calls == [("project_provisional", "v2")]
    assert provisional.tier == "T2"
    assert provisional.tier_provisional is False
    assert provisional.policy_snapshot_version == "v2"
    assert provisional.policy_stale is True
    assert frozen.policy_stale is True


def test_frozen_artifacts_and_registration_number_never_change() -> None:
    consumer, repository, _ = build_consumer()
    before = repository.get_project("project_frozen")

    asyncio.run(consumer.handle(event()))

    after = repository.get_project("project_frozen")
    assert after.frozen_form_hash == before.frozen_form_hash
    assert after.submitted_materials == before.submitted_materials
    assert after.registration_number == before.registration_number
    assert after.tier == before.tier
    assert after.policy_snapshot_version == "v1"


def test_notifications_and_timeline_ids_are_deterministic() -> None:
    consumer, repository, _ = build_consumer()

    asyncio.run(consumer.handle(event()))

    expected = {
        "policy.updated:v2:project_provisional:policy_stale",
        "policy.updated:v2:project_provisional:tier_recalculated",
        "policy.updated:v2:project_frozen:policy_stale",
    }
    assert set(repository.notifications) == expected
    assert set(repository.timeline) == expected


def test_event_replay_has_no_side_effects() -> None:
    consumer, repository, recalc = build_consumer()
    first = asyncio.run(consumer.handle(event()))
    notifications = repository.notifications
    timeline = repository.timeline

    second = asyncio.run(consumer.handle(event()))

    assert first.already_processed is False
    assert second.model_dump() == {
        "stale_marked": 0,
        "recalculated": 0,
        "already_processed": True,
    }
    assert recalc.calls == [("project_provisional", "v2")]
    assert repository.notifications == notifications
    assert repository.timeline == timeline


def test_recalc_failure_keeps_stale_and_does_not_write_receipt() -> None:
    consumer, repository, _ = build_consumer(fail_recalc=True)

    with pytest.raises(FakeRecalcError):
        asyncio.run(consumer.handle(event()))

    assert repository.get_project("project_provisional").policy_stale is True
    assert repository.has_receipt("policy.updated:v2") is False
    assert (
        "policy.updated:v2:project_provisional:policy_stale"
        in repository.notifications
    )
