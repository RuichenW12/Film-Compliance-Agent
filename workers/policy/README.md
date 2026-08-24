# Policy Workers

Owner: Richard

This is the main runtime workspace for Workstream B. It contains executable policy-loop behavior; source configuration and seed/snapshot data belong in the repository-level [`policy/`](../../policy/README.md) directory.

## Modules

| Module | Responsibility |
|---|---|
| Policy refresh | Normalize configured fixture sources, archive local content, and produce deterministic diffs and proposals |
| Proposal adapter | Return a deterministic schema-validated draft during Gate 2 |
| Publisher | Validate a human-approved proposal and create the next policy snapshot |
| Outbox dispatcher | Publish committed `policy.updated` events without coupling event delivery to snapshot persistence |
| Update consumer | Mark affected projects stale and request recalculation only for provisional classifications |
| Local assembly | Connect the Gate 2 adapters for same-process acceptance tests |

## Dependencies

- Inputs: `policy/policy_sources.yaml`, the previous normalized source, shared schemas, and approved proposal data.
- Outputs: policy proposals, policy snapshots, outbox records, `policy.updated`, notifications, and timeline events.
- A-line dependency: the internal `recalc-tier` endpoint. This worker must not reimplement classification rule D1c.

## Safety boundary

- A model may draft a proposal but cannot publish it.
- Failed fetches keep serving the last known good snapshot.
- Policy events must be idempotent.
- Frozen forms, submitted materials, and registration numbers are immutable to policy updates.

Gate 2 implements only deterministic local adapters and an in-memory acceptance boundary. HTTP/Gemini/cloud adapters, API wiring, and deployed verification remain future gates.
