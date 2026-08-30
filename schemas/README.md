# Schemas

This directory is the implemented shared A/B contract boundary.

Current contracts include:

- project, fact, finding, form, task, notification, and timeline models;
- PolicySnapshot, PolicyProposal, and PolicyUpdatedEvent;
- shared enums and error envelopes;
- SnapshotService interfaces and contract fixtures.

Contract changes that affect both workstreams require review from Maxine and Richard. Runtime-specific helper types should remain with their owning module instead of expanding the shared surface.

`policy_snapshot.py` and `snapshot.py` implement the frozen policy handshake and
local YAML-backed `SnapshotService`. The other modules define the current
project, asset, review-session, finding, form, task, notification, timeline,
and error-envelope contracts used by the API, workflow service, stores, and
tests. Cloud adapters remain outside this package behind the same interfaces.
