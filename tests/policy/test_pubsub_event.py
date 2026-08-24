from datetime import datetime, timezone
import json

import pytest

from schemas.policy_snapshot import PolicyUpdatedEvent
from workers.policy.adapters.pubsub_event import (
    PolicyEventPublishError,
    PubSubEventPublisher,
)


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
EVENT = PolicyUpdatedEvent(
    snapshot_version="v2",
    impact=["D1c"],
    thresholds_published=False,
    effective_from=NOW,
    published_at=NOW,
    idempotency_key="policy.updated:v2",
)


class FakeFuture:
    def __init__(self, result="message-123", error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.timeouts: list[int] = []

    def result(self, timeout: int):
        self.timeouts.append(timeout)
        if self._error is not None:
            raise self._error
        return self._result


class FakePublisher:
    def __init__(self, future: FakeFuture | None = None) -> None:
        self.future = future or FakeFuture()
        self.topic_calls: list[tuple[str, str]] = []
        self.publish_calls: list[tuple[str, bytes]] = []

    def topic_path(self, project: str, topic: str) -> str:
        self.topic_calls.append((project, topic))
        return f"projects/{project}/topics/{topic}"

    def publish(self, topic_path: str, payload: bytes):
        self.publish_calls.append((topic_path, payload))
        return self.future


def test_resolved_topic_path_and_publish_validated_json() -> None:
    publisher = FakePublisher()
    adapter = PubSubEventPublisher(
        publisher,
        publisher.topic_path("film-project", "policy-updated"),
    )

    message_id = adapter.publish(EVENT)

    assert publisher.topic_calls == [("film-project", "policy-updated")]
    assert message_id == "message-123"
    assert publisher.future.timeouts == [30]
    topic_path, payload = publisher.publish_calls[0]
    assert topic_path == "projects/film-project/topics/policy-updated"
    assert json.loads(payload.decode("utf-8")) == EVENT.model_dump(mode="json")


@pytest.mark.parametrize(
    "future",
    [FakeFuture(error=RuntimeError("credential secret")), FakeFuture(result="")],
)
def test_sdk_failure_or_empty_message_id_raises_stable_error(future) -> None:
    adapter = PubSubEventPublisher(
        FakePublisher(future),
        "projects/film-project/topics/policy-updated",
    )

    with pytest.raises(PolicyEventPublishError) as exc_info:
        adapter.publish(EVENT)

    assert exc_info.value.code == "POLICY_EVENT_PUBLISH_FAILED"
    assert "secret" not in str(exc_info.value)
