# Upload-first Demo Review Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task by task. Every production change follows red → green → refactor; do not skip the failing-test observation.

**Goal:** Replace the creator demo entry with an English upload-first review flow that extracts editable project details, pauses for confirmation, then classifies, analyzes risk, fills a form, and exposes three review artifacts.

**Architecture:** Add a deep `ReviewFacade` module over the existing project workflow, asset, classification, finding, form, and storage services. A small `ReviewSession` state machine is the only orchestration contract exposed to the new API and React flow. Existing project APIs and staff/admin pages remain implemented but are unlinked and outside the demo path.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, in-memory/SQLite document stores, python-docx, ReportLab, React 19, Next.js 16, Vitest/Testing Library, Playwright.

**Authoritative design:** `docs/technical/upload-first-demo-review-tdd.md`

---

### Task 1: Add ReviewSession contracts and store adapters

**Files:**

- Create: `schemas/reviews.py`
- Modify: `schemas/__init__.py`
- Modify: `core/repositories.py`
- Modify: `store/memory.py`
- Modify: `store/sqlite.py`
- Modify: `tests/test_store_conformance.py`
- Create: `tests/test_review_sessions.py`

**Step 1: Write failing contract tests**

Cover:

- `ConfirmedReviewDetails` rejects `AmountBracket.UNKNOWN`, empty tags, duplicate/blank tags, and tags over 40 characters;
- script sessions from `EXTRACTING` onward require source references;
- idea sessions reject source references;
- `FAILED` requires error code/message and `COMPLETE` requires confirmed details;
- both memory and SQLite stores round-trip `ReviewSession` exactly and SQLite survives adapter reconstruction.

Use one shared conformance helper:

```python
def assert_review_session_store(store, reopen=None):
    saved = store.put(make_review_session())
    assert store.get(saved.review_id) == saved
    if reopen is not None:
        assert reopen().get(saved.review_id) == saved
```

**Step 2: Run tests and verify RED**

```bash
.venv/bin/python -m pytest -o addopts='' -q \
  tests/test_review_sessions.py tests/test_store_conformance.py
```

Expected: import/attribute failures because the contracts and adapters do not exist.

**Step 3: Implement the minimal contracts and adapters**

Implement the enums/models exactly as section 6 of the technical design. Add only:

```python
class ReviewSessionStore(Protocol):
    def put(self, session: ReviewSession) -> ReviewSession: ...
    def get(self, review_id: str) -> ReviewSession | None: ...
```

Use the existing SQLite documents table with logical collection `review_sessions`; do not add a migration or a list/delete interface.

**Step 4: Run focused and regression tests**

```bash
.venv/bin/python -m pytest -o addopts='' -q \
  tests/test_review_sessions.py tests/test_store_conformance.py \
  tests/test_schema_attribute_reads.py
```

**Step 5: Commit**

```bash
git add schemas/reviews.py schemas/__init__.py core/repositories.py \
  store/memory.py store/sqlite.py tests/test_review_sessions.py \
  tests/test_store_conformance.py
git commit -m "feat: add review session contracts"
```

### Task 2: Parse and preserve uploaded scripts

**Files:**

- Create: `core/script_text.py`
- Modify: `schemas/assets.py`
- Modify: `core/errors.py`
- Modify: `pyproject.toml`
- Create: `tests/test_script_text.py`
- Modify: `tests/test_uploads.py`

**Step 1: Write failing parser tests**

Use `tests/fixtures/scripts/e2e-30min-public-security.md` to assert:

```python
parsed = parse_script(FIXTURE.name, FIXTURE.read_bytes())
assert parsed.title == "先挂电话"
assert parsed.structure.source_episode_count == 1
assert parsed.structure.source_total_minutes == 30
assert parsed.structure.source_scene_count == 15
```

Also test strict UTF-8/BOM handling, empty input, unsupported extension, 5 MiB limit, fake/empty DOCX, DOCX paragraph/table order, and inert prompt-injection text.

**Step 2: Run tests and verify RED**

```bash
.venv/bin/python -m pytest -o addopts='' -q tests/test_script_text.py
```

**Step 3: Implement minimal parser and dependency changes**

- add runtime dependencies `python-docx`, `python-multipart`, and `reportlab`;
- add `pytest-asyncio>=0.25,<1` to the test extra;
- add optional `text_storage_uri` to `AssetVersion` while preserving old JSON compatibility;
- add structured input errors and status mapping;
- ensure raw SHA-256 always covers original bytes, never normalized text.

**Step 4: Run focused tests**

```bash
.venv/bin/python -m pytest -o addopts='' -q \
  tests/test_script_text.py tests/test_uploads.py tests/test_response_schemas.py
```

**Step 5: Commit**

```bash
git add core/script_text.py schemas/assets.py core/errors.py pyproject.toml \
  tests/test_script_text.py tests/test_uploads.py
git commit -m "feat: parse review script uploads"
```

### Task 3: Extract safe intake candidates

**Files:**

- Create: `core/script_intake.py`
- Modify: `core/llm.py`
- Modify: `prompts/` (add the versioned intake prompt in the existing prompt layout)
- Create: `tests/test_script_intake.py`

**Step 1: Write failing analyzer tests**

Add a scripted adapter that returns tags, synopsis, `10 × 3 minutes`, and an amount band. Assert deterministic title/structure provenance, suggested-field explanations, document delimiters, allowed threshold values, partial validation, and `UnavailableLLM` fallback.

**Step 2: Run tests and verify RED**

```bash
.venv/bin/python -m pytest -o addopts='' -q tests/test_script_intake.py
```

**Step 3: Implement analyzer**

Make one structured LLM request with `SCRIPT_INTAKE_PROMPT_ID="script_intake"`, version `v1`. Treat document content only as data inside `<<<DOC>>>`; discard unknown bands, false quotes, negative counts, non-conserving durations, and overlong values as partial output.

**Step 4: Run focused tests**

```bash
.venv/bin/python -m pytest -o addopts='' -q \
  tests/test_script_intake.py tests/test_jobs.py tests/test_fact_extraction.py
```

**Step 5: Commit**

```bash
git add core/script_intake.py core/llm.py prompts tests/test_script_intake.py
git commit -m "feat: extract review intake candidates"
```

### Task 4: Bridge confirmed values into the existing workflow

**Files:**

- Modify: `core/workflow_service.py`
- Modify: `core/review.py`
- Modify: `schemas/enums.py`
- Create: `tests/test_review_confirmation.py`
- Modify: `tests/test_script_review.py`

**Step 1: Write failing confirmation tests**

Assert that `apply_review_confirmation` writes title, confirmed intent, `USER_ANSWER` facts, and correct stage (`SCRIPT_READY` or `IDEA`) in one workflow-owned operation. Add a semantic-backend failure test proving deterministic findings remain and status becomes pending rather than pass.

**Step 2: Run tests and verify RED**

```bash
.venv/bin/python -m pytest -o addopts='' -q \
  tests/test_review_confirmation.py tests/test_script_review.py
```

**Step 3: Implement the bridge and semantic fallback**

Do not allow candidate values to call this method. Only `ConfirmedReviewDetails` enter the project aggregate. Record `review.details_confirmed` without copying story text into timeline details.

**Step 4: Run focused regression tests**

```bash
.venv/bin/python -m pytest -o addopts='' -q \
  tests/test_review_confirmation.py tests/test_script_review.py \
  tests/test_fact_extraction.py tests/test_classify.py tests/test_guards.py
```

**Step 5: Commit**

```bash
git add core/workflow_service.py core/review.py schemas/enums.py \
  tests/test_review_confirmation.py tests/test_script_review.py
git commit -m "feat: apply confirmed review details"
```

### Task 5: Implement ReviewFacade and fixture-level state machine

**Files:**

- Create: `core/review_facade.py`
- Modify: `api/deps/services.py`
- Create: `tests/test_review_facade.py`
- Create: `tests/test_review_demo_fixture.py`

**Step 1: Write failing facade tests**

Test start, get, confirm, retry, owner isolation, idea mode, idempotent duplicate confirmation, manual confirmation after intake failure, semantic pending, and memory/SQLite restoration. Assert candidates do not mutate project intent before confirmation.

The fixture acceptance must prove:

- original checksum unchanged;
- extracted `先挂电话`, source `1 × 30`, suggested `10 × 3`;
- user confirmation precedes classification;
- result is Class 1 / co-review / public-security subject;
- scenes 3, 4, 10, 11, and 14 are located as needs-human findings;
- unrelated sensitive categories are absent.

**Step 2: Run tests and verify RED**

```bash
.venv/bin/python -m pytest -o addopts='' -q \
  tests/test_review_facade.py tests/test_review_demo_fixture.py
```

**Step 3: Implement the facade**

Expose only:

```python
start(command)
get(review_id, actor_uid)
confirm(review_id, actor_uid, details)
retry_intake(review_id, actor_uid)
source(review_id, actor_uid)
artifact(review_id, actor_uid, artifact_type)
```

Build a UI-safe `ReviewView` projection that excludes project IDs, asset IDs, raw workflow states, task IDs, internal flags, and policy pack names.

**Step 4: Run focused and core regression tests**

```bash
.venv/bin/python -m pytest -o addopts='' -q \
  tests/test_review_facade.py tests/test_review_demo_fixture.py \
  tests/test_default_v2_integration.py tests/test_golden_samples.py
```

**Step 5: Commit**

```bash
git add core/review_facade.py api/deps/services.py \
  tests/test_review_facade.py tests/test_review_demo_fixture.py
git commit -m "feat: orchestrate upload-first reviews"
```

### Task 6: Generate immutable review artifacts

**Files:**

- Create: `core/review_artifacts.py`
- Create: `tests/test_review_artifacts.py`
- Modify: `core/review_facade.py`

**Step 1: Write failing artifact tests**

Assert PDF magic/media type/file names, confirmed values, classification boundary, applicant placeholder, findings/evidence/semantic status, and full annotated source preservation with stable `RISK-###` notes. Assert idea mode exposes only the form and renderer failure leaves session COMPLETE.

**Step 2: Run tests and verify RED**

```bash
.venv/bin/python -m pytest -o addopts='' -q tests/test_review_artifacts.py
```

**Step 3: Implement pure artifact composition**

`ArtifactComposer` receives an immutable package and never reads stores or invokes analysis. Use `STSong-Light` for Chinese PDF text and Helvetica for English. Insert Markdown annotations as HTML comments after matching source lines.

**Step 4: Run focused tests**

```bash
.venv/bin/python -m pytest -o addopts='' -q \
  tests/test_review_artifacts.py tests/test_review_demo_fixture.py
```

**Step 5: Commit**

```bash
git add core/review_artifacts.py core/review_facade.py \
  tests/test_review_artifacts.py tests/test_review_demo_fixture.py
git commit -m "feat: generate review artifacts"
```

### Task 7: Expose the review HTTP contract

**Files:**

- Create: `api/routers/reviews.py`
- Modify: `api/routers/__init__.py`
- Modify: `api/dto.py`
- Modify: `api/main.py`
- Modify: `api/errors.py`
- Create: `tests/test_reviews_api.py`

**Step 1: Write failing API tests**

Cover multipart script/idea creation, GET recovery, confirm, retry, owner/404/state/validation errors, redacted view, source bytes/checksum, all artifact headers, and safe `Content-Disposition`.

**Step 2: Run tests and verify RED**

```bash
.venv/bin/python -m pytest -o addopts='' -q tests/test_reviews_api.py
```

**Step 3: Implement routes and DTO mapping**

Routes adapt HTTP to `ReviewFacade`; they do not orchestrate lower-level services. Reuse `Principal` and the shared error envelope. Let FastAPI/browser set multipart boundaries.

**Step 4: Run API regression tests**

```bash
.venv/bin/python -m pytest -o addopts='' -q \
  tests/test_reviews_api.py tests/test_api_intake.py tests/test_response_schemas.py
```

**Step 5: Commit**

```bash
git add api/routers/reviews.py api/routers/__init__.py api/dto.py \
  api/main.py api/errors.py tests/test_reviews_api.py
git commit -m "feat: expose review demo API"
```

### Task 8: Build the English three-screen React flow

**Files:**

- Create: `web/lib/reviews-api.ts`
- Create: `web/components/review-flow.tsx`
- Create: `web/components/upload-step.tsx`
- Create: `web/components/confirm-step.tsx`
- Create: `web/components/results-step.tsx`
- Create: `web/app/review-flow.module.css`
- Modify: `web/app/page.tsx`
- Replace: `web/app/wizard/page.tsx`
- Create: `web/tests/reviews-api.test.ts`
- Create: `web/tests/review-flow.test.tsx`

**Step 1: Write failing client/component tests**

Test multipart behavior, upload-first primary action, idea secondary path, editable candidates, explicit confirmation gate, state restoration from `?review=`, semantic-pending copy, Class 1/co-review/findings, mode-appropriate downloads, focus management, and absence of old controls/internal identifiers.

**Step 2: Run tests and verify RED**

```bash
cd web && npm test -- tests/reviews-api.test.ts tests/review-flow.test.tsx
```

**Step 3: Implement the minimal flow**

- `/` renders the three-screen client flow;
- `/wizard` is a server redirect to `/`;
- URL stores only review ID;
- all labels and user-facing copy are English;
- file input remains keyboard accessible;
- confirmation screen is editable and no analysis begins before its submit;
- `Beyond this demo` is static, non-clickable presentation only.

**Step 4: Run frontend regression checks**

```bash
cd web && npm test
cd web && npm run typecheck
```

**Step 5: Commit**

```bash
git add web/lib/reviews-api.ts web/components/review-flow.tsx \
  web/components/upload-step.tsx web/components/confirm-step.tsx \
  web/components/results-step.tsx web/app/review-flow.module.css \
  web/app/page.tsx web/app/wizard/page.tsx \
  web/tests/reviews-api.test.ts web/tests/review-flow.test.tsx
git commit -m "feat: add upload-first review UI"
```

### Task 9: Simplify creator navigation without deleting staff tools

**Files:**

- Modify: `web/app/layout.tsx`
- Modify: `web/app/globals.css`
- Modify: creator-facing locale/copy files only where still referenced
- Modify: relevant layout/navigation tests

**Step 1: Write failing layout tests**

Assert creator navigation no longer links wizard, collection, dashboard, institution, admin, policy, role switching, or project-ID controls. Assert staff/admin source pages still compile and remain reachable by direct URL.

**Step 2: Run tests and verify RED**

```bash
cd web && npm test
```

**Step 3: Implement the navigation/style simplification**

Keep global CSS to reset/tokens/layout; keep review-specific styling in the CSS module. Add responsive and reduced-motion rules for 1440/1024/768/390 widths.

**Step 4: Run frontend verification**

```bash
cd web && npm test
cd web && npm run typecheck
cd web && npm run build
```

**Step 5: Commit**

```bash
git add web/app/layout.tsx web/app/globals.css web/locales web/tests
git commit -m "refactor: simplify creator demo shell"
```

### Task 10: Add real-browser fixture acceptance and finalize status

**Files:**

- Modify: `web/package.json`
- Modify: `web/package-lock.json`
- Create: `web/playwright.config.ts`
- Create: `web/e2e/review-demo.spec.ts`
- Modify: `docs/technical/upload-first-demo-review-tdd.md`

**Step 1: Add Playwright and write the failing E2E**

Pin `@playwright/test` to `1.62.1`. Test the primary fixture at 1440, 1024, 768, and 390 CSS px, keyboard-only progression, refresh recovery, no horizontal scroll, confirmation pause, results, and three downloads.

**Step 2: Run E2E and verify RED before final wiring fixes**

```bash
cd web && npx playwright test e2e/review-demo.spec.ts
```

**Step 3: Make only the E2E-observed fixes**

Do not turn static downstream cards into live workflow. Do not claim Vertex live validation when using the scripted adapter.

**Step 4: Run final verification from clean processes**

```bash
.venv/bin/python -m pytest -o addopts='' -q
cd web && npm test
cd web && npm run typecheck
cd web && npm run build
cd web && npx playwright test e2e/review-demo.spec.ts
git diff --check
git status --short
```

**Step 5: Update design implementation status and commit**

Record exactly what is implemented, what was tested with adapters, whether real browser acceptance passed, and whether Vertex live smoke was run.

```bash
git add web/package.json web/package-lock.json web/playwright.config.ts \
  web/e2e/review-demo.spec.ts docs/technical/upload-first-demo-review-tdd.md
git commit -m "test: verify upload-first demo flow"
```

### Task 11: Review the completed branch

**Step 1: Re-read requirements and inspect the complete diff**

Compare implementation against both design documents, with special attention to the explicit confirmation gate, editable values, risk semantics, static downstream cards, and absence of internal workflow leakage.

**Step 2: Run the full verification suite again if review changes any file**

Use the commands from Task 10. Do not reuse stale results.

**Step 3: Use the branch-finishing workflow**

Present actual verified status and integration options. Do not merge, push, or create a PR unless the user asks.
