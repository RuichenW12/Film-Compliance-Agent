"""Time source. Injected so tests never depend on wall-clock time."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    """Test clock; each call may advance by a fixed step."""

    def __init__(self, start: datetime, step_seconds: float = 0.0) -> None:
        if start.tzinfo is None:
            raise ValueError("FixedClock requires an aware datetime")
        self._current = start
        self._step_seconds = step_seconds

    def now(self) -> datetime:
        current = self._current
        if self._step_seconds:
            from datetime import timedelta

            self._current = current + timedelta(seconds=self._step_seconds)
        return current
