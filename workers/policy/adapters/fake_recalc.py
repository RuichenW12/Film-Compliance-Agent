"""Deterministic fake of the A-line recalc-tier endpoint."""

from typing import Literal

from .memory_projects import InMemoryProjectRepository
from ..consumer import RecalcResult


class FakeRecalcError(RuntimeError):
    pass


class FakeRecalcClient:
    def __init__(
        self,
        repository: InMemoryProjectRepository,
        *,
        new_tier: Literal["T1", "T2", "T3"],
        fail_on: set[str] | None = None,
    ) -> None:
        self._repository = repository
        self._new_tier = new_tier
        self._fail_on = set(fail_on or ())
        self.calls: list[tuple[str, str]] = []

    async def recalc_tier(
        self, project_id: str, snapshot_version: str
    ) -> RecalcResult:
        self.calls.append((project_id, snapshot_version))
        if project_id in self._fail_on:
            raise FakeRecalcError(project_id)
        project = self._repository.get_project(project_id)
        if (
            not project.tier_provisional
            or project.workflow_status in {"FORM_FROZEN", "FILED"}
        ):
            return RecalcResult(
                tier=project.tier,
                tier_provisional=project.tier_provisional,
                changed=False,
            )
        self._repository.apply_recalc(project_id, snapshot_version, self._new_tier)
        return RecalcResult(
            tier=self._new_tier,
            tier_provisional=False,
            changed=True,
        )
