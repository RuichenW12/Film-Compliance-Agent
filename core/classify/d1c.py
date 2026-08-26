"""D1c TierJudge (TDD 4.5). Pure function, no LLM.

An amount tier is final only when the pinned pack publishes a usable threshold
set. Budget-band fallbacks and incomplete threshold data stay provisional.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from schemas.enums import BudgetBand, Tier

# Placeholder band-to-tier mapping used only while official amounts are unpublished.
PROVISIONAL_BAND_TIER: dict[BudgetBand, Tier] = {
    BudgetBand.BAND_A: Tier.T1,
    BudgetBand.BAND_B: Tier.T2,
    BudgetBand.BAND_C: Tier.T3,
}

# With an unknown band we assume the stricter of the amount-based tiers and say so.
STRICTER_ASSUMPTION = Tier.T2


@dataclass
class TierDecision:
    tier: Tier
    tier_provisional: bool
    pending_flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    comparison_card: list[dict] = field(default_factory=list)
    clause_ref: str | None = None


# The pack may carry the flag under either key: `thresholds_published` is what
# the policy loop publishes, `official_published` is the older TDD spelling.
PUBLISHED_KEYS = ("thresholds_published", "official_published")


def _thresholds_published(pack3: dict, snapshot_thresholds_published: bool | None) -> bool:
    for key in PUBLISHED_KEYS:
        if key in pack3:
            return bool(pack3[key])
    if snapshot_thresholds_published is not None:
        return bool(snapshot_thresholds_published)
    return False


def _tier_from_amount(amount_rmb: float, thresholds: dict) -> Tier | None:
    t1_min = thresholds.get("T1_min_rmb")
    t2_min = thresholds.get("T2_min_rmb")
    if t1_min is not None and amount_rmb >= float(t1_min):
        return Tier.T1
    if t2_min is not None and amount_rmb >= float(t2_min):
        return Tier.T2
    if t1_min is not None or t2_min is not None:
        return Tier.T3
    return None


def _provisional_from_band(
    budget_band: BudgetBand,
    *,
    pending_flags: list[str],
) -> TierDecision:
    if budget_band is BudgetBand.UNKNOWN:
        return TierDecision(
            tier=STRICTER_ASSUMPTION,
            tier_provisional=True,
            pending_flags=["budget_unknown", *pending_flags],
            reasons=["tier.assumed_stricter_pending_budget"],
            comparison_card=[
                {"tier": tier.value, "band": band.value}
                for band, tier in PROVISIONAL_BAND_TIER.items()
            ],
        )
    return TierDecision(
        tier=PROVISIONAL_BAND_TIER[budget_band],
        tier_provisional=True,
        pending_flags=pending_flags,
        reasons=["tier.provisional_missing_exact_inputs"],
    )


def _thresholds_for_mode(pack3: dict, is_ai_generated: bool | None) -> dict:
    sets = pack3.get("threshold_sets") or {}
    if sets:
        if is_ai_generated is None:
            return {}
        key = "ai_generated" if is_ai_generated else "live_action"
        return sets.get(key) or {}
    return pack3.get("thresholds") or {}


def judge_tier(
    budget_band: BudgetBand,
    pack3: dict,
    snapshot_thresholds_published: bool | None = None,
    investment_amount_rmb: float | None = None,
    is_ai_generated: bool | None = None,
) -> TierDecision:
    published = _thresholds_published(pack3, snapshot_thresholds_published)
    threshold_sets = pack3.get("threshold_sets") or {}

    if threshold_sets and is_ai_generated is None:
        return _provisional_from_band(
            budget_band,
            pending_flags=["generation_mode_required"],
        )

    thresholds = _thresholds_for_mode(pack3, is_ai_generated)

    if published and investment_amount_rmb is not None and thresholds:
        tier = _tier_from_amount(investment_amount_rmb, thresholds)
        if tier is not None:
            return TierDecision(
                tier=tier,
                tier_provisional=False,
                reasons=["tier.from_official_thresholds"],
                clause_ref=thresholds.get("clause_ref"),
            )

    if published and investment_amount_rmb is None:
        return _provisional_from_band(
            budget_band,
            pending_flags=["amount_required"],
        )

    if published:
        return _provisional_from_band(
            budget_band,
            pending_flags=["thresholds_unavailable"],
        )

    return _provisional_from_band(
        budget_band,
        pending_flags=["amount_official"],
    )
