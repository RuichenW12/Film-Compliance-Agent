"""Idempotent policy.updated consumer orchestration."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from schemas.policy_snapshot import ImpactNode, PolicyUpdatedEvent

from .adapters.memory_projects import (
    InMemoryProjectRepository,
    ProjectEffect,
    ProjectPolicyState,
)


class RecalcResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: Literal["T1", "T2", "T3"]
    tier_provisional: bool
    changed: bool


class RecalcClient(Protocol):
    async def recalc_tier(
        self, project_id: str, snapshot_version: str
    ) -> RecalcResult: ...


class ConsumeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stale_marked: int
    recalculated: int
    already_processed: bool


class PolicyUpdatedConsumer:
    def __init__(
        self,
        repository: InMemoryProjectRepository,
        recalc_client: RecalcClient,
    ) -> None:
        self._repository = repository
        self._recalc_client = recalc_client

    async def handle(self, event: PolicyUpdatedEvent) -> ConsumeResult:
        if self._repository.has_receipt(event.idempotency_key):
            return ConsumeResult(
                stale_marked=0, recalculated=0, already_processed=True
            )

        stale_marked = 0
        recalculated = 0
        event_version = int(event.snapshot_version[1:])
        for project in self._repository.list_projects(limit=100):
            if int(project.policy_snapshot_version[1:]) >= event_version:
                continue
            if not self._is_affected(project, event):
                continue

            self._repository.mark_policy_stale(project.project_id)
            self._upsert_effect(event, project.project_id, "policy_stale")
            stale_marked += 1

            if (
                event.thresholds_published
                and ImpactNode.D1C in event.impact
                and ImpactNode.D1C in project.impact_nodes
                and project.has_classification
                and project.tier_provisional
            ):
                result = await self._recalc_client.recalc_tier(
                    project.project_id, event.snapshot_version
                )
                if result.changed:
                    recalculated += 1
                    self._upsert_effect(
                        event, project.project_id, "tier_recalculated"
                    )

        self._repository.put_receipt(event.idempotency_key)
        return ConsumeResult(
            stale_marked=stale_marked,
            recalculated=recalculated,
            already_processed=False,
        )

    @staticmethod
    def _is_affected(
        project: ProjectPolicyState, event: PolicyUpdatedEvent
    ) -> bool:
        d1c = (
            ImpactNode.D1C in event.impact
            and ImpactNode.D1C in project.impact_nodes
            and project.has_classification
        )
        c1a = (
            ImpactNode.C1A in event.impact
            and ImpactNode.C1A in project.impact_nodes
            and project.has_review
        )
        return d1c or c1a

    def _upsert_effect(
        self,
        event: PolicyUpdatedEvent,
        project_id: str,
        kind: Literal["policy_stale", "tier_recalculated"],
    ) -> None:
        effect_id = f"{event.idempotency_key}:{project_id}:{kind}"
        self._repository.upsert_effect(
            ProjectEffect(
                effect_id=effect_id,
                event_key=event.idempotency_key,
                project_id=project_id,
                kind=kind,
            )
        )
