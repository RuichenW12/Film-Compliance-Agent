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

## 2026-08-24

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
