# Dynamic Intake, Step Tabs, and English Fixtures Design

**Date:** 2026-08-30

**Status:** Implemented and locally verified; Vertex demo intake/risk live smoke not run

**Scope owner:** Upload-first creator demo

## 1. Goal

Extend the upload-first demo in three bounded ways:

1. add complete English versions of the checked-in 30-minute and 70-minute
   synthetic scripts;
2. ensure Tags, Synopsis, episode recommendations, and investment guidance are
   generated from the current upload rather than a fixed demo response;
3. make the three progress steps usable as navigation tabs after a step has
   been visited, including editing confirmed values and rerunning analysis.

The demo still ends at the review package. Institution collaboration, filing,
and policy administration remain showcase-only.

## 2. Current Problem

Production `ScriptIntakeAnalyzer` already sends the current normalized script
to its configured `LLMClient`. The local browser demo does not demonstrate that
behavior: `scripts/review_demo_server.py` installs one fixed `INTAKE_REPLY`, so
unrelated uploads receive the same Tags, Synopsis, episode plan, and investment
band.

The frontend also renders the progress indicator as static text. Once a user
reaches results, they cannot return to the confirmed values, edit them, and
rerun classification without starting over.

## 3. Confirmed Product Decisions

### 3.1 Dynamic intake

- The normal demo runtime uses the configured Vertex/Gemini adapter and sends
  the current uploaded script for intake extraction.
- The UI displays a real `EXTRACTING` processing state and polls the persisted
  ReviewSession. It does not display a fabricated percentage.
- A model or credential failure preserves deterministic title and structure
  parsing, returns `partial` or `unavailable`, and allows retry or manual entry.
- Local automated tests use a content-aware test LLM. It must return different
  Tags and Synopsis for different documents; it must not use a single global
  reply.
- Local adapter results and real Vertex smoke results are reported separately.

### 3.2 Step navigation

The three progress items become tabs with the following rules:

- an unvisited future step is disabled;
- a visited step can be selected without a backend request;
- the selected tab controls presentation only and does not invent a server
  workflow state;
- refresh selects the furthest valid step represented by ReviewSession;
- no separate Back button is added.

When a user selects Upload after reaching Confirm, the existing source remains
visible. They can continue with it or select a replacement, which starts a new
ReviewSession. When a user selects Confirm after reaching Results, fields are
seeded from the last `confirmed` values, not the original AI candidates.

Submitting changed values from a completed review performs a reanalysis on the
same project and source. Merely switching tabs does not rerun analysis.

### 3.3 English fixtures

Create, without replacing the Chinese originals:

- `tests/fixtures/scripts/e2e-30min-public-security-en.md`
- `tests/fixtures/scripts/e2e-70min-judicial-long-context-en.md`

Each English file is a complete translation of its Chinese source, including
test metadata, synopsis, characters, episodes, scenes, dialogue, appendices,
and evidence-boundary text. The translation preserves:

- the 30-minute fixture's one episode and 15 scenes;
- the 70-minute fixture's seven episodes and 28 scenes;
- machine keys such as `public_security` and `judicial`;
- exact English source phrases that the bounded local semantic adapter can cite;
- synthetic, externally unreviewed, and non-legal-advice labeling.

The English fixtures are test drafts, not golden compliance samples.

## 4. Runtime Design

### 4.1 Intake path

```text
Upload
  -> validate and normalize current file
  -> persist ReviewSession(EXTRACTING)
  -> current document + trusted threshold context -> LLMClient
  -> validate field values and provenance
  -> persist ReviewSession(AWAITING_CONFIRMATION)
  -> user edits and confirms
```

The HTTP create operation remains synchronous internally for this iteration.
The UI displays processing while that request is active; restored transitional
sessions continue to use ReviewSession polling. The processing display is
driven by the request or persisted state, not a timer pretending that work
exists.

The production application must not import the content-aware test adapter. The
local demo entrypoint may select a real Vertex client through configuration and
use a clearly named content-aware fallback only when the real client is
unavailable.

### 4.2 Reanalysis path

Add a review-facade operation and HTTP endpoint for completed reviews:

```text
COMPLETE
  -> user selects Confirm tab and edits last confirmed values
  -> reanalyze(details)
  -> atomic COMPLETE -> ANALYZING claim
  -> overwrite confirmed project intent/facts
  -> rerun classification and script review
  -> regenerate form projection
  -> COMPLETE
```

The operation uses the existing project, uploaded AssetVersion, and
ReviewSession. It does not duplicate the project or source. Existing upsert and
finding-deduplication behavior must be retained. Concurrent reanalysis requests
must not both claim the same completed session.

If reanalysis fails, the ReviewSession becomes `FAILED` and retains the same
safe recovery boundary as initial analysis. A successful reanalysis replaces
the visible result package with projections from the latest confirmed values.

### 4.3 Frontend state

`ReviewFlow` owns a presentation-only selected step and a visited-step set
derived from the furthest server state seen during the browser session.

- Upload view accepts an optional current-source summary and a Continue action.
- Confirm view chooses `review.confirmed` when present, otherwise candidates.
- Results remain available locally while the user inspects Confirm; switching
  back to Results without submitting does not call the API.
- Submitting from an initial confirmation calls `confirm`; submitting from a
  completed review calls `reanalyze`.
- During either operation, tabs that could cause duplicate submissions are
  disabled and the processing view is announced with `aria-live`.

Progress items are real buttons or tabs with keyboard focus, selected state,
disabled state, and visible focus treatment. They remain usable at 1440, 1024,
768, and 390 CSS pixels.

## 5. Content-Aware Local Adapter

The local E2E adapter exists to prove request-to-document coupling without
claiming cloud validation. It may identify the checked-in fixtures by a
server-controlled SHA-256 or derive bounded candidates from document headings
and metadata. It must:

- inspect the `LLMRequest.document` supplied for that call;
- return fixture-specific Tags and Synopsis in English for English fixtures and
  in the source language for Chinese fixtures;
- preserve duration when suggesting episode count and length;
- reject or return partial data for an unknown document instead of silently
  returning the 30-minute fixture response;
- expose a backend name that clearly identifies it as local/test behavior.

The regular app continues to use the configured real LLM adapter. No fixed
`INTAKE_REPLY` is allowed in the manual demo path.

The same bounded adapter may answer the script-review prompt for the known
English fixtures. Those replies must use an existing category and quote an
exact line from the current document. The governed seed snapshot remains
unchanged because its deterministic trigger patterns are Chinese and carry a
separate evidence boundary. Unknown documents still fail closed.

English `Episode` and `Scene` headings are added to the deterministic structure
and locator parsers alongside the existing Chinese grammar. This is format
support only; it does not add or translate a subject rule.

## 6. Error and Evidence Boundaries

- Intake model output remains editable candidate data until explicit user
  confirmation.
- Dynamic Tags or Synopsis are not compliance findings and do not imply
  approval.
- Vertex failures never become invented successful suggestions.
- English fixtures carry their own synthetic/unreviewed notice and are
  identified by content checksum where the UI or artifacts show fixture
  provenance.
- Reanalysis does not mutate the exact uploaded source bytes or checksum.
- Browser and local adapter tests do not count as Vertex live validation.

## 7. Verification

### 7.1 Fixture tests

- both English files parse as strict UTF-8 Markdown;
- titles, duration, episode count, and 15/28 scene counts match their Chinese
  sources;
- through the bounded local semantic adapter, the expected target category is
  found from an exact English source quote and non-target categories do not
  appear;
- each file retains its synthetic/unreviewed and non-guidance boundary.

### 7.2 Intake tests

- two different uploads produce different Tags and Synopsis;
- the adapter receives the exact current normalized document;
- processing, partial, unavailable, retry, and manual-entry behavior remain
  truthful;
- real Vertex smoke, when run, is recorded separately with its backend name.

### 7.3 Reanalysis tests

- Results -> Confirm shows the last confirmed values;
- tab switching alone creates no request;
- edited details trigger exactly one reanalysis request;
- the same review and asset are reused;
- updated confirmation, classification, and generated form are visible;
- duplicate or concurrent reanalysis is rejected atomically;
- failure restores a safe FAILED view.

### 7.4 Browser acceptance

Run the English 30-minute fixture through upload, processing, confirmation,
results, tab navigation, edit, and reanalysis at the four supported widths and
by keyboard. Add a separate long-context acceptance for the English 70-minute
fixture that verifies extraction and structure without imposing an unsuitable
short browser timeout on full semantic analysis.

## 8. Out of Scope

- translating the 10-minute baseline;
- automatic screenplay rewriting;
- simultaneous comparison of multiple uploads;
- a numeric fake progress bar;
- creating institution, filing, or policy-management steps;
- treating synthetic English fixtures as expert-reviewed golden samples;
- changing the source screenplay when a user edits Tags or Synopsis.

## 9. Implemented and Verified Boundary (2026-08-30)

The implemented manual demo selects the configured repository Vertex adapter
when explicitly available, or the clearly named `local-content-aware-demo`
fallback. The fallback is content-aware but fixture-bounded: it checks the
normalized document SHA-256 plus prompt/version/schema, provides distinct
intake and semantic responses for the four checked-in Chinese/English 30- and
70-minute fixtures, and fails closed for an unknown document. It is not a
general local model and its results are not evidence of Vertex behavior.

Completed-review edits now reuse the same review, project, uploaded asset, and
source checksum. Generation-aware compare-and-swap plus project-aggregate
publication prevents an older concurrent reanalysis from replacing a newer
result. Visited progress items are real keyboard-accessible tabs; tab switching
alone has no backend side effect, and there is no separate Back button.

Fresh final verification produced:

- Python: 900 tests collected, 897 passed, 3 skipped, with one existing
  Starlette/httpx deprecation warning;
- Web unit/component tests: 13 files and 49 tests passed;
- TypeScript (`tsc --noEmit`) and the Next.js production build: exit 0;
- deterministic Playwright E2E: 6 tests passed, covering the English 30-minute
  upload/confirm/results/reanalysis flow at 1440, 1024, 768, and 390 CSS pixels,
  the English 70-minute differentiated intake, and keyboard tab navigation.

The two checked-in English fixtures were generated in section/scene chunks
from only their corresponding checked-in synthetic Chinese fixtures using the
repository's existing `VertexGeminiLLM`, model `gemini-3.5-flash`, and the ADC
available at generation time. That translation provenance is not a separate
live demo intake or risk-analysis smoke. No external request was made during
final verification, and a real Vertex demo intake/risk smoke remains unrun and
unverified.

Both English fixtures remain synthetic, externally unreviewed test drafts.
They have not received independent bilingual expert review and are neither
golden compliance samples nor legal guidance. The governed deterministic seed
still has a Chinese-only classification pattern boundary; English subject
evidence in deterministic E2E comes from the fixture-bounded semantic adapter,
uses an exact source quote, and remains marked for human review.

Institution collaboration, filing, and policy administration remain
showcase-only and are not steps in this demo flow. The synchronous demo's task
claim, generation CAS, and aggregate publication are covered, but `RUNNING`
jobs have no lease or automatic worker-crash recovery; that remains future
asynchronous infrastructure rather than a completed demo capability.
