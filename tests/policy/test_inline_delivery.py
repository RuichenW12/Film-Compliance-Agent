"""A rule change is never marked delivered before it has been.

The first version of this wiring published to a queue, marked the outbox row
sent, and handed the event to the consumer afterwards. That order loses events:
`list_pending_outbox` selects only `PENDING` rows, so a process that died
between the mark and the handoff left an outbox claiming the event was sent and
projects that were never flagged -- with nothing left to notice or retry.

The fix is ordinary and worth stating plainly: deliver, then acknowledge. A
failure leaves the row `PENDING`, the next publish picks it up, and the
consumer's receipt guard makes the retry a no-op if it had actually succeeded.
At-least-once with an idempotent handler, instead of at-most-once with none.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from schemas.policy_snapshot import (
    ImpactNode,
    OutboxStatus,
    PolicyOutbox,
    PolicyUpdatedEvent,
)
from workers.policy.adapters.live_projects import InlineOutboxDelivery

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def _event() -> PolicyUpdatedEvent:
    return PolicyUpdatedEvent(
        snapshot_version="v3",
        effective_from="2026-09-01T00:00:00+08:00",
        impact=[ImpactNode.D1C],
        thresholds_published=True,
        published_at=NOW,
        idempotency_key="policy.updated:v3",
    )


class FakeOutbox:
    """Just the two methods the delivery uses, and a record of what happened."""

    def __init__(self) -> None:
        self.rows = {
            "outbox_1": PolicyOutbox(
                topic="policy.updated",
                payload=_event(),
                status=OutboxStatus.PENDING,
                created_at=NOW,
                sent_at=None,
                pubsub_message_id=None,
            )
        }
        self.marked: list[str] = []

    def list_pending_outbox(self, limit: int):
        return [
            (key, row)
            for key, row in self.rows.items()
            if row.status is OutboxStatus.PENDING
        ][:limit]

    def mark_outbox_sent(self, outbox_id, sent_at, message_id) -> None:
        self.marked.append(outbox_id)
        self.rows[outbox_id] = self.rows[outbox_id].model_copy(
            update={"status": OutboxStatus.SENT}
        )


class RecordingConsumer:
    def __init__(self, fail_times: int = 0) -> None:
        self.calls = 0
        self._fail_times = fail_times

    async def handle(self, event):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise RuntimeError("the fan-out stumbled")
        return {"handled": event.snapshot_version}


@pytest.mark.asyncio
async def test_a_delivered_event_is_acknowledged() -> None:
    outbox, consumer = FakeOutbox(), RecordingConsumer()
    delivery = InlineOutboxDelivery(outbox, consumer, lambda: NOW)

    await delivery.deliver()

    assert consumer.calls == 1
    assert outbox.marked == ["outbox_1"]


@pytest.mark.asyncio
async def test_a_failed_delivery_leaves_the_row_pending() -> None:
    """The whole point: a lost rule change must stay retryable."""

    outbox, consumer = FakeOutbox(), RecordingConsumer(fail_times=1)
    delivery = InlineOutboxDelivery(outbox, consumer, lambda: NOW)

    with pytest.raises(RuntimeError):
        await delivery.deliver()

    assert outbox.marked == [], "nothing may be acknowledged that was not handled"
    assert outbox.rows["outbox_1"].status is OutboxStatus.PENDING


@pytest.mark.asyncio
async def test_the_next_attempt_picks_it_back_up() -> None:
    outbox, consumer = FakeOutbox(), RecordingConsumer(fail_times=1)
    delivery = InlineOutboxDelivery(outbox, consumer, lambda: NOW)

    with pytest.raises(RuntimeError):
        await delivery.deliver()
    await delivery.deliver()

    assert consumer.calls == 2
    assert outbox.marked == ["outbox_1"]
    assert outbox.rows["outbox_1"].status is OutboxStatus.SENT


@pytest.mark.asyncio
async def test_an_acknowledged_event_is_not_delivered_again() -> None:
    outbox, consumer = FakeOutbox(), RecordingConsumer()
    delivery = InlineOutboxDelivery(outbox, consumer, lambda: NOW)

    await delivery.deliver()
    await delivery.deliver()

    assert consumer.calls == 1
