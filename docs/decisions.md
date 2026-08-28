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
| [D-021](#d-021) | A | Confirming the roadmap starts collection in the same call | Accepted, supersedes part of D-A4 deferral |
| [D-022](#d-022) | A | A form field is filled only from a confirmed fact; freezing hashes it | Accepted |
| [D-023](#d-023) | A | The institution registry ships empty; an unknown institution is unverifiable, not invalid | Accepted |
| [D-024](#d-024) | A | One C1-a finding per scene, with every matching line kept | Accepted |
| [D-025](#d-025) | A | Every long job is a task first; the runner decides where it executes | Accepted |
| [D-026](#d-026) | Shared | Final amount tiers require amount, mode, and usable thresholds | Accepted |
| [D-027](#d-027) | Shared | A computationally final result does not imply human-verified policy | Accepted |
| [D-033](#d-033) | Shared | A disputed policy reading is reported provisional, never settled | Published as D-026; narrowed by [D-034](#d-034), subject half superseded by [D-031](#d-031) |
| [D-034](#d-034) | Shared | 广电办发〔2024〕35号 settles two readings and adds two tier triggers | Published as D-027 |
| [D-028](#d-028) | Shared | A clause carries its own document's effective date | Accepted |

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

## D-021

**Confirming the roadmap starts collection in the same call** · Area: A · Status: Accepted · 2026-08-25

`ROADMAP_CONFIRMED` had no way out. Its only successor is
`COLLECTING_MATERIALS`, and the natural trigger — attaching the first material
card — cannot fire while `p5` publishes no cards. The whole path downstream of
the roadmap was therefore unreachable, which only became visible when the gate
needed to be passed.

`confirm_roadmap` now transitions twice: `ROADMAP_CONFIRMED`, then
`COLLECTING_MATERIALS`. Both are recorded, so the audit trail still shows the
roadmap being confirmed as its own event, and the `Roadmap` document carries
`confirmed` regardless. The project simply rests where the work actually is.

There is precedent: `classify` already chains `INTAKE_DONE -> FORM_JUDGED ->
CLASSIFIED` in one call for the same reason — the intermediate state is a fact
worth recording, not a place to wait.

The same discovery pass fixed a second gap. The state table only allows
`GATE_D3_PASSED` from `REVIEW_RUNNING` or `REVISION_LOOP`, so the gate is
unreachable until a pre-check has run — correct, but it surfaced as
`transition COLLECTING_MATERIALS -> GATE_D3_PASSED is not allowed`, which tells
a creator nothing. `pass_gate` now checks first and says "the script pre-check
must run before the gate can be passed".

This partly supersedes the T-A4 note that a pre-check does not move state: it
still does not move a project that has not started collecting, but from
`COLLECTING_MATERIALS` it now advances to `REVIEW_RUNNING`, and to
`REVISION_LOOP` when blocking findings exist. That was always T-A5 work; T-A4
deferred it rather than inventing a path while `p4` and `p5` were empty.

Revisit when `p5` publishes real material cards: attaching the first card may
become the more honest trigger for collection, and this chained transition
should then be reconsidered rather than left in place out of habit.

## D-022

**A form field is filled only from a confirmed fact, and freezing hashes it** · Area: A · Status: Accepted · 2026-08-25

The form is built, never written. Each field comes from the same
`required_facts` the D3 gate reads, so the gate and the form cannot disagree
about what a filing needs. Then:

- a **confirmed fact** fills the field and the field carries that fact's
  `SourceRef`, so every value on a form can be traced to the document line or
  the human answer that produced it;
- **conflicting facts** leave the field in `conflict` and neither value is
  rendered — two sources disagreeing is not an answer;
- **anything else** stays `pending` and renders as `待补充`.

A human confirming a field is recorded as a `user_answer` fact, not as a
document fact. Both fill the form; only one of them is traceable to a document,
and the form must be able to show which is which.

Freezing requires `GATE_D3_PASSED` and no pending field, then hashes the draft
over its values, their provenance, and the pinned snapshot version. That makes a
frozen form verifiable against the policy it was prepared under, and it is why
the hash covers sources rather than values alone: the same value from a
different source is a different filing.

A frozen form is immutable — editing returns `409`, and re-freezing returns the
same draft rather than a new hash.

Revisit when the institution console can return a form for correction: today
`FORM_FROZEN -> REVISION_LOOP` exists in the state table but nothing performs
it, and unfreezing will need its own rule about what happens to the old hash.

## D-023

**The institution registry ships empty, and an unknown institution is unverifiable rather than invalid** · Area: A · Status: Accepted · 2026-08-25

TDD section 11 forbids real licence verification, and ground rule 3 forbids
inventing entity names and licence numbers. Both bear on the same feature, so
the console is built to make the limitation structural rather than remembered:

1. **The registry ships empty.** No institution is bundled with the product. An
   administrator loads demo entries through `PUT /v1/admin/institutions`, and
   the tests supply their own, so nothing in the repository asserts that any
   real company exists or holds a licence.
2. **`LicenseCheck.mock` is always true.** Every response says the check was a
   mock. There is no code path that produces a non-mock check.
3. **An unknown institution is `institution_not_in_registry`, with `capital_ok`
   and `no_foreign_ok` left `None`.** Unknown is not the same as failed, and
   neither is the same as passed. The same distinction the LLM layer draws
   between pending and clean.

A mock check that fails still stops the flow: accepting requires a check that
passed, so an institution the demo registry rejects cannot accept a project.
A demo that let a failed check through would teach the wrong lesson about what
the gate is for.

Two smaller calls recorded here rather than left to be re-derived:

- **Re-submitting switches institutions.** The state table allows
  `INSTITUTION_REVIEW -> INSTITUTION_REVIEW`, so a project under review can be
  sent to a different institution. The frozen form is untouched by the switch,
  which is tested.
- **The registration number is input, never output.** `record_filing` refuses a
  blank one and stores what it is given verbatim. It is the single value in the
  system that a human must read off a government screen, and the one the product
  may never generate — the model already refuses a `FILED` project without one.

Revisit when a real filing partner is involved: the capital threshold in
`core/institution.py` is a demo constant, not policy, and a real check would
read its criteria from a pack and stop being mock — at which point every
`mock=True` in this module becomes a lie that needs removing rather than
updating.

## D-024

**One C1-a finding per scene, with every matching line kept** · Area: A · Status: Accepted · 2026-08-25

Findings deduplicated on `(category, quote)`, meaning one per matching *line*.
Against the one-line-per-scene fixtures the harness shipped with, that looked
identical to one per scene. Against a real script it is not: a courtroom scene
that names the judge in eleven lines produced eleven findings.

Eleven alerts pointing into the same scene do not give a creator eleven
decisions. They give one decision — rewrite, waive, or escalate that scene — and
ten rows to dismiss. Each also needed its own action, so waiving that scene meant
clicking waive eleven times.

Findings now group on `(category, episode, scene)`. The long fixture goes from 25
findings to 14, one per scene.

**Deduping must not lose the way back**, so the finding keeps every line it
matched:

- `Locator.quote` — the first matching line, verbatim, as before;
- `Locator.line` — that line's 1-based position in the uploaded document;
- `Locator.match_lines` — every line in the scene that matched.

A creator sees one row per scene and can still open any individual line. The
collection UI lists the line numbers under the quote.

Two limits worth naming:

1. **The locator quote is the first match, not the worst.** The pattern stage
   has no notion of severity within a category, so a scene holding one incidental
   mention and one serious one shows the earlier of them. The line list makes the
   others reachable; ranking them would need the semantic stage.
2. **Grouping is per scene, never across scenes.** Two courtroom scenes in
   different episodes are two separate rewrites and stay two findings.

**This changes `schemas/findings.py`, which is the shared contract boundary.**
Both additions are optional with defaults, so nothing existing breaks and the
policy loop is unaffected — it never reads `Locator`. Flagged for B's awareness
rather than assumed: if the field names should differ, they are cheap to change
now and expensive after data exists.

Revisit when the semantic stage runs for real: it could rank matches within a
scene, at which point the locator should quote the strongest line rather than
the first.

## D-025

**Every long job is a task first, and the runner decides where it executes** · Area: A · Status: Accepted · 2026-08-26

Fact extraction and script review ran inside the HTTP request and recorded
nothing. `TaskType` declared seven job types and exactly one place in the
codebase created a `WorkflowTask` — the teaser — so `GET /tasks` returned an
empty list for every project that had actually had work done to it.

That is survivable while the semantic stages are skipped and a review is
instant. It stops being survivable the moment real Gemini is configured: the
30-minute fixture is 40KB and the 70-minute one is 55KB, and a review of either
becomes a call far longer than an HTTP request should hold open.

So the job record and the execution are now separate concerns:

- **the record is the contract.** Every job writes a `WorkflowTask` with its
  idempotency key, status, and result, whether or not a worker was involved;
- **the runner is a deployment decision.** `InlineRunner` does the work now and
  the caller still gets its answer in the response — local development and the
  whole test suite use it, so a demo needs no queue. `QueuedRunner` publishes
  and leaves the task `queued`; `workers/jobs.JobWorker` finishes it.

Verified against the 30-minute fixture: inline returns 9 findings in the
response; queued returns 0 with `backend: "queued"`, and the worker then
produces the same 9. A creator's timeline shows `job.recorded` either way, plus
`job.completed` when a worker finished it.

**Idempotency is now enforced in one place for every job type**, on
`{project_id}:{task_type}:{asset_version}` — ground rule 6. It was previously
load-bearing only for the teaser, because nothing else created a task, and a
rule that only one caller honours is not a rule.

One bug this shook out immediately: `review_incremental` was chosen when
findings already existed for the version being reviewed. Re-running a review of
the same version therefore flipped the job type, which changed the key, which
let the replay review the same script twice. Incremental now means *relative to
an earlier version* — decided from prior review tasks, not from findings — so a
replay of one version is one task.

A queued review answers with no findings and `backend: "queued"`. That is
deliberately visible rather than hidden behind an empty list: nothing has
happened yet, and a UI must be able to tell that apart from "the script is
clean".

Revisit when Pub/Sub is wired: `QueuedRunner` needs a real publisher, and the
worker needs an entrypoint that pulls from a subscription rather than being
handed a task. Neither changes the service, which is the point of the seam.

## D-026

**A final amount tier requires an exact amount, a known generation mode, and a
usable published threshold set** · Area: Shared · Status: Accepted · 2026-08-26

`budget_band` remains a provisional comparison aid. `thresholds_published=true`
does not make a result final when the selected threshold set or exact amount is
missing. D1c selects `live_action` or `ai_generated` from the stored intent and
returns the selected pack evidence; it never falls through to the other mode.

## D-027

**A computationally final result does not imply human-verified policy** · Area: Shared · Status: Accepted · 2026-08-26

The local default v2 is complete enough to drive the domestic T1/T2/T3 workflow
without empty policy packs. It remains `mock_verified`: the amounts, process
steps, material requirements, wording, dates, and evidence mappings have not all
been approved by a human policy reviewer.

`tier_provisional=false` answers a narrow computational question: the runtime
had an exact amount, a known generation mode, and a usable threshold set. It
does not promote the policy input that produced the tier. Every classification
therefore pins both the snapshot version and its separate verification status,
and the API and UI keep the mock warning visible through the workflow.

Promotion is whole-snapshot and human-only. Automated tests may prove schema,
cross-pack consistency, publication safety, and deterministic workflow
behavior, but they cannot change `verification_status` to `human_verified`.
That requires every item in
[`policy-v2-human-review-checklist.md`](policy-v2-human-review-checklist.md) to be
reviewed, its evidence recorded, and a human reviewer to authorize the change.

This decision does not claim cloud deployment, official endorsement, or legal
advice. Cloud bootstrap and Gate 5-b remain separate work.

## D-033

**A disputed policy reading is reported provisional, never settled** · Area: Shared · Status: Accepted, revisit when the primary sources arrive · 2026-08-26

> Published as **D-026** and renumbered to D-033 on 2026-08-28: two different
> decisions had been written under that id on the same day, so `#d-026` resolved
> to the other one and every reference to this entry pointed at the wrong text.
> The id no longer tracks the date for this entry; the date above does.

The v2 source archive records two places where the product was asserting more
than its sources support. Both were documented in the archive and invisible in
the running system, which is the failure this repository exists to avoid: a gap
presented as a result.

### The threshold boundary

`SRC-002` states the live-action boundary two ways **on the same page** —
「达到300万元及以上」(`>=`) and 「达到300万元以上」(`>`). The code has to pick
one reading to compute anything, and picks the inclusive `>=`. That is a
reasonable default and it was silently final: an amount of exactly ¥3,000,000
returned `T1` with `tier_provisional: False`, and a test locked that in.

An answer that depends on an unresolved contradiction is not a settled answer.
An amount **exactly equal** to a threshold now returns the inclusive tier with
`tier_provisional: True` and `threshold_boundary_disputed`. One yuan either side
is unaffected — only equality is in dispute, and treating the whole range as
uncertain would be its own kind of dishonesty.

### The special-subject disposal

A subject hit set `tier=T1, tier_provisional=False, co_review_required=True`
unconditionally. The cited article is narrower: the authority consults **when it
considers it necessary**. So a hit is a strong indication, not a settled tier.

While the rules that produced the hit carry `expert_pending` — as the seed's do,
since the trigger vocabulary was written by this codebase and not by a regulator
([D-002](#d-002), [D-018](#d-018)) — the tier is reported provisional with
`subject_disposal_unconfirmed`.

**Co-review is deliberately kept.** Of the two readings it is the safer one for a
creator to plan around: preparing for co-review that turns out unnecessary costs
time, and skipping co-review that turns out required costs the filing. The tier
is a claim about the law; the co-review prompt is advice about preparation, and
they do not need the same standard of proof.

Confirmed rules settle both: when the pack publishes `expert_pending: false`, the
tier is final again with no flag, and no code changes. There is a test for that
path so the provisional marking cannot quietly become permanent.

### Why this is shared

The readings are B's to resolve — they come from the policy sources — but the
assertions were being made in A's classification code. Neither the snapshot nor
the archive needed changing; what changed is that the product now says what it
does not know.

Revisit when the primary sources arrive: the original NRTA notice behind
`SRC-002` settles the boundary, and a filing partner settles whether a subject
hit fixes the tier. Both should then flip to settled by publishing confirmed
rules rather than by editing this logic.

## D-034

**广电办发〔2024〕35号 settles two readings and adds two tier triggers** · Area: Shared · Status: Accepted · 2026-08-26

> Published as **D-027** and renumbered to D-034 on 2026-08-28, for the same
> collision described in [D-033](#d-033).

The original of 广电办发〔2024〕35号 arrived in the policy library. It is the
document the 2026 threshold adjustment amends, and reading it changes three
things — two of them corrections to [D-033](#d-033), written a day earlier on
weaker evidence.

### The boundary is not disputed, and D-033 over-flagged it

35号 writes 「总投资额度达到**100万元及以上**」 and 「总投资额度在
**30万元（含）**—100万元之间」. The 2026 adjustment uses the same pattern, and
the AI standard writes 「达到80万元及以上」 with no variant at all. Three
documents, one drafting convention, all inclusive.

D-033 flagged **every** equality as disputed on the strength of a single
republished page that wrote the live-action boundary two ways. That was
over-flagging: it marked the AI thresholds uncertain when their source is
unambiguous.

Which boundary is genuinely unsettled is now the **pack's** call. A threshold
set may carry `disputed_boundaries: [T1_min_rmb]`, and nothing is flagged unless
the policy data says so. The seed says so for nothing. If the primary notice
([`MISSING.md`](policy-library/MISSING.md) M-001) turns out to contradict this,
the flag comes back as a data change rather than a code change.

### The special-subject disposal is well founded

D-033 flagged the T1-plus-co-review outcome because Order 16 article 14 has the
authority consult only when it considers it necessary. 35号 is explicit:
特殊题材的微短剧「**按有关协审工作机制落实审核要求**」. The disposal is not an
over-reach and is no longer flagged.

What remains provisional is narrower and still true: the trigger vocabulary that
decided a scene *is* special subject was written by this codebase, not by a
regulator ([D-002](#d-002)). The flag is renamed `subject_match_unconfirmed` to
say that, because the previous name blamed the wrong step.

### 重点微短剧 has four triggers, and two were missing

35号 defines it as meeting **any one** of:

1. 符合特殊题材 — modelled
2. 总投资额度达到门槛 — modelled
3. **长短视频平台招商主推，或在各终端首页首屏推荐播出** — was missing
4. **自愿按重点微短剧申报** — was missing

A 300,000 RMB ordinary drama that a platform puts on its front page is a
重点微短剧. The product classified it T3 on amount alone, which is not a
cautious error in the safe direction: it under-classifies, and the creator
prepares for the wrong regime.

`IntentProfile` gains `platform_promoted` and `voluntary_key_declaration`, the
wizard asks both, and either alone returns T1 without consulting the amount.
Unanswered is not treated as true — an unasked question must not promote a
project.

Revisit when M-001 arrives: it may restate these conditions, and if the 2026
adjustment changed them, this is where it shows.

## D-028

**A clause carries its own document's effective date** · Area: Shared · Status: Accepted · 2026-08-26

The snapshot's `effective_from` said 2026-08-26 while 微短剧发展管理办法 — the
document `p1`, `p2` and `p6` are built from — takes effect **2026-09-01**. The
obvious fix is to change the snapshot date to match. It breaks the product:

```
effective_from: 2026-09-01  ->  latest_version() raises SNAPSHOT_NOT_FOUND
```

`SnapshotService.latest_version()` only considers snapshots whose
`effective_from` has passed, so a future-dated snapshot cannot be selected and
nothing classifies until that date. Verified rather than assumed.

The two fields answer different questions:

- **snapshot `effective_from`** — from when may this snapshot be used at all;
- **a clause's effective date** — from when does the provision itself apply.

One snapshot legitimately holds both: the tier thresholds have applied since
2026-01-01 and 2026-07-01, while Order 16 applies from 2026-09-01. A single
snapshot-level date cannot be true for all of them, which is why the conflict
looked like a mistake and was not one.

`Clause` therefore gains an optional `effective_from` and an `in_force(as_of)`
that returns `None` when the date is unknown — unknown is not the same as
already in force, the same distinction the licence check draws in
[D-023](#d-023). The seeds record the dates their own sources state.

A classification whose evidence cites a provision not yet in force now carries
`clause_not_yet_in_force`, and the UI says which document and from when in plain
language rather than showing a flag name.

The check runs once over the finished classification rather than in each branch
of the chain. Each branch cites different clauses, and the first attempt at this
only inspected the subject rules — which meant a project citing a tier clause
was silently unflagged. A rule only some paths honour is not a rule.

**What this does not do:** it does not stop the product applying a
not-yet-effective provision. On 2026-08-27 the definition of a micro-drama is
Order 16's, five days early. That is a deliberate limit — the output is an
advisory pre-check, the alternative is refusing to classify at all for five
days, and the flag makes the situation visible. Revisit if a future snapshot
carries a provision months rather than days away, where continuing to apply it
would be harder to defend.

There was already a `Regime` enum with `CURRENT` and `FROM_2026_09_01`, unused
and unwired. It is left alone: a date on the clause is the fact that is actually
true, while an enum member naming one specific date will age badly.

## D-029

**A recalculated tier must not relax a subject-derived one** · Area: Shared · Status: Open, blocking nothing yet · 2026-08-27

`recalc_tier` recomputes a provisional tier by calling `judge_tier` — the
amount/band stage, D1c — and nothing else. That is correct for a project whose
tier came from an amount. It is wrong for one whose tier came from a subject
hit: D1b is never re-run, so the band-derived answer simply overwrites the
subject-derived one. Measured against the live seed: a 缉毒/卧底 logline
classifies `T1`, and one recalc drops it to `T2` while `co_review_required`
stays `true`, the subject match stays in `matched_rules`, and the evidence still
cites `nrta-order-16-article-5`. The record ends up asserting a tier that its
own evidence does not support, and it errs toward *less* scrutiny.

This became reachable rather than theoretical when subject hits started being
reported provisional ([D-028](#d-028) and the special-subject disposal above):
`recalc_tier` only touches provisional tiers, so while a subject hit was final
this path was never entered. Nothing about recalc changed — what changed is who
is now eligible for it.

Three readings, none of them free:

1. **Skip re-tiering when a subject hit is present.** Cheapest, and preserves
   the stricter answer. But a genuinely new threshold then never reaches these
   projects at all.
2. **Re-run D1b during recalc.** Most correct, and most expensive — it puts a
   model call inside a fan-out that today is deterministic and synchronous, and
   the semantic stage is occasionally a miss (see below), so a refresh could
   relax a tier through model variance rather than through policy.
3. **Take the stricter of the two** and record both. Preserves scrutiny without
   a model call, at the cost of a tier that is a max() of two stages rather than
   the output of one.

Left open deliberately: it changes the meaning of the `/v1/internal/*` recalc
contract that T-B3 calls, so it needs both workstream owners rather than
whoever noticed it. `scripts/e2e_check.py` is left reporting two failures here
instead of being adjusted to match current behavior — a green check that
encodes a relaxed tier is worse than a red one.

Revisit when: T-B3 wires the real recalc fan-out, or sooner if a snapshot
publishes real amount thresholds, since that is when recalc starts changing
tiers for reasons other than a placeholder band mapping.

**Related, not the same defect:** when the D1b model call succeeds but returns
quotes that are not verbatim in the document, every hit is discarded
(`core/classify/d1b.py:154`) and the tier degrades T1 → T2 with **no pending
flag** — indistinguishable from "no special subject found". Observed on roughly
2 of 14 live classifies of the same fixture. An `UpstreamLLMError` sets
`subject_semantic_check_pending`; a silent miss sets nothing. Given that a
missing backend is reported and never faked, a discarded-quote miss arguably
deserves the same signal. Not changed here, for the same reason as above.

## D-030

**The filing route is snapshot data, and cites the 规章 rather than the 通知** · Area: Shared · Status: Accepted · 2026-08-27

A tier on its own does not tell a creator anything they can act on. 「T2」 is a
label; 「报省级以上，拿到批准文件之前不得播出」 is an answer. So a classification
now carries `filing_route`.

Two choices in it are worth recording.

**Why the route is data, not code.** The mapping tier → authority is short enough
to hard-code in `chain.py`, and that was the tempting version. It is also exactly
the kind of thing that changes without the code changing: a province issuing its
二类 implementing rules, or a future notice moving a threshold between levels.
Putting it in `p4_process_templates.filing_routes` means such a change is a
snapshot publish, which is already the audited path, rather than a deploy. The
cost is a route that can go missing — handled by returning `None`, never a
default.

**Why it cites 总局令第16号 and not 广电办发〔2024〕35号.** Both state the same
three levels, and 35号 states them more plainly. But the Order is a 部门规章 and
35号 is a 规范性文件: the higher instrument wins where both speak. Article 12
carries the pre-shoot filing, article 13 the split between national publication
and provincial审核, article 17 makes a grant a precondition of release for the
first two tiers, and article 34 makes the platform verify the first two and
number the third. That is the whole route without leaving the regulation.

There is also a practical reason. 35号 has no `SRC-` id in the sources-v2
archive — it lives in `docs/policy-library/` as `P-002` — and citing it would
have meant either adding it to a directory with its own checksum tests, or
citing a clause the snapshot cannot resolve. The rule that an unsourced route is
withheld would then have deleted the route entirely.

**What this does not do:** it does not model 属地. The route says *which level*,
not *which province*, and `IntentProfile` still has no jurisdiction field. For T2
that gap is load-bearing — article 12 makes the pre-shoot filing 「可以」参照适用
and article 13 leaves the detail to provincial rules, so the pack reports
`varies_by_province` rather than a settled answer. Revisit when a province
publishes its 二类 implementing rules, which cannot happen before the Order takes
effect on 2026-09-01.

## D-031

**Whether a rule is expert-confirmed is settled before publication, not at classify time** · Area: Shared · Status: Accepted · 2026-08-27 · Supersedes the subject half of [D-033](#d-033), and closes [D-029](#d-029)

D-033 made a special-subject hit report `tier_provisional: true` whenever the
rules behind it carried `expert_pending`. The reasoning was honest: the trigger
vocabulary was written by this codebase, not by a regulator, so the tier rested
on an unvetted match.

It was the wrong field to say it in, for three reasons.

**It said something false.** `tier_provisional` means *this project's tier may
still move*. What was actually true is *this policy data has not been vetted* —
a fact about the snapshot, shared by every project classified against it. The
snapshot already reports that, in `policy_verification_status`
(`mock_verified`) and each pack's `mapping_status`. The claim was being made
twice, once in the right place and once in the wrong one.

**It was a debt nothing could repay.** `expert_pending` is read in five places
and written in none: its value comes entirely from the pack YAML, and no code
path can clear it. All nine seed subject rules carry `true`. So every special
subject hit read as unsettled *permanently*, with no action available to anyone
that would settle it.

**It reached across a boundary it should not have.** Confirming a rule belongs
to the outer loop — crawl, propose, human review, publish. The product loop
should trust what the library contains and give the creator a definite answer.
Letting an outer-loop debt decide an inner-loop conclusion made the creator
carry the policy team's uncertainty.

**What it broke.** `recalc_tier` only touches provisional tiers. While subject
hits were final it never saw them; once D-033 made them provisional it did, and
it recomputes from `judge_tier` alone. A 缉毒 project therefore relaxed **T1 to
T2** on any policy refresh while keeping `co_review_required`, its subject
match, and evidence citing `nrta-order-16-article-5` — a tier its own evidence
did not support, moving toward less scrutiny, silently. That is D-029, and it
needed no fix of its own: cutting the transduction puts subject hits back
outside recalc's reach.

**What stays.** `expert_pending` keeps both of its honest consumers: the
`rules_expert_pending` and `subject_match_unconfirmed` flags still surface on
the classification, and `core/review.py` still downgrades findings from such
rules to `needs_human` rather than `block`. It reports; it no longer decides.

**Still missing, deliberately not built here.** Two gaps this exposes.

1. There is no per-rule confirmation step. The admin loop can publish or discard
   a whole proposal, but an expert cannot mark one rule confirmed, so nothing
   can set `expert_pending` to false except publishing a snapshot that already
   says so. `publish` should also record when a snapshot still carries unvetted
   rules rather than emitting it silently.
2. `ImpactNode` has only `D1C` and `C1A`. A change to `p2_subject_rules` has no
   node to declare, so `_is_affected` returns false and projects classified on
   the old vocabulary are **not even marked stale**. The word list is the part
   most likely to change — it comes from trend and sentiment research — so this
   is the live gap. It is left for T-B3, when `impact_nodes` is first computed
   for real projects; today it exists only in the policy loop's memory adapter.

Revisit when either is built.

## D-032

**The English UI drops the Chinese gloss; a Chinese bundle comes later** · Area: A · Status: Accepted · 2026-08-27 · Narrows the i18n half of locked decision 1

`lib/i18n.ts` records: *the UI is English; Chinese legal terms are kept with an
English gloss.* In practice the bundle had drifted into three different habits,
and only one of them was the decision.

Most entries were not glosses at all but repetitions —
`"Special subject 特殊题材 (special subject)"` names the same idea three times,
and eight material labels shared that shape. A few were Chinese with no English
at all (`待补充`, `国家广电总局`), which is the opposite of a glossed English UI.
Only a handful were the real case the decision was written for: 重点微短剧,
广电办发〔2024〕35号.

The gloss had a genuine argument behind it. A creator filing for real meets
重点微短剧 on the government's own pages and forms, and an English-only product
leaves them unable to match what they see. That argument is not wrong — it is
just answered better by a **Chinese bundle** than by a mixed English one. Mixing
serves neither reader: the English speaker reads past characters they cannot
parse, and the Chinese speaker gets English scaffolding around the terms they
actually need.

So: the English bundle is English, `zh.json` keeps the same keys and will carry
the Chinese terms when it is filled in, and `t()` already falls back to English
for keys the Chinese bundle has not reached yet.

**What this does not touch.** Clause ids (`nrta-order-16-article-5`), snapshot
versions and evidence refs are identifiers, not display text, and are unchanged.
Neither are source comments: a comment citing 广电办发〔2024〕35号 points a
developer at the actual document, and translating that would cost traceability
for nothing.

Revisit when the Chinese bundle is written, or if a user testing the English UI
cannot find on a government site the thing the product told them about — that is
the failure mode this trades away, and it is worth watching for.

## D-035

**Intake help explains the question rather than reading the answer** · Area: A · Status: Accepted · 2026-08-28 · Replaces the conversational extraction built earlier the same day

Testing the wizard in a browser found three fields a first-time creator cannot
answer, all of the same shape: `budget_band` rendering raw enum values and
defaulting to one, `domestic_platforms` prefilled with platforms nobody named,
and two 广电办发〔2024〕35号 conditions with no hint that leaving both off is
normal. Better labels fixed the symptom. The disease is that **a form cannot
answer a question back**.

The first attempt at the cure was conversational intake: the creator describes
the project, a model reads their sentence, and proposed values appear in the
form for confirmation. It was built and it worked — `core/intake_chat.py`, a
traceability guard, twenty tests, an endpoint that could not write. It is
deleted.

**Why it went.** Reading someone's answer accepts their confusion and works
around it. Explaining the question removes it. Both help a creator who does not
know what 招商主推 means; only one of them leaves them understanding the form
they are signing. And the extraction route carried a permanent cost for that
weaker outcome: every value it proposed was a value a model had chosen, so the
whole apparatus of quotes, inferred flags and confirmation existed to make that
survivable.

The replacement has no such apparatus because it has nothing to guard. The
reply schema is `{answer, clause_refs}` — **there is no value field**, so no
phrasing of a question and no instruction buried in one can reach the form. A
test asserts that shape directly, because if a value field ever reappears the
guard has to come back with it.

**What survived the change**, because neither was about extraction:

- Explanations are drawn from clause text passed as trusted context, and a
  clause id the model names but the pinned snapshot does not carry is dropped.
  A reference nobody can follow is worse than none — and this domain has already
  burned us once, with thresholds sourced from a republished municipal page.
- The model may say what the tiers are. It may not say which one a project is
  in. That answer comes from the chain, with evidence; a conversational guess
  would carry none and be believed anyway.

**What was given up.** Someone who types a paragraph describing their whole
project still fills the form field by field. That is a real cost, and the reason
to accept it is that the paragraph was never the hard part — understanding what
was being asked was.

Revisit if field help lands and people still abandon the form, which would mean
the problem was typing after all.


## D-036

**A threshold-aligned bracket settles a tier; an invented band never could** · Area: Shared · Status: Accepted · 2026-08-28 · Supersedes the band half of [D-003](#d-003)

D-003 mapped `band_a/b/c` to T1/T2/T3 and marked every such tier provisional.
That was right at the time and for the reason it gave: the thresholds were not
published, so the bands were a placeholder and a tier from one was a guess
dressed as an answer.

The thresholds are published now — 1,000,000 and 3,000,000 for live action,
300,000 and 800,000 for AI — and that changes what a range can mean. `band_c`
was a label somebody chose. `below_lower` is defined *by* the published figures,
so answering it says exactly what a number under 1,000,000 would say. Continuing
to report that as provisional understated what the creator had told us, and made
the honest answer — "I don't know the exact figure yet" — cost them a settled
result they were entitled to.

So `BudgetBand` becomes `AmountBracket`, and a bracket produces a **settled**
tier whenever the thresholds behind it are usable. It stays provisional when
they are not — no published set, or no production mode to choose a set with —
because then there is nothing for the bracket to be relative to.

**Why relative rather than numeric.** The brackets are not `under_1m` and
`under_300k`; they are `below_lower`, `between`, `at_or_above_upper`. The figures
differ by production mode, and encoding either set into the enum would have put
policy data into a type. One enum, resolved against whichever set applies, and
the interface fills in the numbers — which it does from the AI checkbox, so the
same dropdown reads "Under ¥1,000,000" or "Under ¥300,000" depending.

**What this does not change.** The exact amount is still wanted: the freeze gate
lists `investment_amount_rmb` among its required facts, so `amount_required`
still appears on a bracket-derived classification. It has simply stopped being a
reason to hedge a tier the bracket already decided.

**The boundary.** `at_or_above_upper` includes the threshold itself, and
[D-033](#d-033) records that one source states that boundary two ways. The pack
may still flag a disputed boundary and nothing in the seed does, so the inclusive
reading stands and the bracket is settled. Revisit if a snapshot ever populates
`disputed_boundaries`: the most-chosen option becoming provisional would be a
poor trade, and the better answer would then be to ask for the figure instead.

**The one duplication.** `web/lib/enums.ts` carries the figures so the dropdown
can show them, which is a second copy of policy data. The tier is still computed
server-side from the pinned snapshot and stays correct if the two drift; the
labels would not. Accepted because a range with no numbers is a question nobody
can answer, and recorded here so the staleness is findable.
