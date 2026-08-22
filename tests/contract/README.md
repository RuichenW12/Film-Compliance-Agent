# Contract Tests

This directory will verify the shared boundaries between Workstream A and Workstream B.

The first contract milestone will prove that:

- A line can load Richard's validated seed snapshot through SnapshotService;
- both lines can serialize and deserialize the same `policy.updated` fixture;
- future-effective snapshots are not selected as the current effective snapshot;
- policy update handling preserves frozen forms, submitted materials, and registration numbers.

No contract test or fixture exists in this scaffold.
