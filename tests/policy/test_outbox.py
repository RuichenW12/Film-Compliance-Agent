from datetime import datetime, timedelta, timezone

from schemas.policy_snapshot import (
    OutboxStatus,
    PolicyOutbox,
    PolicyUpdatedEvent,
)
from workers.policy.adapters.fake_event_publisher import FakeEventPublisher
from workers.policy.outbox import OutboxDispatcher
from workers.policy.repository import InMemoryPolicyRepository


NOW = datetime(2026, 8, 23, 17, 0, tzinfo=timezone(timedelta(hours=8)))


def add_pending(repository: InMemoryPolicyRepository, version_number: int) -> str:
    version = f"v{version_number}"
    outbox_id = f"policy.updated:{version}"
    event = PolicyUpdatedEvent(
        snapshot_version=version,
        impact=["D1c"],
        thresholds_published=True,
        effective_from=NOW,
        published_at=NOW,
        idempotency_key=outbox_id,
    )
    repository.put_outbox(
        outbox_id,
        PolicyOutbox(
            topic="policy.updated",
            payload=event,
            status=OutboxStatus.PENDING,
            created_at=NOW + timedelta(seconds=version_number),
            sent_at=None,
            pubsub_message_id=None,
        ),
    )
    return outbox_id


def test_successful_send_marks_outbox_sent() -> None:
    repository = InMemoryPolicyRepository()
    outbox_id = add_pending(repository, 2)
    event_publisher = FakeEventPublisher()
    dispatcher = OutboxDispatcher(repository, event_publisher, clock=lambda: NOW)

    summary = dispatcher.dispatch()

    row = repository.get_outbox(outbox_id)
    assert summary.model_dump() == {"selected": 1, "sent": 1, "failed": 0}
    assert row.status is OutboxStatus.SENT
    assert row.sent_at == NOW
    assert row.pubsub_message_id == "message-v2"


def test_failed_send_remains_pending() -> None:
    repository = InMemoryPolicyRepository()
    outbox_id = add_pending(repository, 2)
    event_publisher = FakeEventPublisher(fail_on={outbox_id})
    dispatcher = OutboxDispatcher(repository, event_publisher, clock=lambda: NOW)

    summary = dispatcher.dispatch()

    row = repository.get_outbox(outbox_id)
    assert summary.model_dump() == {"selected": 1, "sent": 0, "failed": 1}
    assert row.status is OutboxStatus.PENDING
    assert row.sent_at is None
    assert row.pubsub_message_id is None


def test_second_dispatch_selects_nothing_after_success() -> None:
    repository = InMemoryPolicyRepository()
    add_pending(repository, 2)
    event_publisher = FakeEventPublisher()
    dispatcher = OutboxDispatcher(repository, event_publisher, clock=lambda: NOW)

    first = dispatcher.dispatch()
    second = dispatcher.dispatch()

    assert first.sent == 1
    assert second.model_dump() == {"selected": 0, "sent": 0, "failed": 0}
    assert event_publisher.call_count == 1


def test_dispatch_hard_limits_selection_to_twenty() -> None:
    repository = InMemoryPolicyRepository()
    for version_number in range(2, 27):
        add_pending(repository, version_number)
    event_publisher = FakeEventPublisher()
    dispatcher = OutboxDispatcher(repository, event_publisher, clock=lambda: NOW)

    summary = dispatcher.dispatch(limit=99)

    assert summary.model_dump() == {"selected": 20, "sent": 20, "failed": 0}
    pending = [
        row
        for row in repository.list_outbox().values()
        if row.status is OutboxStatus.PENDING
    ]
    assert len(pending) == 5
