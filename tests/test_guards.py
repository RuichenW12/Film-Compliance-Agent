"""T-A1 acceptance: every guard branch of the D3 gate and the state machine."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.errors import GateBlockedError, StateInvalidError
from core.gate import can_freeze_form, evaluate_gate_d3
from core.state_machine import GateContext, is_allowed, transition
from schemas.assets import MaterialCard
from schemas.common import EvidenceRef, Fact, SourceRef
from schemas.enums import (
    Actor,
    AlertOption,
    AssetKind,
    FactStatus,
    FindingSeverity,
    FindingStatus,
    MaterialStatus,
    ProjectState,
    SourceRefType,
)
from schemas.findings import Alert, AlertChoice, AlertDept, Finding, Locator
from schemas.project import Project

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
REQUIRED_FACTS = (
    "title",
    "episode_count",
    "episode_minutes",
    "applicant_entity",
    "investment_structure",
)


def make_project(state: ProjectState = ProjectState.REVIEW_RUNNING, **overrides) -> Project:
    payload = {
        "project_id": "proj_test",
        "owner_uid": "u_demo",
        "state": state,
        "created_at": NOW,
        "updated_at": NOW,
    }
    payload.update(overrides)
    return Project(**payload)


def evidence() -> list[EvidenceRef]:
    return [EvidenceRef(snapshot_version="v1", clause_id="nrta-order-16-article-5")]


def make_finding(**overrides) -> Finding:
    payload = {
        "finding_id": "fnd_1",
        "asset_version": "av_1",
        "locator": Locator(episode=5, scene=2, quote="公安干警持枪进入现场"),
        "category": "public_security",
        "severity": FindingSeverity.BLOCK,
        "evidence_refs": evidence(),
    }
    payload.update(overrides)
    return Finding(**payload)


def make_alert(chosen: AlertOption | None = None) -> Alert:
    return Alert(
        risk_reason="alert.subject_edge_case",
        dept=AlertDept(name="公安主管部门", practical_contact="属地公安局宣传部门"),
        options=[
            AlertChoice(id=AlertOption.A_KEEP_AND_COREVIEW, action="keep", impact="longer"),
            AlertChoice(id=AlertOption.B_MODIFY, action="modify", impact="rewrite"),
        ],
        chosen_option=chosen,
    )


def full_facts() -> list[Fact]:
    return [
        Fact(
            fact_id=f"fact_{key}",
            key=key,
            value="value",
            source_ref=SourceRef(type=SourceRefType.USER_ANSWER, answer_id="q1"),
        )
        for key in REQUIRED_FACTS
    ]


def validated_materials() -> list[MaterialCard]:
    return [
        MaterialCard(
            material_id="mat_script",
            name_key="material.script",
            asset_kind=AssetKind.SCRIPT,
            status=MaterialStatus.VALID,
        )
    ]


def test_gate_passes_when_nothing_is_outstanding():
    result = evaluate_gate_d3(make_project(), [], full_facts(), validated_materials())
    assert result.passed is True
    assert result.gaps == []


def test_open_block_finding_stops_the_gate():
    result = evaluate_gate_d3(
        make_project(), [make_finding()], full_facts(), validated_materials()
    )
    assert result.passed is False
    assert result.as_dict()["gaps"][0] == {"check": "open_blocks", "items": ["fnd_1"]}


def test_undispatched_alert_counts_as_blocking():
    finding = make_finding(
        severity=FindingSeverity.CO_REVIEW_REQUIRED, alert=make_alert(chosen=None)
    )
    result = evaluate_gate_d3(
        make_project(), [finding], full_facts(), validated_materials()
    )
    assert result.passed is False
    assert any(gap.check == "alerts_undispatched" for gap in result.gaps)


def test_dispatched_alert_clears_the_gate():
    finding = make_finding(
        severity=FindingSeverity.CO_REVIEW_REQUIRED,
        alert=make_alert(chosen=AlertOption.A_KEEP_AND_COREVIEW),
    )
    result = evaluate_gate_d3(
        make_project(), [finding], full_facts(), validated_materials()
    )
    assert result.passed is True


def test_missing_required_facts_stop_the_gate():
    facts = [fact for fact in full_facts() if fact.key != "investment_structure"]
    result = evaluate_gate_d3(make_project(), [], facts, validated_materials())
    assert result.passed is False
    assert any(
        gap.check == "facts_missing" and "investment_structure" in gap.items
        for gap in result.gaps
    )


def test_pending_institution_facts_are_acceptable():
    facts = [
        fact
        if fact.key != "applicant_entity"
        else Fact(
            fact_id="fact_pending",
            key="applicant_entity",
            value=None,
            source_ref=SourceRef(type=SourceRefType.INSTITUTION),
            status=FactStatus.PENDING_INSTITUTION,
        )
        for fact in full_facts()
    ]
    result = evaluate_gate_d3(make_project(), [], facts, validated_materials())
    assert result.passed is True


def test_unvalidated_material_stops_the_gate():
    materials = [
        MaterialCard(
            material_id="mat_script",
            name_key="material.script",
            asset_kind=AssetKind.SCRIPT,
            status=MaterialStatus.UPLOADED,
        )
    ]
    result = evaluate_gate_d3(make_project(), [], full_facts(), materials)
    assert result.passed is False
    assert any(gap.check == "materials_unvalidated" for gap in result.gaps)


def test_unevidenced_conclusion_is_rejected_at_the_model_boundary():
    with pytest.raises(ValueError):
        make_finding(evidence_refs=[])


def test_needs_human_finding_without_evidence_is_allowed_but_blocks():
    finding = make_finding(severity=FindingSeverity.NEEDS_HUMAN, evidence_refs=[])
    result = evaluate_gate_d3(
        make_project(), [finding], full_facts(), validated_materials()
    )
    assert result.passed is False
    assert any(gap.check == "findings_needs_human" for gap in result.gaps)


def test_resolved_findings_no_longer_block():
    finding = make_finding(status=FindingStatus.RESOLVED)
    result = evaluate_gate_d3(
        make_project(), [finding], full_facts(), validated_materials()
    )
    assert result.passed is True


def test_freeze_is_only_reachable_from_the_gate():
    assert can_freeze_form(make_project(ProjectState.GATE_D3_PASSED)) is True
    assert can_freeze_form(make_project(ProjectState.REVIEW_RUNNING)) is False


def test_transition_writes_an_audit_entry(clock):
    project = make_project(ProjectState.DRAFT)
    result = transition(
        project,
        ProjectState.INTAKE_DONE,
        actor=Actor.CREATOR,
        reason="intent.submitted",
        clock=clock,
    )
    assert result.project.state is ProjectState.INTAKE_DONE
    assert result.audit.from_state == "DRAFT"
    assert result.audit.to_state == "INTAKE_DONE"
    assert result.timeline.event == "state.INTAKE_DONE"


def test_illegal_transition_is_refused(clock):
    project = make_project(ProjectState.DRAFT)
    with pytest.raises(StateInvalidError):
        transition(
            project,
            ProjectState.FORM_FROZEN,
            actor=Actor.SYSTEM,
            reason="skip",
            clock=clock,
        )


def test_terminal_states_are_terminal(clock):
    project = make_project(ProjectState.EXIT_NON_DRAMA)
    with pytest.raises(StateInvalidError):
        transition(
            project,
            ProjectState.CLASSIFIED,
            actor=Actor.SYSTEM,
            reason="reopen",
            clock=clock,
        )


def test_gate_transition_refuses_when_blocked(clock):
    project = make_project(ProjectState.REVIEW_RUNNING)
    context = GateContext(
        findings=[make_finding()], facts=full_facts(), materials=validated_materials()
    )
    with pytest.raises(GateBlockedError) as excinfo:
        transition(
            project,
            ProjectState.GATE_D3_PASSED,
            actor=Actor.SYSTEM,
            reason="gate",
            clock=clock,
            gate_context=context,
        )
    assert excinfo.value.details["gaps"][0]["check"] == "open_blocks"


def test_gate_transition_passes_when_clear(clock):
    project = make_project(ProjectState.REVIEW_RUNNING)
    context = GateContext(findings=[], facts=full_facts(), materials=validated_materials())
    result = transition(
        project,
        ProjectState.GATE_D3_PASSED,
        actor=Actor.SYSTEM,
        reason="gate",
        clock=clock,
        gate_context=context,
    )
    assert result.project.state is ProjectState.GATE_D3_PASSED


def test_filing_requires_a_registration_number(clock):
    project = make_project(ProjectState.READY_FOR_EXTERNAL_FILING)
    with pytest.raises(StateInvalidError):
        transition(
            project,
            ProjectState.FILED,
            actor=Actor.INSTITUTION,
            reason="filed",
            clock=clock,
        )

    numbered = make_project(
        ProjectState.READY_FOR_EXTERNAL_FILING, registration_number="剧审字[2026]第0001号"
    )
    result = transition(
        numbered,
        ProjectState.FILED,
        actor=Actor.INSTITUTION,
        reason="filed",
        clock=clock,
    )
    assert result.project.state is ProjectState.FILED


def test_transition_table_covers_every_state():
    from core.state_machine import ALLOWED_TRANSITIONS

    assert set(ALLOWED_TRANSITIONS) == set(ProjectState)
    assert is_allowed(ProjectState.GATE_D3_PASSED, ProjectState.FORM_FROZEN)
