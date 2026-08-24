"""Pending policy event dispatch."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import logging
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from schemas.policy_snapshot import PolicyUpdatedEvent

from .interfaces import OutboxRepository


_LOGGER = logging.getLogger(__name__)


class EventPublisher(Protocol):
    def publish(self, event: PolicyUpdatedEvent) -> str: ...


class DispatchSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected: int
    sent: int
    failed: int


class OutboxDispatcher:
    def __init__(
        self,
        repository: OutboxRepository,
        publisher: EventPublisher,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._publisher = publisher
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def dispatch(self, limit: int = 20) -> DispatchSummary:
        bounded_limit = max(0, min(limit, 20))
        pending = self._repository.list_pending_outbox(bounded_limit)
        sent = 0
        failed = 0
        for outbox_id, row in pending:
            try:
                message_id = self._publisher.publish(row.payload)
                self._repository.mark_outbox_sent(
                    outbox_id, self._clock(), message_id
                )
                sent += 1
            except Exception:
                _LOGGER.exception(
                    "policy outbox dispatch failed: outbox_id=%s", outbox_id
                )
                failed += 1
        return DispatchSummary(selected=len(pending), sent=sent, failed=failed)
