# Policy Snapshot v2 Real-Data Vertical Slice Design

**Date:** 2026-08-26

**Status:** Superseded for the remaining v2 data scope by
`2026-08-26-policy-snapshot-v2-complete-mock-design.md`. The exact-amount and
mode-specific tier runtime described here has already been implemented.

**Primary owner:** Richard (policy workstream)

**Shared consumer:** Maxine (product workflow)

## 1. Outcome

Deliver the first locally runnable, evidence-bound policy snapshot slice that
classifies both live-action and AI-generated micro-dramas by actual investment
amount and prevents filing-material cards from binding the wrong asset type.

This is not a generic policy rules engine and it is not Gate 5-b. It does not
provision GCS, Firestore, Pub/Sub, Cloud Run, or Scheduler resources.

The vertical path is:

```text
Wizard investment amount + generation mode
  -> IntentProfile
  -> D1c selects the live-action or AI threshold set
  -> Classification pinned to snapshot v2 and its evidence
  -> p4 roadmap (when sourced)
  -> p5 material cards (when sourced)
  -> each card binds only a matching asset kind
```

## 2. Constraints

1. Preserve `policy/seed-snapshot-v1.yaml` as an immutable handshake fixture.
2. A v2 candidate is opt-in through `SNAPSHOT_SEED_PATH`; it is not the default
   until Richard has reviewed the evidence and Maxine has verified consumption.
3. Missing data remains visible. Empty p4/p5 packs continue to produce pending
   states rather than invented workflows or filing requirements.
4. Special-subject classification takes precedence over amount classification.
5. A budget band without an exact amount never produces a final tier.
6. Government wording, partner operational rules, and model proposals remain
   distinguishable.
7. The implementation adds only the fields required by this vertical slice.

## 3. Effective-time boundary

The current date is 2026-08-26. The NRTA `Micro-drama Development Management
Measures` currently stored in v1 takes effect on 2026-09-01. Before that date,
v2 must not cite those clauses as if they were already effective.

Two different times are retained:

- `PolicySnapshot.effective_from`: when the reviewed snapshot becomes active in
  this product;
- `p3.threshold_sets.*.effective_from`: when the underlying threshold policy
  became effective.

The v2 top-level effective time is the actual review/activation time. It is not
backdated to a source policy's effective date. A future NRTA regime will be a
later snapshot rather than a mutation of v2.

## 4. Shared contract changes

### 4.1 Exact investment amount

Add the following optional field to both the API intake contract and the stored
intent profile:

```python
investment_amount_rmb: int | None = Field(default=None, ge=0)
```

The unit is whole RMB. The MVP does not add currencies, exchange rates, a money
object, or user-defined ranges.

Rules:

- an exact amount takes precedence over `budget_band`;
- without an exact amount, the result remains `tier_provisional=true`;
- with `is_ai_generated=None`, the result remains provisional and carries
  `generation_mode_required`, even when an amount exists;
- with a known mode and exact amount, D1c selects the matching threshold set;
- a special-subject hit remains final T1 regardless of amount.

The value must flow through:

- `api.dto.IntentRequest`;
- `schemas.project.IntentProfile`;
- the Wizard request;
- `WorkflowService.run_classification`;
- `WorkflowService.recalc_tier`;
- fact projection for user-confirmed intent values.

### 4.2 Material asset kind

Add one required value to every p5 material-card definition and to
`schemas.assets.MaterialCard`:

```yaml
material_cards:
  - material_id: mat_synopsis
    name_key: material.synopsis
    asset_kind: synopsis
    required: true
```

```python
asset_kind: AssetKind
```

Keep the existing asset kinds and add exactly one administrative-document kind:

```text
synopsis
script
prompts
final_film
subtitle_sheet
supporting_document
```

One card accepts one kind. The MVP does not add `allowed_asset_kinds`, MIME
constraints, file-size constraints, or conditional expressions.

The backend rejects a mismatched attachment with HTTP 422 and leaves the card
unchanged. The collection UI selects the latest asset matching each card's
`asset_kind`; it no longer offers the latest script to every card.

### 4.3 Evidence selection from packs

The current classification chain hard-codes future NRTA clause IDs for form and
tier evidence. V2 data cannot be honest while the consumer ignores its evidence
mapping.

Add a single `clause_ref` string where the consumer needs it:

- `p1_form_definition.clause_ref`;
- `p2_subject_rules.subject_rules[].clause_ref` (already supported);
- `p3_tier_thresholds.threshold_sets.*.clause_ref`.

D1a/D1c use these selected references when assembling the classification. V1
retains its existing fallback behavior; v2 must provide the references.

No generic evidence expression or multi-clause graph is introduced.

## 5. Snapshot v2 pack content

V2 is a real-data first slice, not a claim that every pack is complete.

| Pack | V2 content | Readiness |
| --- | --- | --- |
| p1 | Current effective micro-drama definition and its source | Source required |
| p2 | Nine special-subject categories, using only partner-confirmed wording | Can be structured now |
| p3 | Live-action and AI amount thresholds | Can be implemented now |
| p4 | Filing steps, order, owner, and published duration | Await guide/partner material |
| p5 | Actual form fields and required material cards | Await form/submitted sample |
| p6 | Only clauses referenced by p1/p2/p3/p5 | Added with each verified pack |

### 5.1 Tier thresholds

```yaml
p3_tier_thresholds:
  thresholds_published: true
  threshold_sets:
    live_action:
      effective_from: "2026-01-01T00:00:00+08:00"
      T1_min_rmb: 3000000
      T2_min_rmb: 1000000
      clause_ref: tier-live-action-2026
    ai_generated:
      effective_from: "2026-07-01T00:00:00+08:00"
      T1_min_rmb: 800000
      T2_min_rmb: 300000
      clause_ref: tier-ai-generated-2026
```

Candidate source pages:

- live-action threshold government republication:
  `https://whhlyj.baoji.gov.cn/zzzb/xygl/202601/t20260115_1240723.html`;
- AI threshold government republication:
  `https://wxb.xzdw.gov.cn/wlcb/cbgz/202606/t20260626_680352.html`.

The raw page, normalized text, retrieval time, and hash must be retained by the
existing policy-source pipeline before Richard marks the data reviewed.

### 5.2 Special-subject rules

V2 replaces synthesized placeholder keywords with explicit rule entries.

- If partners have confirmed only category names, literal trigger patterns are
  limited to those category names.
- Synonyms and scenario phrases are not invented by code.
- Unreviewed entries keep `expert_pending=true`.
- Gemini may propose a candidate semantic hit, but it cannot promote an
  unreviewed rule into a deterministic compliance conclusion.

### 5.3 Process and form packs

Until an official provincial guide, form template, or partner-submitted filing
package is available, keep these packs visibly empty:

```yaml
p4_process_templates:
  templates: {}

p5_form_templates:
  required_facts: []
  material_cards: []
```

When source material arrives:

- omit `est_weeks` unless a source publishes a duration;
- set `required=true` only when the form/guide clearly requires the item;
- leave `why_clause_id` empty when no legal clause supports the requirement;
- point `template_uri` to the official template where one exists;
- map each material card to one `asset_kind`;
- label a provincial procedure by its real jurisdiction rather than presenting
  it as a national process.

## 6. Classification behavior

```text
special subject hit
  -> T1, final, co-review required

otherwise, generation mode missing
  -> provisional, generation_mode_required

otherwise, exact amount missing
  -> budget-band comparison only, provisional, amount_required

otherwise, live-action
  -> live_action threshold set -> final T1/T2/T3

otherwise, AI-generated
  -> ai_generated threshold set -> final T1/T2/T3
```

If the selected threshold set is absent, malformed, or not marked published,
classification falls back to a provisional result. It must not silently use the
other generation mode's thresholds.

## 7. Failure behavior

- Source fetch failure leaves the active snapshot unchanged.
- Invalid Gemini proposal output does not update any pack.
- An incomplete v2 candidate is not made the default.
- Missing amount or generation mode is surfaced as a pending field.
- Mismatched material assets are rejected before card mutation.
- Empty p4/p5 data remains visible through existing pending behavior.
- A shared-contract conflict with Maxine pauses that code seam; Richard can
  continue source collection and pack drafting independently.

## 8. TDD and verification

### 8.1 Contract tests

- exact amount accepts zero and positive integers, rejects negative values;
- `MaterialCard.asset_kind` is required and rejects unknown values;
- `supporting_document` is mirrored in Python and TypeScript enums;
- the v2 candidate validates all six packs;
- top-level and p3 `thresholds_published` values agree.

### 8.2 Tier boundary tests

Live-action:

- 2,999,999 -> T2;
- 3,000,000 -> T1;
- 999,999 -> T3;
- 1,000,000 -> T2.

AI-generated:

- 799,999 -> T2;
- 800,000 -> T1;
- 299,999 -> T3;
- 300,000 -> T2.

Protection cases:

- no amount -> provisional;
- no generation mode -> provisional;
- published thresholds plus only a budget band -> provisional;
- same amount may produce different live-action and AI tiers;
- a low-investment special subject remains T1;
- evidence points to the selected threshold set's `clause_ref`.

### 8.3 Material tests

- synopsis card + synopsis asset succeeds;
- synopsis card + script asset returns 422;
- a rejected attachment does not change card state;
- the UI offers the newest matching asset for each card;
- independent asset kinds retain independent version chains.

### 8.4 Local end-to-end cases

1. Live-action, general subject, RMB 1,500,000 -> final T2 with live-action
   threshold evidence.
2. AI-generated, general subject, RMB 500,000 -> final T2 with AI threshold
   evidence.
3. Same amount in the two modes -> mode-specific results.
4. Low-investment special subject -> final T1 with co-review.

Run v2 explicitly:

```bash
SNAPSHOT_SEED_PATH=policy/seed-snapshot-v2.yaml \
  uvicorn api.main:app --reload
```

The acceptance suite must verify that the response records
`policy_snapshot_version=v2`.

### 8.5 Completion gate

- Python tests pass;
- frontend tests and production build pass;
- all amount boundaries pass;
- missing inputs never produce a final tier;
- material-kind enforcement works in API and UI;
- v1 is unchanged;
- v2 runs through local API and UI when selected explicitly;
- no cloud resource is required.

## 9. Delivery sequence

1. Synchronize from the latest `origin/main` in an isolated worktree.
2. Land the shared contract and failing tests first.
3. Implement amount propagation and mode-specific D1c selection.
4. Implement material-kind validation and matching UI behavior.
5. Add evidence references to p1/p3 consumption.
6. Add the reviewed p3/p6 v2 data and explicit p2 entries.
7. Keep p4/p5 empty until the original guide/form arrives.
8. Run focused, full backend, frontend, and build verification.
9. Ask Maxine to review the shared seams and consume v2 locally.
10. Switch the default seed only after both owners approve.

Separate shared-code and policy-data commits so either can be reviewed or
reverted without rewriting the other.

## 10. Non-goals

- Gate 5-b event delivery or cloud deployment;
- direct government filing;
- a multi-jurisdiction policy expression engine;
- currencies or exchange-rate conversion;
- inferred filing durations, contacts, or mandatory documents;
- automatic promotion of Gemini output to reviewed policy;
- treating the 2026-09-01 NRTA measures as currently effective before that
  date.
