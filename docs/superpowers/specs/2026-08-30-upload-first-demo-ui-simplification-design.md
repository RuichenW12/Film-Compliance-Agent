# Upload-first Demo UI Simplification Design

**Date:** 2026-08-30

**Status:** Confirmed; ready for implementation planning

**Scope owner:** Product workflow / Demo experience

## 1. Goal

Replace the current creator-facing workflow console with one focused English demo:

1. upload an existing script;
2. review and edit AI-extracted or AI-suggested project details;
3. run classification and script-risk analysis, then download a completed review package.

The demo ends at the review package. Institution collaboration, filing, and live policy
administration remain product capabilities, but they are not interactive steps in this demo.

The default assumption is that the user already has a script. `I only have an idea` remains a
secondary path for manual entry of essential project information.

## 2. Demo fixture and evidence boundary

The primary demo fixture is:

`tests/fixtures/scripts/e2e-30min-public-security.md`

It is a synthetic, externally unreviewed test script titled `《先挂电话》`. It is useful for
demonstrating Markdown upload, long-script parsing, scene locators, and public-security subject
findings. It is not a golden compliance sample and must not be presented as an industry-approved
or legal benchmark.

Expected demo behavior:

- source structure: one episode, approximately 30 minutes, 15 scenes;
- extracted title: `先挂电话`;
- suggested adaptation plan: an editable 10 episodes × 3 minutes split, preserving the same
  approximate 30-minute total;
- suggested investment value: one current policy band, not a fabricated precise amount;
- classification: public-security subject handling takes priority over the investment band;
- findings: `public_security`, with at least scenes 3, 4, 10, 11, and 14 locatable;
- finding severity from the current placeholder rules: `needs_human`, never an automatic legal
  block;
- `political`, `military`, `diplomatic`, `national_security`, `united_front`, `ethnic`,
  `religious`, and `judicial` must not be invented.

## 3. Product principles

1. **One screen, one job.** Upload, confirmation, and results are separate screens.
2. **Human confirmation before judgment.** AI suggestions cannot enter classification or a form
   until the user confirms or edits them.
3. **Provenance is visible.** The UI distinguishes text extracted from the script, AI inference,
   and user-confirmed data.
4. **Unknown remains unknown.** Missing or unavailable output is not converted into a default or
   a pass.
5. **The original script is immutable.** The annotated script is a new derivative file; it adds
   comments but never rewrites the source.
6. **Policy output is routing support, not legal approval.** The UI uses `Needs human review` and
   never claims that a work has passed government or legal review.
7. **Internal workflow complexity stays internal.** The demo does not expose project IDs, raw
   state enums, policy-pack names, pending-flag keys, or service orchestration.

## 4. Information architecture

### 4.1 Primary navigation

The creator demo has no dashboard navigation and no role switcher. Its global chrome contains:

- Film Compliance product mark;
- `AI micro-drama review` context label;
- a three-step progress indicator: `Upload`, `Confirm details`, `Review results`.

The step indicator represents a screen stack. The active screen owns input. Back returns to the
previous screen without destroying the uploaded source or confirmed draft.

### 4.2 Screen 1 — Upload

Primary copy:

- heading: `Upload a script. Skip the questionnaire.`
- supporting copy: the system extracts project details first and will not start compliance
  analysis until the user confirms them;
- primary action: `Extract project details`;
- trust statement: `Your original file is never modified.`

Accepted in the first release:

- `.md`;
- UTF-8 `.txt`;
- `.docx` with text extraction.

PDF and OCR are out of scope. The upload control accepts one script only. Asset-kind selectors,
material cards, attachment validation, and version-history tables are absent from the UI.

`I only have an idea` appears as a visually secondary link. It opens manual entry rather than an
upload requirement. Because this path has no source script, it can produce confirmed project
details, classification, and a Project Review Form, but it cannot produce scene findings or an
Annotated Script. It is not part of the primary demo acceptance path.

### 4.3 Screen 2 — Confirm details

The screen presents editable candidate fields:

| Field | Candidate source | Confirmation behavior |
|---|---|---|
| Project title | Extracted from script | Editable |
| Tags | AI suggested | Editable list |
| Synopsis | AI summarized | Editable long text |
| Episode count | Extracted structure plus AI suggestion | Editable positive integer |
| Length per episode | Extracted total plus AI suggestion | Editable positive duration |
| Investment band | AI suggested | Editable controlled choice |

The source script's `1 × 30 min` structure remains visible as evidence. The suggested adaptation
plan is shown separately; it must not silently replace the source structure.

Investment is suggested as a policy-aligned band, for example:

- below CNY 300,000;
- CNY 300,000–800,000;
- CNY 800,000 or above.

The labels and thresholds come from the active snapshot rather than being duplicated in the
frontend. The system returns an estimate explanation using total duration, character count,
location count, and production complexity, but it does not produce a false-precision number.

Primary action: `Confirm & analyze risks`.

Confirmation writes user-approved values into the inputs read by classification. Uploading or
extracting alone does not write confirmed project facts.

For the upload-first demo, `production_stage` is internally set to `SCRIPT_READY`. The user is not
shown the old multi-option stage selector.

### 4.4 Screen 3 — Review results

The results screen has three levels:

1. **Decision summary** — class, route, co-review requirement, and a plain-English boundary.
2. **Scene findings** — scene locator, original quote, category, human-review status, evidence,
   and non-destructive suggestion.
3. **Review package** — three downloadable files.

For `《先挂电话》`, the expected summary is `Class 1`, `Co-review required`, and
`Public security subject`. It must also state that the subject category takes priority over the
estimated investment band and that the output is not a legal approval.

When there are no deterministic findings, the correct text is `No rule-based risks detected`.
If semantic analysis is unavailable or pending, the page must not say `Passed`.

## 5. Review package

### 5.1 Project Review Form

Download name and format: `project-review-form.pdf`.

Contains:

- confirmed title, tags, synopsis, episode plan, length, and investment band;
- classification, route, snapshot version, and cited evidence;
- any field that still requires an institution.

`applicant_entity` is never guessed. It renders as `To be supplied by filing institution` and
does not block the demo package.

This is a review-preparation form, not proof that a government filing has been submitted or
accepted.

### 5.2 Risk Summary

Download name and format: `risk-summary.pdf`.

Contains:

- counts by category and status;
- classification boundary;
- one entry per finding with episode, scene, quote, evidence, and suggested next action;
- explicit semantic-analysis availability;
- the synthetic-fixture and non-legal-advice boundary.

### 5.3 Annotated Script

Download name and format: `annotated-script.md`.

Starts from a byte-for-byte preserved source copy and produces a separate derivative document.
Each finding adds an adjacent note containing:

- stable risk number;
- `Needs human review` status;
- category;
- policy evidence reference;
- explanation;
- optional revision suggestion.

The original prose and dialogue are not automatically rewritten. The unmodified source remains
downloadable and auditable through its original checksum.

## 6. Frontend state model

The demo frontend consumes one lightweight `ReviewSession` state:

```text
UPLOADING
  → EXTRACTING
  → AWAITING_CONFIRMATION
  → ANALYZING
  → COMPLETE | FAILED
```

The existing `ProjectState` remains internal. The UI never renders its raw values.

Progress is event-driven by real request or job completion:

```text
Reading script
  → Classifying project
  → Reviewing scenes
  → Preparing files
```

The UI does not animate through fake timed progress. Refreshing the page restores the session
from the backend state.

## 7. Minimal service boundary

Expose a review-oriented facade while reusing the current domain services:

- `POST /v1/reviews` — accept one script, create the internal project and asset, and start intake
  analysis;
- `GET /v1/reviews/{review_id}` — return session state, candidate details, confirmed details, or
  results;
- `POST /v1/reviews/{review_id}/confirm` — validate and persist user confirmation, then start
  classification and script review;
- `GET /v1/reviews/{review_id}/artifacts/{artifact_type}` — download `form`, `summary`, or
  `annotated-script`.

The facade prevents the frontend from orchestrating project creation, upload tickets, asset
completion, fact extraction, intent submission, classification, review, forms, and exports as
unrelated calls.

## 8. Reused implementation

Reuse without redesigning:

- Project and AssetVersion storage;
- source checksums and immutable version records;
- D1a/D1b/D1c classification;
- PolicySnapshot packs and evidence references;
- current subject-rule and script-review pipelines;
- scene locators and Finding records;
- FormDraft field assembly;
- memory/SQLite store ports.

Do not rewrite classification, policy publication, Finding semantics, or storage drivers as part
of this UI simplification.

## 9. Required additions

### 9.1 Script Intake Analyzer

Produces candidates without confirming them. It returns extracted facts and inferred
suggestions in one response, and each item contains:

- value;
- origin: `extracted` or `suggested`;
- confidence or uncertainty signal;
- source quote when the origin is `extracted`;
- explanation when the origin is `suggested`.

This is separate from the existing verbatim-only fact extractor.

### 9.2 Confirmation Bridge

Validates the confirmation payload, records user-confirmed values with a user-answer source, and
updates the IntentProfile consumed by classification. This closes the current gap where asset
facts do not automatically become classification inputs.

### 9.3 Review Facade

Owns ReviewSession state and composes existing application services. It is an application-layer
module, not a second classification implementation.

### 9.4 Artifact Composer

Creates the three result files from confirmed details, classification, findings, evidence, and
the immutable source asset. Artifact failure is isolated per file; it does not erase the analysis
result or rerun classification.

## 10. UI simplification map

### Keep and reshape

- script upload;
- candidate confirmation and manual editing;
- classification explanation;
- risk findings with scene locations;
- three downloads;
- secondary idea-only manual entry.

### Make automatic

- project creation;
- upload ticket and asset version creation;
- intake extraction;
- intent submission;
- classification;
- script pre-check;
- review-form assembly.

### Remove from the demo surface

- role switcher and project-ID loader;
- channel and theatrical-intent questions;
- multi-option production-stage controls;
- episode-length slider and full budget comparison table;
- roadmap and roadmap confirmation;
- facts, assets, and version-chain panels;
- material cards and attach/validate/waive controls;
- manual extract and pre-check buttons;
- accept/reject/resolve/waive finding workflow;
- D3 gate controls and gap diagnostics;
- form freeze, hash, and institution-defer controls;
- dashboard, timeline, notifications, and teaser controls;
- institution queue, license checks, submission, and filing-number entry;
- interactive policy crawl, proposals, and snapshot administration;
- raw IDs, enums, pending-flag keys, and policy-pack names.

Backend capabilities are not deleted solely because their demo controls are hidden.

### Showcase only

A non-interactive `Beyond this demo` section shows exactly three cards:

- Institution collaboration;
- Filing workflow;
- Live policy updates.

Each item is one short explanation or static visual. It does not enter the main navigation or
change ReviewSession state.

## 11. Error handling

- Unsupported, empty, or unreadable files stay on Upload with a specific error.
- Missing candidates open Confirm with blank editable fields; no hidden defaults are inserted.
- If the intake LLM is unavailable or times out, Confirm opens with `Analysis unavailable`, blank
  editable fields, and `Retry extraction`; the user can complete the fields manually.
- If semantic risk analysis is unavailable or times out, deterministic findings remain visible,
  semantic status is `Pending`, and the result is never labeled as a clean pass.
- Invalid confirmation values are attached to their fields.
- Classification or findings that require a person still produce a result package labeled
  `Needs human review`.
- A failed artifact keeps the completed result and offers a per-artifact retry.
- A refresh resumes Confirm, Analyzing, Complete, or Failed from server state.

## 12. Visual and accessibility requirements

- English UI chrome; original Chinese titles, quotes, and script text remain untranslated unless
  a separate translation is explicitly generated.
- Anchor/container-based responsive layout rather than absolute screen coordinates.
- Critical controls stay inside safe margins at all supported widths.
- Every screen has an initial keyboard focus and visible focus state.
- Keyboard and mouse can both complete the flow.
- Risk status uses icon, text, and structure, not color alone.
- Text containers grow with content; button widths are not fixed to one English phrase.
- Reduced-motion preference disables nonessential transitions.
- No clipping, overlap, or horizontal page scroll at 1440, 1024, 768, and 390 CSS pixels.

## 13. Acceptance

Using `e2e-30min-public-security.md`:

1. Markdown upload succeeds and source SHA-256 remains unchanged.
2. The source title and `1 × 30 min` structure are visible.
3. An editable short-episode plan and investment band are suggested.
4. User edits persist, and only confirmed values reach classification.
5. Public-security handling produces Class 1 and co-review regardless of the budget band.
6. At least scenes 3, 4, 10, 11, and 14 are locatable as `public_security` findings.
7. Placeholder-rule findings remain `Needs human review`.
8. Unrelated categories are not invented.
9. All three artifacts download; the annotated script preserves all source text.
10. Semantic unavailability never renders as a clean pass.
11. The full flow is keyboard reachable and passes the four responsive widths.
12. The creator flow exposes no role switch, internal project ID, raw enum, or policy admin
    control.

Verification must include focused unit/API/component tests plus one real-browser run of the
fixture through all three screens. Passing focused tests does not prove cloud deployment.

## 14. Out of scope

- automatic script rewriting;
- legal or government approval claims;
- batch or multi-script upload;
- PDF/OCR;
- real authentication, multi-user collaboration, or permissions;
- institution submission and filing as interactive demo steps;
- policy administration as an interactive demo step;
- cloud deployment or asynchronous-infrastructure upgrades;
- changes to classification, policy, or Finding core semantics;
- a complete localization project beyond English demo chrome.

## 15. Baseline verification

After installing `pytest-asyncio` in the shared local virtual environment, the isolated-worktree
baseline was rerun with:

```bash
/Users/ruichenwang/Documents/ChatGPT/AllAgentic/.venv/bin/python -m pytest -q
```

The suite collected 675 tests: 672 passed, 3 skipped, and 0 failed. The previous 10 async-test
failures were therefore an environment dependency issue, not failing policy behavior and not a
reason to sunset those tests or the full-suite baseline.

The run emitted one non-blocking `StarletteDeprecationWarning`: the current FastAPI test client
uses `httpx` and recommends migrating to `httpx2`. That migration is unrelated to this design and
does not block implementation.

Because `[project.optional-dependencies].test` still does not declare `pytest-asyncio`, the
implementation plan must make the test environment reproducible before relying on this baseline
in CI. It must also define focused demo verification while retaining the full suite as the
regression baseline.
