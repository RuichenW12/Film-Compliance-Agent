"""D1c TierJudge (TDD 4.5). Pure function, no LLM.

Amount thresholds for the 2026-09-01 regime are not published yet, so any tier
derived from a budget band is marked provisional and shown as "暂定/待官方".
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


def _thresholds_published(pack3: dict, snapshot_thresholds_published: bool | None) -> bool:
    if "official_published" in pack3:
        return bool(pack3["official_published"])
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


def judge_tier(
    budget_band: BudgetBand,
    pack3: dict,
    snapshot_thresholds_published: bool | None = None,
    investment_amount_rmb: float | None = None,
) -> TierDecision:
    thresholds = pack3.get("thresholds") or {}
    published = _thresholds_published(pack3, snapshot_thresholds_published)

    if published and investment_amount_rmb is not None:
        tier = _tier_from_amount(investment_amount_rmb, thresholds)
        if tier is not None:
            return TierDecision(
                tier=tier,
                tier_provisional=False,
                reasons=["tier.from_official_thresholds"],
            )

    if budget_band is BudgetBand.UNKNOWN:
        return TierDecision(
            tier=STRICTER_ASSUMPTION,
            tier_provisional=True,
            pending_flags=["budget_unknown", "amount_official"],
            reasons=["tier.assumed_stricter_pending_budget"],
            comparison_card=[
                {"tier": tier.value, "band": band.value}
                for band, tier in PROVISIONAL_BAND_TIER.items()
            ],
        )

    tier = PROVISIONAL_BAND_TIER[budget_band]
    if published:
        return TierDecision(
            tier=tier,
            tier_provisional=False,
            reasons=["tier.from_band_with_published_thresholds"],
        )
    return TierDecision(
        tier=tier,
        tier_provisional=True,
        pending_flags=["amount_official"],
        reasons=["tier.provisional_thresholds_unpublished"],
    )
