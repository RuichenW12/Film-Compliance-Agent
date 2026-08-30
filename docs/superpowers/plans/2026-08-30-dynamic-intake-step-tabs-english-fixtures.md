# Dynamic Intake, Step Tabs, and English Fixtures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add English 30/70-minute fixtures, make demo intake depend on the current upload with Vertex-first/local-fallback behavior, and let users revisit completed steps and reanalyze edited details.

**Architecture:** Preserve `ScriptIntakeAnalyzer` as the single intake validator and add a content-aware `LLMClient` only for local demo fallback. Add one atomic `ReviewFacade.reanalyze` operation for completed sessions, then make the React progress control a presentation-only tab state that calls reanalysis only on submit.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, Vertex Gemini, Memory/SQLite stores, React 19, Next.js 16, Vitest/Testing Library, Playwright.

---

## File map

- Create `tests/fixtures/scripts/e2e-30min-public-security-en.md`: complete English 30-minute fixture.
- Create `tests/fixtures/scripts/e2e-70min-judicial-long-context-en.md`: complete English 70-minute fixture.
- Modify `core/script_text.py`: parse English duration, episode, and scene metadata.
- Modify `core/review.py`: locate English Episode/Scene headings without changing subject rules.
- Create `core/demo_intake_llm.py`: content-aware local fallback implementing `LLMClient`.
- Modify `scripts/review_demo_server.py`: use configured Vertex first and the content-aware fallback otherwise.
- Modify `core/review_facade.py`: atomic reanalysis of a completed review.
- Modify `api/routers/reviews.py`: expose `POST /v1/reviews/{review_id}/reanalyze`.
- Modify `web/lib/reviews-api.ts`: add the reanalysis client operation.
- Modify `web/components/review-flow.tsx`: visited-step tabs and presentation state.
- Modify `web/components/upload-step.tsx`: current-source summary and Continue action.
- Modify `web/components/confirm-step.tsx`: prefer last confirmed values and reanalysis copy.
- Modify relevant Python, Vitest, and Playwright tests.
- Modify `docs/technical/upload-first-demo-review-tdd.md`: record implemented and verified boundaries.

### Task 1: Add complete English screenplay fixtures

**Files:**
- Create: `tests/fixtures/scripts/e2e-30min-public-security-en.md`
- Create: `tests/fixtures/scripts/e2e-70min-judicial-long-context-en.md`
- Create: `tests/test_english_review_fixtures.py`
- Modify: `core/script_text.py`
- Modify: `core/review.py`
- Modify: `tests/test_script_text.py`
- Modify: `tests/test_scene_parsing.py`

- [ ] **Step 1: Write failing English-format parser tests**

Add compact unit cases for English metadata and headings before adding the long
fixtures. Require `parse_script` to accept `Episodes: 7`, `Target runtime: 70
minutes`, and 28 `### Episode N Scene N:` headings. Require `split_scenes` to
carry the correct episode/scene coordinates and to stop at an English appendix
heading.

- [ ] **Step 2: Run the parser tests and verify RED**

```bash
PYTHONPATH=$PWD /Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/pytest \
  tests/test_script_text.py tests/test_scene_parsing.py -q
```

Expected: FAIL because the current regexes recognize only Chinese metadata and
episode/scene headings.

- [ ] **Step 3: Add bilingual format parsing**

Extend the existing regex grammar with English alternatives for `Episodes`,
`Target runtime`/`Total runtime`, `Episode`, and `Scene`. Keep the Chinese
patterns and the rule that appendices are excluded. Do not add English aliases
to `policy/seed-snapshot-v2.yaml`; format parsing is separate from governed
subject triggers.

- [ ] **Step 4: Write failing fixture-contract tests**

Add tests that require both files, parse them with `parse_script`, count scene
headings with `split_scenes`, and assert the evidence boundary and machine keys:

```python
@pytest.mark.parametrize(
    "name,title,episodes,minutes,scenes,key",
    [
        ("e2e-30min-public-security-en.md", "Hang Up First", 1, 30, 15, "public_security"),
        ("e2e-70min-judicial-long-context-en.md", "The Blank Byline", 7, 70, 28, "judicial"),
    ],
)
def test_english_fixture_contract(name, title, episodes, minutes, scenes, key):
    raw = (FIXTURES / name).read_bytes()
    parsed = parse_script(name, raw)
    assert parsed.title == title
    assert parsed.structure.source_episode_count == episodes
    assert parsed.structure.source_total_minutes == minutes
    located = {(scene.episode, scene.scene) for scene in split_scenes(parsed.text) if scene.scene}
    assert max(scene.episode or 0 for scene in split_scenes(parsed.text)) == episodes
    assert len(located) == scenes
    assert key in parsed.text
    assert "synthetic" in parsed.text.lower()
    assert "not legal" in parsed.text.lower()
```

- [ ] **Step 5: Run the fixture tests and verify RED**

Run:

```bash
PYTHONPATH=$PWD /Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/pytest tests/test_english_review_fixtures.py -q
```

Expected: FAIL because both `-en.md` files are missing.

- [ ] **Step 6: Translate the 30-minute fixture**

Create a full English translation preserving the one-episode/15-scene structure,
filmable actions, character tactics, scam-call/public-security terminology, test
metadata, and synthetic/unreviewed boundary. Preserve `public_security` exactly.

- [ ] **Step 7: Translate the 70-minute fixture**

Create a full English translation preserving seven episodes/four scenes each,
the missing-page and authorship continuity, mediation/court terminology, test
metadata, and synthetic/unreviewed/non-guidance boundary. Preserve `judicial`
exactly.

- [ ] **Step 8: Run fixture and parser tests**

Run:

```bash
PYTHONPATH=$PWD /Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/pytest \
  tests/test_english_review_fixtures.py tests/test_script_text.py \
  tests/test_scene_parsing.py -q
```

Expected: PASS; 30-minute parses as 1 episode/30 minutes/15 scenes and 70-minute
parses as 7 episodes/70 minutes/28 scenes.

- [ ] **Step 9: Commit**

```bash
git add tests/fixtures/scripts/e2e-30min-public-security-en.md \
  tests/fixtures/scripts/e2e-70min-judicial-long-context-en.md \
  tests/test_english_review_fixtures.py core/script_text.py core/review.py \
  tests/test_script_text.py tests/test_scene_parsing.py
git commit -m "test: add English long-form review fixtures"
```

### Task 2: Replace fixed demo intake with document-aware inference

**Files:**
- Create: `core/demo_intake_llm.py`
- Modify: `scripts/review_demo_server.py`
- Create: `tests/test_demo_intake_llm.py`
- Modify: `tests/test_review_demo_fixture.py`

- [ ] **Step 1: Write failing content-coupling tests**

Construct `LLMRequest` values for the English 30- and 70-minute documents and
require different results:

```python
def test_demo_intake_depends_on_current_document():
    llm = DemoIntakeLLM()
    thirty = llm.structured(intake_request(THIRTY.read_text()))
    seventy = llm.structured(intake_request(SEVENTY.read_text()))
    assert thirty["tags"]["value"] != seventy["tags"]["value"]
    assert thirty["synopsis"]["value"] != seventy["synopsis"]["value"]
    assert "public security" in thirty["tags"]["value"]
    assert "judicial" in seventy["tags"]["value"]
```

Also assert an unknown document raises `UpstreamLLMError` rather than returning
one of the known fixture responses.

- [ ] **Step 2: Run the test and verify RED**

```bash
PYTHONPATH=$PWD /Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/pytest tests/test_demo_intake_llm.py -q
```

Expected: collection FAIL because `core.demo_intake_llm` does not exist.

- [ ] **Step 3: Implement the bounded local adapter**

Implement `DemoIntakeLLM` with `name = "local-content-aware-demo"`. It hashes
`request.document` and returns candidates from a checksum-indexed map for the
four Chinese/English 30/70 fixtures. For `SCRIPT_INTAKE_PROMPT_ID`, each reply
contains fixture-specific English/source-language Tags and Synopsis,
duration-preserving episode suggestions, and the editable amount-band estimate.
For the script-review prompt, known English fixtures return only governed
category keys with exact source-line quotes; add a test that `review_script`
locates those quotes and records their episode/scene. Unknown hashes or prompt
IDs raise `UpstreamLLMError`.

Do not modify the governed YAML trigger patterns to make the English fixtures
pass. The local semantic response is explicit test behavior, not a new policy
rule or legal translation.

- [ ] **Step 4: Make the demo server Vertex-first**

Replace the global fixed `INTAKE_REPLY` with:

```python
settings = Settings.from_env()
settings = replace(settings, snapshot_seed_path="policy/seed-snapshot-v2.yaml")
real_llm = build_llm(settings)
llm = real_llm if real_llm.available() else DemoIntakeLLM()
```

Keep the entrypoint label explicit: local fallback proves document coupling,
not Vertex connectivity. Do not catch live Vertex request failures inside this
adapter; `ScriptIntakeAnalyzer` already converts `UpstreamLLMError` into an
editable unavailable state.

- [ ] **Step 5: Verify GREEN and regression behavior**

```bash
PYTHONPATH=$PWD /Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/pytest \
  tests/test_demo_intake_llm.py tests/test_script_intake.py tests/test_review_demo_fixture.py -q
```

Expected: PASS and the two long fixtures produce distinct candidates.

- [ ] **Step 6: Commit**

```bash
git add core/demo_intake_llm.py scripts/review_demo_server.py \
  tests/test_demo_intake_llm.py tests/test_review_demo_fixture.py
git commit -m "feat: make demo intake document aware"
```

### Task 3: Add atomic reanalysis for completed reviews

**Files:**
- Modify: `core/review_facade.py`
- Modify: `api/routers/reviews.py`
- Modify: `web/lib/reviews-api.ts`
- Modify: `tests/test_review_facade.py`
- Modify: `tests/test_reviews_api.py`
- Modify: `web/tests/reviews-api.test.ts`

- [ ] **Step 1: Write failing facade and API tests**

Require a completed review to accept edited details on the same identifiers:

```python
updated = service.reanalyze(
    completed.review_id,
    "u_demo",
    confirmed(title="Edited title", tags=["judicial", "drama"]),
)
assert updated.review_id == completed.review_id
assert updated.source_sha256 == completed.source_sha256
assert updated.confirmed.title == "Edited title"
assert stores.projects.list_all()[0].title_working == "Edited title"
```

Add tests for non-COMPLETE rejection, different owner rejection, two concurrent
claims, and the HTTP `POST /v1/reviews/{id}/reanalyze` response.

- [ ] **Step 2: Run tests and verify RED**

```bash
PYTHONPATH=$PWD /Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/pytest \
  tests/test_review_facade.py tests/test_reviews_api.py -q
```

Expected: FAIL because `reanalyze` and its route do not exist.

- [ ] **Step 3: Refactor one internal analysis pipeline**

Extract the post-claim body of `confirm` to:

```python
def _analyze_confirmed(
    self, session: ReviewSession, details: ConfirmedReviewDetails
) -> ReviewView:
    self._workflow.apply_review_confirmation(session.project_id, session.mode, details)
    self._workflow.run_classification(session.project_id)
    # run script review, project form, defer applicant, persist COMPLETE
```

Both initial confirmation and reanalysis call this helper, preserving the same
FAILED terminalization and artifact behavior.

- [ ] **Step 4: Implement atomic COMPLETE-to-ANALYZING reanalysis**

`reanalyze` verifies ownership and COMPLETE state, builds an ANALYZING session
with new confirmed details, and calls `compare_and_put(review_id,
ReviewState.COMPLETE, analyzing)`. A failed claim returns `STATE_INVALID`.
Identical details may return the existing COMPLETE view without rerunning.

- [ ] **Step 5: Add the HTTP and TypeScript clients**

Add `POST /{review_id}/reanalyze` using `ConfirmedReviewDetails`, plus:

```typescript
export function reanalyzeReview(id: string, details: ConfirmedReviewDetails) {
  return reviewRequest<ReviewView>(
    `/v1/reviews/${encodeURIComponent(id)}/reanalyze`,
    { method: "POST", body: JSON.stringify(details) }
  );
}
```

- [ ] **Step 6: Verify GREEN**

Run the command from Step 2 and `cd web && npm test -- reviews-api.test.ts`.
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/review_facade.py api/routers/reviews.py web/lib/reviews-api.ts \
  tests/test_review_facade.py tests/test_reviews_api.py web/tests/reviews-api.test.ts
git commit -m "feat: reanalyze edited review details"
```

### Task 4: Turn progress steps into visited navigation tabs

**Files:**
- Modify: `web/components/review-flow.tsx`
- Modify: `web/components/upload-step.tsx`
- Modify: `web/components/confirm-step.tsx`
- Modify: `web/components/results-step.tsx`
- Modify: `web/app/review-flow.module.css`
- Modify: `web/tests/review-flow.test.tsx`

- [ ] **Step 1: Write failing interaction tests**

Add Testing Library coverage that requires:

```typescript
expect(screen.getByRole("tab", { name: /Upload/ })).toHaveAttribute("aria-selected", "true");
expect(screen.getByRole("tab", { name: /Review results/ })).toBeDisabled();
```

After reaching COMPLETE, click Confirm details and assert fields use
`COMPLETE_VIEW.confirmed`. Edit the title, submit, and assert exactly one
`reanalyzeReview(review_id, editedDetails)` call. Click Results and Upload tabs
without editing and assert neither `confirmReview` nor `reanalyzeReview` gains a
call. Verify no Back button exists.

- [ ] **Step 2: Run the test and verify RED**

```bash
cd web && npm test -- review-flow.test.tsx
```

Expected: FAIL because progress items are list items, not tabs, and reanalysis
is not wired.

- [ ] **Step 3: Implement presentation-only step state**

Add `selectedStep: 1 | 2 | 3` and `furthestStep: 1 | 2 | 3`. Derive the furthest
step from server state, never reduce it during local tab switches, and render
the progress control with `role="tablist"` and button tabs. Disable tabs above
`furthestStep` and all tabs during a mutating request.

- [ ] **Step 4: Preserve current source on the Upload tab**

Extend `UploadStep` with optional `currentReview` and `onContinue`. When present,
render the safe filename/checksum summary and a `Continue with current script`
button. Selecting a new file still starts a new ReviewSession.

- [ ] **Step 5: Seed confirmation from latest truth**

In `ConfirmStep`, choose each initial value from `review.confirmed` when present,
otherwise from candidates. Change the submit label to `Confirm changes &
reanalyze` for a COMPLETE review while keeping `Confirm & analyze risks` for the
initial gate.

- [ ] **Step 6: Wire submit behavior**

In `ReviewFlow`, initial submissions call `confirmReview`; completed review edits
call `reanalyzeReview`. Successful responses select Results and keep all three
tabs visited. Errors re-fetch the server state as today.

- [ ] **Step 7: Verify accessibility and responsive CSS**

Run:

```bash
cd web && npm test -- review-flow.test.tsx && npm run typecheck && npm run build
```

Expected: PASS; tab roles, arrow/tab keyboard access, focus treatment, and
1440/1024/768/390 layouts remain valid.

- [ ] **Step 8: Commit**

```bash
git add web/components/review-flow.tsx web/components/upload-step.tsx \
  web/components/confirm-step.tsx web/components/results-step.tsx \
  web/app/review-flow.module.css web/tests/review-flow.test.tsx
git commit -m "feat: navigate and rerun completed reviews"
```

### Task 5: Expand real-browser acceptance

**Files:**
- Modify: `web/e2e/review-demo.spec.ts`
- Modify: `web/playwright.config.ts` only if timeout separation is required

- [ ] **Step 1: Write failing browser scenarios**

Use the English 30-minute fixture for the primary four-width flow. Assert its
English title, English Tags/Synopsis, tab navigation, confirmed-value restore,
one reanalysis request, updated title in Results/downloaded form, and no Back
button. Add a 70-minute test that stops after extraction and asserts seven
episodes, 70 minutes, 28 scenes, judicial-specific Tags, and a distinct Synopsis.

- [ ] **Step 2: Run E2E and verify RED**

```bash
cd web
E2E_PYTHON=/Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/python \
PYTHONPATH=/Users/ruichenwang/Documents/ChatGPT/AllAgentic-demo-ui-design \
npm run test:e2e
```

Expected: FAIL on missing English fixtures/tab/reanalysis behavior.

- [ ] **Step 3: Make only observed integration fixes**

Correct accessible names, focus transfer, test-server fixture mapping, or
processing waits exposed by Playwright. Do not add institution/filing actions or
fake progress.

- [ ] **Step 4: Verify GREEN**

Repeat Step 2. Expected: all viewport, keyboard, reanalysis, download-content,
and 70-minute extraction tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/e2e/review-demo.spec.ts web/playwright.config.ts
git commit -m "test: verify dynamic English demo flow"
```

### Task 6: Final verification and status

**Files:**
- Modify: `docs/technical/upload-first-demo-review-tdd.md`
- Modify: `docs/superpowers/specs/2026-08-30-dynamic-intake-step-tabs-english-fixtures-design.md`

- [ ] **Step 1: Run full verification from clean processes**

```bash
cd /Users/ruichenwang/Documents/ChatGPT/AllAgentic-demo-ui-design
PYTHONPATH=$PWD /Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/pytest -q
cd web
npm test
npm run typecheck
npm run build
E2E_PYTHON=/Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/python \
PYTHONPATH=/Users/ruichenwang/Documents/ChatGPT/AllAgentic-demo-ui-design \
npm run test:e2e
```

Expected: all commands PASS. Record exact counts. A Vertex smoke is listed as
unverified unless a separate live request is actually run with configured ADC.

- [ ] **Step 2: Update implementation boundaries**

Mark the design implemented only for behaviors proven above. Record local
content-aware fallback, real Vertex smoke status, English fixture provenance,
and that institution/filing features remain showcase-only.

- [ ] **Step 3: Run publication checks**

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only the pre-existing untracked
`docs/superpowers/.DS_Store` remains outside intended changes.

- [ ] **Step 4: Commit**

```bash
git add docs/technical/upload-first-demo-review-tdd.md \
  docs/superpowers/specs/2026-08-30-dynamic-intake-step-tabs-english-fixtures-design.md
git commit -m "docs: record dynamic intake verification"
```
