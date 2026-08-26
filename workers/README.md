# Workers

This directory is reserved for asynchronous jobs and event consumers.

Planned worker families:

- product workers for fact extraction, script review, and other long-running tasks;
- policy workers under [`policy/`](policy/README.md);
- notification and outbox dispatch where required by the shared event contracts.

Workers communicate through schemas and events defined in `schemas/`. At-least-once delivery is assumed, so every future consumer must be idempotent.

## Current implementation

- `hello.py` — Vertex AI wiring check (`python -m workers.hello`). It proves the ADC identity can reach Gemini and that structured output round-trips; it makes no compliance judgement.

Still to build: the fact extractor, the scene review worker, the notification consumer, and the push routes on port 8081.

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
