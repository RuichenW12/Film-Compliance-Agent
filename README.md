# Film Compliance Agent

Film Compliance Agent is a planned workflow for helping micro-drama creators and licensed institutions prepare compliance reviews and filing materials. The product path combines deterministic gates, evidence-linked AI review, human confirmation, and versioned policy snapshots.

> Repository status: structure and ownership scaffold only. Runtime services, models, UI, infrastructure, and policy data have not been implemented yet.

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

## First milestone

The first repository milestone is a contract-level handshake: the product workstream can load a validated seed snapshot, while the policy workstream can emit a validated `policy.updated` fixture. No live crawler or cloud deployment is required for that handshake.
