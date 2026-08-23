# Policy Loop Gate 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal FastAPI policy administration API and a concise Next.js UI that completes the deterministic Gate 2 fixture crawl-to-publish loop in a real browser.

**Architecture:** A process-scoped `PolicyApiState` assembles the existing Gate 2 repository, refresh, publisher, dispatcher, file blob adapter, and a narrow run launcher. FastAPI owns HTTP concerns only; Next.js owns presentation only and reaches policy state exclusively through one typed API client.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, pytest, Next.js 16.3.2, React 19.2.8, TypeScript 5.9.3, Vitest 4.1.11, jsdom 30.0.1, React Testing Library 16.3.2.

---

## Scope guard

Gate 3 includes the seven `/v1/admin/policy/*` endpoints, mock admin authorization, background fixture crawl, API-specific response models, the two approved Policy Admin pages, component tests, production build, and a local browser acceptance run.

Excluded: real login, Firestore, GCS, Pub/Sub, Cloud Run, Scheduler, HTTP policy fetch, Gemini, persistence across API restarts, proposal editing, UI libraries, charts, and non-policy product pages.

Gate 3 is currently stacked on Gate 2 commit `ed1894e`. Before creating its PR, first merge Gate 2 PR #5 and then align this branch with the resulting `origin/main` so the Gate 3 PR contains no duplicate Gate 2 changes.

## File map

### Python

- `workers/policy/launch.py`: create run records and execute refresh without exposing refresh internals to HTTP routes.
- `workers/policy/local_demo.py`: expose the already-created file blob adapter to the Gate 3 assembly.
- `api/models/policy.py`: API-only request and response models; shared Gate 1 contracts remain unchanged.
- `api/errors.py`: typed HTTP errors, the stable error envelope, and FastAPI exception registration.
- `api/deps/policy.py`: process-scoped local state, fixture baseline initialization, clock injection, and mock admin dependency.
- `api/routes/admin_policy.py`: the seven thin management endpoints.
- `api/main.py`: FastAPI application factory, lifespan, and local CORS.
- `tests/policy/test_launch.py`: launcher RED/GREEN tests.
- `tests/policy/test_admin_routes.py`: API integration tests through `TestClient`.

### Web

- `web/package.json`, `web/package-lock.json`: exact Node dependency graph and scripts.
- `web/tsconfig.json`, `web/next.config.ts`, `web/vitest.config.ts`, `web/vitest.setup.ts`, `web/next-env.d.ts`: minimal Next.js and test configuration.
- `web/app/layout.tsx`, `web/app/globals.css`: one simple administration shell and approved visual tokens.
- `web/app/admin/policy/page.tsx`: thin list route.
- `web/app/admin/policy/proposals/[proposalId]/page.tsx`: thin detail route.
- `web/components/policy/policy-admin-page.tsx`: crawl/run/proposal/snapshot state and rendering.
- `web/components/policy/proposal-detail-page.tsx`: proposal read, effective-date guard, publish, and discard state.
- `web/lib/policy-api.ts`: all API DTOs, request code, and stable `PolicyApiError`.
- `web/tests/policy-api.test.ts`: real API client behavior against a stubbed network boundary.
- `web/tests/policy-admin-page.test.tsx`: list, crawl polling, reload, and inline error behavior.
- `web/tests/proposal-detail-page.test.tsx`: future-effective guard and mutation/navigation behavior.

## Task 1: Add the narrow policy run launcher

**Files:**

- Create: `workers/policy/launch.py`
- Create: `tests/policy/test_launch.py`

- [ ] **Step 1: Write the failing launcher tests**

Create tests for deterministic IDs, immediate running state, execution delegation, and unknown source rejection:

```python
NOW = datetime(2026, 8, 23, 20, 0, tzinfo=timezone(timedelta(hours=8)))
SOURCE = PolicySource(
    source_id="nrta_micro_drama",
    url="https://www.nrta.gov.cn/example",
    content_selector="#zoom",
    enabled=True,
)
FIXTURES = Path(__file__).parents[1] / "fixtures" / "policy"


def build_launcher(
    tmp_path: Path,
) -> tuple[PolicyRunLauncher, InMemoryPolicyRepository]:
    repository = InMemoryPolicyRepository()
    refresh = PolicyRefreshModule(
        sources={SOURCE.source_id: SOURCE},
        fetcher=FixtureSourceFetcher(
            {SOURCE.source_id: FIXTURES / "source-v1.html"}
        ),
        blob_store=FileBlobStore(tmp_path / "blobs"),
        proposal_model=FakeProposalModel(
            ProposalDraft(
                summary="unused baseline draft",
                impact=[ImpactNode.D1C],
                effective_from=NOW,
                draft_pack_updates={
                    PackName.P3_TIER_THRESHOLDS: {
                        "thresholds_published": True
                    }
                },
            )
        ),
        repository=repository,
    )
    return (
        PolicyRunLauncher(repository, refresh, {SOURCE.source_id}),
        repository,
    )


def test_launch_creates_running_record_before_execution(tmp_path: Path) -> None:
    launcher, repository = build_launcher(tmp_path)
    run_id = launcher.launch(SOURCE.source_id, NOW)
    assert run_id == "run_001"
    assert repository.get_run(run_id).status == "running"


def test_execute_completes_the_created_run(tmp_path: Path) -> None:
    launcher, repository = build_launcher(tmp_path)
    run_id = launcher.launch(SOURCE.source_id, NOW)
    result = asyncio.run(launcher.execute(run_id, SOURCE.source_id, NOW))
    assert result.run_id == run_id
    assert repository.get_run(run_id).status == "no_change"


def test_unknown_source_is_rejected_without_a_run(tmp_path: Path) -> None:
    launcher, repository = build_launcher(tmp_path)
    with pytest.raises(PolicyLaunchError) as exc_info:
        launcher.launch("missing_source", NOW)
    assert exc_info.value.code == "POLICY_SOURCE_NOT_FOUND"
    assert repository.list_runs() == {}
```

Add `InMemoryPolicyRepository.list_runs()` only through a test that first fails because the read API is absent. It must return deep copies like the existing list methods.

- [ ] **Step 2: Run RED**

Run:

```bash
.venv/bin/pytest tests/policy/test_launch.py -q
```

Expected: collection fails because `workers.policy.launch` does not exist.

- [ ] **Step 3: Implement the minimum launcher**

Implement this public shape:

```python
class PolicyLaunchError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class PolicyRunLauncher:
    def __init__(
        self,
        repository: InMemoryPolicyRepository,
        refresh: PolicyRefreshModule,
        source_ids: set[str],
    ) -> None:
        self._repository = repository
        self._refresh = refresh
        self._source_ids = frozenset(source_ids)
        self._counter = 0

    def launch(self, source_id: str, now: datetime) -> str:
        if source_id not in self._source_ids:
            raise PolicyLaunchError(
                "POLICY_SOURCE_NOT_FOUND", "policy source not found"
            )
        self._counter += 1
        run_id = f"run_{self._counter:03d}"
        self._repository.create_run(run_id, source_id, now)
        return run_id

    async def execute(
        self, run_id: str, source_id: str, now: datetime
    ) -> RefreshResult:
        return await self._refresh.run(run_id, source_id, now)
```

`launch` validates `source_id` before incrementing the counter, generates `run_001`, `run_002`, and so on, then calls `repository.create_run`. `execute` only calls `refresh.run`; it does not catch or rewrite `PolicyRefreshError`.

- [ ] **Step 4: Run GREEN and regression**

```bash
.venv/bin/pytest tests/policy/test_launch.py -q
.venv/bin/pytest -q
```

Expected: launcher tests pass and the previous 47 tests remain green.

- [ ] **Step 5: Commit**

```bash
git add workers/policy/launch.py workers/policy/repository.py tests/policy/test_launch.py
git commit -m "feat: launch local policy refresh runs"
```

## Task 2: Define the API boundary and read endpoints

**Files:**

- Modify: `pyproject.toml`
- Create: `api/__init__.py`
- Create: `api/models/__init__.py`
- Create: `api/models/policy.py`
- Create: `api/errors.py`
- Create: `api/deps/__init__.py`
- Create: `api/deps/policy.py`
- Create: `api/routes/__init__.py`
- Create: `api/routes/admin_policy.py`
- Create: `api/main.py`
- Modify: `workers/policy/local_demo.py`
- Create: `tests/policy/test_admin_routes.py`

- [ ] **Step 1: Add test infrastructure only**

Add runtime dependencies and package discovery:

```toml
dependencies = [
  "beautifulsoup4>=4.13,<5",
  "fastapi>=0.116,<1",
  "pydantic>=2.11,<3",
  "PyYAML>=6,<7",
  "uvicorn>=0.35,<1",
]

[project.optional-dependencies]
test = [
  "httpx>=0.28,<1",
  "pytest>=8,<9",
]

[tool.setuptools.packages.find]
include = ["api*", "schemas*", "workers*"]
```

Install the updated editable project:

```bash
.venv/bin/python -m pip install -e '.[test]'
```

- [ ] **Step 2: Write failing auth and read tests**

Use `with TestClient(create_app(state)) as client:` and a fixed `NOW`. Cover:

```python
def test_admin_routes_require_mock_admin(api_client: TestClient) -> None:
    response = api_client.get("/v1/admin/policy/snapshots")
    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "POLICY_ADMIN_FORBIDDEN",
            "message": "admin role required",
            "details": {},
        }
    }


def test_seed_snapshot_is_listed(api_client: TestClient) -> None:
    response = admin_get(api_client, "/v1/admin/policy/snapshots")
    assert response.status_code == 200
    assert [row["version"] for row in response.json()] == ["v1"]


def test_missing_run_and_proposal_use_stable_envelopes(
    api_client: TestClient,
) -> None:
    run = admin_get(api_client, "/v1/admin/policy/runs/missing")
    proposal = admin_get(api_client, "/v1/admin/policy/proposals/missing")
    assert (run.status_code, run.json()["error"]["code"]) == (
        404,
        "POLICY_RUN_NOT_FOUND",
    )
    assert (proposal.status_code, proposal.json()["error"]["code"]) == (
        404,
        "POLICY_PROPOSAL_NOT_FOUND",
    )
```

The `state` fixture calls `asyncio.run(build_local_policy_api_state(tmp_path / "blobs", clock=lambda: NOW))`. A proposal-detail fixture then creates and executes one launcher run directly:

```python
run_id = state.launcher.launch(SOURCE_ID, NOW)
asyncio.run(state.launcher.execute(run_id, SOURCE_ID, NOW))
assert run_id == "run_001"
```

This exercises the real Gate 2 Diff path without depending on the command route that Task 3 adds.

Seed a proposal through the state fixture and assert pending filtering, descending `created_at`, the parsed `source_diff_text`, and no internal filesystem path in error responses.

- [ ] **Step 3: Run RED**

```bash
.venv/bin/pytest tests/policy/test_admin_routes.py -q
```

Expected: collection fails because `api.main` and response models do not exist.

- [ ] **Step 4: Implement API-only models**

Define strict Pydantic models with `ConfigDict(extra="forbid")`:

```python
class CrawlRequest(ApiModel):
    source_id: str


class CrawlResponse(ApiModel):
    run_id: str


class ProposalSummary(ApiModel):
    proposal_id: str
    summary: str
    impact: list[ImpactNode]
    effective_from: AwareDatetime
    status: ProposalStatus


class ProposalDetail(ProposalSummary):
    source_diff_uri: str
    source_diff_text: str
    draft_pack_updates: dict[PackName, dict[str, Any]]
    published_version: Version | None


class SnapshotSummary(ApiModel):
    version: Version
    published_at: AwareDatetime
    effective_from: AwareDatetime
    published_by: str
    thresholds_published: bool
```

Also define:

```python
class PolicyRunResponse(ApiModel):
    run_id: str
    source_id: str
    status: Literal["running", "no_change", "proposal_created", "failed"]
    started_at: AwareDatetime
    finished_at: AwareDatetime | None
    previous_sha256: str | None
    current_sha256: str | None
    proposal_id: str | None
    error: str | None


class PublishResponse(ApiModel):
    snapshot_version: Version
```

- [ ] **Step 5: Implement stable API errors and authorization**

Use one exception type:

```python
class PolicyApiError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
```

Register a handler that returns exactly `{"error": {"code", "message", "details"}}`. `require_admin` reads `X-Mock-Role` with `Header(default=None)` and raises `POLICY_ADMIN_FORBIDDEN` unless it equals `admin`.

- [ ] **Step 6: Implement the injected API state, local assembly, and read routes**

`PolicyApiState` has exactly these fields:

```python
@dataclass(frozen=True)
class PolicyApiState:
    repository: InMemoryPolicyRepository
    launcher: PolicyRunLauncher
    publisher: PolicyPublisher
    dispatcher: OutboxDispatcher
    blob_store: FileBlobStore
    clock: Callable[[], datetime]
```

Modify `LocalPolicyLoop` to expose the single `FileBlobStore` already used by refresh; do not create a second store.

Implement `build_local_policy_api_state(blob_root, clock)` in this task. It builds the Gate 2 loop with seed v1, fixture v1, a fixed already-effective proposal draft, and the fake event publisher; creates and awaits `run_baseline`; switches the fetcher to fixture v2; then returns `PolicyApiState` with a fresh launcher whose first public run is `run_001`. A baseline failure propagates and prevents the API from serving a broken demo.

Implement `create_app(initial_state)` for injected test state: install the exception handler, store the state on `app.state.policy`, and include the read router. Task 3 extends the same factory with its default lifespan and CORS; do not create a second application factory.

Implement `get_policy_state(request: Request) -> PolicyApiState`. Read routes use repository public methods, sort proposals by `created_at` descending and snapshots by `published_at` descending, and map missing keys to the documented 404 codes.

For proposal detail:

```python
try:
    raw = json.loads(state.blob_store.read_text(proposal.source_diff_uri))
    source_diff_text = PolicyDiff.model_validate(raw).unified_diff
except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
    raise PolicyApiError(
        500,
        "POLICY_BLOB_READ_FAILED",
        "proposal diff could not be read",
    ) from exc
```

Do not include `exc`, URI, or path in the response.

- [ ] **Step 7: Run GREEN and regression**

```bash
.venv/bin/pytest tests/policy/test_admin_routes.py -q
.venv/bin/pytest -q
```

Expected: read tests pass and all previous tests remain green.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml api workers/policy/local_demo.py tests/policy/test_admin_routes.py
git commit -m "feat: expose policy administration reads"
```

## Task 3: Add crawl, publish, discard, and the default app lifespan

**Files:**

- Modify: `api/deps/policy.py`
- Modify: `api/routes/admin_policy.py`
- Modify: `api/main.py`
- Modify: `tests/policy/test_admin_routes.py`

- [ ] **Step 1: Write failing command tests**

Add route tests that prove behavior instead of method calls:

```python
def test_crawl_returns_202_and_background_task_creates_proposal(
    api_client: TestClient,
) -> None:
    response = admin_post(
        api_client,
        "/v1/admin/policy/crawl",
        json={"source_id": SOURCE_ID},
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    run = admin_get(api_client, f"/v1/admin/policy/runs/{run_id}").json()
    assert run["status"] == "proposal_created"
    assert run["proposal_id"] == "proposal_001"


def test_publish_creates_v2_and_snapshot_list_is_descending(
    api_client: TestClient,
) -> None:
    proposal_id = crawl_to_proposal(api_client)
    response = admin_post(
        api_client,
        f"/v1/admin/policy/proposals/{proposal_id}/publish",
    )
    assert response.status_code == 201
    assert response.json() == {"snapshot_version": "v2"}
    snapshots = admin_get(api_client, "/v1/admin/policy/snapshots").json()
    assert [row["version"] for row in snapshots] == ["v2", "v1"]
```

Also add separate tests for unknown source 404, future-effective 409, discard 204, repeated mutation 409, and a failing fake event publisher that leaves the outbox pending while Publish still returns 201. Add an OPTIONS preflight test with origin `http://127.0.0.1:3000` and assert `access-control-allow-origin` returns that exact origin; use an unapproved origin in a second assertion and confirm the header is absent.

- [ ] **Step 2: Run RED**

```bash
.venv/bin/pytest tests/policy/test_admin_routes.py -q
```

Expected: command routes return 404 or 405 because they are absent.

- [ ] **Step 3: Implement command routes**

The crawl route must preserve `202` semantics:

```python
now = state.clock()
run_id = state.launcher.launch(body.source_id, now)
background_tasks.add_task(
    state.launcher.execute,
    run_id,
    body.source_id,
    now,
)
return CrawlResponse(run_id=run_id)
```

Publish calls `state.publisher.publish(proposal_id, "admin_richard", state.clock())`, maps the three `PolicyPublishError` codes to 409/503, calls `state.dispatcher.dispatch()` after success, and returns 201 with only `snapshot_version`.

Discard calls the existing publisher method and returns an empty `Response(status_code=204)`.

- [ ] **Step 4: Implement app lifespan and CORS**

`create_app(initial_state: PolicyApiState | None = None)` must:

- install the policy exception handler;
- include the admin router;
- allow only `http://localhost:3000` and `http://127.0.0.1:3000` via `CORSMiddleware`;
- allow methods `GET`, `POST`, and `OPTIONS`, and headers `Content-Type` and `X-Mock-Role`;
- use the injected state unchanged in tests;
- otherwise create a `TemporaryDirectory`, await `build_local_policy_api_state`, store it on `app.state.policy`, yield, and clean up at shutdown.

Baseline errors propagate out of lifespan and prevent startup. Do not catch them and expose an empty application.

Expose `app = create_app()` for:

```bash
.venv/bin/uvicorn api.main:app --reload --port 8000
```

- [ ] **Step 5: Run GREEN and Python verification**

```bash
.venv/bin/pytest tests/policy/test_admin_routes.py -q
.venv/bin/pytest -q
.venv/bin/python -m compileall -q api schemas workers
.venv/bin/python -m pip check
```

Expected: all tests pass, compile exits 0, and pip reports no broken requirements.

- [ ] **Step 6: Commit**

```bash
git add api tests/policy/test_admin_routes.py
git commit -m "feat: complete local policy admin commands"
```

## Task 4: Scaffold and test the typed web API client

**Files:**

- Modify: `.gitignore`
- Create: `web/package.json`
- Create: `web/package-lock.json`
- Create: `web/tsconfig.json`
- Create: `web/next.config.ts`
- Create: `web/next-env.d.ts`
- Create: `web/vitest.config.ts`
- Create: `web/vitest.setup.ts`
- Create: `web/lib/policy-api.ts`
- Create: `web/tests/policy-api.test.ts`

- [ ] **Step 1: Create test and build configuration**

Initialize only the approved packages:

```bash
cd web
npm install --save-exact next@16.3.2 react@19.2.8 react-dom@19.2.8
npm install --save-dev --save-exact typescript@5.9.3 @types/node@26.2.0 @types/react@19.2.18 @types/react-dom@19.2.4 vitest@4.1.11 jsdom@30.0.1 @testing-library/react@16.3.2 @testing-library/jest-dom@7.0.1 @testing-library/user-event@14.6.6
```

`package.json` scripts must be exactly:

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run"
  }
}
```

Configure the `@/*` alias to the `web/` root in both TypeScript and Vitest. Use jsdom and load `@testing-library/jest-dom/vitest` from `vitest.setup.ts`. Ignore `web/node_modules/`, `web/.next/`, and `web/coverage/`.

- [ ] **Step 2: Write failing real-client tests**

Stub only `globalThis.fetch`. Test that the real client sends the role header, uses the configured base URL, decodes success, accepts 204, and turns the error envelope into `PolicyApiError`:

```typescript
it("sends the admin role and decodes a crawl", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ run_id: "run_001" }), { status: 202 }),
  );
  vi.stubGlobal("fetch", fetchMock);

  await expect(startCrawl(SOURCE_ID)).resolves.toEqual({ run_id: "run_001" });
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8000/v1/admin/policy/crawl",
    expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ "X-Mock-Role": "admin" }),
    }),
  );
});
```

- [ ] **Step 3: Run RED**

```bash
npm --prefix web test -- policy-api.test.ts
```

Expected: import fails because `web/lib/policy-api.ts` does not exist.

- [ ] **Step 4: Implement the typed client**

Define DTOs matching the Pydantic response models and one request helper:

```typescript
export class PolicyApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown>,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-Mock-Role": "admin",
      ...init?.headers,
    },
  });
  if (!response.ok) throw await decodePolicyError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
```

Export the seven functions approved in the spec; page code must not call `fetch` directly.

- [ ] **Step 5: Run GREEN**

```bash
npm --prefix web test -- policy-api.test.ts
```

Expected: all policy API client tests pass.

- [ ] **Step 6: Commit**

```bash
git add .gitignore web/package.json web/package-lock.json web/tsconfig.json web/next.config.ts web/next-env.d.ts web/vitest.config.ts web/vitest.setup.ts web/lib web/tests/policy-api.test.ts
git commit -m "feat: add typed policy web client"
```

## Task 5: Build the concise Policy Admin list page

**Files:**

- Create: `web/app/layout.tsx`
- Create: `web/app/globals.css`
- Create: `web/app/admin/policy/page.tsx`
- Create: `web/components/policy/policy-admin-page.tsx`
- Create: `web/tests/policy-admin-page.test.tsx`

- [ ] **Step 1: Write failing list-page tests**

Stub the imported API module at the network seam. Cover initial content, crawl terminal handling, data reload, and one inline error:

```typescript
it("shows the fixture label, pending proposals, and snapshots", async () => {
  listPendingProposals.mockResolvedValue([PROPOSAL]);
  listSnapshots.mockResolvedValue([SNAPSHOT]);
  render(<PolicyAdminPage />);
  expect(screen.getByText("Synthetic local fixture")).toBeInTheDocument();
  expect(await screen.findByText(PROPOSAL.summary)).toBeInTheDocument();
  expect(screen.getByText("v1")).toBeInTheDocument();
});


it("runs a crawl until terminal state and reloads proposals", async () => {
  startCrawl.mockResolvedValue({ run_id: "run_001" });
  getRun.mockResolvedValue({
    run_id: "run_001",
    source_id: SOURCE_ID,
    status: "proposal_created",
    proposal_id: "proposal_001",
  });
  render(<PolicyAdminPage pollDelayMs={0} />);
  await userEvent.click(screen.getByRole("button", { name: "Run fixture crawl" }));
  expect(await screen.findByText("proposal_created")).toBeInTheDocument();
  expect(listPendingProposals).toHaveBeenCalledTimes(2);
});
```

The public `pollDelayMs` prop is a legitimate polling configuration with a production default of 1000 ms; it is not a test-only state mutation method.

- [ ] **Step 2: Run RED**

```bash
npm --prefix web test -- policy-admin-page.test.tsx
```

Expected: component import fails.

- [ ] **Step 3: Implement the page state and semantic markup**

`PolicyAdminPage` must:

- load proposals and snapshots with `Promise.all` on mount;
- show a busy crawl button while starting or polling;
- call `getRun` until `no_change`, `proposal_created`, or `failed`;
- stop polling and show an inline `role="alert"` on any API failure;
- reload proposals and snapshots after a successful terminal run;
- render proposal links with `/admin/policy/proposals/${proposal_id}`;
- render status text in addition to status color;
- clear scheduled timers on unmount.

The route file only renders `<PolicyAdminPage />`.

- [ ] **Step 4: Implement the approved minimal CSS**

Define CSS custom properties for background, surface, border, text, muted text, blue action, success, warning, and danger. Use a centered `max-width: 960px`, 8/16/24/32 px spacing, native system fonts, visible focus outlines, wrapping tables/cards at narrow widths, and `pre { overflow-x: auto; }`. Do not add images, remote fonts, icons, animations, or dark mode.

- [ ] **Step 5: Run GREEN and build**

```bash
npm --prefix web test -- policy-admin-page.test.tsx
npm --prefix web test
npm --prefix web run build
```

Expected: component tests pass and Next production build succeeds.

- [ ] **Step 6: Commit**

```bash
git add web/app web/components/policy/policy-admin-page.tsx web/tests/policy-admin-page.test.tsx
git commit -m "feat: add policy administration list page"
```

## Task 6: Build the proposal detail and human actions

**Files:**

- Create: `web/app/admin/policy/proposals/[proposalId]/page.tsx`
- Create: `web/components/policy/proposal-detail-page.tsx`
- Create: `web/tests/proposal-detail-page.test.tsx`

- [ ] **Step 1: Write failing detail tests**

Test read rendering, the future-effective guard, publish, discard, and inline errors:

```typescript
it("disables publish for a future-effective proposal", async () => {
  getProposal.mockResolvedValue({
    ...PROPOSAL_DETAIL,
    effective_from: "2999-01-01T00:00:00Z",
  });
  render(<ProposalDetailPage proposalId="proposal_001" />);
  expect(await screen.findByText(PROPOSAL_DETAIL.summary)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Publish" })).toBeDisabled();
  expect(screen.getByText(/not effective yet/i)).toBeInTheDocument();
});


it("publishes and returns to the policy list", async () => {
  getProposal.mockResolvedValue(PROPOSAL_DETAIL);
  publishProposal.mockResolvedValue({ snapshot_version: "v2" });
  render(<ProposalDetailPage proposalId="proposal_001" />);
  await userEvent.click(await screen.findByRole("button", { name: "Publish" }));
  expect(publishProposal).toHaveBeenCalledWith("proposal_001");
  expect(push).toHaveBeenCalledWith("/admin/policy");
});
```

Use an equivalent independent test for Discard. Mock only `useRouter` and the API module.

- [ ] **Step 2: Run RED**

```bash
npm --prefix web test -- proposal-detail-page.test.tsx
```

Expected: component import fails.

- [ ] **Step 3: Implement the detail component and route**

`ProposalDetailPage` must:

- fetch once when `proposalId` changes;
- show summary, impact chips, formatted effective time, `pre` source Diff, and a native `<details>` JSON preview;
- compute future-effective with `Date.parse(proposal.effective_from) > Date.now()`;
- disable both mutation buttons while either request is pending;
- independently disable Publish and explain why when future-effective;
- call the typed client and `router.push("/admin/policy")` on success;
- preserve the page and show `role="alert"` on failure.

The dynamic route uses `useParams<{ proposalId: string }>()` and passes the value into the component. Do not duplicate data access in the route.

- [ ] **Step 4: Run GREEN and web verification**

```bash
npm --prefix web test -- proposal-detail-page.test.tsx
npm --prefix web test
npm --prefix web run build
```

Expected: all web tests and the production build pass.

- [ ] **Step 5: Commit**

```bash
git add web/app/admin/policy/proposals web/components/policy/proposal-detail-page.tsx web/tests/proposal-detail-page.test.tsx
git commit -m "feat: add policy proposal review page"
```

## Task 7: Document, run the browser gate, and close review findings

**Files:**

- Modify: `api/README.md`
- Modify: `web/app/admin/policy/README.md`
- Modify: `tests/README.md`
- Modify: `docs/README.md`
- Modify: `README.md`

- [ ] **Step 1: Update only current-state documentation**

Document two local commands:

```bash
.venv/bin/uvicorn api.main:app --reload --port 8000
npm --prefix web run dev
```

State explicitly that Gate 3 uses synthetic fixtures and in-memory state, resets on API restart, and does not prove real policy, Gemini, GCP, or deployment behavior. Update the repository status so it no longer claims that no API or UI exists.

- [ ] **Step 2: Run complete automated verification**

```bash
.venv/bin/pytest -q
.venv/bin/python -m compileall -q api schemas workers
.venv/bin/python -m pip check
npm --prefix web test
npm --prefix web run build
git diff --check
git status --short
```

Expected: Python tests, web tests, compile, dependency check, and production build all pass; diff check is clean; status contains only Gate 3 files.

- [ ] **Step 3: Run real-browser acceptance**

Start API and web servers in separate sessions. In a real browser:

1. Open `http://127.0.0.1:3000/admin/policy`.
2. Confirm `Synthetic local fixture` is visible.
3. Click `Run fixture crawl` and wait for `proposal_created`.
4. Open `proposal_001`.
5. Confirm summary, `D1c`, effective time, source Diff, and pack JSON.
6. Click `Publish`.
7. Confirm the list shows snapshots in `v2`, `v1` order and v2 thresholds are published.
8. Request `http://127.0.0.1:8000/v1/admin/policy/snapshots` without `X-Mock-Role`; confirm the stable 403 envelope.
9. Save one list-page screenshot and one proposal-detail screenshot under a temporary QA directory outside the repository; visually inspect both for clipping, overlap, unreadable contrast, and narrow-width overflow.

- [ ] **Step 4: Request independent code review**

Review the complete Gate 3 diff against the approved spec. Treat Critical and Important findings as blockers. For every accepted defect, first add a failing regression test, observe RED, implement the minimum fix, and rerun the focused and full suites.

- [ ] **Step 5: Align with main after Gate 2 merges**

After PR #5 is merged:

```bash
git fetch origin
git rebase origin/main
```

Resolve only Gate 3 branch conflicts. Rerun the complete automated verification and browser acceptance after the rebase. Do not force-push until the rebased history and diff against `origin/main` are verified.

- [ ] **Step 6: Final verification and handoff**

```bash
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
git status -sb
```

Expected: only Gate 3 design, plan, API, web, tests, and docs differ; the worktree is clean; the branch is ready to push and open as a ready PR.

## Gate 3 exit criteria

- Browser crawl returns a run ID and reaches `proposal_created` through a background refresh.
- The proposal detail displays the actual Gate 2 file-backed Diff through an API DTO.
- Publish creates v2, best-effort dispatches the outbox, and snapshot history reads v2 before v1.
- Discard and repeated mutations preserve the Gate 2 state machine.
- A future-effective proposal is blocked in both the component and Publisher-backed API.
- Every management endpoint rejects requests without the mock admin role.
- Python tests, web tests, compile checks, dependency checks, and Next production build pass.
- The real browser fixture crawl-to-publish flow passes with no visible layout defects.
- Independent review has no unresolved Critical or Important finding.
- No Gate 4 cloud adapter or Gate 5 deployment work is present.
