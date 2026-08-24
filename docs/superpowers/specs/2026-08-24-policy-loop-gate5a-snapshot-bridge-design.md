# Policy Loop Gate 5-a — Published Snapshot Read Bridge

**Date:** 2026-08-24
**Owner:** Richard (workstream B), with the existing workstream A read seam
**Status:** Approved for implementation
**Decision superseded/closed by this work:** D-012 once acceptance passes

## 1. Problem

The unified application currently has two policy views:

- workstream A receives a `SnapshotService`, but the default
  `FileSnapshotService` can read only `policy/seed-snapshot-v1.yaml`;
- workstream B publishes v2 and later snapshots into its `PolicyRepository`.

Publishing v2 therefore succeeds in the policy administration loop while a
subsequent product-side `recalc-tier` for v2 returns snapshot-not-found. The
schemas are already aligned; the missing piece is a read adapter plus shared
process composition.

## 2. Goal

Make a snapshot committed by the policy publisher immediately readable through
Maxine's existing `SnapshotService` interface in the same application process.

Gate 5-a is complete when this local sequence passes:

1. create and classify a provisional project against v1;
2. publish the deterministic policy proposal as v2 through the admin route;
3. call the existing internal `recalc-tier` route with v2;
4. observe that the product reads v2 from the same policy repository and clears
   the provisional result;
5. confirm that protected/non-provisional data is not rewritten.

This proves snapshot visibility. It does not yet prove event-driven fan-out.

## 3. Existing interfaces remain authoritative

No shared policy schema changes are needed.

### A-line read interface

`schemas.snapshot.SnapshotService` remains the only policy read interface known
to product logic:

```python
latest_version(as_of: datetime | None = None) -> str
get_pack(name: PackName, version: str | None = None) -> dict
clause(clause_id: str, version: str) -> Clause
```

`WorkflowService` and the classification chain continue to depend only on this
interface. They must not import a policy repository or Firestore client.

### B-line publication interface

`PolicyPublisher` continues to write through `PublicationRepository`.
`commit_publication()` remains the atomic operation that creates the snapshot,
creates the outbox row, and marks the proposal published.

The policy repository remains the single source of truth for published
snapshots in the unified application. Gate 5-a adds no second write path.

## 4. Chosen design

### 4.1 Narrow repository read seam

Add a B-internal `SnapshotReadRepository` protocol with only:

```python
get_snapshot(version: str) -> PolicySnapshot
list_snapshots() -> dict[str, PolicySnapshot]
```

Both `InMemoryPolicyRepository` and `FirestorePolicyRepository` already provide
these methods. `PolicyRepository` will include this protocol, but no product
module will depend on it.

### 4.2 Repository-backed adapter

Add `RepositorySnapshotService` under
`workers/policy/adapters/repository_snapshot.py`. It implements the existing
shared `SnapshotService` and depends only on `SnapshotReadRepository`.

Its behavior matches `FileSnapshotService`:

- `latest_version(as_of)` selects only snapshots whose `effective_from` is not
  later than the timezone-aware requested time, then orders by
  `(effective_from, published_at)`;
- `get_pack()` reads the selected snapshot and returns a deep copy, so product
  callers cannot mutate repository state;
- `clause()` validates and returns a `Clause` from the selected legal pack;
- missing versions and the absence of an effective snapshot become
  `SnapshotNotFoundError`;
- a missing clause remains `KeyError`, matching the file adapter.

Gate 5-a accepts inline packs, which is what the current seed and deterministic
proposal publish. A pack containing only `blob_uri` is not resolved in this
gate. GCS pack resolution belongs to the later cloud integration step and must
be added behind `SnapshotService`, not exposed to product callers.

### 4.3 Shared composition

Change application assembly, not product logic:

1. application lifespan resolves the policy state first;
2. if the caller supplied an `AppContext`, preserve it unchanged;
3. otherwise build `AppContext` with
   `RepositorySnapshotService(policy_state.repository)`;
4. store both objects on the same FastAPI application.

`build_context()` gains an optional `snapshots: SnapshotService` dependency.
Its standalone default remains `FileSnapshotService`, preserving A-line unit
tests and static-seed development.

The unified default application therefore uses one repository instance:

```text
admin publish
    -> PolicyPublisher
    -> PolicyRepository.commit_publication(v2, outbox)
    -> RepositorySnapshotService reads the same repository
    -> WorkflowService.recalc_tier(..., v2)
```

## 5. Consistency and failure semantics

- A reader cannot observe a snapshot before `commit_publication()` succeeds.
- An outbox dispatch failure does not hide or roll back an already committed
  snapshot; existing retry semantics remain unchanged.
- A missing or malformed requested version fails closed and does not fall back
  silently to v1.
- Explicit version reads stay pinned to that version. Only a call without a
  version uses `latest_version()`.
- Product classification, frozen forms, submitted materials, and registration
  numbers remain protected by the existing `WorkflowService` rules.
- In-memory state is process-local demo behavior. Firestore durability is not
  claimed by the local acceptance.

## 6. Alternatives rejected

### Mirror every publication back to YAML

Rejected because it creates two sources of truth and adds crash windows between
repository commit and file write.

### Let product logic read Firestore directly

Rejected because it couples A-line classification to B-line storage and makes
local tests require cloud configuration.

### Add write methods to `SnapshotService`

Rejected because product callers need read-only policy access. Publication,
proposal state, and outbox atomicity remain B-line responsibilities.

### Add a snapshot HTTP API

Rejected for Gate 5-a because both modules already share a process and a typed
read seam. A network interface would add authentication, serialization, retry,
and availability concerns without solving a current deployment requirement.

## 7. Verification

### Adapter tests

- v1 and v2 are readable by explicit version;
- latest selection respects `effective_from` and timezone validation;
- unknown version raises `SnapshotNotFoundError`;
- returned packs are deep copies;
- clause lookup matches `FileSnapshotService` behavior.

### Composition tests

- an explicitly supplied `AppContext` is never replaced;
- the default unified app and policy routes share one repository-backed
  snapshot view;
- the seed snapshot remains visible before any publication.

### Gate 5-a integration acceptance

- create a romance project and classify it against v1 as provisional;
- launch the fixture refresh and publish v2 through `/v1/admin/policy`;
- call `/v1/internal/projects/{id}/recalc-tier` with v2 and the internal token;
- assert `changed=true`, `tier_provisional=false`, and the project pins v2;
- assert an unknown v99 still returns the stable 404 envelope;
- retain the existing frozen/non-provisional mutation-protection tests;
- run the full Python suite, Web tests, and Next production build.

## 8. Explicit non-goals

- wiring `policy.updated` delivery to the real recalc endpoint;
- project enumeration and impact filtering;
- notification and timeline fan-out from the policy consumer;
- Cloud Scheduler or Cloud Run deployment;
- real GCP credentials or a named-project cloud PASS;
- GCS `blob_uri` pack resolution;
- changing `PolicySnapshot`, `PolicyUpdatedEvent`, or recalc response schemas;
- consolidating the two router directories or two auth helpers.

Those items remain Gate 5-b or deployment work after snapshot visibility is
closed.
