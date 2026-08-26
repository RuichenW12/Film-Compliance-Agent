# Policy Tier Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the product accept an exact RMB investment amount and safely classify live-action versus AI-generated micro-dramas from a published, evidence-mapped p3 threshold pack.

**Architecture:** Keep policy data inside `p3_tier_thresholds` and keep D1c pure. The intake aggregate owns the amount and generation mode, the classification chain passes those values to D1c, and D1c returns the selected clause reference with its tier decision. A published flag without usable thresholds remains provisional; no static v2 seed is activated in this plan because the current-effective p1 source still requires review.

**Tech Stack:** Python 3.11+, Pydantic v2, FastAPI, pytest, React 19, Next.js 16, TypeScript, Vitest, Testing Library.

---

## Scope boundary

This is Plan A of the approved vertical-slice design. It covers the tier path:

```text
Intent request -> stored exact amount -> D1c mode selection
-> final/provisional tier -> selected evidence -> Wizard request
```

The independent `MaterialCard.asset_kind` change is Plan B and is not mixed
into these commits. A real `seed-snapshot-v2.yaml` activation is also separate:
the runtime built here is tested with explicit packs, while the active seed
continues to be v1 until current-effective p1 evidence is reviewed.

## File map

- `schemas/project.py`: owns the stored `IntentProfile` amount.
- `api/dto.py`: owns request validation for the optional exact amount.
- `core/classify/d1c.py`: selects a threshold set and returns a tier decision.
- `core/classify/chain.py`: passes intent values to D1c and maps selected policy
  evidence into `Classification`.
- `core/workflow_service.py`: reruns D1c with stored intent during policy recalc.
- `tests/test_api_intake.py`: proves API validation and persistence.
- `tests/test_classify.py`: proves exact amount boundaries and provisional rules.
- `tests/test_app_policy_snapshot_bridge.py`: proves a flag-only publication
  cannot turn a provisional tier into a final tier.
- `web/app/wizard/page.tsx`: collects and submits the exact amount.
- `web/locales/en.json`, `web/locales/zh.json`: label and pending-state copy.
- `web/tests/wizard-page.test.tsx`: proves the browser request contract.
- `docs/decisions.md`: records the shared runtime decision.

### Task 1: Add the exact-amount API contract

**Files:**
- Modify: `tests/test_api_intake.py`
- Modify: `schemas/project.py:16-35`
- Modify: `api/dto.py:27-40`

- [ ] **Step 1: Write failing API persistence and validation tests**

Add these tests to `tests/test_api_intake.py`:

```python
def test_intent_accepts_and_persists_exact_investment_amount(client):
    project_id = create_project(client)
    response = client.post(
        f"/v1/projects/{project_id}/intent",
        json={**ROMANCE_INTENT, "investment_amount_rmb": 1_500_000},
    )

    assert response.status_code == 200
    project = client.get(f"/v1/projects/{project_id}").json()["project"]
    assert project["intent_profile"]["investment_amount_rmb"] == 1_500_000


def test_intent_rejects_a_negative_exact_investment_amount(client):
    project_id = create_project(client)
    response = client.post(
        f"/v1/projects/{project_id}/intent",
        json={**ROMANCE_INTENT, "investment_amount_rmb": -1},
    )

    assert response.status_code == 422
    errors = response.json()["error"]["details"]["errors"]
    assert errors[0]["loc"][-1] == "investment_amount_rmb"
    assert errors[0]["type"] == "greater_than_equal"
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
/Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/python -m pytest \
  tests/test_api_intake.py::test_intent_accepts_and_persists_exact_investment_amount \
  tests/test_api_intake.py::test_intent_rejects_a_negative_exact_investment_amount -q
```

Expected: both fail because `IntentRequest` forbids the unknown field; the first
returns 422 and the second reports `extra_forbidden`, not `greater_than_equal`.

- [ ] **Step 3: Add the minimal shared fields**

In `schemas/project.py`, add to `IntentProfile` after `budget_band`:

```python
investment_amount_rmb: int | None = Field(default=None, ge=0)
```

In `api/dto.py`, add to `IntentRequest` after `budget_band`:

```python
investment_amount_rmb: int | None = Field(default=None, ge=0)
```

No currency object, decimals, or range type is added.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the Step 2 command again.

Expected: `2 passed`.

- [ ] **Step 5: Run the intake regression file**

Run:

```bash
/Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/python -m pytest \
  tests/test_api_intake.py -q
```

Expected: all intake tests pass.

- [ ] **Step 6: Commit the contract**

```bash
git add schemas/project.py api/dto.py tests/test_api_intake.py
git commit -m "feat: accept exact investment amount"
```

### Task 2: Select live-action and AI threshold sets in D1c

**Files:**
- Modify: `tests/test_classify.py`
- Modify: `core/classify/d1c.py`

- [ ] **Step 1: Write the failing boundary and missing-input tests**

Add this pack and tests to `tests/test_classify.py`:

```python
PUBLISHED_THRESHOLD_PACK = {
    "thresholds_published": True,
    "threshold_sets": {
        "live_action": {
            "effective_from": "2026-01-01T00:00:00+08:00",
            "T1_min_rmb": 3_000_000,
            "T2_min_rmb": 1_000_000,
            "clause_ref": "tier-live-action-2026",
        },
        "ai_generated": {
            "effective_from": "2026-07-01T00:00:00+08:00",
            "T1_min_rmb": 800_000,
            "T2_min_rmb": 300_000,
            "clause_ref": "tier-ai-generated-2026",
        },
    },
}


@pytest.mark.parametrize(
    ("is_ai_generated", "amount", "expected"),
    [
        (False, 2_999_999, Tier.T2),
        (False, 3_000_000, Tier.T1),
        (False, 999_999, Tier.T3),
        (False, 1_000_000, Tier.T2),
        (True, 799_999, Tier.T2),
        (True, 800_000, Tier.T1),
        (True, 299_999, Tier.T3),
        (True, 300_000, Tier.T2),
    ],
)
def test_published_threshold_sets_use_mode_and_exact_amount(
    is_ai_generated, amount, expected
):
    decision = judge_tier(
        BudgetBand.UNKNOWN,
        PUBLISHED_THRESHOLD_PACK,
        True,
        investment_amount_rmb=amount,
        is_ai_generated=is_ai_generated,
    )

    assert decision.tier is expected
    assert decision.tier_provisional is False
    expected_clause = (
        "tier-ai-generated-2026"
        if is_ai_generated
        else "tier-live-action-2026"
    )
    assert decision.clause_ref == expected_clause


def test_exact_amount_without_generation_mode_stays_provisional():
    decision = judge_tier(
        BudgetBand.BAND_B,
        PUBLISHED_THRESHOLD_PACK,
        True,
        investment_amount_rmb=1_500_000,
        is_ai_generated=None,
    )

    assert decision.tier_provisional is True
    assert "generation_mode_required" in decision.pending_flags
    assert decision.clause_ref is None


def test_published_thresholds_without_exact_amount_stay_provisional():
    decision = judge_tier(
        BudgetBand.BAND_C,
        PUBLISHED_THRESHOLD_PACK,
        True,
        investment_amount_rmb=None,
        is_ai_generated=False,
    )

    assert decision.tier is Tier.T3
    assert decision.tier_provisional is True
    assert "amount_required" in decision.pending_flags


def test_published_flag_without_usable_thresholds_stays_provisional():
    decision = judge_tier(
        BudgetBand.BAND_C,
        {"thresholds_published": True},
        True,
        investment_amount_rmb=1_500_000,
        is_ai_generated=False,
    )

    assert decision.tier is Tier.T3
    assert decision.tier_provisional is True
    assert "thresholds_unavailable" in decision.pending_flags


def test_same_amount_can_land_in_different_mode_specific_tiers():
    live = judge_tier(
        BudgetBand.UNKNOWN,
        PUBLISHED_THRESHOLD_PACK,
        True,
        investment_amount_rmb=500_000,
        is_ai_generated=False,
    )
    ai = judge_tier(
        BudgetBand.UNKNOWN,
        PUBLISHED_THRESHOLD_PACK,
        True,
        investment_amount_rmb=500_000,
        is_ai_generated=True,
    )

    assert live.tier is Tier.T3
    assert ai.tier is Tier.T2
```

Update the existing `test_published_thresholds_make_the_tier_final` call to
pass `is_ai_generated=False`; keep its legacy flat-pack assertion as a v1
compatibility check.

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
/Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/python -m pytest \
  tests/test_classify.py -q
```

Expected: failures show that `judge_tier` does not accept
`is_ai_generated`, `TierDecision` has no `clause_ref`, and a flag-only pack is
incorrectly made final from its budget band.

- [ ] **Step 3: Extend `TierDecision` and add small helpers**

In `core/classify/d1c.py`, extend `TierDecision`:

```python
clause_ref: str | None = None
```

Add:

```python
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


def _thresholds_for_mode(pack3: dict, is_ai_generated: bool) -> dict:
    sets = pack3.get("threshold_sets") or {}
    if sets:
        key = "ai_generated" if is_ai_generated else "live_action"
        return sets.get(key) or {}
    return pack3.get("thresholds") or {}
```

- [ ] **Step 4: Implement the minimal decision order**

Extend `judge_tier` with:

```python
is_ai_generated: bool | None = None,
```

Use this order:

```python
published = _thresholds_published(pack3, snapshot_thresholds_published)

if is_ai_generated is None:
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

if published and not thresholds:
    return _provisional_from_band(
        budget_band,
        pending_flags=["thresholds_unavailable"],
    )
```

Retain the existing unpublished-threshold fallback, routed through
`_provisional_from_band(..., pending_flags=["amount_official"])`.

- [ ] **Step 5: Run classifier tests and verify GREEN**

Run the Step 2 command again.

Expected: all `tests/test_classify.py` tests pass.

- [ ] **Step 6: Commit D1c**

```bash
git add core/classify/d1c.py tests/test_classify.py
git commit -m "feat: select tier thresholds by generation mode"
```

### Task 3: Propagate stored intent and pack-selected evidence

**Files:**
- Modify: `tests/test_classify.py`
- Create: `tests/test_tier_recalc.py`
- Modify: `core/classify/chain.py`
- Modify: `core/workflow_service.py`

- [ ] **Step 1: Write a failing chain-level evidence test**

Import `EvidenceRef`, `PackName`, and `SnapshotService`, then add this test double
to `tests/test_classify.py`:

```python
class ThresholdSnapshots(SnapshotService):
    def __init__(self, base: SnapshotService) -> None:
        self._base = base

    def latest_version(self, as_of=None) -> str:
        return "v2"

    def get_pack(self, name: PackName, version: str | None = None) -> dict:
        if PackName(name) is PackName.P3_TIER_THRESHOLDS:
            return dict(PUBLISHED_THRESHOLD_PACK)
        return self._base.get_pack(name, "v1")

    def clause(self, clause_id: str, version: str):
        return self._base.clause(clause_id, "v1")
```

Add:

```python
def test_chain_reads_amount_and_mode_from_intent_and_uses_selected_evidence(
    intent_romance, channels, snapshots
):
    threshold_snapshots = ThresholdSnapshots(snapshots)
    intent = intent_romance.model_copy(
        update={"investment_amount_rmb": 1_500_000, "is_ai_generated": False}
    )

    outcome = classify(intent, channels, threshold_snapshots)

    assert outcome.classification.tier is Tier.T2
    assert outcome.classification.tier_provisional is False
    assert outcome.classification.evidence_refs == [
        EvidenceRef(
            snapshot_version="v2",
            clause_id="tier-live-action-2026",
        )
    ]


def test_special_subject_still_overrides_a_low_exact_amount(
    intent_crime, channels, snapshots
):
    threshold_snapshots = ThresholdSnapshots(snapshots)
    intent = intent_crime.model_copy(
        update={"investment_amount_rmb": 1, "is_ai_generated": True}
    )

    outcome = classify(intent, channels, threshold_snapshots)

    assert outcome.classification.tier is Tier.T1
    assert outcome.classification.special_subject_hit is True
    assert outcome.classification.co_review_required is True
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
/Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/python -m pytest \
  tests/test_classify.py::test_chain_reads_amount_and_mode_from_intent_and_uses_selected_evidence -q
```

Expected: the chain does not read the stored exact amount/mode and still emits
the hard-coded `nrta-order-16-article-5` evidence.

- [ ] **Step 3: Make the chain own propagation**

In `core/classify/chain.py`, remove the separate
`investment_amount_rmb` parameter from `classify`. Change the D1c call to:

```python
tier_decision = judge_tier(
    intent.budget_band,
    pack3,
    thresholds_published,
    investment_amount_rmb=intent.investment_amount_rmb,
    is_ai_generated=intent.is_ai_generated,
)
```

Build amount evidence with:

```python
tier_clause_id = tier_decision.clause_ref or TIER_CLAUSE_ID
```

and use `tier_clause_id` in the final `EvidenceRef`.

For form/exit evidence, select:

```python
form_clause_id = str(pack1.get("clause_ref") or FORM_CLAUSE_ID)
```

before constructing the form `EvidenceRef`. This preserves v1 while allowing a
reviewed pack to replace the future hard-coded clause.

- [ ] **Step 4: Pass stored intent during recalculation**

In `WorkflowService.recalc_tier`, change the D1c call to:

```python
decision = judge_tier(
    project.intent_profile.budget_band,
    pack3,
    self._thresholds_published(snapshot_version),
    investment_amount_rmb=project.intent_profile.investment_amount_rmb,
    is_ai_generated=project.intent_profile.is_ai_generated,
)
```

When `decision.clause_ref` is present, replace amount-tier evidence with:

```python
"evidence_refs": [
    EvidenceRef(
        snapshot_version=snapshot_version,
        clause_id=decision.clause_ref,
    )
],
```

Import `EvidenceRef` from `schemas.common`. Do not alter frozen-project guards.

- [ ] **Step 5: Write a real repository-backed recalc test**

Create `tests/test_tier_recalc.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

import yaml

from core.clock import FixedClock
from core.llm import UnavailableLLM
from core.workflow_service import WorkflowService
from schemas.enums import BudgetBand, ClaimedFormType, Tier
from schemas.policy_snapshot import PackName, PolicyPacks, PolicySnapshot
from store.memory import InMemoryStores
from workers.policy.adapters.repository_snapshot import RepositorySnapshotService
from workers.policy.repository import InMemoryPolicyRepository

ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)


def test_recalc_uses_stored_amount_mode_and_selected_evidence():
    raw = yaml.safe_load(
        (ROOT / "policy" / "seed-snapshot-v1.yaml").read_text(encoding="utf-8")
    )
    seed = PolicySnapshot.model_validate(raw)
    repository = InMemoryPolicyRepository()
    repository.put_snapshot(seed)
    snapshots = RepositorySnapshotService(repository)
    workflow = WorkflowService(
        InMemoryStores(), snapshots, FixedClock(NOW), UnavailableLLM()
    )

    project = workflow.create_project("u_owner", "Exact amount")
    workflow.submit_intent(
        project.project_id,
        {
            "form_type_claimed": ClaimedFormType.MICRO_DRAMA,
            "logline": "A general workplace romance.",
            "episode_count": 30,
            "episode_minutes": 2,
            "budget_band": BudgetBand.BAND_C,
            "investment_amount_rmb": 1_500_000,
            "is_ai_generated": False,
        },
    )
    project, _ = workflow.run_classification(project.project_id)
    assert project.classification.tier_provisional is True

    packs = seed.packs.model_dump(mode="python")
    packs[PackName.P3_TIER_THRESHOLDS.value] = {
        "thresholds_published": True,
        "threshold_sets": {
            "live_action": {
                "effective_from": "2026-01-01T00:00:00+08:00",
                "T1_min_rmb": 3_000_000,
                "T2_min_rmb": 1_000_000,
                "clause_ref": "tier-live-action-2026",
            },
            "ai_generated": {
                "effective_from": "2026-07-01T00:00:00+08:00",
                "T1_min_rmb": 800_000,
                "T2_min_rmb": 300_000,
                "clause_ref": "tier-ai-generated-2026",
            },
        },
    }
    legal = dict(packs[PackName.P6_LEGAL_CLAUSES.value])
    legal["clauses"] = [
        *legal.get("clauses", []),
        {
            "clause_id": "tier-live-action-2026",
            "title": "2026 live-action micro-drama thresholds",
            "text": "T1 starts at RMB 3,000,000 and T2 starts at RMB 1,000,000.",
            "source_url": "https://whhlyj.baoji.gov.cn/zzzb/xygl/202601/t20260115_1240723.html",
        },
        {
            "clause_id": "tier-ai-generated-2026",
            "title": "2026 AI-generated micro-drama thresholds",
            "text": "T1 starts at RMB 800,000 and T2 starts at RMB 300,000.",
            "source_url": "https://wxb.xzdw.gov.cn/wlcb/cbgz/202606/t20260626_680352.html",
        },
    ]
    packs[PackName.P6_LEGAL_CLAUSES.value] = legal
    data = seed.model_dump(mode="python")
    data.update(
        version="v2",
        published_at=NOW,
        effective_from=NOW,
        published_by="admin_richard",
        packs=PolicyPacks.model_validate(packs),
        thresholds_published=True,
    )
    repository.put_snapshot(PolicySnapshot.model_validate(data))

    result = workflow.recalc_tier(project.project_id, "v2")
    updated = workflow.get_project(project.project_id)

    assert result.tier is Tier.T2
    assert result.tier_provisional is False
    assert result.changed is True
    assert updated.classification.policy_snapshot_version == "v2"
    assert updated.classification.evidence_refs[0].clause_id == "tier-live-action-2026"
```

- [ ] **Step 6: Run the recalc test and verify RED**

Run:

```bash
/Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/python -m pytest \
  tests/test_tier_recalc.py -q
```

Expected: the recalculation ignores stored exact amount/mode and does not replace
the selected evidence.

- [ ] **Step 7: Verify chain and workflow tests**

Run:

```bash
/Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/python -m pytest \
  tests/test_classify.py tests/test_tier_recalc.py \
  tests/test_api_intake.py tests/test_notifications.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit propagation and evidence**

```bash
git add core/classify/chain.py core/workflow_service.py tests/test_classify.py tests/test_tier_recalc.py
git commit -m "feat: propagate exact amount into tier classification"
```

### Task 4: Keep flag-only publications provisional and project the amount fact

**Files:**
- Modify: `tests/test_app_policy_snapshot_bridge.py`
- Modify: `tests/test_api_intake.py`
- Modify: `core/classify/chain.py`

- [ ] **Step 1: Change the bridge requirement before implementation**

Add `"investment_amount_rmb": 1_500_000` to `ROMANCE_INTENT` in
`tests/test_app_policy_snapshot_bridge.py`. Change the post-publication
expectations to:

```python
assert recalculated.json() == {
    "tier": "T3",
    "tier_provisional": True,
    "changed": False,
}

classification = project.json()["project"]["classification"]
assert classification["policy_snapshot_version"] == "v2"
assert classification["tier_provisional"] is True
```

This test states that `thresholds_published=true` without threshold values is
not enough evidence for a final tier.

Add to `tests/test_api_intake.py`:

```python
def test_classification_projects_exact_amount_as_a_user_answer_fact(client):
    project_id = create_project(client)
    client.post(
        f"/v1/projects/{project_id}/intent",
        json={**ROMANCE_INTENT, "investment_amount_rmb": 1_500_000},
    )
    client.post(f"/v1/projects/{project_id}/classify")

    facts = client.get(f"/v1/projects/{project_id}/facts").json()
    amount = next(fact for fact in facts if fact["key"] == "investment_amount_rmb")
    assert amount["value"] == 1_500_000
    assert amount["source_ref"]["answer_id"] == "intent.investment_amount_rmb"
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
/Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/python -m pytest \
  tests/test_app_policy_snapshot_bridge.py \
  tests/test_api_intake.py::test_classification_projects_exact_amount_as_a_user_answer_fact -q
```

Expected: the bridge old behavior becomes final, and the amount fact is absent.

- [ ] **Step 3: Project the exact amount as an evidence-backed user answer**

In `_intent_facts` in `core/classify/chain.py`, append:

```python
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
```

No generated or inferred amount is stored.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the Step 2 command again.

Expected: all focused tests pass.

- [ ] **Step 5: Commit the safety regression**

```bash
git add core/classify/chain.py tests/test_app_policy_snapshot_bridge.py tests/test_api_intake.py
git commit -m "fix: keep incomplete threshold publications provisional"
```

### Task 5: Add the exact amount to the Wizard

**Files:**
- Create: `web/tests/wizard-page.test.tsx`
- Modify: `web/app/wizard/page.tsx`
- Modify: `web/locales/en.json`
- Modify: `web/locales/zh.json`

- [ ] **Step 1: Write the failing browser contract test**

Create `web/tests/wizard-page.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import WizardPage from "@/app/wizard/page";

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("WizardPage", () => {
  it("submits an exact RMB investment amount", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json({ project_id: "proj_001", state: "DRAFT" }))
      .mockResolvedValueOnce(json({ state: "INTAKE_DONE", missing: [] }))
      .mockResolvedValueOnce(json({ tracks_enabled: { china: true, us: false } }))
      .mockResolvedValueOnce(
        json({
          classification: {
            form_type: "micro_drama",
            tier: "T2",
            tier_provisional: false,
            special_subject_hit: false,
            co_review_required: false,
            matched_rules: [],
            policy_snapshot_version: "v2",
            pending_flags: [],
            evidence_refs: []
          },
          exit: null,
          roadmap_preview: { template: "T2_5steps" },
          state: "CLASSIFIED"
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(<WizardPage />);
    await user.type(screen.getByLabelText("Logline"), "A workplace romance.");
    await user.type(screen.getByLabelText("Investment amount (RMB)"), "1500000");
    await user.click(screen.getByRole("button", { name: "Run classification" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    const intent = JSON.parse(String(fetchMock.mock.calls[1][1]?.body));
    expect(intent.investment_amount_rmb).toBe(1_500_000);
  });
});
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
cd web
NODE_OPTIONS=--localstorage-file=/tmp/codex-film-compliance-vitest-localstorage.json \
  npm test -- tests/wizard-page.test.tsx
```

Expected: Testing Library cannot find `Investment amount (RMB)`.

- [ ] **Step 3: Add the minimal Wizard input and request field**

In `WizardPage`, add:

```tsx
const [investmentAmount, setInvestmentAmount] = useState("");
```

Add the field after budget band:

```tsx
<label>
  <span>{t("wizard.investment_amount_rmb")}</span>
  <input
    type="number"
    min={0}
    step={1}
    value={investmentAmount}
    onChange={(event) => setInvestmentAmount(event.target.value)}
  />
</label>
```

Add to the intent request body:

```tsx
...(investmentAmount === ""
  ? {}
  : { investment_amount_rmb: Number(investmentAmount) })
```

Add locale entries:

```json
"wizard.investment_amount_rmb": "Investment amount (RMB)"
```

and:

```json
"wizard.investment_amount_rmb": "实际投资金额（人民币元）"
```

Also replace the now-inaccurate provisional badge copy:

```json
"classification.provisional": "Provisional (exact amount, generation mode, or usable threshold data is still required)"
```

and:

```json
"classification.provisional": "暂定（仍需实际金额、生成方式或可用门槛数据）"
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the Step 2 command again.

Expected: `1 passed`.

- [ ] **Step 5: Run frontend tests and typecheck**

Run:

```bash
NODE_OPTIONS=--localstorage-file=/tmp/codex-film-compliance-vitest-localstorage.json npm test
npm run typecheck
```

Expected: all tests pass and TypeScript exits 0.

- [ ] **Step 6: Commit the Wizard change**

```bash
git add web/app/wizard/page.tsx web/locales/en.json web/locales/zh.json web/tests/wizard-page.test.tsx
git commit -m "feat: collect exact investment amount in wizard"
```

### Task 6: Record the decision and run the tier-runtime completion gate

**Files:**
- Modify: `docs/decisions.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Append the shared decision**

Add this row to the decision table:

```markdown
| [D-026](#d-026) | Shared | Final amount tiers require amount, mode, and usable thresholds | Accepted |
```

Append this section to `docs/decisions.md`:

```markdown
## D-026

**A final amount tier requires an exact amount, a known generation mode, and a
usable published threshold set** · Area: Shared · Status: Accepted · 2026-08-26

`budget_band` remains a provisional comparison aid. `thresholds_published=true`
does not make a result final when the selected threshold set or exact amount is
missing. D1c selects `live_action` or `ai_generated` from the stored intent and
returns the selected pack evidence; it never falls through to the other mode.
```

Add this section immediately below the `## 2026-08-26` heading in
`CHANGELOG.md`:

```markdown
### Shared — exact-amount, mode-specific tier runtime

- Intake and the Wizard now accept `investment_amount_rmb` as an optional,
  non-negative whole-RMB value.
- D1c selects `live_action` or `ai_generated` threshold data from the pinned p3
  pack. A missing amount, missing generation mode, or flag-only publication
  remains provisional ([D-026](docs/decisions.md#d-026)).
- Final amount tiers and recalculation carry the selected pack `clause_ref`
  instead of always citing the hard-coded future NRTA article.
- This changes the shared intake and policy-pack seam. It does not activate a
  static v2 seed or change Gate 5-b.
```

- [ ] **Step 2: Run formatting checks**

```bash
git diff --check
```

Expected: exit 0.

- [ ] **Step 3: Run the complete backend suite**

```bash
/Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/python -m pytest
```

Expected: all tests pass; cloud-prerequisite tests may remain skipped.

- [ ] **Step 4: Run complete frontend verification**

```bash
cd web
NODE_OPTIONS=--localstorage-file=/tmp/codex-film-compliance-vitest-localstorage.json npm test
npm run typecheck
npm run build
```

Expected: tests, typecheck, and production build all exit 0.

- [ ] **Step 5: Verify the branch contains only intended changes**

```bash
git status --short
git diff --name-only origin/main...HEAD
git diff --check origin/main...HEAD
```

Expected: only the tier-runtime code, tests, documentation, and the approved
design/plan files are present.

- [ ] **Step 6: Commit documentation**

```bash
git add docs/decisions.md CHANGELOG.md docs/superpowers/plans/2026-08-26-policy-tier-runtime.md
git commit -m "docs: record exact-amount tier runtime"
```

## Follow-on plans

1. `MaterialCard.asset_kind` contract, backend attachment validation, and UI
   matching behavior.
2. Real policy-data activation: current-effective p1 evidence, reviewed p2
   entries, p3/p6 sources, and opt-in `seed-snapshot-v2.yaml`.
3. If p5 later changes `required_facts`, decide whether fact-extraction job
   idempotency includes snapshot version or uses an explicit re-extract task.
