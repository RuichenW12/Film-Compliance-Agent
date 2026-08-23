# Contract Tests

This directory will verify the shared boundaries between Workstream A and Workstream B.

The Gate 1 contract suite proves that:

- A line can load Richard's validated seed snapshot through SnapshotService;
- both lines can serialize and deserialize the same `policy.updated` fixture;
- future-effective snapshots are not selected as the current effective snapshot;
- the shared proposal, outbox, and recalc-tier messages enforce their frozen shapes.

Consumer side-effect invariants for frozen forms, submitted materials, and registration numbers belong to the Gate 2 module tests, where those stores and consumers exist.
