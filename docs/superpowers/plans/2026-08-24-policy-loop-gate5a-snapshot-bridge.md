# Policy Loop Gate 5-a Snapshot Read Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a policy snapshot published through Richard's administration loop immediately readable by Maxine's existing product-side `SnapshotService` in the same FastAPI process, then prove `publish v2 -> recalc-tier v2` through HTTP.

**Architecture:** Keep `SnapshotService` as the product boundary and `PolicyRepository` as the publication source of truth. Add a two-method repository read protocol and a repository-backed `SnapshotService` adapter, then wire the default unified app so its product and policy states share one repository. Preserve an explicitly injected `AppContext` and retain `FileSnapshotService` as the standalone fallback.

**Tech Stack:** Python 3.12, FastAPI lifespan composition, Pydantic v2, pytest, in-memory policy repository, existing Next.js admin UI checks.

---

## Scope guardrails

- Do not change models under `schemas/`.
- Do not add a snapshot HTTP endpoint, a second YAML write path, or direct Firestore access to product code.
- Do not resolve GCS `blob_uri` packs in this gate; current v1/v2 acceptance uses inline packs.
- Do not add event fan-out, project enumeration, notification delivery, or cloud deployment claims.
- Preserve current protection in `WorkflowService`: only provisional classifications may be recalculated; frozen and non-provisional state remains untouched.
- Treat local in-process acceptance as Gate 5-a evidence only. Gate 5-b still owns real `policy.updated` delivery and deployed end-to-end evidence.

## File map

| File | Planned change |
| --- | --- |
| `workers/policy/interfaces.py:43-65` | Add the narrow `SnapshotReadRepository` protocol and compose it into `PolicyRepository`. |
| `tests/policy/test_repository_interfaces.py:1-17` | Prove the in-memory implementation satisfies the new read seam. |
| `workers/policy/adapters/repository_snapshot.py` | Add the repository-backed implementation of Maxine's existing `SnapshotService`. |
| `tests/policy/test_repository_snapshot_service.py` | Lock parity with `FileSnapshotService`: effective dating, version errors, copies, and clauses. |
| `api/deps/services.py:30-50` | Allow explicit `SnapshotService` injection while preserving the file-backed default. |
| `api/main.py:28-70` | Resolve policy state before constructing the default product context and share its repository. |
| `tests/test_app_policy_snapshot_bridge.py` | Prove the HTTP path from admin publication to product recalculation. |
| `docs/decisions.md` | Mark D-012 resolved locally by Gate 5-a and retain the cloud/fan-out boundary. |
| `README.md`, `api/README.md`, `tests/README.md`, `CHANGELOG.md` | Document the new composition and exact verification boundary. |

## Task 1: Expose the repository snapshot read seam

**Files:**

- Modify: `workers/policy/interfaces.py:43-65`
- Modify: `tests/policy/test_repository_interfaces.py:1-17`

- [ ] **Step 1: Write the failing protocol test**

Replace `tests/policy/test_repository_interfaces.py` with:

```python
from datetime import datetime, timezone
from pathlib import Path

import yaml

from schemas.policy_snapshot import PolicySnapshot
from workers.policy.interfaces import PolicyRepository, SnapshotReadRepository
from workers.policy.repository import InMemoryPolicyRepository


NOW = datetime(2026, 8, 24, 0, 0, tzinfo=timezone.utc)
SEED_PATH = Path(__file__).parents[2] / "policy" / "seed-snapshot-v1.yaml"


def test_in_memory_repository_works_through_composed_protocol() -> None:
    repository: PolicyRepository = InMemoryPolicyRepository()

    repository.create_run("run_protocol", "nrta_micro_drama", NOW)

    assert repository.get_run("run_protocol").status == "running"


def test_in_memory_repository_works_through_snapshot_read_protocol() -> None:
    raw = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    seed = PolicySnapshot.model_validate(raw)
    repository = InMemoryPolicyRepository()
    repository.put_snapshot(seed)

    reader: SnapshotReadRepository = repository

    assert reader.get_snapshot("v1").version == "v1"
    assert list(reader.list_snapshots()) == ["v1"]
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python -m pytest tests/policy/test_repository_interfaces.py -q
```

Expected: collection fails with `ImportError: cannot import name 'SnapshotReadRepository' from 'workers.policy.interfaces'`.

- [ ] **Step 3: Add the minimal protocol**

In `workers/policy/interfaces.py`, insert this immediately before `PolicyReadRepository`:

```python
class SnapshotReadRepository(Protocol):
    def get_snapshot(self, version: str) -> PolicySnapshot: ...
    def list_snapshots(self) -> dict[str, PolicySnapshot]: ...
```

Then change the final composed protocol to:

```python
class PolicyRepository(
    RefreshRepository,
    PublicationRepository,
    OutboxRepository,
    PolicyReadRepository,
    SnapshotReadRepository,
    Protocol,
):
    def put_snapshot(self, snapshot: PolicySnapshot) -> None: ...
```

Keep `PolicyReadRepository.list_snapshots()` unchanged for admin list compatibility. The apparent duplicate method is intentional: `PolicyReadRepository` is the admin-query surface, while `SnapshotReadRepository` is the minimum adapter dependency. Do not make product code import either protocol.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python -m pytest tests/policy/test_repository_interfaces.py tests/policy/test_publish.py tests/policy/test_firestore_policy.py -q
```

Expected: all selected tests pass, demonstrating both in-memory behavior and no Firestore adapter regression.

- [ ] **Step 5: Commit the seam**

```bash
git add workers/policy/interfaces.py tests/policy/test_repository_interfaces.py
git diff --cached --check
git commit -m "refactor: expose policy snapshot read seam"
```

## Task 2: Implement the repository-backed `SnapshotService`

**Files:**

- Create: `workers/policy/adapters/repository_snapshot.py`
- Create: `tests/policy/test_repository_snapshot_service.py`

- [ ] **Step 1: Write adapter contract tests**

Create `tests/policy/test_repository_snapshot_service.py`:

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from schemas.policy_snapshot import PackName, PolicyPacks, PolicySnapshot
from schemas.snapshot import SnapshotNotFoundError
from workers.policy.adapters.repository_snapshot import RepositorySnapshotService
from workers.policy.repository import InMemoryPolicyRepository


ROOT = Path(__file__).parents[2]
SEED_PATH = ROOT / "policy" / "seed-snapshot-v1.yaml"
NOW = datetime(2026, 8, 24, 0, 0, tzinfo=timezone.utc)


def seed_repository() -> tuple[InMemoryPolicyRepository, PolicySnapshot]:
    raw = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    seed = PolicySnapshot.model_validate(raw)
    repository = InMemoryPolicyRepository()
    repository.put_snapshot(seed)
    return repository, seed


def make_v2(
    seed: PolicySnapshot,
    *,
    effective_from: datetime = NOW,
) -> PolicySnapshot:
    packs = seed.packs.model_dump(mode="python")
    packs[PackName.P3_TIER_THRESHOLDS.value] = {
        **packs[PackName.P3_TIER_THRESHOLDS.value],
        "thresholds_published": True,
    }
    data = seed.model_dump(mode="python")
    data.update(
        version="v2",
        published_at=NOW,
        effective_from=effective_from,
        published_by="admin_richard",
        packs=PolicyPacks.model_validate(packs),
        thresholds_published=True,
    )
    return PolicySnapshot.model_validate(data)


def test_explicit_versions_are_readable_and_packs_are_copies() -> None:
    repository, seed = seed_repository()
    repository.put_snapshot(make_v2(seed))
    service = RepositorySnapshotService(repository)

    v1 = service.get_pack(PackName.P3_TIER_THRESHOLDS, "v1")
    v2 = service.get_pack(PackName.P3_TIER_THRESHOLDS, "v2")

    assert v1["thresholds_published"] is False
    assert v2["thresholds_published"] is True
    v2["thresholds_published"] = False
    assert service.get_pack(
        PackName.P3_TIER_THRESHOLDS, "v2"
    )["thresholds_published"] is True


def test_latest_version_respects_effective_from_and_timezone() -> None:
    repository, seed = seed_repository()
    future = NOW + timedelta(days=1)
    repository.put_snapshot(make_v2(seed, effective_from=future))
    service = RepositorySnapshotService(repository)

    assert service.latest_version(as_of=NOW) == "v1"
    assert service.latest_version(as_of=future) == "v2"
    with pytest.raises(ValueError, match="timezone"):
        service.latest_version(as_of=NOW.replace(tzinfo=None))


def test_unknown_version_and_no_effective_snapshot_fail_closed() -> None:
    repository, seed = seed_repository()
    service = RepositorySnapshotService(repository)

    with pytest.raises(SnapshotNotFoundError, match="v99"):
        service.get_pack(PackName.P3_TIER_THRESHOLDS, "v99")
    with pytest.raises(SnapshotNotFoundError, match="no snapshot is effective"):
        service.latest_version(as_of=seed.effective_from - timedelta(seconds=1))


def test_clause_lookup_matches_the_file_adapter_contract() -> None:
    repository, _ = seed_repository()
    service = RepositorySnapshotService(repository)

    clause = service.clause("nrta-order-16-article-2", "v1")

    assert clause.clause_id == "nrta-order-16-article-2"
    with pytest.raises(KeyError, match="clause not found"):
        service.clause("missing_clause", "v1")
```

Before executing, confirm the seed's legal clause identifier with:

```bash
rg -n "nrta-order-16-article-2" policy/seed-snapshot-v1.yaml
```

If this exact identifier is absent, use the first existing seed clause ID in both assertions; do not add test-only seed data.

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python -m pytest tests/policy/test_repository_snapshot_service.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'workers.policy.adapters.repository_snapshot'`.

- [ ] **Step 3: Implement behavioral parity with `FileSnapshotService`**

Create `workers/policy/adapters/repository_snapshot.py`:

```python
"""Expose published repository snapshots through the product read contract."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from schemas.policy_snapshot import Clause, PackName, PolicySnapshot
from schemas.snapshot import SnapshotNotFoundError, SnapshotService
from workers.policy.interfaces import SnapshotReadRepository


class RepositorySnapshotService(SnapshotService):
    """Read inline policy packs from the policy repository."""

    def __init__(self, repository: SnapshotReadRepository) -> None:
        self._repository = repository

    def latest_version(self, as_of: datetime | None = None) -> str:
        effective_at = as_of or datetime.now(timezone.utc)
        if effective_at.tzinfo is None or effective_at.utcoffset() is None:
            raise ValueError("as_of must include timezone information")

        candidates = [
            snapshot
            for snapshot in self._repository.list_snapshots().values()
            if snapshot.effective_from <= effective_at
        ]
        if not candidates:
            raise SnapshotNotFoundError(
                "no snapshot is effective at the requested time"
            )

        latest = max(
            candidates,
            key=lambda snapshot: (
                snapshot.effective_from,
                snapshot.published_at,
            ),
        )
        return latest.version

    def get_pack(self, name: PackName, version: str | None = None) -> dict:
        selected_version = version or self.latest_version()
        snapshot = self._snapshot(selected_version)
        return deepcopy(getattr(snapshot.packs, name.value))

    def clause(self, clause_id: str, version: str) -> Clause:
        legal_pack = self.get_pack(PackName.P6_LEGAL_CLAUSES, version)
        for raw_clause in legal_pack.get("clauses", []):
            clause = Clause.model_validate(raw_clause)
            if clause.clause_id == clause_id:
                return clause
        raise KeyError(f"clause not found: {clause_id}")

    def _snapshot(self, version: str) -> PolicySnapshot:
        try:
            return self._repository.get_snapshot(version)
        except KeyError as exc:
            raise SnapshotNotFoundError(
                f"snapshot not found: {version}"
            ) from exc
```

Do not catch `ValueError` or Pydantic validation failures here: repository corruption must not be disguised as a missing version. Do not add `blob_uri` fetching in this adapter.

- [ ] **Step 4: Run adapter parity tests and verify GREEN**

Run:

```bash
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python -m pytest tests/policy/test_repository_snapshot_service.py tests/test_snapshot_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Type-compile the new module**

Run:

```bash
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python -m compileall -q workers/policy/adapters/repository_snapshot.py
```

Expected: exit code 0 with no output.

- [ ] **Step 6: Commit the adapter**

```bash
git add workers/policy/adapters/repository_snapshot.py tests/policy/test_repository_snapshot_service.py
git diff --cached --check
git commit -m "feat: read policy snapshots through repository"
```

## Task 3: Share published snapshots in the unified FastAPI composition

**Files:**

- Modify: `api/deps/services.py:30-50`
- Modify: `api/main.py:28-70`
- Create: `tests/test_app_policy_snapshot_bridge.py`

- [ ] **Step 1: Write the full HTTP acceptance test**

Create `tests/test_app_policy_snapshot_bridge.py`:

```python
"""Gate 5-a: admin publication becomes product-readable in one process."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.deps.policy import SOURCE_ID, PolicyApiState, build_local_policy_api_state
from api.deps.services import build_context
from api.main import create_app
from api.settings import Settings


NOW = datetime(2026, 8, 23, 20, 30, tzinfo=timezone(timedelta(hours=8)))
INTERNAL_TOKEN = "t_gate5a_internal"
ADMIN_HEADERS = {"X-Mock-Role": "admin"}
CREATOR_HEADERS = {"X-Mock-Role": "creator", "X-User-Id": "u_gate5a"}
ROMANCE_INTENT = {
    "form_type_claimed": "micro_drama",
    "genre_keywords": ["甜宠"],
    "logline": "总裁与实习生在职场相遇，逐渐走到一起的爱情故事。",
    "episode_count": 30,
    "episode_minutes": 2,
    "budget_band": "band_c",
    "is_ai_generated": False,
}


@pytest.fixture
def policy_state(tmp_path: Path) -> PolicyApiState:
    return asyncio.run(
        build_local_policy_api_state(
            tmp_path / "blobs",
            clock=lambda: NOW,
        )
    )


def create_provisional_romance(client: TestClient) -> str:
    created = client.post(
        "/v1/projects",
        json={"title_working": "Gate 5-a romance"},
        headers=CREATOR_HEADERS,
    )
    assert created.status_code == 201
    project_id = created.json()["project_id"]

    intent = client.post(
        f"/v1/projects/{project_id}/intent",
        json=ROMANCE_INTENT,
        headers=CREATOR_HEADERS,
    )
    assert intent.status_code == 200

    classified = client.post(
        f"/v1/projects/{project_id}/classify",
        headers=CREATOR_HEADERS,
    )
    assert classified.status_code == 200
    classification = classified.json()["classification"]
    assert classification["tier"] == "T3"
    assert classification["tier_provisional"] is True
    assert classification["policy_snapshot_version"] == "v1"
    return project_id


def publish_v2(client: TestClient) -> str:
    crawl = client.post(
        "/v1/admin/policy/crawl",
        json={"source_id": SOURCE_ID},
        headers=ADMIN_HEADERS,
    )
    assert crawl.status_code == 202

    run = client.get(
        f"/v1/admin/policy/runs/{crawl.json()['run_id']}",
        headers=ADMIN_HEADERS,
    )
    assert run.status_code == 200
    assert run.json()["status"] == "proposal_created"

    published = client.post(
        "/v1/admin/policy/proposals/"
        f"{run.json()['proposal_id']}/publish",
        headers=ADMIN_HEADERS,
    )
    assert published.status_code == 201
    assert published.json() == {"snapshot_version": "v2"}
    return published.json()["snapshot_version"]


def test_publish_v2_then_product_recalc_reads_the_same_repository(
    policy_state: PolicyApiState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTERNAL_TOKEN", INTERNAL_TOKEN)

    with TestClient(create_app(policy_state=policy_state)) as client:
        assert client.get("/healthz").json()["snapshot_version"] == "v1"
        project_id = create_provisional_romance(client)

        missing = client.post(
            f"/v1/internal/projects/{project_id}/recalc-tier",
            json={"snapshot_version": "v99"},
            headers={"X-Internal-Token": INTERNAL_TOKEN},
        )
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "NOT_FOUND"
        assert "v99" in missing.json()["error"]["message"]

        version = publish_v2(client)
        assert client.get("/healthz").json()["snapshot_version"] == "v2"

        recalculated = client.post(
            f"/v1/internal/projects/{project_id}/recalc-tier",
            json={"snapshot_version": version},
            headers={"X-Internal-Token": INTERNAL_TOKEN},
        )
        assert recalculated.status_code == 200
        assert recalculated.json() == {
            "tier": "T3",
            "tier_provisional": False,
            "changed": True,
        }

        project = client.get(
            f"/v1/projects/{project_id}",
            headers=CREATOR_HEADERS,
        )
        assert project.status_code == 200
        classification = project.json()["project"]["classification"]
        assert classification["policy_snapshot_version"] == "v2"
        assert classification["tier_provisional"] is False


def test_explicit_context_is_not_replaced_by_policy_composition(
    policy_state: PolicyApiState,
) -> None:
    run_id = policy_state.launcher.launch(SOURCE_ID, NOW)
    result = asyncio.run(policy_state.launcher.execute(run_id, SOURCE_ID, NOW))
    assert result.proposal_id is not None
    policy_state.publisher.publish(result.proposal_id, "admin_richard", NOW)
    assert set(policy_state.repository.list_snapshots()) == {"v1", "v2"}

    explicit = build_context(Settings(internal_token=INTERNAL_TOKEN))
    with TestClient(
        create_app(context=explicit, policy_state=policy_state)
    ) as client:
        assert client.get("/healthz").json()["snapshot_version"] == "v1"
        assert client.app.state.context is explicit
```

- [ ] **Step 2: Run the HTTP test and verify RED**

Run:

```bash
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python -m pytest tests/test_app_policy_snapshot_bridge.py -q
```

Expected: `test_publish_v2_then_product_recalc_reads_the_same_repository` fails because the current default product context still uses `FileSnapshotService`; `/healthz` remains at v1 after publication and recalc of v2 returns 404.

- [ ] **Step 3: Add injectable snapshot composition**

In `api/deps/services.py`, change `build_context` to:

```python
def build_context(
    settings: Settings | None = None,
    *,
    snapshots: SnapshotService | None = None,
) -> AppContext:
    settings = settings or Settings.from_env()
    return AppContext(
        settings=settings,
        stores=InMemoryStores(),
        snapshots=snapshots or FileSnapshotService(settings.snapshot_path),
        clock=SystemClock(),
        llm=build_llm(settings),
    )
```

Do not change `default_context()`. Its no-argument call intentionally keeps the standalone file-backed behavior.

- [ ] **Step 4: Resolve policy state before the default product context**

In `api/main.py`, add:

```python
from workers.policy.adapters.repository_snapshot import RepositorySnapshotService
```

Then replace the context assignment and lifespan body inside `create_app()` with this composition:

```python
    def install_policy_state(app: FastAPI, resolved: PolicyApiState) -> None:
        app.state.policy = resolved
        if context is None:
            app.state.context = build_context(
                Settings.from_env(),
                snapshots=RepositorySnapshotService(resolved.repository),
            )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if policy_state is not None:
            install_policy_state(app, policy_state)
            yield
            return
        with TemporaryDirectory(prefix="film-compliance-policy-") as temp_dir:
            resolved = await build_local_policy_api_state(
                Path(temp_dir) / "blobs"
            )
            install_policy_state(app, resolved)
            yield
```

After constructing `app = FastAPI(...)`, replace the unconditional context line with:

```python
    if context is not None:
        app.state.context = context
```

This ordering is deliberate:

- an explicit context is available immediately, including tests that do not enter the lifespan context manager;
- a default context is built only after the policy repository exists;
- lifespan never replaces an explicit context;
- the global `app = create_app()` resolves its default context during startup, as FastAPI expects.

- [ ] **Step 5: Run the new acceptance test and verify GREEN**

Run:

```bash
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python -m pytest tests/test_app_policy_snapshot_bridge.py -q
```

Expected: both tests pass. The first proves `publish v2 -> health v2 -> recalc v2`; the second proves explicit injection still pins the file-backed v1 view.

- [ ] **Step 6: Run composition regression tests**

Run:

```bash
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python -m pytest tests/test_api_intake.py tests/policy/test_admin_routes.py tests/test_guards.py -q
```

Expected: all selected tests pass, including the existing v99 envelope and mutation-protection checks.

- [ ] **Step 7: Commit unified composition**

```bash
git add api/deps/services.py api/main.py tests/test_app_policy_snapshot_bridge.py
git diff --cached --check
git commit -m "feat: share published snapshots with product workflow"
```

## Task 4: Record the Gate 5-a boundary and run final verification

**Files:**

- Modify: `docs/decisions.md`
- Modify: `docs/superpowers/specs/2026-08-24-policy-loop-gate5a-snapshot-bridge-design.md`
- Modify: `README.md`
- Modify: `api/README.md`
- Modify: `tests/README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update D-012 without erasing its history**

In the D-012 row of `docs/decisions.md`, change its status to:

```text
Resolved locally by Gate 5-a
```

Append this paragraph to the D-012 detail section:

```markdown
**Gate 5-a resolution (2026-08-24):** the unified FastAPI composition now
adapts its policy repository to the existing product-side `SnapshotService`.
A snapshot published through the admin route is therefore immediately readable
by `recalc-tier` in the same process. This closes local snapshot visibility only;
real `policy.updated` fan-out, project selection, deployed services, and cloud
credentials remain Gate 5-b/deployment evidence.
```

- [ ] **Step 2: Mark the approved design as locally implemented**

Change the design status line to:

```markdown
**Status:** Implemented and verified locally; Gate 5-b fan-out remains open
```

Only make this status change after Task 3 tests are green.

- [ ] **Step 3: Document the composition in the repository guides**

Add this concise statement to the root `README.md` architecture/current-status section:

```markdown
- Gate 5-a snapshot bridge: the unified API injects the policy repository into
  the existing product `SnapshotService`, so an admin-published inline snapshot
  is available to `recalc-tier` without a second write path.
```

Add this to `api/README.md` near the dependency layout:

```markdown
In the unified app, lifespan startup creates the policy state first and builds
the default `AppContext` with a repository-backed `SnapshotService`. Supplying
an explicit `AppContext` keeps that context unchanged; standalone composition
continues to default to `FileSnapshotService`.
```

Add this to `tests/README.md` near the API/integration suite description:

```markdown
`test_app_policy_snapshot_bridge.py` is the local Gate 5-a closure: it publishes
v2 through the admin API and recalculates a provisional v1 project through the
internal API against that same v2 snapshot. It is not cloud or event-fan-out
evidence.
```

Add a 2026-08-24 Gate 5-a entry to `CHANGELOG.md`:

```markdown
### Gate 5-a — published snapshot read bridge

- Added a narrow policy snapshot repository read seam and a repository-backed
  implementation of the existing product `SnapshotService`.
- Unified FastAPI composition now shares published inline snapshots between
  admin publication and product recalculation while preserving explicit context
  injection and the file-backed standalone fallback.
- Added local HTTP acceptance for `publish v2 -> recalc-tier v2`; event fan-out,
  cloud deployment, and GCS pack resolution remain outside this gate.
```

- [ ] **Step 4: Run the focused Gate 5-a suite**

Run:

```bash
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python -m pytest \
  tests/policy/test_repository_interfaces.py \
  tests/policy/test_repository_snapshot_service.py \
  tests/test_app_policy_snapshot_bridge.py \
  tests/test_api_intake.py \
  tests/policy/test_admin_routes.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Run the full Python verification**

Run:

```bash
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python -m pytest -q
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python -m compileall -q api core schemas store workers tests
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python -m pip check
```

Expected: full pytest pass, compileall exit code 0, and `No broken requirements found.` Record the exact pytest count in the handoff; do not reuse the baseline count.

- [ ] **Step 6: Run Web regression checks**

Run:

```bash
npm --prefix web test
npm --prefix web run build
```

Expected: all Vitest tests pass and the Next production build exits 0. No UI change is expected from Gate 5-a.

- [ ] **Step 7: Run packaging verification**

Run:

```bash
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python -m pip wheel --no-deps --no-build-isolation --wheel-dir dist .
```

Expected: one project wheel is created successfully. Keep generated `dist/` artifacts untracked unless repository policy explicitly tracks them.

- [ ] **Step 8: Run source/cloud smoke with honest classification**

Run:

```bash
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python scripts/policy_gate4_smoke.py --source
/private/tmp/film-compliance-gate4-worktree/.venv/bin/python scripts/policy_gate4_smoke.py --cloud
```

Expected: source smoke passes. Cloud smoke may report `SKIP` when credentials or named resources are absent; record it as `SKIP`, never as `PASS`. A genuine configured-resource failure must remain a failure and be investigated before completion.

- [ ] **Step 9: Audit scope, typing, and unresolved markers**

Run:

```bash
git diff --check
git diff --name-only
rg -n 'T[B]D|T[O]DO|FIX[M]E|\.\.\.' \
  workers/policy/adapters/repository_snapshot.py \
  tests/policy/test_repository_snapshot_service.py \
  tests/test_app_policy_snapshot_bridge.py
```

Expected:

- `git diff --check` exits 0;
- changed files are limited to the file map in this plan;
- the marker scan produces no output;
- `WorkflowService` and `schemas/` have no diff;
- the adapter imports `SnapshotReadRepository`, while product code still imports only `SnapshotService`.

- [ ] **Step 10: Request independent code review before the final commit**

Ask the reviewer to check only Critical/Important issues against:

- effective-date parity with `FileSnapshotService`;
- missing-version fail-closed behavior;
- explicit-context preservation;
- lifecycle availability of `app.state.context`;
- publication/recalc repository identity;
- no overclaim of cloud or event fan-out.

Apply validated findings with their own failing regression test before changing implementation. Rerun the affected focused suite and the full Python suite after any fix.

- [ ] **Step 11: Commit documentation and final evidence**

```bash
git add \
  docs/decisions.md \
  docs/superpowers/specs/2026-08-24-policy-loop-gate5a-snapshot-bridge-design.md \
  README.md api/README.md tests/README.md CHANGELOG.md
git diff --cached --check
git commit -m "docs: record local snapshot bridge closure"
git status --short
```

Expected: commit succeeds and `git status --short` is empty. If generated packaging artifacts appear, remove only those known generated files before claiming a clean tree; do not clean unrelated user files.

## Completion evidence to report

The final Gate 5-a handoff must distinguish these outcomes:

- **PASS — local contract:** adapter parity tests and repository protocol tests.
- **PASS — local HTTP integration:** admin crawl/publish creates v2, product health sees v2, and internal recalc pins the project to v2 and clears provisional status.
- **PASS — regression:** exact Python/Web/build/package counts and commands from the current HEAD.
- **PASS or SKIP — cloud smoke:** report the tool's actual classification and reason.
- **OPEN — Gate 5-b:** real `policy.updated` delivery, affected-project selection, notification/timeline fan-out, and deployed cloud acceptance.

Do not describe Gate 5-a as full end-to-end production acceptance.
