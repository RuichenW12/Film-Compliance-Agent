"""D3 gate and freeze guards (TDD sections 3 and 4.11). Pure functions, no LLM, no human."""

from __future__ import annotations

from dataclasses import dataclass, field

from schemas.assets import MaterialCard
from schemas.common import Fact
from schemas.enums import FactStatus, MaterialStatus, ProjectState
from schemas.findings import Finding
from schemas.project import Project

# Facts the registration form cannot be frozen without. A snapshot pack may
# override this list via p5_form_templates.required_facts.
DEFAULT_REQUIRED_FACT_KEYS: tuple[str, ...] = (
    "title",
    "episode_count",
    "episode_minutes",
    "applicant_entity",
    "investment_structure",
)


@dataclass(frozen=True)
class Gap:
    check: str
    items: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"check": self.check, "items": list(self.items)}


@dataclass(frozen=True)
class GateResult:
    passed: bool
    gaps: list[Gap] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"passed": self.passed, "gaps": [gap.as_dict() for gap in self.gaps]}


def required_fact_keys(form_pack: dict | None = None) -> tuple[str, ...]:
    if form_pack:
        configured = form_pack.get("required_facts")
        if configured:
            return tuple(str(key) for key in configured)
    return DEFAULT_REQUIRED_FACT_KEYS


def evaluate_gate_d3(
    project: Project,
    findings: list[Finding],
    facts: list[Fact],
    materials: list[MaterialCard],
    form_pack: dict | None = None,
) -> GateResult:
    """Machine-readable gap report. Empty gaps means the gate opens."""

    gaps: list[Gap] = []

    open_blocks = [
        finding.finding_id
        for finding in findings
        if finding.severity.value == "block" and finding.blocks_gate_d3
    ]
    if open_blocks:
        gaps.append(Gap("open_blocks", open_blocks))

    undispatched_alerts = [
        finding.finding_id
        for finding in findings
        if finding.alert is not None
        and finding.alert.chosen_option is None
        and finding.blocks_gate_d3
    ]
    if undispatched_alerts:
        gaps.append(Gap("alerts_undispatched", undispatched_alerts))

    unresolved_needs_human = [
        finding.finding_id
        for finding in findings
        if finding.severity.value == "needs_human" and finding.blocks_gate_d3
    ]
    if unresolved_needs_human:
        gaps.append(Gap("findings_needs_human", unresolved_needs_human))

    usable_fact_keys = {
        fact.key
        for fact in facts
        if fact.status in (FactStatus.CONFIRMED, FactStatus.PENDING_INSTITUTION)
    }
    missing_facts = [
        key for key in required_fact_keys(form_pack) if key not in usable_fact_keys
    ]
    if missing_facts:
        gaps.append(Gap("facts_missing", missing_facts))

    conflicting_facts = [
        fact.key for fact in facts if fact.status is FactStatus.CONFLICT
    ]
    if conflicting_facts:
        gaps.append(Gap("facts_conflicting", sorted(set(conflicting_facts))))

    unvalidated_materials = [
        material.material_id
        for material in materials
        if material.required
        and material.status not in (MaterialStatus.VALID, MaterialStatus.WAIVED)
    ]
    if unvalidated_materials:
        gaps.append(Gap("materials_unvalidated", unvalidated_materials))

    return GateResult(passed=not gaps, gaps=gaps)


def can_pass_gate_d3(
    project: Project,
    findings: list[Finding],
    facts: list[Fact],
    materials: list[MaterialCard],
    form_pack: dict | None = None,
) -> bool:
    return evaluate_gate_d3(project, findings, facts, materials, form_pack).passed


def can_freeze_form(project: Project) -> bool:
    """Freezing is only ever reachable through the gate."""

    return project.state is ProjectState.GATE_D3_PASSED
