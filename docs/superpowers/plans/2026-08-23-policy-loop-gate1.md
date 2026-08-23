# Policy Loop Gate 1 Implementation Plan

> **For Codex:** Execute this plan task-by-task with test-driven development. Do not start Gate 2 work.

**Goal:** Freeze the v1 Policy/A-line handshake as executable Python schemas, a current static seed snapshot, a file-backed `SnapshotService`, and passing contract tests.

**Architecture:** `schemas/policy_snapshot.py` owns the shared Pydantic contracts. `schemas/snapshot.py` exposes the A-line read interface and a file adapter that validates YAML through those contracts. `policy/seed-snapshot-v1.yaml` is the only Gate 1 data source. Tests exercise contracts through public imports and the adapter; no network or cloud service is involved.

**Tech Stack:** Python 3.11 project contract, Pydantic 2, PyYAML 6, pytest 8.

---

## Scope guard

Gate 1 includes only:

- shared enums and models for snapshots, proposals, outbox events, and recalc-tier;
- the six-pack static seed snapshot;
- the `SnapshotService` interface plus local YAML adapter;
- one shared `policy.updated` JSON fixture and contract tests.

Explicitly excluded: source crawling, normalization/diff workers, Gemini, proposal publishing, outbox dispatch, consumer side effects, Firestore/GCS/Pub/Sub, FastAPI routes, and policy UI.

## Task 1: Establish the Python test harness

**Files:**

- Create: `pyproject.toml`
- Create: `tests/contract/test_policy_contract.py`

**Steps:**

1. Declare Python `>=3.11`, runtime dependencies `pydantic` and `PyYAML`, and a pytest dev dependency.
2. Write contract tests against the public objects named in the TDD before any schema implementation exists.
3. Run the contract test file and confirm RED because the shared schema modules do not yet exist.

## Task 2: Implement and freeze the shared contracts

**Files:**

- Create: `schemas/__init__.py`
- Create: `schemas/policy_snapshot.py`
- Test: `tests/contract/test_policy_contract.py`

**Steps:**

1. Add string enums for six pack names, impact nodes, proposal status, and outbox status.
2. Add timezone-aware datetime validation and the `vN` version rule.
3. Add fixed six-pack validation, including the inline-or-blob exclusivity rule.
4. Add `PolicySnapshot`, `PolicyProposal`, `PolicyUpdatedEvent`, `PolicyOutbox`, `Clause`, and recalc-tier request/response models with only the invariants approved in the TDD.
5. Run focused model tests until GREEN.

## Task 3: Add the static seed and SnapshotService file adapter

**Files:**

- Create: `policy/seed-snapshot-v1.yaml`
- Create: `schemas/snapshot.py`
- Test: `tests/contract/test_policy_contract.py`

**Steps:**

1. Extend tests for loading the seed, all six packs, current/future effective selection, explicit pack lookup, and clause lookup.
2. Run the new tests and confirm RED because the adapter and seed are absent.
3. Add a minimal current-effective seed. Keep unpublished thresholds explicit and preserve the partner's strict special-subject co-review rule as operational data.
4. Implement `SnapshotService` and `FileSnapshotService`; validate all loaded YAML through `PolicySnapshot`.
5. Return `SNAPSHOT_NOT_FOUND` through a typed exception when no effective snapshot exists; never fall forward to a future snapshot.
6. Run focused adapter tests until GREEN.

## Task 4: Add the cross-line event fixture and complete contract coverage

**Files:**

- Create: `tests/fixtures/policy/policy-updated-v2.json`
- Test: `tests/contract/test_policy_contract.py`

**Steps:**

1. Add tests proving both producer-style and consumer-style parsing use the same `PolicyUpdatedEvent` model.
2. Cover rejection of invalid version, impact, idempotency key, proposal state, outbox state, and malformed recalc-tier messages.
3. Add the minimal valid JSON fixture.
4. Run the full contract suite until GREEN.

## Task 5: Verify and hand off Gate 1

**Files:**

- Modify only if necessary: files listed above.

**Steps:**

1. Run the full test suite.
2. Run a package/build check appropriate to the minimal Python project.
3. Run `git diff --check` and inspect `git status --short`.
4. Review the diff against the Gate 1 scope guard and remove accidental Gate 2 work.
5. Commit, push `codex/policy-loop-gate1`, and open a PR without merging it.

## Gate 1 exit criteria

- The seed snapshot parses and exposes all six packs.
- `SnapshotService` reads the seed and refuses future-only snapshots.
- Both lines parse the same `policy.updated` fixture.
- Invalid version, impact, and derived idempotency key are rejected.
- Recalc-tier request and response shapes are executable and tested.
- All tests pass without network or GCP.
