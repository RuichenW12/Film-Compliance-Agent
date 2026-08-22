# Policy Workers

Owner: Richard

This is the main runtime workspace for Workstream B. It contains executable policy-loop behavior; source configuration and seed/snapshot data belong in the repository-level [`policy/`](../../policy/README.md) directory.

## Planned modules

| Module | Responsibility |
|---|---|
| Policy refresh job | Fetch configured official pages, archive raw content, normalize text, and produce deterministic diffs |
| Proposal generator | Ask Gemini to turn a deterministic diff into a schema-validated draft proposal |
| Publisher | Validate a human-approved proposal and create the next policy snapshot |
| Outbox dispatcher | Publish committed `policy.updated` events without coupling event delivery to snapshot persistence |
| Update consumer | Mark affected projects stale and request recalculation only for provisional classifications |
| Policy notifier | Produce `policy_stale` and `tier_recalculated` notifications and timeline events |

## Dependencies

- Inputs: `policy/policy_sources.yaml`, the previous normalized source, shared schemas, and approved proposal data.
- Outputs: policy proposals, policy snapshots, outbox records, `policy.updated`, notifications, and timeline events.
- A-line dependency: the internal `recalc-tier` endpoint. This worker must not reimplement classification rule D1c.

## Safety boundary

- A model may draft a proposal but cannot publish it.
- Failed fetches keep serving the last known good snapshot.
- Policy events must be idempotent.
- Frozen forms, submitted materials, and registration numbers are immutable to policy updates.

No policy worker implementation exists in this scaffold.
