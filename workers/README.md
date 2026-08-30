# Workers

This directory contains the product job worker and policy refresh/event workers.

Worker families:

- product workers for fact extraction and script review;
- policy workers under [`policy/`](policy/README.md);
- notification and outbox dispatch where required by the shared event contracts.

Workers communicate through schemas and events defined in `schemas/`. At-least-once delivery is assumed, so every future consumer must be idempotent.

## Current implementation

- `hello.py` — Vertex AI wiring check (`python -m workers.hello`). It proves the ADC identity can reach Gemini and that structured output round-trips; it makes no compliance judgement.
- `jobs.py` — idempotent fact-extraction and script-review task execution for a configured queue runner.
- `policy/` — policy refresh, proposal, publication, outbox, and cloud-adapter boundaries documented in [`policy/README.md`](policy/README.md).

The current Cloud Run recording deployment does not run a separate worker
service: review work runs inline. Durable queue delivery, leases/crash recovery,
notification consumers, and a deployed push-worker route remain future work.

## Product jobs

`jobs.py` holds `JobWorker`, which finishes the tasks `core.jobs.QueuedRunner`
publishes: fact extraction and script review. It calls the same
`WorkflowService` methods the API calls, so the work has one implementation and
only the trigger differs.

A task already in a terminal state is acknowledged and dropped, because Pub/Sub
delivers at least once. A job type the worker does not handle is recorded
`failed` with the reason: drift between the queue and the worker should be
visible, not silent.

With the default `InlineRunner` the API does the work itself and this worker is
unused. See [D-025](../docs/decisions.md#d-025).
