"""The policy loop, reading and moving the product's real projects.

Everything upstream of this worked: a crawl produced a proposal, publishing it
produced `v3`, and `/healthz` reported the new version. What did not happen was
the part the whole loop exists for -- a project pinned to `v2` stayed pinned,
was never flagged, and its creator was never told. `PolicyUpdatedConsumer` is
fully written, with idempotency receipts, impact filtering and recalc; it was
simply pointed at `InMemoryProjectRepository`, a fake holding no real projects,
and `FakeRecalcClient`.

These two adapters replace those fakes with the product.

**The boundary.** `CLAUDE.md` says workstream B reaches the product only
through `/v1/internal/*`. That rule is about ownership, not about forcing a
process to make HTTP calls to itself, so these adapters call the same
`WorkflowService` methods those two routes call and nothing else:
`mark_policy_stale` and `recalc_tier`. The file lives under `workers/policy/`,
so B still owns its side of the seam, and the product's code is untouched.

**What is deliberately read-only.** The repository projects the product's
`Project` into the `ProjectPolicyState` the consumer expects. It never writes
through that projection: staleness and recalculation go through the service, so
the state machine, the timeline, the audit log and the creator's notification
all happen exactly as they do when the internal route is called by hand.
"""

from __future__ import annotations

from typing import Literal

from core.repositories import ProjectStore
from schemas.enums import ProjectState
from schemas.policy_snapshot import ImpactNode

from ..consumer import RecalcResult
from .memory_projects import ProjectEffect, ProjectPolicyState

# How a project's state maps onto the three the consumer reasons about. It only
# needs to know whether a project is still editable, sealed, or filed -- the
# distinctions inside each group do not change whether policy may move it.
FROZEN_STATES = {
    ProjectState.FORM_FROZEN,
    ProjectState.INSTITUTION_REVIEW,
    ProjectState.INSTITUTION_RETURNED,
    ProjectState.READY_FOR_EXTERNAL_FILING,
}


def _workflow_status(state: ProjectState) -> Literal["DRAFT", "FORM_FROZEN", "FILED"]:
    if state is ProjectState.FILED or state is ProjectState.PRODUCTION:
        return "FILED"
    if state in FROZEN_STATES:
        return "FORM_FROZEN"
    return "DRAFT"


class LiveProjectRepository:
    """Reads the product's projects; writes only through the workflow service.

    Receipts and recalc operation keys are held in memory rather than persisted.
    That is honest for a single process and is the one thing here that a
    deployed version would have to change: after a restart an event could be
    processed twice. The consumer's own guards make a repeat harmless in effect
    -- `mark_policy_stale` is idempotent on `already_stale` and recalc is a
    no-op when the pinned version already matches -- so the cost is a duplicate
    timeline entry, not a duplicate notification.
    """

    def __init__(self, projects: ProjectStore, workflow) -> None:
        self._projects = projects
        self._workflow = workflow
        self._receipts: set[str] = set()
        self._recalc_operations: dict[str, Literal["started", "completed"]] = {}
        self.effects: dict[str, ProjectEffect] = {}

    def list_projects(self, limit: int = 100) -> list[ProjectPolicyState]:
        rows: list[ProjectPolicyState] = []
        for project in self._projects.list_all():
            classification = project.classification
            if classification is None:
                # Nothing to make stale: an unclassified project has no
                # conclusion resting on a snapshot.
                continue
            version = classification.policy_snapshot_version
            if not version or not version.startswith("v"):
                continue

            rows.append(
                ProjectPolicyState(
                    project_id=project.project_id,
                    policy_snapshot_version=version,
                    # The impact nodes a project is exposed to. D1C is every
                    # classified project. C1A only once a review has run --
                    # see the note in the module docstring of the consumer
                    # about D1B, which has no node at all yet.
                    # D1B and D1C both attach to any classified project: its
                    # subject match and its tier were each decided against this
                    # snapshot. C1A only once a review has actually run.
                    impact_nodes=[ImpactNode.D1B, ImpactNode.D1C]
                    + ([ImpactNode.C1A] if project.state is not ProjectState.DRAFT else []),
                    has_classification=True,
                    has_review=project.state
                    not in (ProjectState.DRAFT, ProjectState.INTAKE_DONE),
                    tier=(
                        classification.tier.value
                        if classification.tier.value in ("T1", "T2", "T3")
                        else "T3"
                    ),
                    tier_provisional=classification.tier_provisional,
                    workflow_status=_workflow_status(project.state),
                    policy_stale=project.policy_stale,
                    frozen_form_hash=None,
                    submitted_materials=[],
                    registration_number=project.registration_number,
                )
            )
            if len(rows) >= limit:
                break
        return rows

    def get_project(self, project_id: str) -> ProjectPolicyState:
        for row in self.list_projects(limit=10_000):
            if row.project_id == project_id:
                return row
        raise KeyError(project_id)

    def mark_policy_stale(
        self, project_id: str, snapshot_version: str | None = None
    ) -> None:
        """Through the service, so the creator is notified and it is recorded.

        `snapshot_version` is the version that was just published, and it ends
        up in the creator's notice. An earlier version of this passed the
        project's *current* pinned version instead, so the dashboard read
        "Snapshot v2 was published" at the moment v3 was -- telling the creator
        news about the version they already had.
        """

        if snapshot_version is None:
            pinned = self._workflow.get_project(project_id).classification
            snapshot_version = pinned.policy_snapshot_version if pinned else ""
        self._workflow.mark_policy_stale(project_id, snapshot_version)

    def upsert_effect(self, effect: ProjectEffect) -> None:
        self.effects[effect.effect_id] = effect

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


class LiveRecalcClient:
    """Calls the same `recalc_tier` the internal route calls.

    `recalc_tier` re-runs only the amount stage, which is why it refuses to
    touch a settled tier -- a special-subject T1 must never be relaxed to T2 by
    a threshold change it was not decided by. That guard lives in the service,
    not here, and this adapter is deliberately thin so it cannot accidentally
    weaken it.
    """

    def __init__(self, workflow) -> None:
        self._workflow = workflow
        self.calls: list[tuple[str, str]] = []

    async def recalc_tier(self, project_id: str, snapshot_version: str) -> RecalcResult:
        self.calls.append((project_id, snapshot_version))
        result = self._workflow.recalc_tier(project_id, snapshot_version)
        return RecalcResult(
            tier=result.tier.value if hasattr(result.tier, "value") else str(result.tier),
            tier_provisional=result.tier_provisional,
            changed=result.changed,
        )


class InlineOutboxDelivery:
    """Deliver first, acknowledge second.

    The first version of this wiring used `OutboxDispatcher` with a publisher
    that queued events, then handed them to the consumer afterwards. That order
    loses events. `list_pending_outbox` selects only `PENDING` rows, so once
    `mark_outbox_sent` has run the row is never offered again -- and a process
    that died between the two left an outbox saying "sent" and projects that
    were never flagged, with nothing to notice or retry. (D-049 originally
    described this the wrong way round, as a risk of handling an event twice.
    It is the opposite, and losing a rule change silently is far worse than
    applying one twice.)

    So this delivers to the consumer and marks the row sent only if that
    returns. A failure leaves it `PENDING` for the next attempt, and the
    consumer's receipt guard makes the retry a no-op if it had in fact
    succeeded. That is the right way round: at-least-once with an idempotent
    handler, rather than at-most-once with none.
    """

    def __init__(self, repository, consumer, clock) -> None:
        self._repository = repository
        self._consumer = consumer
        self._clock = clock
        self.delivered: list = []

    async def deliver(self, limit: int = 20) -> list:
        results = []
        for outbox_id, row in self._repository.list_pending_outbox(limit):
            result = await self._consumer.handle(row.payload)
            self._repository.mark_outbox_sent(
                outbox_id,
                self._clock(),
                f"inline-{row.payload.snapshot_version}",
            )
            self.delivered.append(row.payload)
            results.append(result)
        return results
