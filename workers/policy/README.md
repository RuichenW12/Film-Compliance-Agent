# Policy Workers

Owner: Richard

This is the main runtime workspace for Workstream B. It contains executable policy-loop behavior; source configuration and seed/snapshot data belong in the repository-level [`policy/`](../../policy/README.md) directory.

## Modules

| Module | Responsibility |
|---|---|
| Policy refresh | Normalize configured sources, archive content, and produce deterministic diffs and pending proposals |
| HTTP source adapter | Fetch the configured HTTPS page with bounded redirects, timeout, and response size |
| GCS blob adapter | Create content-addressed raw, normalized, diff, and pack objects without overwriting existing bytes |
| Firestore repository | Validate every read and atomically commit refresh, publication, discard, and outbox transitions |
| Gemini proposal adapter | Draft schema-constrained, evidence-bounded proposals from an explicitly delimited untrusted diff |
| Pub/Sub event adapter | Publish validated `policy.updated` JSON and return a non-empty message ID |
| Publisher | Validate a human-approved proposal and create the next policy snapshot |
| Outbox dispatcher | Publish committed `policy.updated` events without coupling event delivery to snapshot persistence |
| Update consumer | Mark affected projects stale and request recalculation only for provisional classifications |
| Local assembly | Connect deterministic adapters for same-process acceptance tests |
| Cloud assembly | Construct the five Gate 4 adapters from explicit settings while keeping Google imports optional locally |

## Dependencies

- Inputs: `policy/policy_sources.yaml`, the previous normalized source, shared schemas, and approved proposal data.
- Outputs: policy proposals, policy snapshots, outbox records, `policy.updated`, notifications, and timeline events.
- A-line dependency: the internal `recalc-tier` endpoint. This worker must not reimplement classification rule D1c.

## Safety boundary

- A model may draft a proposal but cannot publish it.
- Failed fetches keep serving the last known good snapshot.
- Policy events must be idempotent.
- Frozen forms, submitted materials, and registration numbers are immutable to policy updates.

Gate 4 implements the real adapter seams and metadata-only smoke checks. The source mode proves the real NRTA page can be fetched and that a subsequent injected failure preserves last-known-good state. The cloud mode reports `SKIP` when configuration is absent and requires an explicitly named smoke topic; fixture or injected-adapter tests are never presented as deployed-cloud evidence.

This gate owns only `policy_source_states`, `policy_runs`, `policy_proposals`, `policy_snapshots`, and `policy_outbox`. It does not add Maxine-owned project, notification, timeline, or `recalc-tier` persistence.
