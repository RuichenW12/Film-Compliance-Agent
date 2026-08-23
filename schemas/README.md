# Schemas

This directory is the shared A/B contract boundary.

Planned contracts include:

- project, fact, finding, form, task, notification, and timeline models;
- PolicySnapshot, PolicyProposal, and PolicyUpdatedEvent;
- shared enums and error envelopes;
- SnapshotService interfaces and contract fixtures.

Contract changes that affect both workstreams require review from Maxine and Richard. Runtime-specific helper types should remain with their owning module instead of expanding the shared surface.

Gate 1 implements the frozen policy handshake in `policy_snapshot.py` and the local YAML-backed `SnapshotService` in `snapshot.py`. Cloud adapters and non-policy shared schemas remain future work.
