# Film Compliance Agent

Film Compliance Agent is a workflow for helping micro-drama creators and licensed institutions prepare compliance reviews and filing materials. The product path combines deterministic gates, evidence-linked AI review, human confirmation, and versioned policy snapshots.

> Repository status: the shared contracts, the product workflow core (state machine, D3 gate, D1a/D1b/D1c classification chain), the intake and classification API, and the web shell are implemented and unit-tested against the static seed snapshot. Not yet built: material collection, script review (C1-a), form freeze, institution console, the policy refresh loop, and cloud deployment.

## Workstreams

| Workstream | Owner | Scope |
|---|---|---|
| A — Product workflow | Maxine | Intake, classification, material collection, script review, form preparation, institution workflow, and the main product UI |
| B — Policy loop | Richard | Policy sources and seed snapshots, policy refresh worker, change proposals, policy administration UI, snapshot publishing, update consumption, policy notifications, and policy deployment wiring |

The workstreams meet through shared contracts in [`schemas/`](schemas/README.md). Product code develops against the static seed snapshot and does not wait for the live policy refresh loop.

## Local spin-up

The test suite and the API run with no credentials, no emulator, and no network: the snapshot comes from the YAML seed, storage is in-memory, and the LLM backend reports itself unavailable rather than guessing.

```bash
pip install -e ".[api,test]"     # 1. install
python -m pytest                 # 2. verify  (all green, no cloud access needed)
uvicorn api.main:app --port 8080 # 3. run     (http://localhost:8080/healthz)
```

With the API running, `python scripts/e2e_check.py` walks the golden path against the live service and prints, step by step, what works today and which task delivers each step that does not.

The web shell runs separately:

```bash
cd web && npm install && npm run dev   # http://localhost:3000
```

Emulator-backed runs (Firestore on 8791, Pub/Sub on 8792) use `docker compose up`. Copy `.env.example` to `.env` first.

To exercise a real Gemini call, set `GOOGLE_CLOUD_PROJECT`, `REGION`, and `VERTEX_MODEL_GEMINI`, run `gcloud auth application-default login`, then:

```bash
python -m workers.hello
```

## Repository map

| Path | Responsibility |
|---|---|
| [`api/`](api/README.md) | Product-facing and internal HTTP boundaries |
| `core/` | Pure product logic: state machine, guards, D3 gate, classification chain, LLM port. No I/O |
| `store/` | Storage adapters implementing the ports in `core/repositories.py` |
| [`workers/`](workers/README.md) | Asynchronous workers and agent jobs |
| [`workers/policy/`](workers/policy/README.md) | Richard's policy refresh, proposal, publish, and update-consumer runtime |
| [`web/`](web/README.md) | Product and administration UI |
| [`web/app/admin/policy/`](web/app/admin/policy/README.md) | Richard's policy administration UI boundary |
| [`schemas/`](schemas/README.md) | Shared models and A/B interface contracts |
| [`policy/`](policy/README.md) | Policy source configuration and versioned seed/snapshot assets |
| [`prompts/`](prompts/README.md) | Versioned model prompt contracts |
| [`tests/`](tests/README.md) | Contract fixtures, policy scenarios, and golden samples |
| [`infra/`](infra/README.md) | Deployment and cloud-resource definitions |
| [`docs/`](docs/README.md) | Architecture decisions, runbooks, and delivery notes |

## Boundary rules

1. `schemas/` is the single shared contract boundary. Changes that affect both workstreams require review from both owners.
2. `policy/` contains policy inputs and snapshot-shaped data; executable policy behavior belongs in `workers/policy/`.
3. AI may draft policy changes, but only the policy administration UI may publish a snapshot after human confirmation.
4. A policy update may mark projects stale and recalculate provisional classifications. It must not rewrite frozen forms, submitted materials, or registration numbers.
5. Unknown legal, organization, amount, or license fields remain unknown until a source or human confirms them.

## Ground rules the code enforces

- **State is deterministic.** Every transition goes through `core.state_machine.transition()`, which checks guards and writes an audit entry. Agents propose; they never mutate state.
- **Conclusions carry evidence.** A finding or classification that asserts a compliance conclusion without `evidence_refs` into the pinned snapshot is rejected at the model boundary.
- **Unknown stays unknown.** A form field without a `SourceRef` renders as `待补充`; the model layer refuses to mark it filled.
- **Uploaded text is data, not instructions.** Script and logline content is wrapped in `<<<DOC>>>` markers, and any model hit whose quote does not occur verbatim in the document is discarded.
- **Missing model backend is reported, not faked.** With no Vertex configuration the semantic stages emit a pending flag instead of an implied clean result.

## First milestone

The first repository milestone is a contract-level handshake: the product workstream can load a validated seed snapshot, while the policy workstream can emit a validated `policy.updated` fixture. That handshake is green, and the product side now runs the full intake → classification path on top of it.
