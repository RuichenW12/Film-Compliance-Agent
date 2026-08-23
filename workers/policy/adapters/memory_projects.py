"""Minimal A-line project state adapter for Gate 2 acceptance."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from schemas.policy_snapshot import ImpactNode


Version = Annotated[str, StringConstraints(pattern=r"^v[1-9][0-9]*$")]


class ProjectPolicyState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    policy_snapshot_version: Version
    impact_nodes: list[ImpactNode]
    has_classification: bool
    has_review: bool
    tier: Literal["T1", "T2", "T3"]
    tier_provisional: bool
    workflow_status: Literal["DRAFT", "FORM_FROZEN", "FILED"]
    policy_stale: bool
    frozen_form_hash: str | None
    submitted_materials: list[str]
    registration_number: str | None


class ProjectEffect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effect_id: str
    event_key: str
    project_id: str
    kind: Literal["policy_stale", "tier_recalculated"]


class InMemoryProjectRepository:
    def __init__(self) -> None:
        self._projects: dict[str, ProjectPolicyState] = {}
        self._notifications: dict[str, ProjectEffect] = {}
        self._timeline: dict[str, ProjectEffect] = {}
        self._receipts: set[str] = set()
        self._recalc_operations: dict[str, Literal["started", "completed"]] = {}

    @property
    def notifications(self) -> dict[str, ProjectEffect]:
        return {
            effect_id: effect.model_copy(deep=True)
            for effect_id, effect in self._notifications.items()
        }

    @property
    def timeline(self) -> dict[str, ProjectEffect]:
        return {
            effect_id: effect.model_copy(deep=True)
            for effect_id, effect in self._timeline.items()
        }

    def add_project(self, project: ProjectPolicyState) -> None:
        if project.project_id in self._projects:
            raise ValueError(f"project already exists: {project.project_id}")
        self._projects[project.project_id] = project.model_copy(deep=True)

    def get_project(self, project_id: str) -> ProjectPolicyState:
        return self._projects[project_id].model_copy(deep=True)

    def list_projects(self, limit: int = 100) -> list[ProjectPolicyState]:
        project_ids = sorted(self._projects)[:limit]
        return [self.get_project(project_id) for project_id in project_ids]

    def mark_policy_stale(self, project_id: str) -> None:
        project = self._projects[project_id]
        self._projects[project_id] = project.model_copy(
            update={"policy_stale": True}
        )

    def apply_recalc(
        self, project_id: str, snapshot_version: str, tier: str
    ) -> None:
        project = self._projects[project_id]
        project_data = project.model_dump()
        project_data.update(
            policy_snapshot_version=snapshot_version,
            tier=tier,
            tier_provisional=False,
        )
        updated = ProjectPolicyState.model_validate(project_data)
        self._projects[project_id] = updated.model_copy(deep=True)

    def upsert_effect(self, effect: ProjectEffect) -> None:
        copied = effect.model_copy(deep=True)
        self._notifications[effect.effect_id] = copied
        self._timeline[effect.effect_id] = copied.model_copy(deep=True)

    def has_receipt(self, event_key: str) -> bool:
        return event_key in self._receipts

    def put_receipt(self, event_key: str) -> None:
        self._receipts.add(event_key)

    def start_recalc(self, operation_key: str) -> None:
        self._recalc_operations.setdefault(operation_key, "started")

    def complete_recalc(self, operation_key: str) -> None:
        self._recalc_operations[operation_key] = "completed"

    def recalc_status(
        self, operation_key: str
    ) -> Literal["started", "completed"] | None:
        return self._recalc_operations.get(operation_key)
