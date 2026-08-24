# Product workflow v1 — implementation status (workstream A)

Date: 2026-08-23 · Owner: Maxine · Source of truth for scope: API & interface contract v1, TDD v1.

This note records what is running, how it was verified, and what is still assumed. A documented design is not proof of a running system; everything below is backed by tests in `tests/`.

## Delivered

### T-A0 — skeleton and snapshot access

- `api/main.py` FastAPI app with the contract error envelope, `GET /healthz` reporting the pinned snapshot version, the LLM backend, and feature flags.
- `api/settings.py` reads the environment variables in contract section 8; `.env.example` documents them.
- `docker-compose.yml` + `infra/api.Dockerfile` bring up Firestore (8791) and Pub/Sub (8792) emulators alongside the API (8080).
- Policy is read only through `SnapshotService`; the file adapter serves `policy/seed-snapshot-v1.yaml`. Packs are returned as copies so product code cannot mutate policy.
- `workers/hello.py` (`python -m workers.hello`) is the Vertex wiring check.
- `web/` Next.js App Router shell: `/wizard`, `/dashboard`, `/admin`, role switcher, English UI with glossed Chinese legal terms.

**Not verified locally:** the real Gemini call and the emulator compose stack. Neither `gcloud` nor Docker is installed on this machine, so `python -m workers.hello` and `docker compose up` are unrun. Everything else runs without credentials.

### T-A1 — models, state machine, guards

- `schemas/enums.py` is the full enum table from contract section 2; `web/lib/enums.ts` mirrors it.
- Domain documents in `schemas/`: project (with intent, channel, classification, roadmap), asset versions, material cards, facts, findings with the five-field alert, form drafts, tasks, notifications, institution reviews, mock institutions.
- Model-level invariants: a finding asserting a conclusion without `evidence_refs` is rejected; a filled form field without a `SourceRef` is rejected; a confirmed fact cannot be null; a frozen draft needs a hash; a FILED project needs a registration number.
- `core/state_machine.py` holds the transition table for all 21 states, entry guards, and audit + timeline emission on every transition.
- `core/gate.py` implements D3 as a pure function returning machine-readable gaps: `open_blocks`, `alerts_undispatched`, `findings_needs_human`, `facts_missing`, `facts_conflicting`, `materials_unvalidated`.
- Storage ports in `core/repositories.py`; in-memory adapter in `store/memory.py`. The Firestore adapter is the next step and slots in behind the same ports.

### T-A2 — classification chain and API

- `core/classify/` implements D1a (pure rules plus an edge-phrase read), D1b (deterministic pattern match, then one semantic pass), D1c (pure function on thresholds), and the chain that pins one snapshot version.
- Routes: `POST /v1/projects`, `GET /v1/projects/{pid}`, `POST .../intent`, `POST .../channels`, `POST .../classify`, `POST .../tier-choice`, `GET .../gate`, `GET .../timeline`.
- `POST /v1/internal/projects/{pid}/recalc-tier` is live behind `X-Internal-Token` — this is the endpoint the policy loop needs for T-B3. It is a real implementation, not a stub: it recalculates only provisional tiers and refuses to touch frozen, institution-stage, or filed projects.
- `POST /v1/internal/projects/{pid}/policy-stale` marks a project stale without touching its classification.

## Acceptance evidence

`python -m pytest` — 114 tests after the policy-loop merge (67 product, 47 policy and contract), all green, no cloud access required.

| Acceptance criterion | Test |
|---|---|
| Narcotics profile → T1 + co-review, with a verbatim quote | `test_classify.py::test_special_subject_profile_is_t1_with_co_review` |
| Ordinary series → tier by band, marked provisional | `test_classify.py::test_ordinary_series_gets_provisional_tier` |
| Single vlog → EXIT_NON_DRAMA with the AI-labeling duty | `test_classify.py::test_single_video_exits_as_non_drama` |
| Prompt injection in the logline has no effect | `test_classify.py::test_instructions_inside_the_logline_are_data_not_commands` |
| Chain completes well under 5s | `test_classify.py::test_chain_stays_well_under_the_five_second_budget` |
| Undispatched alert counts as blocking at D3 | `test_guards.py::test_undispatched_alert_counts_as_blocking` |
| Four rejection branches plus the passing branch | `test_guards.py` (open blocks, alerts, facts, materials, pass) |
| Every transition writes an audit entry | `test_guards.py::test_transition_writes_an_audit_entry` |
| recalc-tier body parses under the shared contract model | `test_api_intake.py::test_recalc_tier_response_matches_the_shared_contract` |

## Decisions taken while implementing

1. **`core/` and `store/` were added** to the TDD section 9 layout. Pure product logic must be importable by both `api/` and `workers/` without either importing the other, and `schemas/` stays models-only. No shared contract moved.
2. **Seed pack p2 has no trigger text.** The v1 seed names the nine statutory categories but carries no patterns, so `core/classify/subject_rules.py` attaches an operational keyword list and marks every derived rule `expert_pending=True` (locked decision 5a). The UI shows a "rules pending expert confirmation" badge. Partner-reviewed rules replace this list wholesale — the loader already accepts the richer `subject_rules: [...]` shape the policy loop will publish.
3. **Band-to-tier mapping is a placeholder.** With amount thresholds unpublished, `band_a/b/c → T1/T2/T3` and every such tier is `tier_provisional=true`. Unknown band assumes the stricter tier (T2) and returns a comparison card, non-blocking.
4. **No LLM backend means pending, not pass.** Without Vertex configuration the semantic stages add `edge_phrase_check_pending` / `subject_semantic_check_pending` to the classification instead of implying a clean result.
5. **Role header.** The contract names `X-Mock-Role`; locked decision 2 named `X-Demo-Role`. `api/deps/demo_auth.py` accepts both, contract name first.

## Open with the policy workstream

1. **`recalc-tier` response shape.** Settled as [D-006](../decisions.md#d-006): the shared model stays untouched, the body keeps exactly the three contract fields, and the reason travels in the `X-Recalc-Reason` header and the timeline. Nothing consumes a body `reason` today.
2. **Required facts for the gate.** `core/gate.py` defaults to `title, episode_count, episode_minutes, applicant_entity, investment_structure`, overridable from `p5_form_templates.required_facts`. Once the form template pack carries real fields, the default should stop being used.
3. **Impact node vocabulary.** Settled as [D-007](../decisions.md#d-007): `ImpactNode` stays at `D1c` and `C1-a` for the submission. The demo only exercises a tier-threshold change, and extending a frozen enum touches publisher, consumer, and fixtures on both sides. Revisit at the first policy update that alters p1 or p4.

## Merge with the policy loop (2026-08-23)

`origin/main` at Gate 3 was merged into the product branch. Both workstreams now
run as one FastAPI process and one Next.js app. Decisions taken while resolving,
all of which touch Richard's files and want his review:

1. **One app factory.** `create_app` became keyword-only:
   `create_app(*, context=None, policy_state=None)`. Product state and policy
   state no longer compete for the first positional argument. The three call
   sites in `tests/policy/test_admin_routes.py` were updated.
2. **One API port.** The policy client defaulted to `http://127.0.0.1:8000`,
   which points at nothing once both sides share a process. It now falls back
   through `NEXT_PUBLIC_POLICY_API_BASE_URL`, then `NEXT_PUBLIC_API_BASE`, then
   `http://localhost:8080` — the port named in contract section 8. The two URL
   assertions in `web/tests/policy-api.test.ts` were updated.
3. **`httpx2` does not satisfy `httpx`.** The test extra declared
   `httpx2>=2.12`, whose distribution ships a module named `httpx2`. Starlette's
   `TestClient` imports `httpx`, so on a clean clone the policy tests could not
   run — which matters for the Devpost reproducibility requirement. The merged
   `pyproject.toml` declares `httpx>=0.27,<1`.
4. **Windows file URIs.** `FileBlobStore._path_from_uri` used
   `Path(unquote(urlparse(uri).path))`. On Windows that yields `/D:/...`, which
   `Path` reads as the drive-relative `D:...`, so every containment check failed
   and 11 policy tests errored. Verified pre-existing on an unmodified
   `origin/main` worktree, not introduced by the merge. Fixed with
   `url2pathname`, which is correct on both platforms.
5. **One stylesheet and shell.** Richard's `globals.css` design system is the
   base; the product shell classes were appended using his tokens. The product
   layout (top bar, role switcher, disclaimer) now wraps the policy pages too.
6. **Two router directories.** `api/routes/` (policy) and `api/routers/`
   (product) both exist. Nothing breaks, but one of them should be renamed once
   we agree which. **Resolved 2026-08-24:** `api/routers/` won; `admin_policy.py`
   moved and `api/routes/` is gone. See [D-011](../decisions.md#d-011).
7. **Two auth helpers.** `api/deps/policy.require_admin` reads `X-Mock-Role`
   directly; `api/deps/demo_auth.Principal` covers the product routes. Worth
   consolidating on the `Principal` dependency.

Merged verification: 114 Python tests and 12 vitest tests pass, `next build`
produces all routes from both workstreams, and one process answers both
`/v1/projects/...` and `/v1/admin/policy/...`.

Note when building the web app after running `next dev`: the tsconfig includes
`.next/dev/types/**/*.ts`, and stale dev route types make `next build` fail type
checking. `rm -rf web/.next` before building clears it.

## Next

`Firestore adapter behind the existing ports → T-A3 (roadmap templates, collection cards, upload URLs, FactExtractor) → T-A4 (C1-a scene review with the golden-sample harness)`.
