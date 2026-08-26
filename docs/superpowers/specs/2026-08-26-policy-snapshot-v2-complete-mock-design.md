# Complete Mock Policy Snapshot v2 Design

**Date:** 2026-08-26

**Status:** Approved for implementation planning

**Primary owner:** Richard (policy workstream)

**Shared consumer:** Maxine (product workflow)

**Supersedes:** The opt-in, p4/p5-empty remainder of
`2026-08-26-policy-snapshot-v2-real-data-design.md`. The already-implemented
exact-amount and mode-specific tier runtime remains in force.

## 1. Outcome

Provide one structurally complete policy snapshot v2 for local integration of
the China domestic micro-drama workflow. It covers T1, T2, and T3 for both
live-action and AI-generated projects and supplies all six packs so Maxine can
exercise classification, roadmap, materials, form preparation, and the D3 gate.

The data is integration data, not a legal conclusion. It may produce a final
business result such as `tier_provisional=false`, but every consumer must also
see `verification_status=mock_verified` and a non-dismissible “integration data”
label.

This design does not cover overseas policy tracks, cloud provisioning, Gate
5-b, or a generic rules language.

## 2. Locked decisions

1. Local unified development starts from v2 by default. The v1 seed remains a
   regression and compatibility fixture.
2. A mock v2 may drive final tiers and the complete workflow.
3. Policy confidence is separate from computational completeness.
4. Verification is snapshot-wide, not per pack. A snapshot is either
   `mock_verified` or `human_verified`.
5. All p1-p6 packs are populated for the China domestic path.
6. Missing inputs still remain missing. Mock policy never invents an amount,
   generation mode, fact, asset, or human decision.
7. An invalid v2 stops startup; the app never silently falls back to v1.

## 3. Verification contract

Add a two-value shared enum and a field on `PolicySnapshot`:

```python
class VerificationStatus(StrEnum):
    MOCK_VERIFIED = "mock_verified"
    HUMAN_VERIFIED = "human_verified"

class PolicySnapshot(...):
    verification_status: VerificationStatus = VerificationStatus.MOCK_VERIFIED
```

The conservative default preserves existing serialized snapshots and treats
an omitted value as mock, never human-reviewed.

`SnapshotService` adds one read operation:

```python
def verification_status(self, version: str) -> VerificationStatus: ...
```

Both the file and repository adapters implement it. Classification persists
the selected snapshot version and its verification status together. Existing
classification records without the field also default to `mock_verified`.

The two status dimensions are intentionally independent:

```text
tier_provisional=false + verification_status=mock_verified
```

means the inputs and threshold calculation are complete, while the policy data
is still integration-only. `tier_provisional` must not be overloaded to carry
legal confidence.

## 4. Default loading and pinning

Add `policy/seed-snapshot-v2.yaml` and make it the local default. Preserve
`policy/seed-snapshot-v1.yaml` byte-for-byte as the explicit v1 fixture.

The unified app currently hard-codes v1 while building its process-local policy
repository. Change that composition boundary so it reads the configured seed
path, whose default becomes v2. `SNAPSHOT_SEED_PATH=policy/seed-snapshot-v1.yaml`
remains the explicit compatibility override.

The local repository starts with only the selected seed. It does not load both
v1 and v2 and then guess which one is current. Projects pin the version and
verification status used for classification; roadmap, material, form, and gate
operations continue to use that pinned version.

Cloud bootstrap is not changed by this local-default decision and must not
overwrite an existing Firestore snapshot collection.

## 5. Complete v2 pack content

### 5.1 p1 form definition

Include the micro-drama definition used by the product:

- episode duration is strictly less than 20 minutes;
- a continuous plot is required;
- `clause_ref` resolves to p6;
- the candidate source and effective date remain visible through that clause.

This pack exercises D1a. Human review later confirms applicability, wording,
jurisdiction, and effective date.

### 5.2 p2 subject rules

Represent all nine strict special-subject categories as explicit rule entries:

```text
political, military, diplomatic, national_security, united_front,
ethnic, religious, judicial, public_security
```

Each entry carries its literal integration trigger, `expert_pending=true`, and
a p6 `clause_ref`. A clear hit remains final T1 with co-review required and
takes precedence over amount classification. No unreviewed synonyms or scenario
phrases are invented.

### 5.3 p3 tier thresholds

Use the already-supported mode-specific shape:

```yaml
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

These values are allowed to produce final tiers because the entire snapshot is
visibly `mock_verified`. Human review later confirms the amounts, applicability,
jurisdiction, source dates, and effective dates.

### 5.4 p4 process templates

Provide all roadmap templates currently selected by the classification chain.
No duration estimates are included.

| Template | Ordered integration steps |
| --- | --- |
| `T1_7steps` | confirm classification; prepare materials; script pre-check; resolve co-review items; freeze form; institution/authority review; record filing |
| `T2_5steps` | prepare materials; self-check and script pre-check; freeze form; institution review; record filing |
| `T3_4steps` | prepare materials and self-check; freeze form; institution review; record filing |

Every step has a locale key, an owner supported by the current roadmap model,
and only material references that exist in p5. The names describe integration
behavior and carry no claim about a real authority's published procedure.

### 5.5 p5 form and material templates

Use the current single domestic form-pack shape rather than adding conditional
expressions or per-jurisdiction variants.

```yaml
required_facts:
  - title
  - episode_count
  - episode_minutes
  - investment_amount_rmb
  - applicant_entity

material_cards:
  - material_id: mat_synopsis
    asset_kind: synopsis
    required: true
  - material_id: mat_script
    asset_kind: script
    required: true
  - material_id: mat_supporting_document
    asset_kind: supporting_document
    required: false
  - material_id: mat_prompts
    asset_kind: prompts
    required: false
  - material_id: mat_subtitle_sheet
    asset_kind: subtitle_sheet
    required: false
```

Each card also carries its existing locale key fields. `prompts` stays optional
because the current pack has no conditional-expression language and a
live-action project must not be blocked by an AI-only artifact. `final_film`
does not belong in the pre-shoot gate.

Add `supporting_document` to `AssetKind` and add a required `asset_kind` to
`MaterialCard`. One card accepts exactly one kind. Attaching a mismatched asset
returns HTTP 422 and leaves the card unchanged.

### 5.6 p6 legal clauses and candidate sources

p6 contains every clause referenced by p1, p2, p3, or p5. It retains exact
source URLs and distinguishes government text, partner operational rules, and
integration-only descriptions in its wording. No p4 or p5 item receives a
legal `why_clause_id` merely to make the pack look complete.

The snapshot-wide `mock_verified` status applies to these entries until every
source and rule mapping is human-reviewed.

## 6. Semantic validation

Schema validity is necessary but insufficient. Add a pure snapshot semantic
validator that runs when loading a file seed and before storing a published
snapshot.

It rejects:

- a p1, p2, p3, or p5 clause reference missing from p6;
- a p4 material reference missing from p5;
- duplicate material IDs;
- an unsupported or missing material `asset_kind`;
- `T1_min_rmb < T2_min_rmb`;
- a published threshold set missing either boundary or its evidence reference;
- any of the three roadmap templates missing or empty in v2;
- any required p5 fact list or required material-card list missing in v2.

An invalid default seed stops application startup. There is no fallback to v1
and no partial pack loading.

## 7. API and UI propagation

Expose `verification_status` in:

- persisted project classification;
- classification and project responses;
- admin snapshot summaries;
- health output for the active snapshot.

The Wizard result, project dashboard, collection page, and policy admin page
show a non-dismissible banner when the pinned or active status is
`mock_verified`. Copy must say that the data is for integration and not legal
advice. The banner does not replace the existing general disclaimer.

Roadmap and material endpoints do not need a duplicate wrapper field: the
project classification is their pinned policy context and the collection UI
already loads the project. This keeps the shared contract small.

## 8. Error behavior

- Invalid or semantically inconsistent v2: refuse startup or publication.
- Unknown snapshot version: retain the existing 404 behavior.
- Missing amount or generation mode: return a provisional tier even under v2.
- Mismatched material kind: return 422 and do not mutate the card.
- Missing required fact or material: report the existing D3 gate gap.
- Missing Gemini: semantic extraction remains pending; mock policy never turns
  an unrun model check into a clean result.
- Verification status never upgrades automatically because tests passed.

## 9. Test strategy

### Contract and compatibility

- v1 remains readable through both snapshot adapters;
- omitted verification status is conservatively `mock_verified`;
- v2 parses with all six packs and becomes the local default.

### Semantic validation

Test every rejected cross-reference and threshold invariant independently, plus
one fully valid v2 fixture.

### Runtime

- exact live-action and AI boundaries cover T1, T2, and T3;
- special-subject classification wins over amount;
- all three roadmaps build in pack order;
- every material card selects and validates only its declared asset kind;
- required facts and materials block D3 until satisfied;
- a complete result can be non-provisional while remaining mock-verified.

### HTTP and UI integration

- default app health and admin snapshot list report v2/mock;
- Wizard classification reports a final tier and shows the banner;
- dashboard and collection render the same pinned status;
- one deterministic domestic project reaches D3 and form freeze using test
  doubles or fixture facts, without live Gemini credentials;
- the same scenario with a wrong asset kind receives 422 and preserves state.

## 10. Human-review promotion gate

Implementation adds `docs/policy-v2-human-review-checklist.md` with one section
per pack:

- p1: definition, applicability, jurisdiction, original wording, effective date;
- p2: triggers, edge cases, T1/co-review outcome, partner confirmation;
- p3: amounts, mode applicability, jurisdiction, publication and effective dates;
- p4: step order, owners, mandatory steps, and published durations;
- p5: actual fields, requiredness, material names, templates, and asset kinds;
- p6: original text, official URLs, and every rule-to-clause mapping.

Automated tests establish `mock_verified`, never `human_verified`. Promotion
requires every checklist item to be explicitly reviewed, any mock content to be
replaced, the same verification suite to pass, and the whole snapshot to be
republished with `verification_status=human_verified`.

No partial pack promotion is represented in runtime state.

## 11. Out of scope

- overseas policy workflows;
- province-specific variants;
- conditional expression languages;
- multiple allowed asset kinds per card;
- currency conversion or money objects;
- real authority duration promises;
- cloud resource creation or replacement;
- Gate 5-b event-consumer wiring;
- automated approval of human verification.

## 12. Acceptance criteria

The design is implemented when:

1. local startup uses a structurally and semantically valid v2 by default;
2. p1-p6 are populated and the full domestic workflow is executable;
3. final tier calculation and mock verification are simultaneously visible;
4. T1/T2/T3 and live-action/AI paths are covered;
5. material-kind mismatch is rejected without mutation;
6. v1 compatibility remains tested;
7. the deterministic end-to-end integration path reaches D3 and form freeze;
8. no UI or API surface presents mock data as human-verified policy;
9. the human-review checklist exists and no automatic promotion path exists.
