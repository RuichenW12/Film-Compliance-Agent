# Maxine Demo Recording Handoff

**Prepared:** 2026-08-31

**Recording owner:** Maxine

**Purpose:** A practical handoff for rehearsing and recording the current
upload-first Film Compliance Agent demo. The detailed rationale and narration
live in
[`superpowers/specs/2026-08-30-hackathon-demo-recording-design.md`](superpowers/specs/2026-08-30-hackathon-demo-recording-design.md).

## 1. Current production state

Use this URL:

`https://web-827776020662.us-east1.run.app/`

| Item | Recording baseline |
|---|---|
| Web revision | `web-c31228d`, 100% production traffic |
| API revision | `api-gemini35`, 100% production traffic |
| Model | `gemini-3.5-flash` |
| Vertex location | `global` |
| Google model client | Google GenAI SDK |
| Policy | Packaged `Policy Snapshot v2` |
| Store | `memory` |
| Product path | Upload → Confirm details → Review results → Downloads |

The Cloud Run services are in `us-east1`; only the Vertex model endpoint is
`global`. The API uses process-local memory. Scale-to-zero, restart, or API
redeploy can remove the current ReviewSession and generated files. This is
acceptable for the demo and must be stated honestly if persistence comes up.

## 2. What was accepted

The following production run was completed after the Gemini 3.5 upgrade:

| Check | Observed result |
|---|---|
| Fixture | `tests/fixtures/scripts/e2e-30min-public-security-en.md` |
| Title | `Hang Up First` |
| Source structure | 1 episode, 30 minutes, 15 scenes |
| Gemini intake | English tags, complete English Synopsis, episode plan, investment band |
| Accepted suggestion | 3 episodes × 10 minutes; below CNY 300,000 |
| Required confirmation edit | Add the governed tag `Public Security (公安)` |
| Classification after that edit | Class 1 |
| Co-review | Required |
| Subject | Public security |
| Findings | 1 locatable English semantic finding in each accepted run |
| Package | 3 generated artifacts plus unchanged original source |
| Browser console | No warnings or errors |

The accepted run proves that 3.5 works; it does not freeze model wording. Tags,
Synopsis phrasing, episode recommendations, and semantic finding count may vary.
Do not promise `3 × 10` or a fixed quote in the voice-over.

The current Policy Snapshot uses Chinese deterministic subject terms. In two
fresh English runs, the unedited AI suggestions produced Class 1 once and Class
3 once even though both recognized a public-security subject. For a repeatable
recording, use the existing confirmation gate to add exactly
`Public Security (公安)` before the first analysis. This makes the governed
subject explicit and deterministically restores Class 1/co-review while keeping
the source script and the rest of the UI in English.

## 3. Recording fixture

Use only the checked-in synthetic file:

`tests/fixtures/scripts/e2e-30min-public-security-en.md`

Copy it into a clean folder before opening the file picker. The folder should
contain no personal filenames or unrelated materials. Do not use a real script,
private customer data, the Chinese counterpart, or the 70-minute English
judicial fixture for the final take.

## 4. Before each rehearsal

- [ ] Open the production URL and complete Google IAP sign-in.
- [ ] Confirm the page shows Upload, Confirm details, and Review results.
- [ ] Confirm Cloud Run shows `web-c31228d` and `api-gemini35` as the production
      revisions. If a later revision intentionally replaces either one, update
      this document before recording.
- [ ] Put the fixture in a clean demo folder.
- [ ] Rehearse adding exactly `Public Security (公安)` to Tags before the first
      analysis; do not wait for a failed classification and repair it on camera.
- [ ] Close personal tabs, notifications, extensions, bookmarks, terminals,
      billing, IAM, and environment-variable screens.
- [ ] Open the workflow slide and the two Cloud Run service pages.
- [ ] Start from a fresh Upload screen; never preload a completed review.
- [ ] Record at 1920 × 1080, 30 fps, browser zoom 100%.

## 5. Four-minute operating plan

| Time | Action |
|---|---|
| 0:00–0:20 | Explain the creator problem on the empty Upload page. |
| 0:20–0:35 | Upload the synthetic 30-minute script and point to the immutable-source note. |
| 0:35–1:05 | Start extraction and keep the real waiting state visible. |
| 1:05–1:40 | Show title, source structure, English Synopsis, episode plan, and investment band. Add `Public Security (公安)` to Tags. |
| 1:40–2:10 | Confirm and analyze. During the real wait, show the workflow slide once. |
| 2:10–3:10 | Show Class 1/co-review, one clear public-security finding, policy evidence, and the package. |
| 3:10–3:35 | Show the production `.run` URL and current Web/API Cloud Run revisions. |
| 3:35–3:55 | Return to Results and close on human review and immutable source. |

The analysis is a synchronous server-side request. It is fine to switch to the
workflow slide while the browser request remains active, but do not call it a
Pub/Sub job, detached background worker, or event stream.

## 6. What to say

Keep these claims:

- Gemini 3.5 Flash reads the script and proposes editable details.
- The creator confirms the public-security subject with the governed bilingual
  tag `Public Security (公安)` before analysis.
- The Google GenAI SDK calls Gemini through Vertex AI.
- Deterministic code owns confirmation, classification precedence, evidence
  location, state transitions, and failure handling.
- Findings reference a pinned Policy Snapshot and remain human-review inputs.
- The source is unchanged; the form, summary, and annotated script are
  derivatives.
- The Web and API run on Cloud Run.
- This is review preparation, not filing, government acceptance, or legal
  approval.

Do not claim:

- Google ADK;
- Firestore, Pub/Sub, Cloud Storage, durable queues, or cross-restart recovery;
- that the model always recommends the same episode count or wording;
- that zero findings would mean a clean legal pass;
- that the system files anything on the creator's behalf.

## 7. What Maxine may change

Maxine may change:

- shot timing and pauses;
- narration wording and caption length;
- workflow-slide typography and layout;
- which readable public-security finding is featured;
- the exact episode recommendation spoken after seeing the final take.

The required confirmation edit is fixed: add `Public Security (公安)` to Tags.

Changes must preserve the factual boundaries in Section 6. If the production
revision, model, storage backend, fixture, or expected classification changes,
update this handoff and rerun the acceptance gate before recording.

## 8. Acceptance gate for a take

Proceed only when the run has:

- a non-empty title, tags, and Synopsis;
- editable episode and investment suggestions;
- the confirmed tag `Public Security (公安)`;
- Class 1 with co-review required;
- at least one locatable English public-security finding;
- no semantic-pending or extraction-missing warning;
- `project-review-form.pdf`, `risk-summary.pdf`, `annotated-script.md`, and the
  unchanged original source;
- a visible original-source checksum;
- no error banner or browser console error.

Reject the take rather than narrating over a different result.

## 9. Failure handling

| Symptom | Action |
|---|---|
| Extraction or analysis is still running | Keep the same take and shorten the architecture narration. |
| Synopsis or another required suggestion is missing | Stop, save the failure details, and start a new upload after diagnosis. |
| Result is not Class 1/co-review | Stop and verify that Tags contains exactly `Public Security (公安)`; do not fake the intended route. |
| Semantic review is pending | Stop; pending is not a clean result. |
| A download fails | Stop and retain the error before retrying. |
| The old review no longer opens | Start a fresh upload. Memory sessions are not durable. |
| A private account, path, token, or notification appears | Stop. Do not publish that take. |

## 10. Release checklist

- [ ] Complete three full rehearsals.
- [ ] Get two consecutive runs through the acceptance gate.
- [ ] Keep the final uninterrupted product journey under 3:55.
- [ ] Verify captions do not cover evidence, status, filenames, or checksum.
- [ ] Show the `.run` URL and current Cloud Run revisions.
- [ ] Ensure narration says Google GenAI SDK, not ADK.
- [ ] Confirm the required bilingual subject tag is visible before analysis.
- [ ] Ensure no Firestore, Pub/Sub, durable-state, filing, or approval claim is
      present.
- [ ] Upload publicly to YouTube or Vimeo.
- [ ] Verify the published video from an incognito window.

## 11. References

- [Recording design](superpowers/specs/2026-08-30-hackathon-demo-recording-design.md)
- [Root README](../README.md)
- [Deployment reference](deployment.md)
- [Synthetic fixture contract](../tests/fixtures/scripts/README.md)
- [Official Devpost page](https://allthingsagentichackathon.devpost.com/)
