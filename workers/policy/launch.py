"""Create policy run records before executing refresh work."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from .interfaces import RefreshRepository
from .models import RefreshResult
from .refresh import PolicyRefreshModule


RunIdFactory = Callable[[], str]


class PolicyLaunchError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class PolicyRunLauncher:
    def __init__(
        self,
        repository: RefreshRepository,
        refresh: PolicyRefreshModule,
        source_ids: set[str],
        *,
        run_id_factory: RunIdFactory | None = None,
    ) -> None:
        self._repository = repository
        self._refresh = refresh
        self._source_ids = frozenset(source_ids)
        self._counter = 0
        self._run_id_factory = run_id_factory

    def launch(self, source_id: str, now: datetime) -> str:
        if source_id not in self._source_ids:
            raise PolicyLaunchError(
                "POLICY_SOURCE_NOT_FOUND", "policy source not found"
            )
        run_id = self._next_run_id()
        if not run_id:
            raise PolicyLaunchError("POLICY_RUN_ID_INVALID", "run id is empty")
        self._repository.create_run(run_id, source_id, now)
        return run_id

    def _next_run_id(self) -> str:
        if self._run_id_factory is not None:
            return self._run_id_factory()
        self._counter += 1
        return f"run_{self._counter:03d}"

    async def execute(
        self, run_id: str, source_id: str, now: datetime
    ) -> RefreshResult:
        return await self._refresh.run(run_id, source_id, now)
