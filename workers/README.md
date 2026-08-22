# Workers

This directory is reserved for asynchronous jobs and event consumers.

Planned worker families:

- product workers for fact extraction, script review, and other long-running tasks;
- policy workers under [`policy/`](policy/README.md);
- notification and outbox dispatch where required by the shared event contracts.

Workers communicate through schemas and events defined in `schemas/`. At-least-once delivery is assumed, so every future consumer must be idempotent.

No worker implementation exists in this scaffold.
