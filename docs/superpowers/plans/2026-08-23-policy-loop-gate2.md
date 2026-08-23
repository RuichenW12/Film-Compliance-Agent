# Policy Loop Gate 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, network-free policy loop from changed HTML fixture through proposal, snapshot, outbox, dispatch, and idempotent project effects.

**Architecture:** Pure functions own normalization and Diff. Worker classes coordinate injected local adapters. One in-memory policy repository is the Gate 2 publication boundary; a separate in-memory project repository stands in for A-line state so policy code never owns D1c tier rules.

**Tech Stack:** Python 3.11+, Pydantic 2, BeautifulSoup4, PyYAML, pytest.

---

## Scope guard

Gate 2 includes deterministic HTML normalization, local file/fixture/fake adapters, in-memory state, refresh, publish/discard, outbox dispatch, policy.updated consumption, and one offline twelve-step acceptance test.

Excluded: FastAPI, admin UI, HTTP, Gemini, Firestore, GCS, Pub/Sub, Cloud Run, Scheduler, auth, deployment, and live smoke tests.

## File map

- `workers/policy/models.py`: worker-internal records and result types, not shared A/B contracts.
- `workers/policy/normalize.py`: pure extraction, whitespace normalization, hashing, and Diff.
- `workers/policy/repository.py`: narrow repository protocol and in-memory Gate 2 implementation.
- `workers/policy/refresh.py`: refresh orchestration only.
- `workers/policy/publish.py`: publish/discard orchestration only.
- `workers/policy/outbox.py`: pending event delivery only.
- `workers/policy/consumer.py`: stale/recalc/notification coordination only.
- `workers/policy/local_demo.py`: same-process Gate 2 assembly used by acceptance tests.
- `workers/policy/adapters/`: deterministic local adapters without network or cloud dependencies.
- `tests/policy/`: module tests and offline end-to-end acceptance.

### Task 1: Normalize fixture HTML and create deterministic Diff

**Files:**

- Modify: `pyproject.toml`
- Create: `workers/policy/__init__.py`
- Create: `workers/policy/models.py`
- Create: `workers/policy/normalize.py`
- Create: `tests/fixtures/policy/source-v1.html`
- Create: `tests/fixtures/policy/source-v2.html`
- Create: `tests/policy/test_normalize.py`

- [ ] Write tests named `test_html_noise_does_not_change_normalized_hash`, `test_text_change_produces_unified_diff`, and `test_missing_selector_is_an_extract_error`.
- [ ] Run `.venv/bin/pytest tests/policy/test_normalize.py`; expect import failure because `workers.policy.normalize` is absent.
- [ ] Add BeautifulSoup4 to runtime dependencies. Implement `normalize_html(content, selector)`, `sha256_text(text)`, and `create_policy_diff(source_id, previous, current)` using only normalized text.
- [ ] Remove `script`, `style`, and `noscript`; convert non-breaking spaces; collapse repeated whitespace; join non-empty block text with one newline; use SHA-256 and `difflib.unified_diff`.
- [ ] Run the focused test and then `.venv/bin/pytest`; expect all green.

### Task 2: Refresh fixtures into source state and proposals

**Files:**

- Create: `workers/policy/repository.py`
- Create: `workers/policy/refresh.py`
- Create: `workers/policy/adapters/__init__.py`
- Create: `workers/policy/adapters/fixture_source.py`
- Create: `workers/policy/adapters/file_blob.py`
- Create: `workers/policy/adapters/fake_proposal.py`
- Create: `tests/policy/test_refresh.py`

- [ ] Write tests for first-run baseline without proposal, repeat no-change without model call, changed fixture producing one pending proposal and Diff, and failure preserving last-known-good source state.
- [ ] Use `asyncio.run()` instead of adding pytest-asyncio.
- [ ] Run `.venv/bin/pytest tests/policy/test_refresh.py`; expect import failure for the absent refresh module.
- [ ] Implement `PolicyRefreshModule.run(run_id, source_id, now) -> RefreshResult` and typed `PolicyRefreshError`.
- [ ] Implement configured-path-only `FixtureSourceFetcher`, content-addressed `FileBlobStore`, one deterministic `FakeProposalModel`, and `InMemoryPolicyRepository` that never leaks mutable references.
- [ ] Preserve this order: save raw, normalize/save/hash, compare, baseline/no-change or Diff/proposal, then update source state. On any error, mark the run failed and keep the prior source state.
- [ ] Run the focused test and then `.venv/bin/pytest`; expect all green.

### Task 3: Publish or discard proposals atomically in memory

**Files:**

- Create: `workers/policy/publish.py`
- Create: `tests/policy/test_publish.py`

- [ ] Write tests for future-effective rejection, successful v2 creation with proposal transition and pending outbox, repeat-publish conflict without v3, and discard of a pending proposal.
- [ ] Load `policy/seed-snapshot-v1.yaml` into the repository before publication.
- [ ] Run `.venv/bin/pytest tests/policy/test_publish.py`; expect import failure for `workers.policy.publish`.
- [ ] Implement `PolicyPublisher`, `PublishResult`, and typed errors with `POLICY_NOT_EFFECTIVE`, `POLICY_PROPOSAL_CONFLICT`, and `SNAPSHOT_NOT_FOUND` codes.
- [ ] Apply snapshot creation, proposal status/version, and pending outbox as one in-memory commit. Set outbox ID to `policy.updated:vN`; send no event inside publish.
- [ ] Run the focused test and then `.venv/bin/pytest`; expect all green.

### Task 4: Dispatch pending outbox rows

**Files:**

- Create: `workers/policy/outbox.py`
- Create: `workers/policy/adapters/fake_event_publisher.py`
- Create: `tests/policy/test_outbox.py`

- [ ] Write tests for successful send, failed send remaining pending, second dispatch selecting nothing, and the hard maximum of 20 selected rows.
- [ ] Run `.venv/bin/pytest tests/policy/test_outbox.py`; expect import failure for `workers.policy.outbox`.
- [ ] Implement a fake publisher that returns deterministic message IDs or raises a configured error.
- [ ] Implement `OutboxDispatcher.dispatch(limit=20)`, clamp selection to 20, isolate per-row failures, and mark sent only after a message ID exists.
- [ ] Run the focused test and then `.venv/bin/pytest`; expect all green.

### Task 5: Consume policy.updated without touching frozen artifacts

**Files:**

- Create: `workers/policy/consumer.py`
- Create: `workers/policy/adapters/memory_projects.py`
- Create: `workers/policy/adapters/fake_recalc.py`
- Create: `tests/policy/test_consumer.py`

- [ ] Create one provisional project and one FORM_FROZEN or FILED project in tests.
- [ ] Write tests proving only provisional recalc, frozen hash/materials/registration immutability, deterministic notification/timeline IDs, event replay with no side effects, and failed recalc leaving stale state without an event receipt.
- [ ] Run `.venv/bin/pytest tests/policy/test_consumer.py`; expect import failure for `workers.policy.consumer`.
- [ ] Implement `PolicyUpdatedConsumer.handle(event) -> ConsumeResult` and an in-memory project adapter with deterministic upserts.
- [ ] Implement `FakeRecalcClient` as the A-line boundary. It owns tier mutation; the consumer never calculates a tier.
- [ ] Write the event receipt only after every recalculation succeeds.
- [ ] Run the focused test and then `.venv/bin/pytest`; expect all green.

### Task 6: Prove the offline twelve-step path

**Files:**

- Create: `workers/policy/local_demo.py`
- Create: `tests/policy/test_policy_loop.py`
- Modify: `workers/policy/README.md`
- Modify: `tests/README.md`
- Modify: `docs/README.md`

- [ ] Write one end-to-end test against `build_local_policy_loop(...)` that imports the seed, creates provisional and frozen projects, establishes source v1, changes to v2, checks the proposal, publishes v2, checks pending outbox, dispatches, consumes, checks both projects, compares frozen artifacts, and replays the event.
- [ ] Run `.venv/bin/pytest tests/policy/test_policy_loop.py`; expect import failure because `workers.policy.local_demo` is absent.
- [ ] Implement only `build_local_policy_loop(...)` and the small returned assembly object required by that test. Do not add API, CLI, general dependency-injection container, persistence format, or cloud configuration.
- [ ] Document Gate 2 as deterministic local acceptance, not deployed verification.
- [ ] Run `.venv/bin/pytest`; expect all tests green.
- [ ] Run `.venv/bin/python -m compileall -q schemas workers`; expect exit 0.
- [ ] Run `.venv/bin/python -m pip check`; expect no broken requirements.
- [ ] Build a wheel with `--no-deps --no-build-isolation`; expect success.
- [ ] Run `git diff --check` and inspect `git status --short`; expect only Gate 2 files.

## Gate 2 exit criteria

- All runs are deterministic and require no network or GCP.
- First fetch establishes a baseline; repeat is no-change; changed fixture creates one valid proposal.
- Publication creates exactly one next snapshot and one pending outbox atomically.
- Dispatch marks sent only after fake publisher success.
- The provisional project is recalculated only through the fake A-line client.
- The frozen/FILED project becomes stale while form hash, materials, and registration number remain unchanged.
- Replaying the event creates no duplicate business effects.
- The offline twelve-step acceptance test is green.
