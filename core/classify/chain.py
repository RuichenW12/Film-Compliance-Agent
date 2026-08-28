"""S3: run D1a -> D1b -> D1c against one pinned snapshot and assemble the card."""

from __future__ import annotations

from datetime import datetime, timezone

from dataclasses import dataclass, field, replace

from schemas.common import EvidenceRef, SourceRef
from schemas.enums import (
    AlertOption,
    ExitKind,
    FindingSeverity,
    FormType,
    ProductionStage,
    ProjectState,
    SourceRefType,
    Tier,
)
from schemas.findings import Alert, AlertChoice, AlertDept
from schemas.policy_snapshot import PackName
from schemas.project import ChannelProfile, Classification, IntentProfile
from schemas.snapshot import SnapshotNotFoundError, SnapshotService

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


def clauses_not_yet_in_force(
    snapshots: SnapshotService, version: str, clause_ids, as_of: datetime
) -> list[str]:
    """Which cited clauses take effect after `as_of`.

    A snapshot may legitimately carry clauses from documents with different
    effective dates: the tier thresholds have applied since January, while
    微短剧发展管理办法 applies from 2026-09-01. The snapshot's own
    `effective_from` answers a different question — from when the snapshot may
    be used — so it cannot express this, and a classification that rests on a
    provision not yet in force should say so rather than read as settled law.

    A clause with no recorded date is not reported: unknown is not the same as
    future-dated. See D-028.
    """

    future: list[str] = []
    for clause_id in clause_ids:
        try:
            clause = snapshots.clause(clause_id, version)
        except (SnapshotNotFoundError, KeyError):
            continue
        if clause.in_force(as_of) is False:
            future.append(clause_id)
    return sorted(set(future))


def filing_route(
    tier: Tier, snapshots: SnapshotService, version: str
) -> dict | None:
    """Which authority this tier reports to, per the snapshot's p4 pack.

    The three routes are not a product opinion: 总局令第16号 states them.
    Article 12 puts a one-class filing before shooting; article 13 sends the
    national publication to the State Council department while provinces审核
    their own; article 17 makes one- and two-class review a precondition of
    release and leaves three-class to the platform; article 34 makes the
    platform verify the first two and number the third.

    Returned as data from the pack rather than computed here, so a policy
    change is a snapshot change. A route whose clauses are not in this snapshot
    is not returned at all -- an unsourced route is exactly the kind of
    confident-looking answer this product must not give.
    """

    try:
        pack4 = snapshots.get_pack(PackName.P4_PROCESS_TEMPLATES, version)
    except (SnapshotNotFoundError, KeyError):
        return None
    raw = (pack4 or {}).get("filing_routes") or {}
    route = raw.get(tier.value)
    if not isinstance(route, dict):
        return None

    cited = [str(c) for c in route.get("clause_refs") or []]
    known = []
    for clause_id in cited:
        try:
            snapshots.clause(clause_id, version)
        except (SnapshotNotFoundError, KeyError):
            continue
        known.append(clause_id)
    if cited and not known:
        return None

    resolved = dict(route)
    resolved["clause_refs"] = known
    return resolved


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
    """Run the chain, then say whether it rested on a provision not yet in force.

    The check sits here rather than in each branch because every branch cites
    different clauses, and a rule that only some paths honour is not a rule.
    See D-028.
    """

    outcome = _classify(
        intent,
        channels,
        snapshots,
        llm=llm,
        snapshot_version=snapshot_version,
        thresholds_published=thresholds_published,
    )
    classification = outcome.classification
    if classification is None:
        return outcome

    updates: dict = {}

    # Where this tier files. Same reason as the check below: every branch
    # decides a tier, so attaching the route once here beats repeating it in
    # each of them.
    route = filing_route(
        classification.tier, snapshots, classification.policy_snapshot_version
    )
    if route is not None:
        updates["filing_route"] = route

    flags = set(classification.pending_flags)

    future = clauses_not_yet_in_force(
        snapshots,
        classification.policy_snapshot_version,
        [ref.clause_id for ref in classification.evidence_refs],
        datetime.now(timezone.utc),
    )
    if future:
        flags.add("clause_not_yet_in_force")

    # Article 12 puts the one-class filing *before* shooting. Someone already
    # shooting or finished has passed that step, and handing them a roadmap that
    # opens with it would read as advice when it is a problem. Reported, not
    # decided: the tier does not change, and no state moves.
    if classification.tier is Tier.T1 and intent.production_stage in (
        ProductionStage.SHOOTING,
        ProductionStage.FINISHED,
    ):
        flags.add("filing_due_before_shooting")

    if flags != set(classification.pending_flags):
        updates["pending_flags"] = sorted(flags)

    if not updates:
        return outcome

    return replace(
        outcome, classification=classification.model_copy(update=updates)
    )


def _classify(
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
        # T1 plus co-review had looked stronger than its source: Order 16
        # article 14 has the authority consult only when it considers it
        # necessary. 广电办发〔2024〕35号 then turned up and is explicit —
        # 特殊题材的微短剧「按有关协审工作机制落实审核要求」 — so the disposal
        # itself is well founded and no longer flagged.
        #
        # Whether the trigger vocabulary has been confirmed by an expert is a
        # property of the policy data, not of this project's tier. It is settled
        # in the outer loop, before a rule is ever published, and the snapshot
        # already reports its own maturity through policy_verification_status.
        # Letting it also decide tier_provisional said something different and
        # false -- that this project's tier might still move -- and it was a debt
        # nothing could repay: no code path clears expert_pending, so every
        # subject hit read as unsettled forever, and recalc_tier (which only
        # touches provisional tiers) would then overwrite a T1 with the
        # amount-derived tier. The flag stays, as a flag. See D-031, which
        # supersedes this half of D-033.
        rules_unconfirmed = subject.expert_pending
        subject_flags = [
            *pending_flags,
            *(["subject_match_unconfirmed"] if rules_unconfirmed else []),
        ]
        classification = Classification(
            form_type=FormType.MICRO_DRAMA,
            tier=Tier.T1,
            tier_provisional=False,
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
        platform_promoted=intent.platform_promoted,
        voluntary_key_declaration=intent.voluntary_key_declaration,
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
