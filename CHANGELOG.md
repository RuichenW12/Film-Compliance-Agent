# Changelog

What changed, when, and who owns it. Two workstreams share this repository, so
every entry is tagged **A** (product workflow, Maxine) or **B** (policy loop,
Richard), or **Shared** when it touches the contract boundary or both sides.

Why an entry gets written: a reader six days from now — or the other
workstream's agent — must be able to see what moved without reading the diff.
Reasons for non-obvious choices live in [`docs/decisions.md`](docs/decisions.md);
this file links to the decision id rather than repeating the argument.

Conventions:

- newest first, grouped by date;
- each entry states what changed and, where it matters, what was verified;
- a change that alters something the other workstream depends on says so
  explicitly, in bold;
- verification claims name the check that was actually run. "Tests pass" without
  a command is not a verification claim.

---

## 2026-08-25

### A — Veo teaser behind FLAG_VEO_TEASER

- `POST /v1/projects/{pid}/teaser` queues a `teaser` task. The flag is off by
  default and the route says so — a disabled feature is a fact worth telling the
  caller, not a 404.
- **A teaser is promotional material and carries no compliance meaning.** The
  prompt is built from the logline alone: no tier, no clause, no filing status.
  The task records `promotional_only: true` beside the uri and pins the snapshot
  and prompt version, so a generated file cannot later be mistaken for a
  reviewed artifact.
- The logline is wrapped in `<<<DOC>>>` like every other user-supplied document,
  so an instruction inside a logline cannot steer generation. Tested.
- **No backend means no teaser.** With Veo unconfigured the task is
  `needs_human` with `teaser_backend_unavailable` and no result — never a
  placeholder uri, which would look like output. A backend that raises is
  recorded `failed` with the reason rather than swallowed.
- Idempotent on `{project_id}:teaser:{asset_version}` like every other job: a
  repeated request returns the first task and does not generate twice.
- `VideoBackend` is a port with `UnavailableVideo` as the default, mirroring the
  LLM seam, so tests and local runs need no credentials.
- `scripts/e2e_check.py` gains step 18, which now reports rather than listing
  the step as pending.

Verified: `python -m pytest` — 361 passed, 3 skipped, 13 new in
`tests/test_teaser.py` covering the flag, the offline path, prompt injection in a
logline, idempotency, a failing backend, and the absence of any compliance claim
in the generated request.


### A — scene attribution in C1-a, found by B's synthetic scripts

Running the three fixtures from #27 through the real reviewer exposed four
faults in the scene parser. None were visible against the one-line-per-scene
scripts the harness shipped with.

- **Findings attributed to bare lines.** Only lines that themselves carried a
  heading got an episode and scene; everything else reported `None`. A finding a
  creator cannot navigate to is not much use. A line now inherits the episode
  and scene it sits inside, and the markdown form — `### 第N集` followed by
  `**内景·…**` slug lines — is supported alongside `第一集 场景二`.
- **The documents' own disclaimers were reviewed.** The judicial fixture's
  blockquote mentions 庭审 and 审判, so the file's warning that it is synthetic
  produced a finding. Blockquotes and everything above the first episode heading
  are commentary about a script, not script.
- **`第47版` became scene 47.** The 场 in the scene pattern was optional, so any
  `第N…` line reset the scene number.
- **Appendix text was filed under episode 7.** A section heading that is not an
  episode now closes the one before it.

Effect on the long fixture: 38 findings down to 25, every one carrying an
episode, and all seven scenes the fixture names as expected are covered.

A plain script with no episode headings is still reviewed whole, so nothing that
worked before stopped working.

### A — one C1-a finding per scene, with every matching line kept

- Findings deduplicated per matching *line*, so a courtroom scene naming the
  judge in eleven lines produced eleven findings — eleven rows to dismiss for one
  rewrite decision, and eleven clicks to waive it. They now group on
  `(category, episode, scene)`: the long fixture goes from 25 findings to 14.
- **Deduping does not lose the way back.** `Locator` gained `line` (the 1-based
  position of the quoted line) and `match_lines` (every line in the scene that
  matched), so one row per scene still opens onto each individual line. The
  collection UI lists them under the quote. Reasoning and limits in
  [D-024](docs/decisions.md#d-024).
- **B: this adds two optional fields to `schemas/findings.py`**, the shared
  contract boundary. Both default, nothing existing breaks, and the policy loop
  never reads `Locator` — flagged for awareness rather than assumed.

Verified: `python -m pytest` — 348 passed, 3 skipped, 16 new in
`tests/test_scene_parsing.py`. Each case came from running the fixtures, not
from imagination; four assert the statements written into the fixtures
themselves so a fixture and the reviewer cannot drift apart silently; and one
resolves every recorded line number back to a line that really matched.


### A — institution console, the way back from a return, and task reads

- New `/institution` page: the demo registry, submission with its licence
  verdict, the institution's accept/return decision, and filing. The licence
  verdict renders as `mock check passed` / `mock check did not pass` beside a
  `mock` chip and a plain-English disclaimer, and an unknown institution reads
  "Unknown, not approved" rather than looking like a failure or a pass.
- **Closed a dead end:** `INSTITUTION_RETURNED` had no exit. The state table
  allowed the way back to `REVISION_LOOP` but nothing performed it, so a
  returned project could never be corrected and resubmitted. Added
  `POST /v1/projects/{pid}/institution/resume`.
- Added `GET /v1/projects/{pid}/institution` so a creator can read the verdict
  and the return comments on their own project, and
  `GET /v1/projects/{pid}/tasks` for contract step 17. The task list is
  genuinely empty — nothing queues async work yet — and the test says so rather
  than implying coverage.
- `TaskStore` gained `list(project_id)`, with the in-memory adapter.
- Loading the demo registry is offered only to an administrator; other roles see
  why instead of a 403 from a button that should not have been there.
- New `.button-group` style so buttons belonging to one decision sit together
  rather than being pushed to opposite edges by `.action-row`.

Verified: `python -m pytest` — 332 passed, 3 skipped, 6 new;
`npm --prefix web test` — 17 passed; `npm --prefix web run build`. Then driven
in a real browser against a live API: loaded the registry as admin, submitted to
an institution outside it and saw "Unknown, not approved", switched to the
licensed one, accepted as the institution role, recorded a filing, and watched
the badge reach `FILED`.


### A — institution review and filing

- `GET /v1/institutions`, `PUT /v1/admin/institutions`,
  `POST /v1/projects/{pid}/institution/submit`, `.../institution/decide`, and
  `POST /v1/projects/{pid}/filing` complete contract steps 12-14.
- **The registry ships empty and the licence check is always mock**
  ([D-023](docs/decisions.md#d-023)). An institution the registry does not know
  reports `institution_not_in_registry` with both sub-checks `None` — unknown,
  not passed and not failed. Nothing in the repository asserts that a real
  company exists or holds a licence.
- A mock check that failed still stops the flow: accepting requires a check that
  passed, so a foreign-invested demo institution cannot accept a project.
  Accepting also requires the signed agreement; returning requires comments.
- The creator submits and the institution decides; neither may do the other's
  act. Re-submitting while under review switches institutions and leaves the
  frozen form untouched.
- **The registration number is input, never output.** `POST .../filing` refuses
  a blank one and stores what a human supplies, verbatim. Filing never rewrites
  the frozen form — its hash is unchanged after `FILED`, which is tested.

Verified: `python -m pytest` — 326 passed, 3 skipped, 21 new in
`tests/test_institution.py`. Driven against a live API from an empty registry
through to `FILED`: unknown institution reported as unverifiable, bare accept
refused, accept into `READY_FOR_EXTERNAL_FILING`, blank registration number
refused, filing recorded, and the frozen form's hash unchanged afterwards.


### A — gate passage, form preview, field confirmation, and freeze

- `POST /v1/projects/{pid}/gate/pass` moves a project to `GATE_D3_PASSED` or
  refuses with the machine-readable gaps. `GET .../form`,
  `POST .../form/fields/{key}/confirm`, and `POST .../form/freeze` complete
  contract step 11.
- A field is filled only from a confirmed fact and carries that fact's
  `SourceRef`; conflicting facts leave it in `conflict` with neither value
  shown; everything else renders as `待补充`
  ([D-022](docs/decisions.md#d-022)). Freezing requires the gate to have passed
  and no field left pending, then hashes values, provenance, and the snapshot
  version. A frozen form cannot be edited and re-freezing returns the same hash.
- **Two dead ends in the state path, found by needing to reach the gate**
  ([D-021](docs/decisions.md#d-021)): `ROADMAP_CONFIRMED` had no exit because
  its natural trigger is attaching a material card and `p5` publishes none, so
  confirming the roadmap now starts collection in the same call, recording both
  transitions. And the gate refused with `transition COLLECTING_MATERIALS ->
  GATE_D3_PASSED is not allowed`, which tells a creator nothing; it now says the
  pre-check must run first.
- The pre-check now advances the review loop from `COLLECTING_MATERIALS` to
  `REVIEW_RUNNING`, and to `REVISION_LOOP` when blocking findings exist. T-A4
  deferred this rather than invent a path while the packs were empty.

Verified: `python -m pytest` — 305 passed, 3 skipped, 20 new in
`tests/test_form_freeze.py`. The whole golden path driven against a live API:
classify T3, roadmap into `COLLECTING_MATERIALS`, pre-check into
`REVIEW_RUNNING`, gate refused with `facts_missing`, freeze refused with
`STATE_INVALID`, five fields confirmed, gate passed, form frozen with a 64-char
hash, and a post-freeze edit refused with `CONFLICT`.


### A — finding actions and incremental review

- `POST /v1/projects/{pid}/findings/{fid}/action` takes `accept`, `resolve`,
  `waive`, `reject`, or `choose_option`. `waive` and `reject` require a reason,
  recorded on the finding and the timeline.
- **`accept` acknowledges without releasing the gate** ([D-019](docs/decisions.md#d-019)):
  agreeing that a scene is a problem does not make it stop being one.
- `choose_option` dispatches an alert finding's five-field alert. An option that
  was not offered is refused, and a finding with no alert cannot be dispatched.
- Re-reviewing a new script version carries findings forward
  ([D-020](docs/decisions.md#d-020)): a quote still in the script keeps its
  decision and moves to the new version; a vanished quote becomes `self_fixed`
  rather than being deleted. Alert findings are exempt — they come from the
  intent profile, not the script.
- Noted while testing: **the seed's synthesized subject rules never set
  `is_edge_case`, so the edge-case alert path is unreachable with the
  placeholder pack.** The alert tests publish an explicit `subject_rules` pack —
  the shape the policy loop will publish — rather than skipping.

Verified: `python -m pytest` — 285 passed, 3 skipped, 16 new in
`tests/test_finding_actions.py` covering each action, the gate consequence of
each, alert dispatch and its refusals, carry-forward, self-fix, and the timeline.


### A — collection UI, and the CORS bug it found

- New `/collection` page: upload an asset, see the version chain and its sha256,
  extract facts, work the material cards, confirm the roadmap, run the C1-a
  pre-check, and read the findings with their clause citations.
- **Fixed: `PUT` was missing from `allow_methods` in the API's CORS config**, so
  every upload failed in a browser while all 268 tests passed. Found by driving
  the page in a real browser, not by a test. `tests/test_uploads.py` now
  preflights `PUT /v1/uploads/{tid}` so it cannot regress silently.
- Pending flags render as visible warnings rather than being swallowed:
  `roadmap_template_pending`, `fact_extraction_pending`, and
  `script_semantic_check_pending` each say in plain English that the result is
  not clean, matching what the API reports.
- An empty pack renders as "the policy snapshot defines none yet", never as an
  empty-looking success.
- New keys registered in `web/locales/en.json` and `zh.json`.

Verified: `python -m pytest` — 269 passed, 3 skipped; `npm --prefix web test` —
17 passed; `npm --prefix web run build`. Then driven end to end in a real
browser against a live API: upload a script, run the pre-check, and see two
`public_security` findings at `needs_human` citing `nrta-order-16-article-5`,
with both pending-flag warnings visible.

## 2026-08-24

### A — C1-a script pre-check and the golden-sample harness

- `POST /v1/projects/{pid}/review` runs the pre-check over the latest uploaded
  script; `GET /v1/projects/{pid}/findings` lists what it found. Institutions
  and admins may read findings; only the owner triggers a review.
- Stage 1 matches the published p2 rules scene by scene, parsing 第N集/场景N
  headings into `Locator.episode` and `Locator.scene`. Stage 2 is one semantic
  pass that may only report categories the pack publishes, and whose quote must
  occur verbatim in the script — anything else lands in `discarded`.
- **Severity comes from the rule, never the model.** While the p2 keywords are
  the placeholder list, every finding is `needs_human`, not `block`. Each one
  carries an `EvidenceRef` into the pinned snapshot, so ground rule 2 holds by
  construction rather than by review. The ceiling and the condition for changing
  it are recorded in [D-018](docs/decisions.md#d-018): it is revisited after the
  first test against partner-confirmed rules, not tuned on speculation before.
- No backend means `script_semantic_check_pending`. Patterns finding nothing is
  never rendered as a clean script.
- A pre-check reports and does not move project state; the revision loop that
  consumes findings is T-A5. Re-running does not duplicate findings for the same
  asset version.
- Added the golden-sample harness (`tests/test_golden_samples.py`,
  `tests/golden/SCHEMA.md`). It runs synthetic scripts to prove the machinery,
  and rejects any golden sample lacking `provenance` and `reviewed_by`. With no
  samples present it **skips with a reason** — an empty corpus is not evidence
  of accuracy.
- Prompt contract in `prompts/c1a-script-review.v1.md`.

Verified: `python -m pytest` — 268 passed, 3 skipped (the empty golden corpus),
16 new in `tests/test_script_review.py`. Live against the real seed: a
two-scene script yields two `public_security` findings at `needs_human`, each
citing `nrta-order-16-article-5`, and the gate reports them under
`findings_needs_human`.


### A — roadmap preview and confirmation

- `GET /v1/projects/{pid}/roadmap` builds the plan from
  `p4_process_templates` for the template the classification chain already
  chose; `POST .../roadmap/confirm` accepts it and moves the project to
  `ROADMAP_CONFIRMED`.
- An empty template yields no steps and a `roadmap_template_pending` flag rather
  than an invented plan — a creator follows a roadmap, so inventing one is worse
  than showing none. Confirming an empty roadmap is allowed on purpose: refusing
  would block collection, review, and the gate on unpublished policy.
- Confirming twice is one event, not two. An unclassified project is refused.
- The pending flag rides on the API response, not the `Roadmap` document, so
  `schemas/` is unchanged.
- **B: this proposes a shape for `p4_process_templates`** and writes it into the
  seed with empty contents. See [D-017](docs/decisions.md#d-017) — it needs your
  review, along with [D-016](docs/decisions.md#d-016), before real content is
  published into either pack.

Verified: `python -m pytest` — 249 passed, 10 new in `tests/test_roadmap.py`.
Live against the real seed: `T3_4steps` with no steps and
`roadmap_template_pending`, confirm moves the state and keeps the flag.


### A — fact extraction from uploaded assets

- `POST /v1/projects/{pid}/assets/{vid}/extract-facts` reads one asset and
  stores only the facts the document backs verbatim; `GET .../facts` lists them.
- Kept honest three ways, each tested: a quote must occur in the document, the
  value must occur inside its own quote, and a null or blank value is dropped
  rather than stored. Rejected proposals come back in `discarded`.
- With no Vertex backend the response carries `fact_extraction_pending` and
  writes nothing, so an empty list is never read as "the document held nothing".
- Every stored fact carries `SourceRef(type=asset, asset_version, locator=quote)`,
  so a form field rendered from it traces back to the line that produced it.
- Wanted keys come from `p5_form_templates.required_facts` when the pack defines
  them, otherwise the `core.gate` defaults.
- Prompt contract in `prompts/fact-extract.v1.md`.

Verified: `python -m pytest` — 239 passed, 11 new in
`tests/test_fact_extraction.py`, covering the offline pending path, verbatim
rejection, value-not-in-quote rejection, null values, prompt injection inside an
uploaded document, gate gap closure, and role scoping.


### A — policy notifications reach the creator

- `WorkflowService` now writes an inbox entry when a policy update sets
  `policy_stale` or actually changes a tier. A recalculation that changes
  nothing stays silent, and a repeated stale flag notifies once, so consumer
  redelivery cannot refill the inbox. Reasoning in
  [D-014](docs/decisions.md#d-014).
- Added `GET /v1/notifications` (with `unread_only`) and
  `POST /v1/notifications/{nid}/read`. Each caller reads only their own inbox;
  another creator gets 403 on a read receipt and an empty list on a read.
- Added `NotificationStore.get()` to the port and the in-memory adapter, and
  made `list()` return newest first.
- Notification text stays keys plus a flat `params` map. Registered
  `notification.policy_stale.*` and `notification.tier_recalculated.*` in
  `web/locales/en.json` and `zh.json`, added `format()` to `web/lib/i18n.ts`
  for placeholder substitution, and rendered the inbox on `/dashboard`.
- **B depends on this.** It closes the product half of B P0 item 9. The policy
  consumer does not call any notification route: it keeps calling
  `/v1/internal/projects/{pid}/policy-stale` and `.../recalc-tier`, and the
  notification is written inside those calls. Nothing on the B side needs to
  change, and Gate 5-b fan-out now has a visible effect for the creator.

Verified: `python -m pytest` — 202 passed (9 new in `tests/test_notifications.py`,
including the publish-v2 → recalc → notified path); `npm --prefix web test` — 17
passed (5 new); `npm --prefix web run build`; and `python scripts/e2e_check.py`
against a live API on port 8082 with `INTERNAL_TOKEN` set — ALL CHECKS PASSED,
including the six new checks under `17. the creator inbox`. No cloud
credentials, no emulator, no network.

### Shared — one router directory

- `api/routes/admin_policy.py` moved to `api/routers/admin_policy.py` and the
  now-empty `api/routes/` package was deleted. The two directories were the same
  concept one letter apart, left over from the workstream merge.
- The moved file is unchanged apart from its location: it keeps its absolute
  `api.…` imports and its own style, so the diff is a rename plus one import
  line in `api/main.py`. No route path, response, guard, or contract changed.
- **B should know.** This moves a B-owned file. Nothing in `workers/policy/` or
  `web/app/admin/policy/` was touched, and `/v1/admin/policy/*` behaves exactly
  as before, but an in-flight branch that edits `api/routes/admin_policy.py`
  will need to re-target the new path. Reasoning in
  [D-011](docs/decisions.md#d-011).
- The other half of D-011 is deliberately **not** done: `require_admin` and
  `Principal` still coexist, because consolidating them changes how a policy
  route authorizes and that wants B's agreement, not just B's awareness.

Verified: `python -m pytest` — 193 passed, including
`tests/policy/test_admin_routes.py`, which exercises the moved router through
the app factory.

### A — material collection card lifecycle

- `GET /v1/projects/{pid}/materials` builds the card list from the
  `p5_form_templates` pack; `POST .../{mid}/attach`, `.../validate`, and
  `.../waive` move a card through its statuses.
- The D3 gate now materialises cards itself, so a pack-defined required card
  blocks the gate even if nobody has opened the collection page.
- Validation is deterministic only — asset attached, asset exists, bytes
  present. Nothing in it is a compliance judgement.
- A waiver requires a reason and records it; a waived card stops blocking.
- Card loading lives in `core/materials.py`, the only module that knows the pack
  layout.
- **B: this proposes a shape for `p5_form_templates`** and writes it into the
  seed with empty contents. See [D-016](docs/decisions.md#d-016) — it needs your
  review before real content is published into that pack. An empty pack yields
  no cards, and a card whose `why_clause_id` is not in the pinned snapshot keeps
  no clause rather than pointing at a missing one.

Verified: `python -m pytest` — 219 passed, 15 new in `tests/test_materials.py`.
Live check against the real seed on a running API: the empty pack returns `[]`
cards and the gate reports only fact gaps — no invented obligations.

### A — upload tickets and immutable asset versions

- `POST /v1/projects/{pid}/assets/upload-url` issues a one-shot ticket;
  `PUT /v1/uploads/{tid}` takes the bytes and writes one `AssetVersion` with its
  own sha256. `GET .../assets` lists them, `GET .../assets/{vid}/content` serves
  the bytes back.
- The ticket names its `backend`: `local` with no bucket configured, `gcs` once
  `GCS_BUCKET` is set. A missing cloud backend is reported, never disguised as a
  cloud upload. Signed-URL issuance slots in behind the same response shape.
- A ticket is single-use — a replayed upload is a 409, not a silent second
  version. A new version of the same `kind` chains onto the previous one via
  `parent_version`; different kinds never chain together.
- Added `BlobStore` and `UploadTicketStore` ports with in-memory adapters, and
  the `UploadTicket` document to `schemas/assets.py`.
- Deliberately **not** here: the material-card list and fact extraction. Both
  need `p4`/`p5` pack content, which is empty. This is the mechanism half only.

Verified: `python -m pytest` — 204 passed, 11 new in `tests/test_uploads.py`
covering sha256, single-use tickets, version chaining, per-kind isolation,
owner scoping, empty-upload rejection, and the timeline entry.


### Shared — Gate 5-a published snapshot read bridge

- Added a narrow policy snapshot repository read seam and a repository-backed
  implementation of the existing product `SnapshotService`.
- Unified FastAPI composition now shares published inline snapshots between
  admin publication and product recalculation while preserving explicit context
  injection and the file-backed standalone fallback.
- Added local HTTP acceptance for `publish v2 -> recalc-tier v2`; event fan-out,
  cloud deployment, and GCS pack resolution remain outside this gate.

Verified: 193 Python tests via `.venv/bin/python -m pytest`; 12 Vitest tests;
Next production build; `compileall`; `pip check`; and wheel packaging including
the new adapter. The live NRTA source smoke returned `PASS`; cloud smoke returned
`SKIP` (`POLICY_CLOUD_CONFIG_MISSING`), so this is not deployed-cloud evidence.

### B — policy loop Gate 4: real cloud adapters and bounded source ingestion

- Added the HTTPS source adapter with a 20-second total timeout, redirect
  validation, streaming 5 MiB limit, and last-known-good preservation on
  failures.
- Added GCS blob storage, Firestore policy state and outbox persistence, Gemini
  structured proposal drafting, and Pub/Sub `policy.updated` publishing behind
  the existing policy-loop interfaces.
- Added environment-based cloud runtime assembly and explicit source/cloud
  smoke commands. A missing named project, resource, credential, or Gemini model
  is reported as `SKIP`, never as cloud success.
- Kept the Gate 4 persistence scope within B-owned collections. **No shared
  schema or product-workflow persistence contract changed in this gate.**

Verified after merging `origin/main`: 186 Python tests via
`.venv/bin/python -m pytest -q`; 12 Vitest tests via `npm --prefix web test`;
`npm --prefix web run build`; `compileall`; `pip check`; and a wheel containing
the policy source, seed snapshot, and proposal prompt. The live NRTA source
smoke returned `PASS`. The cloud smoke returned `SKIP`
(`POLICY_CLOUD_CONFIG_MISSING`), so this is not deployed-cloud evidence.

## 2026-08-23

### A — an unknown snapshot version returned 500 instead of the error envelope (fixed)

`SnapshotNotFoundError` is a `LookupError`, not an `AppError`, so asking
`recalc-tier` for a version the product cannot read crashed the request. It now
returns a 404 in the contract envelope. Found by manually driving the merged
demo: publish v2 through the policy console, then call `recalc-tier` with
`snapshot_version: v2`.

**Shared, and blocking the closed loop:** that call is *supposed* to succeed. The
product reads policy through `FileSnapshotService`, which only knows
`policy/seed-snapshot-v1.yaml`, while the policy loop publishes new snapshots
into its own repository. Nothing yet bridges the two, so a published v2 is
invisible to the product side. See [D-012](docs/decisions.md#d-012).


### Shared — policy loop merged with the product workflow (PR #7)

Both workstreams now run as one FastAPI process and one Next.js app.

- `create_app` is keyword-only: `create_app(*, context=None, policy_state=None)`.
  Product and policy state no longer compete for the first positional argument.
  **Breaking for callers:** three call sites in `tests/policy/test_admin_routes.py`
  were updated. See [D-008](docs/decisions.md#d-008).
- The web app is unified: Richard's `globals.css` design system is the base, the
  product shell (top bar, role switcher, disclaimer) wraps every page including
  the policy console. React moves to 19.2.8; Next stays 16.3.2.
- Dependencies merged. `fastapi` and `uvicorn` became base dependencies, so the
  `api` extra is gone: install with `pip install -e ".[test]"`.
- **The policy UI now calls port 8080**, not 8000. One process serves both
  sides, and 8080 is the port in contract section 8. The client falls back
  through `NEXT_PUBLIC_POLICY_API_BASE_URL`, `NEXT_PUBLIC_API_BASE`, then
  `http://localhost:8080`. See [D-009](docs/decisions.md#d-009).

Verified: 114 Python tests, 12 vitest tests, `next build` produces all routes
from both workstreams, and one process answers `/v1/projects/...` and
`/v1/admin/policy/...` with the shared error envelope.

### B — `FileBlobStore` could not read its own URIs on Windows (fixed)

`_path_from_uri` built its path from `urlparse(uri).path`, which on Windows
keeps the slash before the drive letter. `Path("/D:/x")` is then read as the
drive-relative `D:x`, every containment check failed, and 11 policy tests
errored. Reproduced on an unmodified `origin/main` worktree, so it predates the
merge. Fixed with `url2pathname`, correct on both platforms.

Verified: the 11 failures became passes; the full suite is green on Windows.

### B — `httpx2` did not satisfy Starlette's test client (fixed)

The test extra declared `httpx2>=2.12`. That distribution ships a module named
`httpx2`, while Starlette's `TestClient` imports `httpx`, so the policy tests
could not run from a clean clone — which is a Devpost reproducibility
requirement. The extra now declares `httpx>=0.27,<1`.

### A — product workflow core, intake and classification API (T-A0, T-A1, T-A2)

- **T-A0**: FastAPI app with the contract error envelope and `GET /healthz`,
  settings for every variable in contract section 8, `docker-compose.yml` for
  the Firestore and Pub/Sub emulators, `python -m workers.hello` as the Vertex
  wiring check, and the Next.js shell (`/wizard`, `/dashboard`, `/admin`).
- **T-A1**: the full enum table in `schemas/enums.py` (mirrored in
  `web/lib/enums.ts`), every TDD section 2 document, the 21-state machine with
  entry guards and audit plus timeline on each transition, and the D3 gate as a
  pure function returning machine-readable gaps. Storage ports with an
  in-memory adapter.
- **T-A2**: D1a, D1b, and D1c with the chain that pins one snapshot version;
  routes for intent, channels, classify, tier-choice, gate, and timeline.
- **Ahead of plan, and B depends on it:** `/v1/internal/projects/{pid}/recalc-tier`
  is a real implementation rather than the stub the plan asked for by D5. It
  recalculates only provisional tiers and refuses to touch frozen,
  institution-stage, or filed projects. The policy consumer can call it directly
  instead of its fake adapter. Needs `X-Internal-Token`; returns
  `{tier, tier_provisional, changed}`.
- New top-level packages `core/` and `store/`; see [D-001](docs/decisions.md#d-001).

Verified: 67 tests at the time of the commit, no credentials or network needed.
`scripts/e2e_check.py` walks the golden path against a running API and reports
each contract section 7 step as PASS, FAIL, or PENDING with its owning task.

Not verified: the real Gemini call and the emulator stack. Neither gcloud nor
Docker is installed on the development machine.

### A — D1c reads `thresholds_published` from the p3 pack

The seed snapshot now carries `thresholds_published` inside `p3_tier_thresholds`.
D1c and the workflow service read that key alongside the older
`official_published` spelling, so a published-threshold snapshot flips
provisional tiers as intended.

### B — policy loop Gate 3: administration API and UI (PR #6)

`/v1/admin/policy` exposes launch-refresh, run status, proposal list and detail,
publish, discard, and snapshot history, guarded by `X-Mock-Role: admin`. The
Next.js console lists proposals and shows a side-by-side diff with a publish
control. Run failure details are redacted before they reach a response.

Scope limit stated by the author: deterministic fixture data, mock
authorization, and process-local state that resets to seed v1 on restart.

### B — policy loop Gate 2: offline refresh, proposal, publish (PR #5)

Fixture fetch, normalization, diff, proposal creation, publish with an outbox,
outbox dispatch, and an idempotent `policy.updated` consumer. A twelve-step
offline acceptance test covers the loop end to end.

**Still open for B:** the consumer calls a fake recalc adapter rather than the
live A-line endpoint above. Wiring it is the demo's highlight shot.

### B — policy loop Gate 1: shared contracts and seed snapshot (PR #4)

`schemas/policy_snapshot.py`, `policy/seed-snapshot-v1.yaml`, the
`SnapshotService` read interface with a file adapter, and the contract tests.
This is the one hard dependency between the workstreams, and it landed first as
planned.

## 2026-08-22

### Shared — repository scaffold (PR #1, PR #2)

Directory ownership, boundary rules, and the workstream split.
