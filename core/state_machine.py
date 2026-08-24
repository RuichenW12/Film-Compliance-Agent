"""Deterministic workflow state machine (TDD section 3).

Ground rule 1: LLM agents propose, they never mutate state. Every transition
goes through `transition()`, which checks guards and emits an audit entry.
"""

from __future__ import annotations

from dataclasses import dataclass

from schemas.assets import MaterialCard
from schemas.common import AuditEntry, Fact, TimelineEvent
from schemas.enums import Actor, ProjectState, TERMINAL_STATES
from schemas.findings import Finding
from schemas.project import Project

from .clock import Clock
from .errors import GateBlockedError, StateInvalidError
from .gate import can_freeze_form, evaluate_gate_d3
from .ids import new_id

S = ProjectState

ALLOWED_TRANSITIONS: dict[ProjectState, frozenset[ProjectState]] = {
    S.DRAFT: frozenset({S.INTAKE_DONE}),
    S.INTAKE_DONE: frozenset(
        {
            S.INTAKE_DONE,
            S.FORM_JUDGED,
            S.NEEDS_HUMAN_FORMTYPE,
            S.EXIT_NON_DRAMA,
            S.EXIT_SISTER_PATH,
        }
    ),
    S.FORM_JUDGED: frozenset(
        {
            S.CLASSIFIED,
            S.NEEDS_HUMAN_SUBJECT,
            S.NEEDS_HUMAN_FORMTYPE,
            S.EXIT_T2,
            S.EXIT_T3,
            S.EXIT_NON_DRAMA,
            S.EXIT_SISTER_PATH,
        }
    ),
    S.CLASSIFIED: frozenset(
        {
            S.CLASSIFIED,
            S.ROADMAP_CONFIRMED,
            S.INTAKE_DONE,
            S.NEEDS_HUMAN_SUBJECT,
            S.EXIT_T2,
            S.EXIT_T3,
        }
    ),
    S.ROADMAP_CONFIRMED: frozenset({S.COLLECTING_MATERIALS, S.CLASSIFIED}),
    S.COLLECTING_MATERIALS: frozenset(
        {S.COLLECTING_MATERIALS, S.REVIEW_RUNNING, S.CLASSIFIED}
    ),
    S.REVIEW_RUNNING: frozenset(
        {S.REVISION_LOOP, S.GATE_D3_PASSED, S.COLLECTING_MATERIALS, S.CLASSIFIED}
    ),
    S.REVISION_LOOP: frozenset(
        {S.REVIEW_RUNNING, S.REVISION_LOOP, S.GATE_D3_PASSED, S.CLASSIFIED}
    ),
    S.GATE_D3_PASSED: frozenset({S.FORM_FROZEN, S.REVISION_LOOP}),
    S.FORM_FROZEN: frozenset({S.INSTITUTION_REVIEW, S.REVISION_LOOP}),
    S.INSTITUTION_REVIEW: frozenset(
        {S.READY_FOR_EXTERNAL_FILING, S.INSTITUTION_RETURNED, S.INSTITUTION_REVIEW}
    ),
    S.INSTITUTION_RETURNED: frozenset({S.REVISION_LOOP, S.COLLECTING_MATERIALS}),
    S.READY_FOR_EXTERNAL_FILING: frozenset({S.FILED}),
    S.FILED: frozenset({S.PRODUCTION}),
    S.PRODUCTION: frozenset(),
    S.NEEDS_HUMAN_FORMTYPE: frozenset(
        {S.FORM_JUDGED, S.EXIT_NON_DRAMA, S.EXIT_SISTER_PATH, S.INTAKE_DONE}
    ),
    S.NEEDS_HUMAN_SUBJECT: frozenset({S.CLASSIFIED, S.EXIT_T2, S.EXIT_T3}),
    S.EXIT_NON_DRAMA: frozenset(),
    S.EXIT_T2: frozenset(),
    S.EXIT_T3: frozenset(),
    S.EXIT_SISTER_PATH: frozenset(),
}


@dataclass(frozen=True)
class GateContext:
    """Everything the D3 guard needs, gathered by the caller from the store."""

    findings: list[Finding]
    facts: list[Fact]
    materials: list[MaterialCard]
    form_pack: dict | None = None


@dataclass
class TransitionResult:
    project: Project
    audit: AuditEntry
    timeline: TimelineEvent


def is_allowed(from_state: ProjectState, to_state: ProjectState) -> bool:
    return to_state in ALLOWED_TRANSITIONS.get(from_state, frozenset())


def transition(
    project: Project,
    to_state: ProjectState,
    *,
    actor: Actor,
    reason: str,
    clock: Clock,
    detail: dict | None = None,
    gate_context: GateContext | None = None,
) -> TransitionResult:
    """Apply one transition or raise. Returns a new project instance plus its audit trail."""

    from_state = project.state

    if from_state in TERMINAL_STATES:
        raise StateInvalidError(
            f"project is in terminal state {from_state.value}",
            {"state": from_state.value},
        )
    if not is_allowed(from_state, to_state):
        raise StateInvalidError(
            f"transition {from_state.value} -> {to_state.value} is not allowed",
            {"from": from_state.value, "to": to_state.value},
        )

    _check_entry_guards(project, to_state, gate_context)

    now = clock.now()
    updated = project.model_copy(update={"state": to_state, "updated_at": now})

    audit = AuditEntry(
        at=now,
        actor=actor,
        from_state=from_state.value,
        to_state=to_state.value,
        reason=reason,
        detail=detail or {},
    )
    timeline = TimelineEvent(
        event_id=new_id("event"),
        at=now,
        actor=actor,
        event=f"state.{to_state.value}",
        detail={"from": from_state.value, "reason": reason, **(detail or {})},
    )
    return TransitionResult(project=updated, audit=audit, timeline=timeline)


def _check_entry_guards(
    project: Project,
    to_state: ProjectState,
    gate_context: GateContext | None,
) -> None:
    if to_state is S.GATE_D3_PASSED:
        if gate_context is None:
            raise StateInvalidError("gate context is required to pass D3")
        result = evaluate_gate_d3(
            project,
            gate_context.findings,
            gate_context.facts,
            gate_context.materials,
            gate_context.form_pack,
        )
        if not result.passed:
            raise GateBlockedError(
                "D3 gate is blocked", {"gaps": [gap.as_dict() for gap in result.gaps]}
            )

    if to_state is S.FORM_FROZEN and not can_freeze_form(project):
        raise StateInvalidError(
            "a form can only be frozen from GATE_D3_PASSED",
            {"state": project.state.value},
        )

    if to_state is S.FILED and not project.registration_number:
        raise StateInvalidError("filing requires a registration_number")

    if to_state in (S.ROADMAP_CONFIRMED, S.COLLECTING_MATERIALS) and project.roadmap is None:
        raise StateInvalidError("a confirmed roadmap is required at this step")
