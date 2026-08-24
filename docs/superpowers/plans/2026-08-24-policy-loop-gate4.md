# Policy Loop Gate 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real HTTP, GCS, Firestore, Gemini, and Pub/Sub adapters behind the existing policy-loop interfaces, prove the real NRTA source path locally, and leave the credential-gated cloud smoke explicitly PASS/FAIL/SKIP.

**Architecture:** Existing refresh, publish, and outbox modules remain the only business workflows. Narrow repository protocols form the storage seam; in-memory and Firestore adapters satisfy those protocols. SDK clients are injected into adapters, Google dependencies stay in an optional `cloud` extra, and Gate 3 remains the default local assembly.

**Tech Stack:** Python 3.11+, Pydantic 2, httpx, PyYAML, Google Cloud Storage, Google Cloud Firestore, Google Cloud Pub/Sub, Google Gen AI SDK, pytest.

---

## Scope and execution rules

- Work only in `/private/tmp/film-compliance-gate4-worktree` on `codex/policy-loop-gate4`.
- Follow red-green-refactor for every production behavior.
- Run the named focused test before and after each implementation step.
- Do not add Cloud Run, Scheduler, push-consumer routes, production auth, Maxine-owned data, or UI changes.
- Never report emulator or fixture evidence as deployed-cloud evidence.
- Preserve the existing 66 Python and 12 Web tests throughout.

## File map

New policy files:

- `workers/policy/interfaces.py`: narrow repository protocols.
- `workers/policy/source_config.py`: strict YAML source loader.
- `workers/policy/adapters/http_source.py`: real HTTPS fetcher.
- `workers/policy/adapters/gcs_blob.py`: content-addressed GCS storage.
- `workers/policy/adapters/firestore_policy.py`: Richard-owned policy persistence and transactions.
- `workers/policy/adapters/gemini_proposal.py`: structured proposal generation with bounded repair.
- `workers/policy/adapters/pubsub_event.py`: validated event publication.
- `workers/policy/cloud_runtime.py`: environment settings and cloud assembly.
- `workers/policy/gate4_smoke.py`: reusable source/full-cloud smoke orchestration.
- `policy/__init__.py`: package marker for versioned policy assets.
- `policy/policy_sources.yaml`: real NRTA source.
- `prompts/__init__.py` and `prompts/policy/__init__.py`: package markers for prompt assets.
- `prompts/policy/proposal-v1.md`: evidence-bound structured proposal prompt.
- `scripts/policy_gate4_smoke.py`: thin CLI.

New tests:

- `tests/policy/test_repository_interfaces.py`
- `tests/policy/test_source_config.py`
- `tests/policy/test_http_source.py`
- `tests/policy/test_gcs_blob.py`
- `tests/policy/fakes/firestore.py`
- `tests/policy/test_firestore_policy.py`
- `tests/policy/test_gemini_proposal.py`
- `tests/policy/test_pubsub_event.py`
- `tests/policy/test_cloud_runtime.py`
- `tests/policy/test_gate4_smoke.py`

Documentation updates:

- `README.md`
- `workers/policy/README.md`
- `policy/README.md`
- `tests/README.md`
- `docs/README.md`

## Task 1: Establish the real repository seam and cloud-safe run IDs

**Files:**

- Create: `workers/policy/interfaces.py`
- Modify: `workers/policy/refresh.py:5-68`
- Modify: `workers/policy/launch.py:5-38`
- Modify: `workers/policy/publish.py:21-39`
- Modify: `workers/policy/outbox.py:14-41`
- Modify: `api/deps/policy.py:14-46`
- Test: `tests/policy/test_repository_interfaces.py`
- Test: `tests/policy/test_launch.py`

- [ ] **Step 1: Write the failing injection test**

Create `tests/policy/test_repository_interfaces.py` with:

```python
from datetime import datetime, timezone

from workers.policy.interfaces import PolicyRepository
from workers.policy.repository import InMemoryPolicyRepository


NOW = datetime(2026, 8, 24, 0, 0, tzinfo=timezone.utc)


def test_in_memory_repository_works_through_composed_protocol() -> None:
    repository: PolicyRepository = InMemoryPolicyRepository()
    repository.create_run("run_protocol", "nrta_micro_drama", NOW)
    assert repository.get_run("run_protocol").status == "running"
```

Then extend `tests/policy/test_launch.py` with:

```python
def test_launcher_uses_injected_run_id_factory(tmp_path: Path) -> None:
    launcher, repository = build_launcher(
        tmp_path,
        run_id_factory=lambda: "run_cloud_abc123",
    )

    assert launcher.launch(SOURCE.source_id, NOW) == "run_cloud_abc123"
    assert repository.get_run("run_cloud_abc123").status == "running"
```

Update the existing helper signature to accept and forward the optional factory:

```python
def build_launcher(
    tmp_path: Path,
    *,
    run_id_factory: Callable[[], str] | None = None,
) -> tuple[PolicyRunLauncher, InMemoryPolicyRepository]:
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
.venv/bin/pytest -q tests/policy/test_repository_interfaces.py tests/policy/test_launch.py
```

Expected: failure because `PolicyRepository` and `run_id_factory` do not exist.

- [ ] **Step 3: Add narrow repository protocols**

Create `workers/policy/interfaces.py` with `Protocol` definitions for the exact methods used by refresh, publication, outbox, and policy reads. Compose them without adding cloud SDK types:

```python
class RefreshRepository(Protocol):
    def create_run(self, run_id: str, source_id: str, started_at: datetime) -> None: ...
    def get_run(self, run_id: str) -> PolicyRun: ...
    def fail_run(self, run_id: str, error: str, finished_at: datetime) -> None: ...
    def get_source_state(self, source_id: str) -> SourceState | None: ...
    def commit_refresh_proposal(self, *, run_id: str, source_id: str,
        proposal: PolicyProposal, source_state: SourceState,
        finished_at: datetime, previous_sha256: str,
        current_sha256: str) -> str: ...
    def commit_refresh_no_change(self, *, run_id: str, source_id: str,
        source_state: SourceState, finished_at: datetime,
        previous_sha256: str | None, current_sha256: str) -> None: ...

class PublicationRepository(Protocol):
    def get_proposal(self, proposal_id: str | None) -> PolicyProposal: ...
    def latest_snapshot(self) -> PolicySnapshot | None: ...
    def commit_publication(self, proposal_id: str, snapshot: PolicySnapshot,
        outbox_id: str, outbox: PolicyOutbox) -> None: ...
    def discard_proposal(self, proposal_id: str) -> None: ...

class OutboxRepository(Protocol):
    def list_pending_outbox(self, limit: int) -> list[tuple[str, PolicyOutbox]]: ...
    def mark_outbox_sent(self, outbox_id: str, sent_at: datetime,
        pubsub_message_id: str) -> None: ...

class PolicyReadRepository(Protocol):
    def list_runs(self) -> dict[str, PolicyRun]: ...
    def list_proposals(self) -> dict[str, PolicyProposal]: ...
    def list_snapshots(self) -> dict[str, PolicySnapshot]: ...
    def get_run(self, run_id: str) -> PolicyRun: ...
    def get_proposal(self, proposal_id: str | None) -> PolicyProposal: ...

class PolicyRepository(
    RefreshRepository,
    PublicationRepository,
    OutboxRepository,
    PolicyReadRepository,
    Protocol,
):
    def put_snapshot(self, snapshot: PolicySnapshot) -> None: ...
```

Use the narrowest protocol in each module constructor. Change `PolicyApiState.repository` to `PolicyRepository` and `blob_store` to the existing `BlobStore` protocol.

- [ ] **Step 4: Add an injected run-ID factory**

Update `PolicyRunLauncher` so the default remains deterministic while cloud assembly can inject UUID IDs:

```python
RunIdFactory = Callable[[], str]

def __init__(
    self,
    repository: RefreshRepository,
    refresh: PolicyRefreshModule,
    source_ids: set[str],
    *,
    run_id_factory: RunIdFactory | None = None,
) -> None:
    self._repository = repository
    self._refresh = refresh
    self._source_ids = frozenset(source_ids)
    self._counter = 0
    self._run_id_factory = run_id_factory

def _next_run_id(self) -> str:
    if self._run_id_factory is not None:
        return self._run_id_factory()
    self._counter += 1
    return f"run_{self._counter:03d}"
```

Reject an empty ID before repository creation.

- [ ] **Step 5: Run focused and full Python tests**

Run:

```bash
.venv/bin/pytest -q tests/policy/test_repository_interfaces.py tests/policy/test_launch.py
.venv/bin/pytest -q
```

Expected: all tests pass, with no behavioral changes to existing local IDs.

- [ ] **Step 6: Commit**

```bash
git add workers/policy/interfaces.py workers/policy/refresh.py workers/policy/launch.py workers/policy/publish.py workers/policy/outbox.py api/deps/policy.py tests/policy/test_repository_interfaces.py tests/policy/test_launch.py
git commit -m "refactor: define policy repository seams"
```

## Task 2: Load the real source and fetch it through HTTPS

**Files:**

- Create: `policy/policy_sources.yaml`
- Create: `workers/policy/source_config.py`
- Create: `workers/policy/adapters/http_source.py`
- Modify: `pyproject.toml:10-16`
- Test: `tests/policy/test_source_config.py`
- Test: `tests/policy/test_http_source.py`

- [ ] **Step 1: Write source-loader tests**

Cover the real file, duplicate IDs, unknown keys, non-HTTPS URLs, and empty selectors:

```python
def test_real_policy_source_is_strictly_loaded() -> None:
    sources = load_policy_sources(ROOT / "policy" / "policy_sources.yaml")
    source = sources["nrta_micro_drama_management_measures"]
    assert source.url == "https://www.nrta.gov.cn/art/2026/7/31/art_113_73785.html"
    assert source.content_selector == "#zoom"
    assert source.enabled is True
```

- [ ] **Step 2: Write HTTP adapter tests with `httpx.MockTransport`**

Tests must cover success, non-2xx, empty bytes, response larger than 5 MiB, timeout, and final non-HTTPS URL. The success test asserts raw bytes and final URL rather than normalized text.

- [ ] **Step 3: Run tests and verify RED**

```bash
.venv/bin/pytest -q tests/policy/test_source_config.py tests/policy/test_http_source.py
```

Expected: import failures for the new loader and adapter.

- [ ] **Step 4: Add the real source file and strict loader**

Use this exact YAML shape:

```yaml
sources:
  - source_id: nrta_micro_drama_management_measures
    url: https://www.nrta.gov.cn/art/2026/7/31/art_113_73785.html
    content_selector: "#zoom"
    enabled: true
```

`load_policy_sources(path)` must require exactly one top-level `sources` key, validate each row through `PolicySource`, and reject duplicate IDs.

- [ ] **Step 5: Implement `HttpSourceFetcher`**

Add `httpx>=0.28,<1` to core dependencies. Implement:

```python
class HttpSourceFetcher:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        timeout_seconds: float = 20.0,
        max_bytes: int = 5 * 1024 * 1024,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes

    async def fetch(self, source: PolicySource) -> FetchedSource:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=5,
            timeout=self._timeout_seconds,
            headers={"User-Agent": "Film-Compliance-Agent/0.1 policy-monitor"},
        )
        try:
            response = await client.get(source.url)
            response.raise_for_status()
            content = response.content
        except httpx.HTTPError as exc:
            raise PolicySourceFetchError(
                "POLICY_SOURCE_FETCH_FAILED", "policy source request failed"
            ) from exc
        finally:
            if owns_client:
                await client.aclose()
        if not content or len(content) > self._max_bytes:
            raise PolicySourceFetchError(
                "POLICY_SOURCE_FETCH_FAILED", "policy source body is invalid"
            )
        if response.url.scheme != "https":
            raise PolicySourceFetchError(
                "POLICY_SOURCE_FETCH_FAILED", "policy source redirect is unsafe"
            )
        return FetchedSource(content=content, source_url=str(response.url))
```

The owned client uses `follow_redirects=True`, `max_redirects=5`, a stable User-Agent, and the configured timeout. Map transport/status/body failures to the stable code `POLICY_SOURCE_FETCH_FAILED` without including response content.

- [ ] **Step 6: Refresh the local dependency environment**

```bash
.venv/bin/python -m pip install -e '.[test]'
```

Expected: `httpx>=0.28,<1` is installed and the editable package remains healthy.

- [ ] **Step 7: Run focused and regression tests**

```bash
.venv/bin/pytest -q tests/policy/test_source_config.py tests/policy/test_http_source.py
.venv/bin/pytest -q
```

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml policy/policy_sources.yaml workers/policy/source_config.py workers/policy/adapters/http_source.py tests/policy/test_source_config.py tests/policy/test_http_source.py
git commit -m "feat: fetch configured policy sources over https"
```

## Task 3: Add content-addressed GCS storage

**Files:**

- Create: `workers/policy/adapters/gcs_blob.py`
- Test: `tests/policy/test_gcs_blob.py`

- [ ] **Step 1: Write fake-client behavior tests**

Use a small fake storage client with `bucket().blob()`, `upload_from_string()`, and `download_as_bytes()`. Cover:

- raw path includes date and SHA-256;
- normalized and diff paths match the design;
- pack JSON uses `policy/packs/{snapshot_version}/{pack_name}.json`;
- upload passes `if_generation_match=0`;
- an identical precondition failure is accepted;
- a mismatched existing object raises `POLICY_BLOB_INTEGRITY_FAILED`;
- `read_text()` rejects non-`gs://`, another bucket, and invalid UTF-8.

- [ ] **Step 2: Run the focused test and verify RED**

```bash
.venv/bin/pytest -q tests/policy/test_gcs_blob.py
```

Expected: import failure for `GcsBlobStore`.

- [ ] **Step 3: Implement the adapter without eager Google imports**

The constructor accepts an injected client and precondition exception type. `from_project(project, bucket)` performs lazy imports of `google.cloud.storage` and `google.api_core.exceptions.PreconditionFailed`.

Implement the same four methods as `FileBlobStore`, plus:

```python
def put_pack(
    self,
    snapshot_version: str,
    pack_name: PackName,
    content: dict[str, object],
) -> BlobRef:
```

Serialize the pack with sorted UTF-8 JSON and store it at `policy/packs/{snapshot_version}/{pack_name.value}.json`. Return `BlobRef(uri=f"gs://{bucket}/{object_name}", sha256=digest)`.

Serialize `PolicyDiff` using sorted, UTF-8 JSON exactly as the file adapter does.

- [ ] **Step 4: Run focused and full tests**

```bash
.venv/bin/pytest -q tests/policy/test_gcs_blob.py
.venv/bin/pytest -q
```

- [ ] **Step 5: Commit**

```bash
git add workers/policy/adapters/gcs_blob.py tests/policy/test_gcs_blob.py
git commit -m "feat: archive policy blobs in gcs"
```

## Task 4: Build the Firestore test harness and validated reads

**Files:**

- Create: `tests/policy/fakes/__init__.py`
- Create: `tests/policy/fakes/firestore.py`
- Create: `workers/policy/adapters/firestore_policy.py`
- Create: `tests/policy/test_firestore_policy.py`

- [ ] **Step 1: Create a minimal transactional fake**

The fake stores documents by full path and provides only the methods used by the adapter:

```python
class FakeFirestoreClient:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, object]] = {}
        self.auto_id = 0

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self, name)

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)

    def run_transaction(self, callback):
        before = deepcopy(self.documents)
        try:
            return callback(self.transaction())
        except Exception:
            self.documents = before
            raise
```

`FakeDocumentSnapshot` exposes `exists`, `id`, and `to_dict()`. Collection streaming returns snapshots sorted by document ID. Transaction `get/create/set/update` acts on the fake client; the runner rollback supplies atomic failure behavior.

- [ ] **Step 2: Write failing validated-read tests**

Cover:

- create/get/list run;
- get/put source state;
- list proposals and snapshots;
- latest snapshot uses numeric `vN`, not lexicographic order;
- invalid stored documents raise Pydantic validation errors;
- missing documents raise `KeyError`.

- [ ] **Step 3: Run the focused test and verify RED**

```bash
.venv/bin/pytest -q tests/policy/test_firestore_policy.py
```

- [ ] **Step 4: Implement base Firestore reads and simple creates**

`FirestorePolicyRepository` accepts `client` and `transaction_runner`. Define collection constants exactly as the design. Use `model_dump(mode="python")` for writes and `model_validate()` for every read.

`from_project()` lazily imports `google.cloud.firestore`, builds the client, and wraps callbacks with `firestore.transactional`.

Use Firestore document IDs as run, proposal, snapshot, and outbox IDs; do not duplicate proposal IDs inside the body.

- [ ] **Step 5: Run focused tests**

```bash
.venv/bin/pytest -q tests/policy/test_firestore_policy.py
```

- [ ] **Step 6: Commit**

```bash
git add tests/policy/fakes workers/policy/adapters/firestore_policy.py tests/policy/test_firestore_policy.py
git commit -m "feat: read validated policy state from firestore"
```

## Task 5: Make Firestore refresh transitions atomic

**Files:**

- Modify: `workers/policy/adapters/firestore_policy.py`
- Modify: `tests/policy/test_firestore_policy.py`

- [ ] **Step 1: Write failing refresh transaction tests**

Add tests proving:

1. `commit_refresh_no_change()` updates run and source state together.
2. `commit_refresh_proposal()` creates an auto-ID proposal and updates run/source state together.
3. Missing or non-running runs produce no proposal and no source-state mutation.
4. `fail_run()` stores failed status but preserves previous hashes and source state.

The atomic failure assertion must inspect the fake client's complete document dictionary before and after.

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
.venv/bin/pytest -q tests/policy/test_firestore_policy.py -k 'refresh or fail_run'
```

- [ ] **Step 3: Implement refresh transaction methods**

Inside each callback:

```python
run_snapshot = transaction.get(run_ref)
run = PolicyRun.model_validate(run_snapshot.to_dict())
if run.status != "running":
    raise ValueError("run is not running")
```

For proposal creation, allocate `proposal_ref = collection.document()` before the callback, transaction-create it, then set source state and run. Return `proposal_ref.id` only after the runner succeeds.

- [ ] **Step 4: Run focused, refresh-module, and full tests**

```bash
.venv/bin/pytest -q tests/policy/test_firestore_policy.py tests/policy/test_refresh.py
.venv/bin/pytest -q
```

- [ ] **Step 5: Commit**

```bash
git add workers/policy/adapters/firestore_policy.py tests/policy/test_firestore_policy.py
git commit -m "feat: commit policy refreshes in firestore"
```

## Task 6: Make Firestore publication and outbox transitions atomic

**Files:**

- Modify: `workers/policy/adapters/firestore_policy.py`
- Modify: `tests/policy/test_firestore_policy.py`

- [ ] **Step 1: Write failing publication tests**

Cover:

- publication changes proposal and creates snapshot/outbox together;
- existing snapshot or outbox rolls back every change;
- discarded/published proposals reject publication;
- discard accepts only pending proposals;
- pending outbox is sorted by `(created_at, id)` and limited;
- marking sent requires pending status and a non-empty message ID.

- [ ] **Step 2: Run and verify RED**

```bash
.venv/bin/pytest -q tests/policy/test_firestore_policy.py -k 'publication or discard or outbox'
```

- [ ] **Step 3: Implement publication, discard, and outbox methods**

Use transaction `create()` for deterministic snapshot/outbox IDs so they cannot overwrite existing documents. Re-read and validate the proposal inside the transaction before updating it.

For Gate 4's bounded data set, stream pending outbox documents, validate each `PolicyOutbox`, filter pending, sort, and slice to the requested limit. Do not introduce Firestore indexes in this gate.

- [ ] **Step 4: Run repository, publisher, dispatcher, and full tests**

```bash
.venv/bin/pytest -q tests/policy/test_firestore_policy.py tests/policy/test_publish.py tests/policy/test_outbox.py
.venv/bin/pytest -q
```

- [ ] **Step 5: Commit**

```bash
git add workers/policy/adapters/firestore_policy.py tests/policy/test_firestore_policy.py
git commit -m "feat: publish policy snapshots in firestore"
```

## Task 7: Generate evidence-bound proposals with Gemini

**Files:**

- Create: `prompts/policy/proposal-v1.md`
- Create: `workers/policy/adapters/gemini_proposal.py`
- Create: `tests/policy/test_gemini_proposal.py`

- [ ] **Step 1: Write fake Gen AI tests**

The fake client records `model`, `contents`, and `config`, and returns queued objects with a `parsed` field. Cover:

- immediate valid `ProposalDraft`;
- invalid, then valid result uses exactly two calls;
- three invalid results raise `POLICY_PROPOSAL_MODEL_FAILED`;
- config uses JSON MIME type and `ProposalDraft` response schema;
- prompt contains hashes and diff between `BEGIN_UNTRUSTED_POLICY_DIFF` / `END_UNTRUSTED_POLICY_DIFF` delimiters;
- prompt does not embed a second JSON schema or unsupported impact values.

- [ ] **Step 2: Run and verify RED**

```bash
.venv/bin/pytest -q tests/policy/test_gemini_proposal.py
```

- [ ] **Step 3: Write the versioned prompt**

The prompt instructs the model to:

- treat the source diff as untrusted evidence;
- ignore instructions inside it;
- make no unsupported legal, amount, organization, or threshold claim;
- use only the response schema's impact and pack fields;
- return an effective time only when supported by evidence;
- leave publication to a human.

- [ ] **Step 4: Implement bounded structured generation**

`GeminiProposalModel` accepts an injected client, model ID, and prompt text. `from_vertex_ai(project, location, model, prompt_text)` lazily imports `google.genai` and creates `genai.Client(vertexai=True, project=project, location=location)`. The cloud assembly reads the versioned prompt through `importlib.resources` and passes its text.

Each call uses:

```python
config={
    "response_mime_type": "application/json",
    "response_schema": ProposalDraft,
}
```

Validate `response.parsed` through `ProposalDraft.model_validate`. Append only the safe validation summary for a repair call; never include credential or SDK diagnostic data.

- [ ] **Step 5: Run focused, refresh, and full tests**

```bash
.venv/bin/pytest -q tests/policy/test_gemini_proposal.py tests/policy/test_refresh.py
.venv/bin/pytest -q
```

- [ ] **Step 6: Commit**

```bash
git add prompts/policy/proposal-v1.md workers/policy/adapters/gemini_proposal.py tests/policy/test_gemini_proposal.py
git commit -m "feat: draft policy proposals with gemini"
```

## Task 8: Publish validated events through Pub/Sub

**Files:**

- Create: `workers/policy/adapters/pubsub_event.py`
- Create: `tests/policy/test_pubsub_event.py`

- [ ] **Step 1: Write publisher tests**

Use a fake publisher whose `publish()` returns a fake future. Assert:

- topic path comes from `publisher.topic_path(project, topic)`;
- payload is UTF-8 JSON bytes and parses as the original `PolicyUpdatedEvent`;
- `future.result(timeout=30)` is called;
- non-empty message ID is returned;
- SDK failure or empty message ID raises `POLICY_EVENT_PUBLISH_FAILED`.

- [ ] **Step 2: Run and verify RED**

```bash
.venv/bin/pytest -q tests/policy/test_pubsub_event.py
```

- [ ] **Step 3: Implement the adapter**

`PubSubEventPublisher` accepts an injected publisher and resolved topic path. `from_project()` lazily imports `google.cloud.pubsub_v1`, creates `PublisherClient`, and resolves the path. Serialize with `event.model_dump_json().encode("utf-8")`.

- [ ] **Step 4: Run focused, dispatcher, and full tests**

```bash
.venv/bin/pytest -q tests/policy/test_pubsub_event.py tests/policy/test_outbox.py
.venv/bin/pytest -q
```

- [ ] **Step 5: Commit**

```bash
git add workers/policy/adapters/pubsub_event.py tests/policy/test_pubsub_event.py
git commit -m "feat: publish policy updates to pubsub"
```

## Task 9: Assemble the credential-gated cloud runtime

**Files:**

- Create: `workers/policy/cloud_runtime.py`
- Create: `tests/policy/test_cloud_runtime.py`
- Create: `policy/__init__.py`
- Create: `prompts/__init__.py`
- Create: `prompts/policy/__init__.py`
- Modify: `pyproject.toml:18-22`

- [ ] **Step 1: Write configuration and import-isolation tests**

Cover:

- missing project, bucket, or topic is a stable configuration error;
- defaults are `global`, `gemini-3.5-flash`, and `(default)`;
- explicit database/model/location values are preserved;
- importing `workers.policy.local_demo`, `api.main`, and every local adapter succeeds when Google modules are hidden;
- source YAML, seed YAML, and the proposal prompt are readable through `importlib.resources`;
- injected factory functions build a runtime without real credentials.

- [ ] **Step 2: Run and verify RED**

```bash
.venv/bin/pytest -q tests/policy/test_cloud_runtime.py
```

- [ ] **Step 3: Add the optional cloud dependency group**

Add:

```toml
cloud = [
  "google-cloud-firestore>=2.28,<3",
  "google-cloud-pubsub>=2.39,<3",
  "google-cloud-storage>=3.13,<4",
  "google-genai>=1,<2",
]
```

Do not move these packages into core dependencies.

Also package the runtime assets:

```toml
[tool.setuptools.packages.find]
include = ["api*", "policy*", "prompts*", "schemas*", "workers*"]

[tool.setuptools.package-data]
policy = ["*.yaml"]
"prompts.policy" = ["*.md"]
```

Create the three empty `__init__.py` package markers. Load the default seed, source YAML, and prompt with `importlib.resources.files()` instead of assuming a repository checkout path.

- [ ] **Step 4: Implement settings and assembly**

Create immutable `CloudPolicySettings.from_env()` and `CloudPolicyRuntime` dataclasses. Define a `CloudAdapterFactories` dataclass for the five constructor callables. Use this exact assembly signature:

```python
def build_cloud_policy_runtime(
    settings: CloudPolicySettings,
    *,
    factories: CloudAdapterFactories | None = None,
) -> CloudPolicyRuntime:
```

The assembly must:

1. load the real source file;
2. build Firestore, GCS, HTTP, Gemini, and Pub/Sub adapters;
3. import `policy/seed-snapshot-v1.yaml` only when no snapshot exists;
4. inject UUID run IDs using `lambda: f"run_{uuid4().hex}"`;
5. return repository, blob store, refresh, launcher, publisher, event publisher, and dispatcher.

Factory injection is a test seam only; callers still receive one assembled runtime.

- [ ] **Step 5: Run focused, full, and dependency checks**

```bash
.venv/bin/pytest -q tests/policy/test_cloud_runtime.py
.venv/bin/pytest -q
.venv/bin/python -m pip check
```

- [ ] **Step 6: Install the cloud extra and verify package imports**

```bash
.venv/bin/python -m pip install -e '.[test,cloud]'
.venv/bin/python -c 'from workers.policy.cloud_runtime import CloudPolicySettings; print(CloudPolicySettings.__name__)'
```

Expected: installation and import succeed without constructing clients or requiring credentials.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml policy/__init__.py prompts/__init__.py prompts/policy/__init__.py workers/policy/cloud_runtime.py tests/policy/test_cloud_runtime.py
git commit -m "feat: assemble the cloud policy runtime"
```

## Task 10: Prove the real NRTA source and last-known-good behavior

**Files:**

- Create: `workers/policy/gate4_smoke.py`
- Create: `scripts/policy_gate4_smoke.py`
- Create: `tests/policy/test_gate4_smoke.py`

- [ ] **Step 1: Write an offline orchestration test**

Inject a successful source fetcher followed by a failing one. Assert the report contains:

```python
assert report.mode == "source"
assert report.source_status == "PASS"
assert report.failure_status == "PASS"
assert report.last_known_good_preserved is True
assert report.normalized_sha256
assert "policy text" not in report.model_dump_json()
```

Also assert the first run establishes `no_change`, the second run is `failed`, and source state plus seed snapshot are byte-for-byte equal before and after failure.

- [ ] **Step 2: Run and verify RED**

```bash
.venv/bin/pytest -q tests/policy/test_gate4_smoke.py -k source
```

- [ ] **Step 3: Implement reusable source smoke**

`run_source_smoke()` accepts source, fetcher, blob store, repository, seed, proposal model, and clock. The production CLI supplies `HttpSourceFetcher`, a temporary `FileBlobStore`, `InMemoryPolicyRepository`, and the real seed.

After the successful baseline, create a second run with a fetcher that raises a stable source error. Catch the expected `PolicyRefreshError`, verify stored last-known-good values, and return a Pydantic report containing only metadata.

- [ ] **Step 4: Add the thin CLI**

The CLI supports:

```text
python scripts/policy_gate4_smoke.py --source
python scripts/policy_gate4_smoke.py --cloud
```

Print one JSON report to stdout and send diagnostics to stderr. Exit 0 only when all checks required by the selected mode pass; missing cloud configuration returns a JSON `SKIP` report with exit 0.

- [ ] **Step 5: Run offline tests and the real NRTA smoke**

```bash
.venv/bin/pytest -q tests/policy/test_gate4_smoke.py -k source
.venv/bin/python scripts/policy_gate4_smoke.py --source
```

Expected real result: source PASS, injected failure PASS, last-known-good preserved. Record the final URL and hash but not full content.

- [ ] **Step 6: Commit**

```bash
git add workers/policy/gate4_smoke.py scripts/policy_gate4_smoke.py tests/policy/test_gate4_smoke.py
git commit -m "feat: verify the real policy source"
```

## Task 11: Add the full-cloud smoke without overstating evidence

**Files:**

- Modify: `workers/policy/gate4_smoke.py`
- Modify: `scripts/policy_gate4_smoke.py`
- Modify: `tests/policy/test_gate4_smoke.py`

- [ ] **Step 1: Write failing PASS/FAIL/SKIP tests**

Cover:

- absent required cloud settings returns `overall="SKIP"` and adapter statuses `SKIP`;
- injected cloud runtime runs the real-source path and persists run/source state;
- injected failure preserves last-known-good;
- Gemini probe validates a synthetic fixture diff without persisting a proposal;
- Pub/Sub probe publishes exactly one validated synthetic event and records only message ID;
- any adapter failure produces `overall="FAIL"` and a stable stage code without secrets.

- [ ] **Step 2: Run and verify RED**

```bash
.venv/bin/pytest -q tests/policy/test_gate4_smoke.py -k cloud
```

- [ ] **Step 3: Implement `run_cloud_smoke()`**

Use the assembled runtime for source/GCS/Firestore work. For the Gemini probe, load the versioned v1/v2 fixture texts, create a `ProposalRequest`, call the real proposal adapter, and validate the returned draft without repository writes.

For Pub/Sub, publish one `PolicyUpdatedEvent` with snapshot version `v2`, `ImpactNode.D1C`, and an idempotency key derived from that version. The configured topic must be an explicit smoke topic; do not create a topic or subscription.

Return per-adapter `PASS/FAIL/SKIP` plus project, database, bucket, topic, model, UTC timestamp, source hash, and message ID. Do not include prompt text, policy content, credentials, or exception tracebacks.

- [ ] **Step 4: Run tests and the credential-gated command**

```bash
.venv/bin/pytest -q tests/policy/test_gate4_smoke.py
.venv/bin/python scripts/policy_gate4_smoke.py --cloud
```

Expected in the current environment: a truthful JSON `SKIP` because required cloud configuration/credentials are unavailable.

- [ ] **Step 5: Commit**

```bash
git add workers/policy/gate4_smoke.py scripts/policy_gate4_smoke.py tests/policy/test_gate4_smoke.py
git commit -m "feat: report gate 4 cloud smoke status"
```

## Task 12: Document, verify, review, and hand off Gate 4

**Files:**

- Modify: `README.md`
- Modify: `workers/policy/README.md`
- Modify: `policy/README.md`
- Modify: `tests/README.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Update documentation without claiming cloud PASS**

Document:

- the five Gate 4 adapters;
- `.[cloud]` installation;
- environment variable names only;
- source and cloud smoke commands;
- current PASS/FAIL/SKIP semantics;
- Gate 5 exclusions;
- the difference between implementation complete and Gate passed.

- [ ] **Step 2: Run the complete automated verification**

```bash
.venv/bin/pytest -q
npm --prefix web test
NEXT_TELEMETRY_DISABLED=1 npm --prefix web run build
.venv/bin/python -m compileall -q api schemas workers scripts
.venv/bin/python -m pip check
```

- [ ] **Step 3: Verify packaging with and without cloud imports**

```bash
mkdir -p /private/tmp/film-compliance-gate4-wheel
.venv/bin/python -m pip wheel --no-deps --no-build-isolation --wheel-dir /private/tmp/film-compliance-gate4-wheel .
.venv/bin/python -c 'import api.main, workers.policy.local_demo'
.venv/bin/python -c 'import workers.policy.adapters.firestore_policy, workers.policy.adapters.gcs_blob, workers.policy.adapters.gemini_proposal, workers.policy.adapters.pubsub_event'
```

- [ ] **Step 4: Run both smoke modes and save evidence outside the repository**

```bash
.venv/bin/python scripts/policy_gate4_smoke.py --source
.venv/bin/python scripts/policy_gate4_smoke.py --cloud
```

Expected current classification: source PASS; cloud SKIP unless credentials/configuration have been supplied.

- [ ] **Step 5: Run Git hygiene checks**

```bash
git diff --check
git diff --check codex/policy-loop-gate3...HEAD
git status -sb
```

- [ ] **Step 6: Commit documentation**

```bash
git add README.md workers/policy/README.md policy/README.md tests/README.md docs/README.md
git commit -m "docs: document gate 4 cloud adapters"
```

- [ ] **Step 7: Request independent review**

Review range: `codex/policy-loop-gate3..HEAD`.

Require the reviewer to check:

- no unresolved Critical or Important defects;
- last-known-good state is preserved across source, blob, model, and repository failures;
- Firestore multi-document changes are atomic;
- local imports do not require Google dependencies or credentials;
- smoke reports do not overstate fixture/emulator/cloud evidence;
- no Gate 5 or Maxine-owned scope entered.

- [ ] **Step 8: Resolve findings with TDD and rerun final verification**

For every Critical or Important finding, add a failing regression test, verify RED, implement the smallest fix, verify GREEN, request focused re-review, and rerun Steps 2–5.

- [ ] **Step 9: Present integration choices**

Only after verification and review are clean, report the exact implementation and smoke status and offer:

1. merge locally;
2. push and create a PR;
3. keep the branch;
4. discard the work.
