"""Deterministic event publisher for Gate 2."""

from schemas.policy_snapshot import PolicyUpdatedEvent


class FakeEventPublishError(RuntimeError):
    pass


class FakeEventPublisher:
    def __init__(self, fail_on: set[str] | None = None) -> None:
        self._fail_on = set(fail_on or ())
        self.published: list[PolicyUpdatedEvent] = []
        self.call_count = 0

    def publish(self, event: PolicyUpdatedEvent) -> str:
        self.call_count += 1
        if event.idempotency_key in self._fail_on:
            raise FakeEventPublishError(event.idempotency_key)
        self.published.append(event.model_copy(deep=True))
        return f"message-{event.snapshot_version}"
