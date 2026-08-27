# Film Compliance Agent

Film Compliance Agent is a workflow for helping micro-drama creators and licensed institutions prepare compliance reviews and filing materials. The product path combines deterministic gates, evidence-linked AI review, human confirmation, and versioned policy snapshots.

> Repository status, workstream A (product): shared contracts, the workflow core (state machine, D3 gate, D1a/D1b/D1c classification chain), the intake and classification API, and the web shell are implemented and unit-tested against the static seed snapshot. Not yet built: material collection, script review (C1-a), form freeze, institution console, and cloud deployment.
>
> Repository status, workstream B (policy loop): Gates 1–3 provide the deterministic local policy demo. Gate 4 adds real HTTP, GCS, Firestore, Gemini, and Pub/Sub adapters behind the same policy-loop interfaces. The real NRTA source smoke passes locally; the full-cloud smoke is currently `SKIP` without named project configuration and credentials. This is not a deployed-cloud PASS.

## Workstreams

| Workstream | Owner | Scope |
|---|---|---|
| A — Product workflow | Maxine | Intake, classification, material collection, script review, form preparation, institution workflow, and the main product UI |
| B — Policy loop | Richard | Policy sources and seed snapshots, policy refresh worker, change proposals, policy administration UI, snapshot publishing, update consumption, policy notifications, and policy deployment wiring |

The workstreams meet through shared contracts in [`schemas/`](schemas/README.md). Product code develops against the static seed snapshot and does not wait for the live policy refresh loop.

## Local spin-up

The test suite and the API run with no credentials, no emulator, and no network: the snapshot comes from the YAML seed, storage is in-memory, and the LLM backend reports itself unavailable rather than guessing.

```bash
pip install -e ".[test]"         # 1. install
python -m pytest                 # 2. verify  (all green, no cloud access needed)
uvicorn api.main:app --port 8080 # 3. run     (http://localhost:8080/healthz)
```

With the API running, `python scripts/e2e_check.py` walks the golden path against the live service and prints, step by step, what works today and which task delivers each step that does not.

The web shell runs separately:

```bash
cd web && npm install && npm run dev   # http://localhost:3000
```

Emulator-backed runs (Firestore on 8791, Pub/Sub on 8792) use `docker compose up`. Copy `.env.example` to `.env` first.

To exercise a real Gemini call through Vertex AI, install the optional client,
choose the project, location, and model available to your account, and create
Application Default Credentials (ADC). Keep credentials outside the repository:

```bash
python -m pip install -e '.[vertex]'

export GOOGLE_CLOUD_PROJECT="your-google-cloud-project-id"
export REGION="your-vertex-location"
export VERTEX_MODEL_GEMINI="your-gemini-model-id"

gcloud auth application-default login
gcloud auth application-default set-quota-project "$GOOGLE_CLOUD_PROJECT"

python -m workers.hello
```

If another local service occupies the OAuth callback port, use
`gcloud auth login --no-launch-browser --update-adc` instead, then set the ADC
quota project as shown above. A successful smoke test prints a JSON greeting
and the selected model and location; it verifies connectivity, not a compliance
judgement.

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
| [`tools/`](tools/partner-review/README.md) | One-shot generators run by hand. Not imported by the product |
| [`docs/`](docs/README.md) | Architecture decisions, runbooks, and delivery notes |

## Tracking changes

Two workstreams share this repository and work in parallel, so every change that
the other side could trip over is written down:

- [`CHANGELOG.md`](CHANGELOG.md) — what changed, when, and who owns it.
- [`docs/decisions.md`](docs/decisions.md) — why, and when a choice should be revisited.

Whoever makes the change writes the entry, in the same pull request.

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
- **Only a human publishes policy.** AI drafts a proposal; the administration UI is the single publish path.

## Implemented local milestone

The product workstream loads a validated seed snapshot and runs the full intake → classification path on top of it. The policy workstream runs a deterministic fixture refresh, reviews the resulting proposal, publishes a new snapshot, and emits a validated `policy.updated` event, all through a local API and UI. See [`api/`](api/README.md), [`web/`](web/README.md), and [`tests/`](tests/README.md) for commands and verification boundaries.

- Gate 5-a snapshot bridge: the unified API injects the policy repository into
  the existing product `SnapshotService`, so an admin-published inline snapshot
  is available to `recalc-tier` without a second write path.

## Gate 4 cloud adapters

Install the default local/test environment or the optional cloud SDKs separately:

```bash
python -m pip install -e '.[test]'
python -m pip install -e '.[test,cloud]'
```

Cloud assembly reads these environment variables by name; no credentials or service-account files belong in the repository:

- required: `GOOGLE_CLOUD_PROJECT`, `POLICY_GCS_BUCKET`, `POLICY_PUBSUB_TOPIC`;
- optional: `GOOGLE_CLOUD_LOCATION`, `POLICY_GEMINI_MODEL`, `FIRESTORE_DATABASE`.

Run the source-only and credential-gated checks with:

```bash
.venv/bin/python scripts/policy_gate4_smoke.py --source
.venv/bin/python scripts/policy_gate4_smoke.py --cloud
```

`PASS` means every check required by that selected mode ran successfully. `FAIL` means a required stage ran and failed. `SKIP` means prerequisites were absent, so the command is not evidence of success. Gate 4 is implementation-complete only after automated checks, the real-source smoke, packaging, and review are clean. Gate 4 is passed only after the named-project cloud smoke reports GCS, Firestore, Gemini, and Pub/Sub all as `PASS`.

Gate 4 does not deploy infrastructure and does not add Maxine-owned project, notification, timeline, or `recalc-tier` persistence. Those integration boundaries remain Gate 5 work.
