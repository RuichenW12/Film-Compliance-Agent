# Decision log

Every choice that a later reader could reasonably question, with the reason
behind it. [`CHANGELOG.md`](../CHANGELOG.md) says what changed; this file says
why, and under what conditions the choice should be revisited.

Scope of this log: decisions that outlive a single task — contract shape,
ownership boundaries, placeholder data, deferrals. Routine implementation
choices stay in the code and its comments.

How to add one: append the next id, never renumber, never delete. A decision
that turns out wrong gets a new entry that supersedes it, and the old entry's
status becomes `Superseded by D-0xx`. That way the reasoning trail survives.

| id | Area | Decision | Status |
|---|---|---|---|
| [D-001](#d-001) | A | `core/` and `store/` added to the TDD layout | Accepted |
| [D-002](#d-002) | A | Subject rules get placeholder keywords, flagged `expert_pending` | Accepted, revisit when partners deliver |
| [D-003](#d-003) | A | Band-to-tier mapping is provisional while thresholds are unpublished | Accepted, revisit when thresholds publish |
| [D-004](#d-004) | A | No LLM backend means pending, never an implied pass | Accepted |
| [D-005](#d-005) | Shared | `X-Mock-Role` is the role header; `X-Demo-Role` is accepted as an alias | Accepted |
| [D-006](#d-006) | Shared | `recalc-tier` keeps the three-field body; the reason travels in a header | Accepted, deferred |
| [D-007](#d-007) | Shared | `ImpactNode` stays at `D1c` and `C1-a` for the hackathon | Accepted, deferred |
| [D-008](#d-008) | Shared | `create_app` takes keyword-only state arguments | Accepted |
| [D-009](#d-009) | Shared | One API process on port 8080 serves both workstreams | Accepted |
| [D-010](#d-010) | B | Wiring the policy consumer to the live recalc endpoint stays with B | Accepted, open |
| [D-011](#d-011) | Shared | Two router directories and two auth helpers coexist for now | Directory half resolved 2026-08-24 |
| [D-012](#d-012) | Shared | The product cannot read published snapshots yet | Resolved locally by Gate 5-a |
| [D-013](#d-013) | B | Gate 4 adds cloud adapters without claiming deployment | Accepted |
| [D-014](#d-014) | Shared | The policy loop triggers notifications; the product produces them | Accepted |
| [D-015](#d-015) | A | Uploads go through a one-shot ticket, not a bare route | Accepted |
| [D-016](#d-016) | Shared | `p5_form_templates` card shape proposed by A, pending B's review | Proposed |
| [D-017](#d-017) | Shared | `p4_process_templates` step shape proposed by A, pending B's review | Proposed |
| [D-018](#d-018) | A | Placeholder subject rules cap C1-a severity at `needs_human` | Accepted, revisit after the first real-rule test |
| [D-019](#d-019) | A | `accept` acknowledges a finding without releasing the gate | Accepted |
| [D-020](#d-020) | A | A vanished quote is `self_fixed`; a surviving one keeps its decision | Accepted |

---

## D-001

**`core/` and `store/` added to the TDD section 9 layout** · Area: A · Status: Accepted · 2026-08-23

TDD section 9 lists `api/`, `workers/`, `schemas/`, `web/`, `policy/`, `prompts/`,
`tests/`, `infra/`. Pure product logic — the state machine, guards, the D3 gate,
the classification chain — has to be importable by both `api/` and `workers/`
without either importing the other, and `schemas/` is models only. Putting the
logic in `api/` would force workers to import the web layer.

So `core/` holds pure logic with no I/O, and `store/` holds storage adapters
behind the ports in `core/repositories.py`. No shared contract moved, and
`schemas/` is still the single boundary between the workstreams.

Revisit if: the layout ever needs to match the TDD literally for a deliverable.

## D-002

**Subject rules get placeholder keywords, flagged `expert_pending`** · Area: A · Status: Accepted, revisit when partners deliver · 2026-08-23

The v1 seed pack names the nine statutory categories but carries no trigger
text, so nothing could match a script at all. D1b therefore attaches an
operational keyword list per category in `core/classify/subject_rules.py`.

Every rule derived that way carries `expert_pending=True`, the classification
carries a `rules_expert_pending` flag, and the UI shows a "rules pending expert
confirmation" badge. This follows locked decision 5a: AI drafts a placeholder
immediately, and the partner-confirmed library replaces it wholesale. The loader
already accepts the richer `subject_rules: [...]` shape the policy loop will
publish, so the swap needs no code change.

The flag is never evidence on its own — the clause reference is.

Revisit when: the partners return the reviewed rule library.

## D-003

**Band-to-tier mapping is provisional while thresholds are unpublished** · Area: A · Status: Accepted, revisit when thresholds publish · 2026-08-23

Amount thresholds for the 2026-09-01 regime are not published. D1c therefore
maps `band_a/b/c → T1/T2/T3` and marks every such tier `tier_provisional=true`,
which the UI shows as 暂定/待官方. An unknown band assumes the stricter of the
amount-based tiers (T2), returns a three-tier comparison card, and does not
block.

The mapping is a placeholder, not a legal reading. When a snapshot publishes
real amounts, `judge_tier` uses them and the provisional flag clears — that path
is already implemented and tested.

Revisit when: a snapshot arrives with `thresholds_published: true` and real
amounts.

## D-004

**No LLM backend means pending, never an implied pass** · Area: A · Status: Accepted · 2026-08-23

The semantic stages of D1a and D1b need Gemini. Local development and CI have no
credentials. The tempting shortcut — treat "no backend" as "nothing found" —
would silently turn an unrun check into a clean result, which is exactly the
failure mode ground rule 2 exists to prevent.

So `UnavailableLLM` refuses to answer, and the chain records
`edge_phrase_check_pending` / `subject_semantic_check_pending` on the
classification. `GET /healthz` reports the backend and whether it is available.
The same rule applies to model output: a hit whose quote does not occur verbatim
in the document is discarded rather than trusted.

## D-005

**`X-Mock-Role` is the role header; `X-Demo-Role` is accepted as an alias** · Area: Shared · Status: Accepted · 2026-08-23

The API contract names `X-Mock-Role`. Locked decision 2 in the TDD named
`X-Demo-Role`. The contract is the stated source of truth when the two disagree,
and the policy workstream had already built against `X-Mock-Role`.

`api/deps/demo_auth.py` reads the contract name first and falls back to the
alias, so neither side breaks. All auth-shaped code stays in that one file so a
real identity provider can replace it later.

## D-006

**`recalc-tier` keeps the three-field body; the reason travels in a header** · Area: Shared · Status: Accepted, deferred · 2026-08-23

API contract section 4.2 shows `{"changed": false, "reason": "not_provisional"}`.
The frozen shared model `RecalcTierResponse` sets `extra="forbid"` with exactly
three fields, and the Gate 1 contract test asserts the exact dump, so adding
`reason` breaks the policy workstream's test.

Adding an optional field would be legal and additive, but nothing needs it: the
consumer only reads `changed`, and the reason is already available in the
`X-Recalc-Reason` response header and the project timeline. Reopening a frozen
contract days before the deadline costs more than it returns.

Decision: leave the shared model untouched, keep the body exactly on contract,
and treat the handbook's `reason` as documentation of intent rather than a
required field.

Revisit if: a consumer genuinely needs the reason in the body. It is then an
optional field plus a test update, approved by both owners.

## D-007

**`ImpactNode` stays at `D1c` and `C1-a` for the hackathon** · Area: Shared · Status: Accepted, deferred · 2026-08-23

`ImpactNode` enumerates which decision node a policy change affects. It allows
only `D1c` (tier thresholds) and `C1-a` (content review). A change to form-type
rules (pack p1) or process templates (pack p4) has no value to name it, so the
product side cannot react to such a change beyond a generic stale flag.

This is a real gap, but the demo path only exercises a tier-threshold change,
which `D1c` covers. Extending a frozen enum affects the publisher, the consumer,
and the fixtures on both sides.

Decision: document the limit, do not extend the enum before the submission.

Revisit when: a policy change that alters p1 or p4 needs to reach product code —
in practice, the first post-hackathon policy update.

## D-008

**`create_app` takes keyword-only state arguments** · Area: Shared · Status: Accepted · 2026-08-23

Both workstreams had written `create_app` with a single positional parameter for
their own state: the product context on one side, the policy state on the other.
Merging them meant one of the two had to lose the position, and a positional
argument that means different things depending on who calls it is a trap.

Signature is now `create_app(*, context=None, policy_state=None)`. Three call
sites in `tests/policy/test_admin_routes.py` and one in `tests/test_api_intake.py`
were updated. Adding a third workstream's state later costs one keyword.

## D-009

**One API process on port 8080 serves both workstreams** · Area: Shared · Status: Accepted · 2026-08-23

The policy UI client defaulted to `http://127.0.0.1:8000` while the product
client used 8080. After the merge one process serves both route families, so one
of those defaults had to point at nothing. Contract section 8 names 8080 for the
API, so 8000 was the one to move.

`web/lib/policy-api.ts` now falls back through `NEXT_PUBLIC_POLICY_API_BASE_URL`,
then `NEXT_PUBLIC_API_BASE`, then `http://localhost:8080`; two URL assertions in
`web/tests/policy-api.test.ts` were updated. Either side can still be pointed at
a different origin through its own environment variable.

## D-010

**Wiring the policy consumer to the live recalc endpoint stays with B** · Area: B · Status: Accepted, open · 2026-08-23

The policy consumer currently calls a fake recalc adapter. The real endpoint
`/v1/internal/projects/{pid}/recalc-tier` is implemented, tested, and live — the
A-line delivered it as a working implementation rather than the stub the plan
required by D5.

Under the construction plan T-B3 belongs to the policy workstream, so the A-line
does not make the swap. It matters because the closed loop — publish a snapshot,
a provisional project recalculates, the creator is notified — is the demo's
highlight.

Interface for whoever wires it: `POST /v1/internal/projects/{pid}/recalc-tier`,
header `X-Internal-Token`, body `{"snapshot_version": "vN"}`, response
`{tier, tier_provisional, changed}`. Only provisional tiers recalculate; frozen,
institution-stage, and filed projects are refused, and the reason comes back in
`X-Recalc-Reason`.

## D-011

**Two router directories and two auth helpers coexist for now** · Area: Shared · Status: Directory half resolved 2026-08-24, auth helpers pending · 2026-08-23

The merge left `api/routes/` (policy) beside `api/routers/` (product), and
`api/deps/policy.require_admin` beside `api/deps/demo_auth.Principal`. Both
work, and renaming files across a workstream boundary mid-sprint risks conflicts
with in-flight branches for no functional gain.

Cleanup, once both sides are between tasks: one router directory, and the policy
routes depending on `Principal` so role handling lives in one place.

**Directory resolution (2026-08-24):** `api/routers/` won and `api/routes/` is
gone — `admin_policy.py` moved into `api/routers/` and the empty package was
deleted. Four product files stayed put and one policy file moved, which is the
smaller move; the name is otherwise arbitrary. The moved file keeps its absolute
`api.…` imports and its own style, so the diff is a rename plus one import line
in `api/main.py`. Called by the A-line owner while B was between tasks; B's file
moved, so B should know, but no policy behavior, route path, or contract
changed.

**Still open:** the two auth helpers. `api/deps/policy.require_admin` reads
`X-Mock-Role` directly and `api/deps/demo_auth.Principal` covers the product
routes. Consolidating those changes how a policy route authorizes, which is a
behavior change in B's code and wants B's agreement, not just B's awareness.

## D-012

**The product cannot read published snapshots yet** · Area: Shared · Status: Resolved locally by Gate 5-a · 2026-08-23

Found by driving the merged demo by hand: publish v2 through the policy console,
then call `recalc-tier` with `snapshot_version: v2`. It fails, because the two
sides hold snapshots in different places.

- The product reads policy only through `SnapshotService`. The only
  implementation is `FileSnapshotService`, which loads
  `policy/seed-snapshot-v1.yaml` and therefore knows exactly one version, v1.
- The policy loop writes published snapshots into its own repository
  (`InMemoryPolicyRepository` today, Firestore plus GCS later).

Nothing bridges them, so every snapshot the loop publishes is invisible to the
product. The full demo sequence — publish a snapshot, a provisional project
recalculates, the creator is notified — cannot complete until it is bridged,
independently of [D-010](#d-010).

The immediate 500 was fixed: an unreadable version now returns a 404 in the
contract envelope rather than crashing.

Options, roughly in order of effort:

1. a `SnapshotService` implementation backed by the policy repository, injected
   into the product context — small, local, and enough for the demo;
2. the policy publisher also writing each published snapshot to a path the file
   adapter reads — simplest, but two copies of the truth;
3. both sides reading Firestore and GCS, which is where the design lands anyway
   and which the deployment tasks require.

The interface is already the right one and does not change: the product only
ever calls `latest_version`, `get_pack`, and `clause`.

Owner: undecided. Needs a call between both workstreams before T-B3 is wired,
since wiring the consumer without this produces a passing test and a broken
demo.

**Gate 5-a resolution (2026-08-24):** the unified FastAPI composition now
adapts its policy repository to the existing product-side `SnapshotService`.
A snapshot published through the admin route is therefore immediately readable
by `recalc-tier` in the same process. This closes local snapshot visibility only;
real `policy.updated` fan-out, project selection, deployed services, and cloud
credentials remain Gate 5-b/deployment evidence.

## D-013

**Gate 4 adds B-owned cloud adapters without claiming deployment or taking over
product persistence** · Area: B · Status: Accepted · 2026-08-24

Gate 4 replaces the policy loop's external-I/O seams with real HTTP, GCS,
Firestore, Gemini, and Pub/Sub adapters. The runtime is assembled from named
environment settings and application-default credentials; credentials and
service-account files do not belong in the repository.

The smoke command reports `PASS`, `FAIL`, or `SKIP` per external stage. A run
with missing project settings, credentials, resources, or a configured Gemini
model is `SKIP`, never evidence that the cloud path works. Gate 4 is therefore
implemented and locally verified, but remains not cloud-passed until every
named-project stage reports `PASS`.

This gate persists only B-owned policy source state, runs, proposals, snapshots,
and outbox entries. Product project, notification, timeline, and `recalc-tier`
persistence remain outside Gate 4. Revisit this boundary in Gate 5 when the
closed-loop consumer is wired to the shared internal endpoint and the snapshot
visibility gap in [D-012](#d-012) has an owner.

## D-014

**The policy loop triggers notifications; the product produces them** · Area: Shared · Status: Accepted · 2026-08-24

B P0 item 9 lists `policy_stale` and `tier_recalculated` notifications as
policy-loop scope, but the boundary rules say B does not edit product code and
reaches the product only through `/v1/internal/*`. Both statements are right and
they do not fit together, so the item is split rather than argued:

- **B triggers.** The update consumer calls `policy-stale` and `recalc-tier`.
  It does not know that notifications exist.
- **A produces.** `WorkflowService` writes the inbox entry inside the same call
  that sets the flag or changes the tier, so a notification cannot exist without
  the state change that justifies it, and cannot be forgotten by a caller.

Three consequences worth writing down, because each one is a choice a later
reader could question:

1. **A recalculation notifies only when something changed.** Re-running the same
   snapshot returns `changed: false` and stays silent. An inbox that fills up
   with "nothing happened" is an inbox nobody reads. The timeline still records
   every recalculation, changed or not, so the audit trail is unaffected.
2. **A repeated stale flag notifies once.** `mark_policy_stale` is called again
   on every redelivery — the consumer is idempotent on
   `{project_id}:{task_type}:{asset_version}`, but retries still reach the
   endpoint. The producer checks whether the project was already stale and skips
   the duplicate, so redelivery cannot refill the inbox.
3. **Text is keys and params, never prose from the server.** The notification
   carries `title_key`, `body_key`, and a flat `params` map; `web/locales/`
   renders them. This keeps ground rule 3 intact — a param the API did not send
   renders as the literal placeholder, not as `undefined` and not as an invented
   value.

Revisit when the consumer is wired to the live endpoint ([D-010](#d-010)): if B
ever needs a notification that no product state change accompanies, this split
stops working and the two owners need a new seam rather than a workaround.

## D-015

**Uploads go through a one-shot ticket, not a bare route** · Area: A · Status: Accepted · 2026-08-24

The client asks for an upload permit and gets back `upload_url`, `method`,
`backend`, and `storage_uri`; it then writes the bytes to that url. Locally the
url is a route on this same API. In the cloud it becomes a signed object-storage
url and the bytes never touch the API process.

Why the indirection now, when only the local path exists: the client flow is
identical either way, so moving to signed urls is a change to one response
field, not a change to how uploading works. A bare `POST .../assets` would have
to be rewritten on both sides.

`backend` is in the response for the same reason the LLM layer reports
`unavailable`: with no `GCS_BUCKET` configured the ticket says `local` out loud
rather than letting a local run look like a cloud one.

Two rules the ticket enforces, both tested:

1. **Single use.** A replayed upload is a `409`, not a silent second version.
   Retries are normal on flaky networks and must not multiply versions.
2. **Chaining is per kind.** A new script version chains onto the previous
   script via `parent_version`; a synopsis never chains onto a script.

Revisit when the GCS adapter lands: the ticket store becomes the place to record
the signed url's expiry, which the local path does not need.

## D-016

**`p5_form_templates` gets a card shape now, proposed by A and pending B's review** · Area: Shared · Status: Proposed, needs B · 2026-08-24

`p5_form_templates` was `{}`. Building the collection UI against an undefined
pack means either guessing the shape or not building. Guessing quietly is the
worse option, so the shape is written down and named as a proposal:

```yaml
p5_form_templates:
  required_facts: [title, applicant_entity]
  material_cards:
    - material_id: mat_synopsis
      name_key: material.synopsis
      required: true
      why_clause_id: nrta-order-16-article-19
      template_uri: https://...
      common_rejects_key: material.synopsis.rejects
```

Three properties the loader enforces, each of which is really a product rule
rather than a formatting preference:

1. **An empty pack yields no cards.** Not a default set, not a placeholder set.
   A missing pack must be visible as missing; invented cards would look
   official and are exactly what ground rule 3 forbids.
2. **`why_clause_id` is resolved against the pinned snapshot,** and a card whose
   clause is absent keeps `why_clause` empty. A card that tells a creator "you
   must submit this" is a compliance assertion, so without a clause behind it
   the card still appears but claims no legal basis.
3. **A malformed entry is skipped, not rendered.** A card with no
   `material_id` or `name_key` has no meaning to show a creator.

The seed now carries this shape with empty contents, so the structure is
reviewable before any real form exists.

Why A proposed it rather than waiting: `p5` is B-owned policy content but the
product is the only consumer, and the alternative was to stop building. **This
needs B's review before real content is published into it.** If B publishes a
different shape, `core/materials.py` is the single place that changes — the
loader is deliberately the only code that knows the pack layout.

Revisit when the real filing form is sourced: the field list may force
`material_cards` to carry per-card `kind`, size, or format constraints, none of
which are guessed here.

## D-017

**`p4_process_templates` gets a step shape now, proposed by A and pending B's review** · Area: Shared · Status: Proposed, needs B · 2026-08-24

The same situation as [D-016](#d-016), one pack over. `p4_process_templates` was
`{}`, and the roadmap is the step the whole collection phase hangs off, so the
shape is written down and named as a proposal rather than guessed quietly:

```yaml
p4_process_templates:
  templates:
    T3_4steps:
      steps:
        - name: roadmap.step.materials
          owner: creator
          material_refs: [mat_synopsis]
          est_weeks: 2
```

Template names are already fixed by the classification chain
(`ROADMAP_TEMPLATE_BY_TIER`: `T1_7steps`, `T2_5steps`, `T3_4steps`), so the pack
only supplies each template's contents.

Two rules the loader enforces:

1. **An empty template yields no steps and a `roadmap_template_pending` flag.**
   A creator follows a roadmap, so inventing one is worse than showing none.
   The flag is on the API response rather than the `Roadmap` document, which
   keeps `schemas/` unchanged.
2. **A step without a `name` or an `owner` is skipped.** It would tell the
   creator neither what to do nor who does it.

Confirming a roadmap with no steps is deliberately allowed. Refusing would block
the entire downstream path — collection, review, gate — on unpublished policy,
which is exactly the coupling the pending-flag pattern exists to avoid. The gap
travels with the response instead.

One wart worth naming: `RoadmapStep.name` carries a message key, while the
equivalent field on `MaterialCard` is called `name_key`. Renaming it touches
`schemas/`, which needs both owners, so it waits for the same conversation that
reviews these two pack shapes.

Revisit when the real filing process is sourced: real steps may need
dependencies between them, per-step deadlines, or an institution-side owner,
none of which are guessed here.

## D-018

**Placeholder subject rules cap C1-a severity at `needs_human`** · Area: A · Status: Accepted, revisit after the first real-rule test · 2026-08-25

Three of the five severities assert a compliance conclusion — `block`,
`co_review_required`, `caution`. `needs_human` asserts the opposite: that the
machine will not say.

The p2 pack names the nine statutory categories but publishes no trigger text,
so `core/classify/subject_rules.py` attaches its own keyword list and marks
every derived rule `expert_pending` ([D-002](#d-002)). When a scene matches
公安 on 卧底警察, what actually happened is that a keyword this codebase
invented matched. Reporting that as `co_review_required` would state a legal
conclusion resting on a guess, and the attached clause citation would make it
look sourced: `nrta-order-16-article-5` is real and does list 公安, but the link
from *this scene* to *that article* came from the keyword list, not the article.

So while `expert_pending` is set, `core/review.py` caps severity:

```python
severity=(
    FindingSeverity.NEEDS_HUMAN
    if rule.expert_pending
    else FindingSeverity.CO_REVIEW_REQUIRED
)
```

**This is not a softening.** `needs_human` blocks the D3 gate exactly as `block`
does, so the project cannot proceed either way. What changes is the claim: "a
person must look at this scene" rather than "this scene requires co-review with
the authority."

Nothing in code has to change when partner-confirmed rules arrive. The pack
publishes `subject_rules: [...]`, the loader stops synthesizing, `expert_pending`
becomes false, and the same scenes begin reporting `co_review_required`.

**Revisit after the first test against real rules, not before.** Whether
`co_review_required` is the right ceiling even for confirmed rules — or whether
some categories should reach `block`, or whether a confirmed rule with a
low-confidence match should still route to a human — is a question the placeholder
list cannot answer. The golden-sample corpus is where that gets decided: samples
written against today's keywords will start failing when real rules land, and
that failure is the signal, because it shows exactly what the partner's rules
changed versus the guesses. Until such a test has been run, this ceiling stays
where it is rather than being tuned on speculation.

## D-019

**`accept` acknowledges a finding without releasing the gate** · Area: A · Status: Accepted · 2026-08-25

Four actions close a finding and they are not interchangeable:

| Action | Status | Releases D3 | Means |
|---|---|---|---|
| `accept` | `accepted` | **no** | "yes, this is a problem" |
| `resolve` | `resolved` | yes | "it is fixed" |
| `waive` | `waived` | yes | "we proceed anyway, and here is why" |
| `reject` | `rejected` | yes | "this finding is wrong, and here is why" |

`accept` deliberately does not release the gate. Agreeing that a scene is a
problem does not make it stop being one, and an "acknowledge" button that
silently unblocked the workflow would be the easiest possible way to walk a
project past its own compliance check.

`waive` and `reject` both require a reason, which is recorded on the finding and
on the timeline. They are the two ways a project moves forward while a machine
still thinks something is wrong, so neither may happen anonymously.

Revisit if the institution console needs to distinguish a creator's waiver from
an institution's: today both would land in the same `waived` status, and only
the timeline actor tells them apart.

## D-020

**A vanished quote is `self_fixed`; a surviving one keeps its decision** · Area: A · Status: Accepted · 2026-08-25

When a new script version is reviewed, prior findings are neither wiped nor left
pointing at a script that no longer exists:

- a quote still present in the new version is **the same problem**, so its
  finding moves to the new `asset_version` and keeps whatever the creator
  decided about it. A waiver already justified is not re-litigated because a
  neighbouring scene changed.
- a quote that has vanished was rewritten, which is the creator fixing it. The
  finding is marked `self_fixed` rather than deleted, so the history of what was
  flagged and what happened to it survives.

Only `open` findings become `self_fixed`. A finding the creator already waived
or rejected keeps that decision even if the scene disappears, because the record
of *why* they decided it matters more than the scene's current presence.

Alert findings are exempt: they come from the intent profile, not the script, so
a script rewrite says nothing about them.

The weakness worth naming: matching on exact quote text means a scene edited
only slightly reads as vanished-and-new — the old finding closes as `self_fixed`
and a fresh one opens. That is the safe direction (a changed scene is re-checked
rather than silently inheriting an old verdict), but it will inflate
`self_fixed` counts. Revisit if the count becomes misleading in the timeline,
or when scene-level diffing exists to match a scene across edits.
