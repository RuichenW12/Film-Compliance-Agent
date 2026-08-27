"""S3: run D1a -> D1b -> D1c against one pinned snapshot and assemble the card."""

from __future__ import annotations

from dataclasses import dataclass, field

from schemas.common import EvidenceRef, SourceRef
from schemas.enums import (
    AlertOption,
    ExitKind,
    FindingSeverity,
    FormType,
    ProjectState,
    SourceRefType,
    Tier,
)
from schemas.findings import Alert, AlertChoice, AlertDept
from schemas.policy_snapshot import PackName
from schemas.project import ChannelProfile, Classification, IntentProfile
from schemas.snapshot import SnapshotService

from ..llm import LLMClient
from .d1a import judge_form_type
from .d1b import judge_subject
from .d1c import judge_tier

ROADMAP_TEMPLATE_BY_TIER = {
    Tier.T1: "T1_7steps",
    Tier.T2: "T2_5steps",
    Tier.T3: "T3_4steps",
}

EXIT_CARD_KEYS = {
    ExitKind.EXIT_NON_DRAMA: "exit.non_drama",
    ExitKind.EXIT_SISTER_PATH: "exit.sister_path",
}

EXIT_STATE = {
    ExitKind.EXIT_NON_DRAMA: ProjectState.EXIT_NON_DRAMA,
    ExitKind.EXIT_SISTER_PATH: ProjectState.EXIT_SISTER_PATH,
}

FORM_CLAUSE_ID = "nrta-order-16-article-2"
TIER_CLAUSE_ID = "nrta-order-16-article-5"


@dataclass
class ExitOutcome:
    kind: ExitKind
    obligations: list[str] = field(default_factory=list)
    card_key: str = ""


@dataclass
class ProposedFact:
    key: str
    value: str | int | float
    source_ref: SourceRef


@dataclass
class ClassificationOutcome:
    """What the chain proposes. The workflow service decides what to persist."""

    classification: Classification | None = None
    exit: ExitOutcome | None = None
    next_state: ProjectState | None = None
    ask_back: list[str] = field(default_factory=list)
    roadmap_preview: dict | None = None
    alert: Alert | None = None
    alert_category: str | None = None
    alert_severity: FindingSeverity | None = None
    facts: list[ProposedFact] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def _intent_facts(intent: IntentProfile) -> list[ProposedFact]:
    facts: list[ProposedFact] = []
    if intent.episode_count is not None:
        facts.append(
            ProposedFact(
                "episode_count",
                intent.episode_count,
                SourceRef(
                    type=SourceRefType.USER_ANSWER, answer_id="intent.episode_count"
                ),
            )
        )
    if intent.episode_minutes is not None:
        facts.append(
            ProposedFact(
                "episode_minutes",
                intent.episode_minutes,
                SourceRef(
                    type=SourceRefType.USER_ANSWER, answer_id="intent.episode_minutes"
                ),
            )
        )
    if intent.investment_amount_rmb is not None:
        facts.append(
            ProposedFact(
                "investment_amount_rmb",
                intent.investment_amount_rmb,
                SourceRef(
                    type=SourceRefType.USER_ANSWER,
                    answer_id="intent.investment_amount_rmb",
                ),
            )
        )
    return facts


def _edge_alert(dept: dict | None) -> Alert:
    mapping = dept or {}
    return Alert(
        risk_reason="alert.subject_edge_case",
        dept=AlertDept(
            name=mapping.get("name", "alert.dept.pending"),
            practical_contact=mapping.get("practical_contact"),
            region_note=mapping.get("region_note"),
        ),
        options=[
            AlertChoice(
                id=AlertOption.A_KEEP_AND_COREVIEW,
                action="alert.option.keep_and_coreview",
                impact="alert.impact.longer_review",
            ),
            AlertChoice(
                id=AlertOption.B_MODIFY,
                action="alert.option.modify",
                impact="alert.impact.rewrite_scenes",
            ),
            AlertChoice(
                id=AlertOption.C_ESCALATE,
                action="alert.option.escalate",
                impact="alert.impact.consult_authority",
            ),
        ],
    )


def classify(
    intent: IntentProfile,
    channels: ChannelProfile,
    snapshots: SnapshotService,
    *,
    llm: LLMClient | None = None,
    snapshot_version: str | None = None,
    thresholds_published: bool | None = None,
) -> ClassificationOutcome:
    version = snapshot_version or snapshots.latest_version()
    verification_status = snapshots.verification_status(version)
    pack1 = snapshots.get_pack(PackName.P1_FORM_DEFINITION, version)
    pack2 = snapshots.get_pack(PackName.P2_SUBJECT_RULES, version)
    pack3 = snapshots.get_pack(PackName.P3_TIER_THRESHOLDS, version)
    form_clause_id = str(pack1.get("clause_ref") or FORM_CLAUSE_ID)

    form_decision = judge_form_type(intent, pack1, llm)

    if form_decision.outcome == "ask_back":
        return ClassificationOutcome(
            ask_back=form_decision.missing, reasons=form_decision.reasons
        )

    if form_decision.outcome == "needs_human":
        return ClassificationOutcome(
            next_state=ProjectState.NEEDS_HUMAN_FORMTYPE,
            reasons=form_decision.reasons,
            classification=Classification(
                form_type=FormType.UNDETERMINED,
                tier=Tier.UNDETERMINED,
                policy_snapshot_version=version,
                policy_verification_status=verification_status,
                pending_flags=[*form_decision.pending_flags, "human_review"],
            ),
            facts=_intent_facts(intent),
        )

    if form_decision.outcome in ("exit_non_drama", "exit_sister_path"):
        kind = (
            ExitKind.EXIT_NON_DRAMA
            if form_decision.outcome == "exit_non_drama"
            else ExitKind.EXIT_SISTER_PATH
        )
        obligations = ["ai_labeling"] if intent.is_ai_generated else []
        obligations.append("platform_rules")
        return ClassificationOutcome(
            classification=Classification(
                form_type=form_decision.form_type,
                tier=Tier.UNDETERMINED,
                policy_snapshot_version=version,
                policy_verification_status=verification_status,
                pending_flags=form_decision.pending_flags,
                evidence_refs=[
                    EvidenceRef(snapshot_version=version, clause_id=form_clause_id)
                ],
            ),
            exit=ExitOutcome(
                kind=kind, obligations=obligations, card_key=EXIT_CARD_KEYS[kind]
            ),
            next_state=EXIT_STATE[kind],
            reasons=form_decision.reasons,
            facts=_intent_facts(intent),
        )

    subject = judge_subject(intent, pack2, llm)
    pending_flags = [*form_decision.pending_flags, *subject.pending_flags]
    evidence = [
        EvidenceRef(snapshot_version=version, clause_id=clause_id)
        for clause_id in subject.clause_refs
    ]

    if subject.special_subject_hit:
        # The strict operational reading is T1 plus co-review. The cited article
        # is narrower: the authority consults when it considers it necessary, so
        # a hit is a strong indication rather than a settled tier. While the
        # rules that produced the hit are themselves unconfirmed, the tier is
        # reported provisional with a flag, and the co-review requirement is
        # kept because it is the safer of the two readings for a creator to plan
        # around. See D-026.
        rules_unconfirmed = subject.expert_pending
        subject_flags = [
            *pending_flags,
            *(["subject_disposal_unconfirmed"] if rules_unconfirmed else []),
        ]
        classification = Classification(
            form_type=FormType.MICRO_DRAMA,
            tier=Tier.T1,
            tier_provisional=rules_unconfirmed,
            special_subject_hit=True,
            co_review_required=True,
            matched_rules=subject.matched_rules,
            confidence=subject.confidence,
            policy_snapshot_version=version,
            policy_verification_status=verification_status,
            pending_flags=subject_flags,
            dept=subject.dept,
            evidence_refs=evidence
            or [EvidenceRef(snapshot_version=version, clause_id=TIER_CLAUSE_ID)],
        )
        return ClassificationOutcome(
            classification=classification,
            next_state=ProjectState.CLASSIFIED,
            roadmap_preview={"template": ROADMAP_TEMPLATE_BY_TIER[Tier.T1]},
            reasons=[*form_decision.reasons, "subject.special_subject_hit"],
            facts=_intent_facts(intent),
        )

    if subject.edge_case_hit:
        classification = Classification(
            form_type=FormType.MICRO_DRAMA,
            tier=Tier.UNDETERMINED,
            matched_rules=subject.edge_rules,
            confidence=subject.confidence,
            policy_snapshot_version=version,
            policy_verification_status=verification_status,
            pending_flags=[*pending_flags, "human_review"],
            dept=subject.dept,
            evidence_refs=evidence,
        )
        return ClassificationOutcome(
            classification=classification,
            next_state=ProjectState.NEEDS_HUMAN_SUBJECT,
            alert=_edge_alert(subject.dept),
            alert_category="subject_edge_case",
            alert_severity=FindingSeverity.NEEDS_HUMAN,
            reasons=[*form_decision.reasons, "subject.edge_case"],
            facts=_intent_facts(intent),
        )

    tier_decision = judge_tier(
        intent.budget_band,
        pack3,
        thresholds_published,
        investment_amount_rmb=intent.investment_amount_rmb,
        is_ai_generated=intent.is_ai_generated,
    )
    tier_clause_id = tier_decision.clause_ref or TIER_CLAUSE_ID
    classification = Classification(
        form_type=FormType.MICRO_DRAMA,
        tier=tier_decision.tier,
        tier_provisional=tier_decision.tier_provisional,
        special_subject_hit=False,
        co_review_required=False,
        matched_rules=[],
        confidence=0.6 if tier_decision.tier_provisional else 1.0,
        policy_snapshot_version=version,
        policy_verification_status=verification_status,
        pending_flags=[*pending_flags, *tier_decision.pending_flags],
        evidence_refs=[
            EvidenceRef(snapshot_version=version, clause_id=tier_clause_id)
        ],
    )
    return ClassificationOutcome(
        classification=classification,
        next_state=ProjectState.CLASSIFIED,
        roadmap_preview={
            "template": ROADMAP_TEMPLATE_BY_TIER[tier_decision.tier],
            "comparison_card": tier_decision.comparison_card,
        },
        reasons=[*form_decision.reasons, *tier_decision.reasons],
        facts=_intent_facts(intent),
    )
