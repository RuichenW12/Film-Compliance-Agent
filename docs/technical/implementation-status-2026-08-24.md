# Implementation status by owner — 2026-08-24

Scope source of truth: API & interface contract v1, TDD v1, and the
[Richard policy loop v1 scope](../superpowers/specs/2026-08-22-richard-policy-loop-v1-design.md).
Ownership source of truth: the workstream table in [`README.md`](../../README.md)
and the boundary rules in [`CLAUDE.md`](../../CLAUDE.md).

Status vocabulary, used strictly:

- ✅ **done** — implemented and covered by a check that was actually run;
- ⚠️ **partial** — code exists but a named part of the item is missing or has
  never executed in the environment it targets;
- ❌ **not started** — no implementation.

Evidence behind every ✅ below: `python -m pytest` (202 passed),
`npm --prefix web test` (17 passed), and a live `python scripts/e2e_check.py`
run against `uvicorn api.main:app` with `INTERNAL_TOKEN` set (ALL CHECKS
PASSED). No cloud credentials, no emulator, no network.

Updated 2026-08-24 after the notification slice landed; the rows it changed name
the commit's files.

## Ownership key

| Owner | Meaning |
|---|---|
| **Maxine (A)** | Product workflow. Owns `api/routers/`, `core/`, `store/`, `web/app/{wizard,dashboard}`, `web/lib/api.ts` |
| **Richard (B)** | Policy loop. Owns `workers/policy/`, `api/routers/admin_policy.py`, `web/app/admin/policy/`, `policy/` |
| **Shared** | `schemas/` — the contract boundary. Changes need both owners |

Boundary rule that decides the ambiguous rows: B does not edit product code and
reaches the product only through `/v1/internal/*`; A does not edit
`workers/policy/` or `web/app/admin/policy/`.

## Workstream A — product workflow (Maxine)

| Task | Sub-item | Owner | Status | Where |
|---|---|---|---|---|
| **T-A0** | FastAPI app, contract error envelope, `GET /healthz` | Maxine | ✅ | `api/main.py`, `api/routers/health.py` |
| | `settings.py` reads contract §8 environment | Maxine | ✅ | `api/settings.py`, `.env.example` |
| | `SnapshotService` + file adapter over seed v1 | Shared | ✅ | `schemas/snapshot.py` |
| | Next.js shell, role switcher, English UI with glossed Chinese terms | Maxine | ✅ | `web/app/`, `web/lib/demoAuth.ts` |
| | Vertex wiring check `python -m workers.hello` | Maxine | ⚠️ | code only — `gcloud` is not installed, never run |
| | docker-compose emulator stack (Firestore 8791, Pub/Sub 8792) | Maxine | ⚠️ | code only — Docker is not installed, never run |
| **T-A1** | Enum table + TypeScript mirror | Shared | ✅ | `schemas/enums.py`, `web/lib/enums.ts` |
| | Domain documents: project, assets, facts, findings, forms, workflow | Shared | ✅ | `schemas/*.py` |
| | Model invariants: evidence_refs, SourceRef, frozen hash, registration number | Shared | ✅ | `tests/test_guards.py` |
| | State machine, 21 states, entry guards, audit + timeline on transition | Maxine | ✅ | `core/state_machine.py` |
| | D3 gate as a pure function returning machine-readable gaps | Maxine | ✅ | `core/gate.py` |
| | Storage ports + in-memory adapter | Maxine | ✅ | `core/repositories.py`, `store/memory.py` |
| | Firestore adapter behind the same ports | Maxine | ❌ | `store/` contains only `memory.py` |
| **T-A2** | D1a, D1b, D1c, and the chain pinning one snapshot version | Maxine | ✅ | `core/classify/` |
| | Intake routes: create, read, intent, channels, classify, tier-choice, gate, timeline | Maxine | ✅ | `api/routers/projects.py` |
| | `POST /v1/internal/.../recalc-tier` behind `X-Internal-Token` | Maxine | ✅ | `api/routers/internal.py` — the endpoint T-B3 calls |
| | `POST /v1/internal/.../policy-stale` | Maxine | ✅ | `api/routers/internal.py` |
| **T-A3** | Roadmap templates and `roadmap/confirm` (contract step 5) | Maxine | ❌ | no route |
| | Material collection cards | Maxine | ❌ | schema only |
| | Upload URLs and asset-version records (step 6) | Maxine | ❌ | no route |
| | `FactExtractor` for title / applicant_entity / investment_structure | Maxine | ❌ | not written — these are the three `facts_missing` the gate reports |
| **T-A4** | C1-a script pre-check with the golden-sample harness (step 8) | Maxine | ❌ | `tests/golden/` holds a README only |
| **T-A5** | Finding actions and incremental review (step 9) | Maxine | ❌ | |
| | Form freeze, field confirm, hash (step 11) | Maxine | ❌ | model invariant exists, no route |
| **T-A6** | Institution console and filing (steps 12–14) | Maxine | ❌ | |
| **T-A7** | Veo teaser (step 18) | Maxine | ❌ | `flags.veo_teaser=false` |
| **cross** | Timeline read (step 17) | Maxine | ✅ | `GET /v1/projects/{pid}/timeline` |
| | Notification producer and reads (step 17) | Maxine | ✅ | producer in `core/workflow_service.py`, routes in `api/routers/notifications.py`, inbox on `/dashboard` ([D-014](../decisions.md#d-014)) |
| | Task reads (step 17) | Maxine | ❌ | `WorkflowTask` schema only |
| | LLM port, and "missing backend is a pending flag, not a pass" | Maxine | ✅ | `core/llm.py`; `core/llm_vertex.py` never run live |

## Workstream B — policy loop (Richard), against the 11 P0 items

| # | P0 item | Owner | Status | Where |
|---|---|---|---|---|
| 1 | PolicySnapshot / PolicyProposal / PolicyUpdatedEvent contracts | Shared | ✅ | `schemas/policy_snapshot.py`, `tests/contract/` |
| 2 | Seed snapshot readable by A's `SnapshotService` | Richard | ✅ | `policy/seed-snapshot-v1.yaml`; Gate 5-a repository bridge |
| 3 | `effective_from` validation and current-snapshot selection | Richard | ✅ | both adapters filter `effective_from <= now`; `workers/policy/publish.py:54` refuses a future publish |
| 4 | Real source crawl, GCS archive, normalization, diff | Richard | ⚠️ | code complete; **real NRTA source smoke `PASS`, cloud smoke `SKIP`** |
| 5 | Fixture-driven proposal generation | Richard | ✅ | `adapters/fixture_source.py`, `fake_proposal.py`; `gemini_proposal.py` never run live |
| 6 | Policy administration UI | Richard | ✅ | `web/app/admin/policy/`, `web/components/policy/` |
| 7 | Human publish transaction and minimal outbox | Richard | ✅ | `workers/policy/publish.py`, `outbox.py` |
| 8 | Idempotent `policy.updated` consumer | Richard | ⚠️ | `consumer.py` runs against a fake recalc adapter; **not wired to the live endpoint** — see [D-010](../decisions.md#d-010) |
| 9 | `policy_stale` and `tier_recalculated` notifications + timeline events | Split | ⚠️ | A's half done: both notifications are produced and readable. **B's half open** — the consumer must call the live internal endpoints ([D-010](../decisions.md#d-010), [D-014](../decisions.md#d-014)) |
| 10 | Cloud Run Job, Pub/Sub, Cloud Scheduler, manual trigger | Richard | ⚠️ | manual trigger ✅, Pub/Sub adapter ✅, **no deployed infrastructure** |
| 11 | Provisional vs frozen / FILED contrast tests | Richard | ✅ | `tests/policy/test_consumer.py:76,96`, `tests/test_api_intake.py:162` |

Gate history: Gates 1–3 ✅. Gate 4 is *implementation-complete* but **not passed** —
passing needs a named-project cloud smoke reporting GCS, Firestore, Gemini, and
Pub/Sub all `PASS`. Gate 5-a ✅. Gate 5-b open.

## The seam between the two workstreams

The loop is closed on paper and open in wiring.

| Seam item | Owner | State |
|---|---|---|
| `publish v2 → recalc-tier v2` reads the same snapshot | Shared | ✅ Gate 5-a, local HTTP only |
| `policy.updated` delivered from B's outbox to A's `/v1/internal/*` | Richard (T-B3, [D-010](../decisions.md#d-010)) | ❌ |
| Project enumeration and impact filtering | Richard | ❌ |
| `policy_stale` / `tier_recalculated` notification fan-out | Split: B triggers, A produces and serves | ⚠️ A's half done, B's half open |
| One router directory, one auth helper | Shared ([D-011](../decisions.md#d-011)) | ⚠️ one directory done, the two auth helpers remain |

## What has never executed anywhere

Three areas are written but unverified in the environment they target, on this
machine because neither `gcloud` nor Docker is installed:

1. the real Gemini call — `python -m workers.hello`, `core/llm_vertex.py`, `adapters/gemini_proposal.py`;
2. the Firestore and Pub/Sub emulator stack — `docker compose up`;
3. any cloud deployment — Cloud Run Job, Cloud Scheduler, a named-project cloud smoke.

Every green result in this document is credential-free, in-memory, and local. A
fixture, fake, emulator, or skipped command is not evidence of a deployed
system.

## Next step per owner

- **Maxine:** T-A3 (roadmap templates, collection cards, upload URLs,
  `FactExtractor`), then T-A4. Nothing needs manual setup first — T-A3 builds
  and tests in memory, and the `FactExtractor` should be written against the LLM
  port's unavailable-backend path before real Vertex is wired. The Firestore
  adapter can slot in behind the ports at any time; nothing is blocked on it and
  Docker is not installed here to verify it.
- **Richard:** Gate 5-b — wire the consumer to the live recalc endpoint per
  [D-010](../decisions.md#d-010), add project enumeration and impact filtering,
  then the notification trigger. The named-project cloud smoke is what turns
  Gate 4 from implementation-complete into passed.
