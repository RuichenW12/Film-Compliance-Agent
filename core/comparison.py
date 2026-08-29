"""What each budget level would cost you, before you have picked one.

At the idea stage a creator has no budget, and asking for one produces a worse
answer than not asking. The useful thing to give them is the other direction:
what each level *means*, so the thresholds become something to plan against
rather than a question they cannot answer.

Every column here is read out of the pinned snapshot. Nothing is estimated and
nothing is scored:

- the money boundaries come from `p3_tier_thresholds.threshold_sets.ai_generated`
- the authority, the pre-production filing duty and whether release is blocked
  come from `p4_process_templates.filing_routes`, which quote 总局令第16号
  articles 12, 13, 17 and 34
- "steps you do yourself" is counted from the process template for that class,
  taking the steps whose `owner` is the creator -- 5 of 7 for one-class, 3 of 5
  for two, 2 of 4 for three
- the statutory deadline comes from article 20, which gives twenty days for a
  one-class decision including ten for expert review. **Only one class has one.**
  Two-class has no stated deadline in the regulation and three-class is platform
  self-review, which is not an administrative approval at all, so those two say
  so rather than guessing.

That last point is the whole discipline of this module in miniature: a
comparison is only useful if the empty cells are honestly empty.
"""

from __future__ import annotations

from schemas.enums import Tier
from schemas.snapshot import PackName, SnapshotNotFoundError, SnapshotService

# The class each band lands in, and the bracket a creator would pick to say so.
# Ordered lightest first, which is the direction a budget grows.
BANDS: tuple[tuple[Tier, str], ...] = (
    (Tier.T3, "below_lower"),
    (Tier.T2, "between"),
    (Tier.T1, "at_or_above_upper"),
)

# Article 20 states a deadline for one-class decisions only. The other two are
# absent from the regulation rather than absent from our reading of it.
STATUTORY_DEADLINE_CLAUSE = "nrta-order-16-article-20"
DEADLINE_BY_TIER: dict[Tier, str | None] = {
    Tier.T1: "deadline.twenty_days_with_expert_review",
    Tier.T2: None,
    Tier.T3: None,
}


def _creator_steps(pack4: dict, template: str) -> tuple[int, int]:
    """(steps the creator does, steps in total) for one process template."""

    templates = (pack4 or {}).get("templates") or {}
    steps = (templates.get(template) or {}).get("steps") or []
    mine = [step for step in steps if step.get("owner") == "creator"]
    return len(mine), len(steps)


def budget_comparison(snapshots: SnapshotService, version: str) -> list[dict] | None:
    """One row per budget band, or None when the snapshot cannot support it.

    Returning None rather than a partial table is deliberate. A comparison with
    invented boundaries would be worse than no comparison, because a creator
    would plan a budget against it.
    """

    try:
        pack3 = snapshots.get_pack(PackName.P3_TIER_THRESHOLDS, version)
        pack4 = snapshots.get_pack(PackName.P4_PROCESS_TEMPLATES, version)
    except (SnapshotNotFoundError, KeyError):
        return None

    thresholds = ((pack3 or {}).get("threshold_sets") or {}).get("ai_generated") or {}
    lower = thresholds.get("T2_min_rmb")
    upper = thresholds.get("T1_min_rmb")
    if lower is None or upper is None:
        return None

    # Imported here rather than at module scope: `chain` imports this module's
    # sibling helpers, and a top-level import would close the cycle.
    from core.classify.chain import ROADMAP_TEMPLATE_BY_TIER, filing_route

    rows: list[dict] = []
    for tier, bracket in BANDS:
        route = filing_route(tier, snapshots, version)
        if route is None:
            # A band with no sourced route is not shown at all, for the same
            # reason `filing_route` itself returns None: an unsourced route is
            # a confident-looking answer we have no business giving.
            return None

        template = ROADMAP_TEMPLATE_BY_TIER.get(tier, "")
        yours, total = _creator_steps(pack4, template)

        deadline_key = DEADLINE_BY_TIER[tier]
        rows.append(
            {
                "tier": tier.value,
                "amount_bracket": bracket,
                "lower_rmb": lower,
                "upper_rmb": upper,
                "authority": route.get("authority"),
                "pre_shoot_filing": route.get("pre_shoot_filing"),
                "blocks_release": route.get("blocks_release_until_granted"),
                "steps_yours": yours,
                "steps_total": total,
                # None means the regulation states no deadline for this class,
                # which the interface renders as such. It does not mean fast.
                "statutory_deadline_key": deadline_key,
                "deadline_clause": (
                    STATUTORY_DEADLINE_CLAUSE if deadline_key else None
                ),
                "clause_refs": route.get("clause_refs") or [],
            }
        )
    return rows
