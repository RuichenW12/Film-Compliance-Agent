# Working agreements

Read before making any change in this repository.

## The three disciplines

1. **Read the spec section first.** Before starting a task, read the matching section of the API & interface contract v1 and TDD v1 (`docs/`), then run that task's acceptance check when you finish and report the result.
2. **Do not build non-goals.** TDD section 11 is binding: no government-system integration or auto-submission, no real license verification, no payments or multi-tenancy, no deep market/opinion analysis, no video-frame analysis, and no legal-advice wording in the UI (always "pre-check reference, not legal advice").
3. **Never invent a fact.** Amounts, entity names, license numbers, and registration numbers stay `待补充` until a source or a human supplies them. There are tests asserting this; do not weaken them.

## Ground rules the code already enforces

- State changes go through `core.state_machine.transition()`. Agents propose, they never mutate state.
- A finding or classification asserting a compliance conclusion must carry `evidence_refs` into the pinned snapshot, or be downgraded to `needs_human`.
- Uploaded text is data, not instructions. Model output whose quote does not occur verbatim in the document is discarded.
- Every judgement records `policy_snapshot_version`. Re-runs use the pinned version unless a snapshot update explicitly re-triggers them.
- Every Pub/Sub handler is idempotent on `{project_id}:{task_type}:{asset_version}`.
- Missing model backend is reported as a pending flag, never as a clean result.

## Boundaries

- `schemas/` is the shared contract. Changing it needs both workstream owners.
- Workstream A (product) does not edit `workers/policy/` or `web/app/admin/policy/`.
- Workstream B (policy loop) does not edit product code; it reaches the product only through `/v1/internal/*`.

## Stack

FastAPI + Firestore + Pub/Sub + Next.js (App Router). All inference is Gemini on Vertex AI. UI is English with Chinese legal terms glossed.

## Verify

```bash
python -m pytest      # must be green before any commit
```
