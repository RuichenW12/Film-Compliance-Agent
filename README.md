# Film Compliance Agent

Film Compliance Agent is a planned workflow for helping micro-drama creators and licensed institutions prepare compliance reviews and filing materials. The product path combines deterministic gates, evidence-linked AI review, human confirmation, and versioned policy snapshots.

> Repository status: Gates 1–3 provide the deterministic local policy demo. Gate 4 adds real HTTP, GCS, Firestore, Gemini, and Pub/Sub adapters behind the same policy-loop interfaces. The real NRTA source smoke passes locally; the full-cloud smoke is currently `SKIP` without named project configuration and credentials. This is not a deployed-cloud PASS.

## Workstreams

| Workstream | Owner | Scope |
|---|---|---|
| A — Product workflow | Maxine | Intake, classification, material collection, script review, form preparation, institution workflow, and the main product UI |
| B — Policy loop | Richard | Policy sources and seed snapshots, policy refresh worker, change proposals, policy administration UI, snapshot publishing, update consumption, policy notifications, and policy deployment wiring |

The workstreams meet through shared contracts in [`schemas/`](schemas/README.md). Product code must be able to develop against a static seed snapshot without waiting for the live policy refresh loop.

## Repository map

| Path | Responsibility |
|---|---|
| [`api/`](api/README.md) | Product-facing and internal HTTP boundaries |
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

## Implemented local milestone

The product workstream can load a validated seed snapshot, while the policy workstream can run a deterministic fixture refresh, review the resulting proposal, publish a new snapshot, and emit a validated `policy.updated` event. The administration flow is exposed through a local API and UI. See [`api/`](api/README.md), [`web/`](web/README.md), and [`tests/`](tests/README.md) for commands and verification boundaries.

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
