"""Create policy run records before executing refresh work."""

from __future__ import annotations

from datetime import datetime

from .models import RefreshResult
from .refresh import PolicyRefreshModule
from .repository import InMemoryPolicyRepository


class PolicyLaunchError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class PolicyRunLauncher:
    def __init__(
        self,
        repository: InMemoryPolicyRepository,
        refresh: PolicyRefreshModule,
        source_ids: set[str],
    ) -> None:
        self._repository = repository
        self._refresh = refresh
        self._source_ids = frozenset(source_ids)
        self._counter = 0

    def launch(self, source_id: str, now: datetime) -> str:
        if source_id not in self._source_ids:
            raise PolicyLaunchError(
                "POLICY_SOURCE_NOT_FOUND", "policy source not found"
            )
        self._counter += 1
        run_id = f"run_{self._counter:03d}"
        self._repository.create_run(run_id, source_id, now)
        return run_id

    async def execute(
        self, run_id: str, source_id: str, now: datetime
    ) -> RefreshResult:
        return await self._refresh.run(run_id, source_id, now)
