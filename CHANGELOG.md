# Changelog

What changed, when, and who owns it. Two workstreams share this repository, so
every entry is tagged **A** (product workflow, Maxine) or **B** (policy loop,
Richard), or **Shared** when it touches the contract boundary or both sides.

Why an entry gets written: a reader six days from now — or the other
workstream's agent — must be able to see what moved without reading the diff.
Reasons for non-obvious choices live in [`docs/decisions.md`](docs/decisions.md);
this file links to the decision id rather than repeating the argument.

Conventions:

- newest first, grouped by date;
- each entry states what changed and, where it matters, what was verified;
- a change that alters something the other workstream depends on says so
  explicitly, in bold;
- verification claims name the check that was actually run. "Tests pass" without
  a command is not a verification claim.

---

## 2026-08-29

### A — a crash waiting on a rare path, and more dead copy

- **`_write_alert_finding` read `intent_profile.logline`, a field that no longer
  exists.** Python's `or` short-circuits, so it was only reached when an alert
  carried no matched-rule quote — which no test produced. On that path a
  creator would have got an `AttributeError` instead of the boundary-subject
  decision the alert exists to offer. Now reads the synopsis, and a test covers
  it (confirmed by reintroducing the bug and watching it fail).
- **`.env.example` pointed at `seed-snapshot-v1.yaml`** while the code defaults
  to v2. Anyone copying it ran on the older snapshot, whose thresholds are
  unpublished, and got a provisional class on every project with no clue why.
- **Fifteen dead copy keys removed** — the `budget_band` field (gone in D-036),
  the reviewer-side submit card (moved in D-047), the "where will it be
  distributed" question you asked me to drop, and two gate strings nothing ever
  rendered.

**Found and left alone, deliberately:** `alert.*` copy has no renderer. The
backend writes alert findings with options — modify the scenes, keep them and
accept co-review, escalate — and no screen shows them, so a creator with a
boundary-subject project never sees the choice. That is a missing feature rather
than dead copy, and it is the largest remaining hole on the creator's side.
Recorded as Q-5.

### A — a copy sweep for our vocabulary and one stale lie

- **Deleted copy for a field that no longer exists.** `help.budget_band` and
  `wizard.budget_band.hint` both told a creator to look at "the exact amount
  above". That field was replaced in D-036 and moved off intake entirely in
  D-038, so the help was describing a screen nobody sees.
- **`help.investment_amount_rmb` was telling creators the wrong thing.** It said
  "this is the field that decides your tier, and only an exact figure gives a
  settled answer". Both halves stopped being true at D-038: the range decides
  the class, and the figure is what the filing form asks for.
- **Notifications spoke in internal terms.** "Snapshot v3 was published. Review
  the project before the pre-shoot gate." now reads "A policy update was
  published after this project was classified. Open it and work the answer out
  again before you go further" — matching the card that offers to do it.
- **Raw class codes reached the dashboard.** A recalculation notice renders
  "moved this project from {previous_tier} to {tier}", and the parameters are
  raw domain values, so it read "from T2 to T3" while every other screen said
  "Class 2". The API still sends keys and parameters rather than prose, which is
  right; the dashboard now maps the tier-shaped ones at the point it turns a
  notification into a sentence.
- **Also plainer:** "The pre-shoot gate is blocked" → "Some things are still
  needed before the form can be locked"; the collection page no longer says
  "C1-a" at a creator.
- Verified: `python -m pytest` (583 passed, 3 skipped), `npx tsc --noEmit`
  clean, and the dashboard read back in the browser.

### Shared — fixes found by looking at the running product

- **The stale notice named the wrong snapshot.** The dashboard read "Snapshot
  v2 was published" at the moment v3 was published — the adapter passed the
  project's *current* pinned version rather than the event's. A notice naming
  the version the creator already had is news about nothing. The consumer now
  passes `event.snapshot_version` through, and a test pins it.
- **Policy events are delivered before they are acknowledged.** The wiring
  marked the outbox row sent and handed the event to the consumer afterwards;
  since only `PENDING` rows are ever selected, a crash in between lost the rule
  change outright with nothing left to retry. `InlineOutboxDelivery` reverses
  the order. [D-052](docs/decisions.md#d-052) also corrects D-049, which
  described the risk backwards as double-handling.
- **The whole policy loop is verified through the UI**, not just the API: as
  Admin, *Run fixture crawl* → *Review proposal* → *Publish*, and a waiting
  creator's project moved `v2` → `v3`, class `T3` → `T2`, with `policy.stale`
  and `classification.recalculated` in its timeline and a notice in the inbox.
- Verified: `python -m pytest` (583 passed, 3 skipped); `python
  scripts/e2e_check.py --base http://localhost:8000` on a fresh process **ALL
  CHECKS PASSED**.

### A — a stale project can be worked out again

- **New `POST /v1/projects/{id}/reclassify`**, and a card on `/collection` that
  offers it: "The rules behind this answer have changed" → *Work it out again*.
  See [D-051](docs/decisions.md#d-051).
- **This was a real dead end.** Automatic recalculation covers a provisional
  tier only. A settled tier is left alone on purpose (D-031) and a subject-rule
  change is not auto-recalculated at all (D-050) — so those creators were told
  their answer was out of date and given no way to get a new one.
- **Three guards, each load-bearing:** it refuses when the project is not stale
  (the flag is the evidence that a different answer is even likely); it refuses
  once the form has been locked and sent (its class is part of what the filing
  company is holding); and it never moves the state, so materials, roadmap and
  uploads survive — re-deciding is not starting over.
- **Fixed a flaw in the card I had just written.** Re-running clears the stale
  flag, and the card hid on that alone — so it vanished at the exact moment it
  had something to say. A creator pressed the button and the whole thing
  disappeared without telling them what happened. It now stays to report the
  result, and says whether the class actually moved. Found in the browser, not
  by the API test that passed.

- **The dashboard badge stopped speaking our vocabulary:** "policy update
  pending review" is now "rules changed — needs redoing".
- **`e2e_check.py` section 23 is now re-runnable.** The demo policy source is
  swapped from its v1 to its v2 fixture once at process start, so a second crawl
  in the same server finds nothing changed. The section detects that and skips
  itself with a reason rather than reporting a failure that says nothing about
  the code.
- **New `docs/QUESTIONS-FOR-MAXINE.md`** — four things I could not decide alone,
  each with what I did in the meantime so nothing is blocked waiting on an
  answer. Q-1 is why Firestore is still unwritten: no Java, no Docker, no
  `gcloud` on this shell and no client library, so it could be written and never
  once executed.
- Verified: `python -m pytest` (578 passed, 3 skipped) including 9 new
  reclassify tests; `python scripts/e2e_check.py --base http://localhost:8000`
  on a fresh process **ALL CHECKS PASSED** with a new section 24 walking
  settled → stale → re-decided → refused again.

## 2026-08-28

### Shared — the policy loop reaches real projects

- **A publish now flags the projects it affects.** Crawl, propose and publish
  all worked already; the fan-out ran against a fake project store, so a
  snapshot could be published and no creator was ever told. New
  `workers/policy/adapters/live_projects.py` points the consumer at the
  product's real projects. See [D-049](docs/decisions.md#d-049).
- **The boundary holds in ownership, not transport.** The adapters call exactly
  the two `WorkflowService` methods `/v1/internal/*` calls, live under
  `workers/policy/`, and change no product code. Writes go through the service,
  so a stale flag produces its transition, timeline entry, audit line and
  notification just as the hand-called route does.
- **New `D1b` impact node**, closing the last gap the loop could not express: a
  change to the subject-trigger vocabulary now marks affected projects stale.
  **It deliberately does not recalculate** — `recalc_tier` redoes the amount
  stage, and answering a subject question with money would assert a conclusion
  the evidence does not support. See [D-050](docs/decisions.md#d-050).
- **`PENDING_STEPS` is now empty.** Every step in contract section 7 is walked
  by the e2e. What remains is infrastructure, not steps: the Firestore adapter
  and the Veo teaser behind its flag.
- **Two of my own assertions were wrong and were fixed, not worked around.** The
  first wiring overrode a dispatcher a test had deliberately pointed at a
  failing publisher; live wiring now only happens on the default path. And the
  first version of the new e2e section used a settled-tier fixture and then
  demanded a recalculation — which D-031 forbids on purpose.
- Verified: `python -m pytest` (569 passed, 3 skipped) including 5 new D1b
  tests; `python scripts/e2e_check.py --base http://localhost:8000` **ALL CHECKS
  PASSED** with a new section 23 walking crawl → proposal → publish → stale →
  notified → recalculated, the project moving `v2` → `v3`.

### A — the creator can send the form, and a returned one can come back

- **The submit card moved from `/institution` to `/collection`**, beneath the
  form it sends. `submit_to_institution` calls `_assert_owner`, so it was always
  the creator's act; it only worked on the reviewer's page because demo auth
  gives every role the same `user_id`. `resume` moved with it. See
  [D-047](docs/decisions.md#d-047).
- **The reviewer's comments are quoted verbatim** rather than paraphrased. They
  are usually Chinese, which is not a D-039 violation: that rule governs our own
  copy, not text a human typed.
- **Found and fixed a dead end.** A returned project could be resumed and its
  gate re-passed but **never resubmitted** — `form_draft` returns a frozen draft
  unchanged and `freeze_form` early-returns one, so the state never reached
  `FORM_FROZEN` again and submit answered 409 forever. `resume_after_return` now
  starts a successor draft with the frozen one as its `parent_draft`, a field
  that had never been set since it was written. See
  [D-048](docs/decisions.md#d-048).
- **Corrected my own copy and my own test.** The resume hint promised the form
  "reopens for editing", which is not what happens and should not be — the sent
  form stays locked as the record. And the first e2e assertion demanded a new
  hash after re-freezing an *unchanged* form, which a content hash must not
  give; it now corrects a field first.
- Verified: `python -m pytest` (564 passed, 3 skipped); `python
  scripts/e2e_check.py --base http://localhost:8000` **ALL CHECKS PASSED** with
  a new section 22 walking submit → returned → resume → correct → re-lock →
  resend; and in Chrome: the send card appeared after locking, sending moved it
  to "the filing company is reviewing it now", a return showed the reviewer's
  words quoted, and "Take it back and fix it" reopened the loop.

### A — the reviewer can find work

- **New `GET /v1/institution/queue`**, institution role only, listing what is
  waiting: projects needing a decision and accepted projects still needing a
  registration number. See [D-046](docs/decisions.md#d-046).
- **The console had every route and no inbox.** Submit, licence check, accept,
  return, resume and filing all worked — by hand a project reached `FILED`
  with a registration number — but the page could only open a project whose id
  somebody pasted in. `ProjectStore.list_all` had been a port method that
  **nothing called** since it was written; the queue is what it was for.
- **An accepted project stays listed** until its registration number is
  recorded, because that is the institution's act too. A returned project
  leaves, being the creator's work again.
- **Nothing is invented in a row:** an unnamed project renders "untitled", and
  there is no synthesised licence verdict — the row carries the actual reasons,
  empty meaning passed.
- **The paste-an-id form stays as a fallback**, same shape as D-041: remove the
  need, not the option.
- **Fixed while testing:** a failed queue load left the card on "Loading…"
  forever, which reads as a hang rather than the 403 it usually is.
- Verified: `python -m pytest` (563 passed, 3 skipped) including 9 new queue
  tests; `python scripts/e2e_check.py --base http://localhost:8000` **ALL CHECKS
  PASSED** with a new section 21 walking submit → queue → accept → file → queue
  empties; and in Chrome as the institution role: the queue listed the project,
  *Open* loaded it in one click, *Accept* moved the row to "a registration
  number", and recording the filing emptied the queue.

### A — projects survive a restart

- **New `store/sqlite.py` behind the existing ports**, selected with
  `STORE_BACKEND=sqlite` (`SQLITE_PATH` sets the file, default
  `var/film-compliance.db`). The default stays `memory`, and an unknown value
  raises rather than silently running in memory. See
  [D-045](docs/decisions.md#d-045).
- **SQLite, not Firestore, and the reason is verification.** Firestore is the
  stack's target but is not enabled and Docker is not installed, so that
  adapter could have been written and never run. It still slots in behind the
  same ports later.
- **`tests/test_store_conformance.py` is the part that matters.** Fourteen
  ports had exactly one implementation, which means their guarantees had never
  been tested as guarantees. 26 assertions now run against **both** backends:
  list order, last-write-wins on facts, first-writer-wins on idempotency keys,
  a ticket spendable once, a newest-first inbox, and an updated form draft that
  must not become the latest. **Shared: a future Firestore adapter passes this
  file or it is not finished.**
- **`AppContext.stores` is now typed as the `Stores` port**, not
  `InMemoryStores`.
- **New confusion this introduces, stated plainly:** with `sqlite`, restarting
  the API no longer resets anything. A second e2e run on the same file fails
  section 17 exactly as a long-lived memory server did — verified, not
  predicted. Resetting means deleting the file; the e2e docstring and
  `.env.example` both say so now.
- Verified: `python -m pytest` (554 passed, 3 skipped) including 52 conformance
  cases across both backends; `python scripts/e2e_check.py --base
  http://localhost:8000` against `STORE_BACKEND=sqlite` **ALL CHECKS PASSED**;
  and a real restart test — a project classified before the API was killed came
  back afterwards with its state, tier, title, four facts, sixteen timeline
  events and the uploaded script intact, then went on to a frozen form
  (`hash bfe64e668a5bf65d`).

### A — the waive reason is asked in the page, not in a browser dialog

- **`window.prompt` is gone from `app/collection/page.tsx`.** Waive now opens a
  small box inside the card: a labelled input, *Waive it*, *Cancel*, and a line
  saying the reason is recorded against the project.
- **Correcting an overstatement in the previous entry.** That entry said the
  prompt "will bite in a live demo". For a person clicking by hand it worked
  — the cancel path was handled and no data was at risk. What it actually
  cost was narrower and worth naming precisely: a native dialog is frequently
  absent from a shared *browser tab*, so an audience sees a frozen page while
  the presenter types into a box they cannot see; and once Chrome offers
  "prevent this page from creating additional dialogs", `prompt` returns null
  and Waive becomes a button that silently does nothing. It also blocks
  automated browser checks, which is how it was found — it froze the tab twice
  during the previous change.
- **Confirm is disabled until a reason is typed**, so the silent no-op is not
  reproduced in the replacement. Escape and *Cancel* both close the box.
- Verified in Chrome on the case that previously froze the tab: the box opens
  and the tab stays alive, the confirm button is disabled while the reason is
  empty, waiving with a reason marks the card `waived` and drops it out of the
  gate's gaps, and both Escape and Cancel close without waiving. Plus
  `python -m pytest` (502 passed, 3 skipped) and `npx tsc --noEmit` clean.

### A — the filing form is on screen, and the journey reaches a lock

- **New "The filing form" card on `/collection`.** Shows every field the 备案
  asks for, what we have, and what is still missing — with a *Save* box per
  unanswered field and an *I don't have one* button on the fields the filing
  company supplies. Ends with *Lock the form*.
- **The gate is stated, not discovered.** The gaps are listed in plain language
  above the button, and the button is disabled until they clear, so a creator
  reads why they cannot finish instead of pressing something and getting a 409.
- **The lock is explained.** "Locking takes a fingerprint of the exact
  contents, so the version reviewed later is provably the one you approved."
  — the hash is a promise to the creator, not a database detail.
- **My own no-Chinese guard caught me.** The first draft of this copy carried
  待补充, 备案 and 广播电视节目制作经营许可证 in the English bundle;
  `test_result_copy.py` failed and they are now English. The guard added in
  D-039 paid for itself within a day.
- **Fixed a raw key that reappeared on a second surface.** Gate gaps rendered
  `material.mat_synopsis` because the gate returns `mat_synopsis` while the
  bundle keys are `material.synopsis`. This is the D-040 defect showing up again
  the moment another screen rendered the same data; `nameGapItem` now handles
  both shapes.
- Verified: `python -m pytest` (502 passed, 3 skipped), `npx tsc --noEmit`
  clean, and a full Chrome walk — classify, hand off, declare no filing
  company, answer title and amount, watch the gaps clear, lock the form, and
  read back `Locked. Fingerprint 2cd1ff12133e…` with the filing company still
  showing as to be supplied.

**Known, not fixed:** `app/collection/page.tsx:389` waives a material through
`window.prompt`, which blocks the page and froze the browser during this work.
It is pre-existing and on a part of the page this change did not touch, so it is
reported rather than rewritten — but it will bite in a live demo.

### A — an individual creator can reach a frozen form

- **`applicant_entity` can be declared blank instead of invented.** A 备案 is
  filed by a company holding the 广播电视节目制作经营许可证, which an individual
  creator does not have. New `POST /v1/projects/{id}/form/fields/{key}/defer`
  records a fact with no value and `PENDING_INSTITUTION` status. See
  [D-044](docs/decisions.md#d-044).
- **The gap stays visible.** The field renders 待补充, the hash covers field
  status so a deferred field and a filled one hash differently, `deferred_keys`
  lists it on the frozen form, and the freeze event records which fields were
  left open. A confirmed value outranks a later deferral.
- **Most of this already existed and was unreachable.** `evaluate_gate_d3`
  accepted `PENDING_INSTITUTION` and `FieldStatus` had the member, but nothing
  produced it and `pending_keys` blocked anything not `FILLED`.
- **e2e section 20** walks an individual creator with no company from intent to
  a frozen form: eight checks, including that an *unanswered* entity still
  blocks and that the frozen form is not quietly complete.
- **This closes D-038's loop.** Intake takes a budget range; the freeze stage is
  where `investment_amount_rmb` is actually collected, and the walk confirms it.
- Verified: `python -m pytest` (502 passed, 3 skipped), `python
  scripts/e2e_check.py --base http://localhost:8000` on a fresh process **ALL
  CHECKS PASSED**.

### A — the frontier was three stages further along than we thought

- **Correction, and the reason it matters.** Planning the work after
  classification, both the 2026-08-24 status doc and `e2e_check.py`'s
  `PENDING_STEPS` said T-A3 to T-A6 were unbuilt. Both were stale. Every route
  exists, and a live walk took a project through roadmap confirm, material
  cards, an upload ticket, fact extraction and the C1-a pre-check into a
  correctly blocked gate. See [D-042](docs/decisions.md#d-042).
- **The e2e now walks steps 5 to 11** in a new section 19, sixteen assertions,
  instead of printing them as pending. `PENDING_STEPS` keeps only the
  policy-loop items that really have no route. **Workstream B: your line is the
  only one left in that list.**
- **The status doc opens with a stale banner** naming `openapi.json` and the
  e2e output as the sources to trust instead.
- **The wizard hands off.** The result card ends with *Continue to your filing
  checklist*, opening `/collection?project=<id>`, which now auto-loads. Before
  this the two screens were joined by copying an opaque id between them. See
  [D-041](docs/decisions.md#d-041).
- **The result card's "what happens next" was wrong** and is corrected: it said
  the next stage was unbuilt when roadmap, materials, facts and the pre-check
  all run. It now names what actually comes next, and keeps the honest caveat
  that freeze and institution submission are unfinished.
- **Fixed a latent bug that no test could see.** `core/extract.py` used a union
  `"type": ["string","number","null"]`, which Vertex rejects — every live
  extraction would have failed while the suite passed. Same defect as the one
  already fixed in `core/intake_help.py`. New `tests/test_response_schemas.py`
  discovers every `*SCHEMA` under `core/` and bans list-valued `type`; five
  schemas covered. See [D-043](docs/decisions.md#d-043).
- **Material cards cite clauses by name**, matching D-040, instead of printing
  `nrta-order-16-article-14`.
- Verified: `python -m pytest` (491 passed, 3 skipped), `npx tsc --noEmit`
  clean, `python scripts/e2e_check.py --base http://localhost:8000` on a fresh
  process **ALL CHECKS PASSED** including the sixteen new checks against real
  Vertex, and a Chrome run following the handoff from a classification into a
  loaded collection page.

### A — English only, and the result cites policies by name

- **Every Chinese gloss is gone from the UI.** "Class 3 (三类)" is now "Class 3",
  "micro-drama (微短剧)" is "micro-drama". `CLAUDE.md`'s stack line said the UI
  was "English with Chinese legal terms glossed" and has been corrected —
  **both workstreams read that line**, so check it before adding UI copy. See
  [D-039](docs/decisions.md#d-039), which supersedes the gloss half of D-032.
- **What that gives up:** a creator told "Class 3" will meet 三类 on the real
  filing form and nothing in the product now bridges the two. Accepted
  deliberately, and recorded as the thing to revisit when the materials and
  filing-form stages ship.
- **Clause ids render as names.** "How we reached this" showed
  `tier-ai-generated-2026`; it now shows "Investment thresholds for AI-generated
  micro-dramas", followed by the instrument and its effective date, and a
  sentence explaining what a pinned policy version means. See
  [D-040](docs/decisions.md#d-040).
- **The technical disclosure is deleted.** `proj_… CLASSIFIED T3_4steps` plus a
  raw flag list told a creator nothing and repeated, as keys, warnings already
  given as sentences. The project id survives as a support reference on the
  disclaimer line.
- **Two new guards.** `tests/test_result_copy.py` now fails if any value in
  `web/locales/en.json` contains a CJK character, and if any `clause_id` or
  `clause_ref` in `policy/*.yaml` has no English name. The second caught
  `nrta-order-16-article-54` in the v1 snapshot, which would have rendered as an
  empty bullet. **Workstream B: adding a clause to a snapshot now requires an
  English name in the bundle.**
- Verified: `python -m pytest` (485 passed, 3 skipped), `npx tsc --noEmit`
  clean, `python scripts/e2e_check.py --base http://localhost:8000` on a fresh
  process **ALL CHECKS PASSED**, and a Chrome run showing the card end to end
  with no Chinese and the provenance reading as prose.

### A — the exact investment amount comes off the intake form

- **Intake no longer asks for the figure.** Since [D-036](docs/decisions.md#d-036)
  a threshold-aligned bracket settles the tier, which left the amount field on
  the form contributing nothing to the answer while asking an idea-stage creator
  for a number they would have to invent. See [D-038](docs/decisions.md#d-038).
- **Nothing moves in the contract.** `IntentProfile.investment_amount_rmb`, the
  DTO field, the POST body key and the per-field help entry all stay — the
  form-freeze stage (T-A5) is where the figure is actually needed and where it
  will be collected.
- **What it gives up, stated plainly:** a budget sitting *exactly* on a
  threshold is the one case the figure decides and the bracket cannot. With an
  amount that project is reported provisional with `threshold_boundary_disputed`
  ([D-033](docs/decisions.md#d-033)); with `at_or_above_upper` alone the
  inclusive reading is taken and the tier reads settled. The detection code is
  untouched and still fires whenever the API receives an amount.
- Verified: `python -m pytest` (483 passed, 3 skipped), `npx tsc --noEmit`
  clean, `python scripts/e2e_check.py --base http://localhost:8000` on a fresh
  process **ALL CHECKS PASSED**, and a Chrome run confirming the form now has
  two number inputs (episodes, minutes) and a bracket-only project still
  settles at Class 3.

### A — the classification result says what to do, in words

- **The result card was a debug view and now reads as an answer.** A creator ran
  a classification and got back `micro_drama`, `Tier T3`, a clause id, a
  `script_verify` chip, `T3_4steps`, and their project's internal state — with
  the filing route, the only actionable part, at the bottom. The verdict is now
  a sentence, the filing route is a numbered "What this means you have to do" at
  the top, and flags read as sentences. See [D-037](docs/decisions.md#d-037).
- **Nothing was deleted.** The matched quotes, clause ids and snapshot version
  moved into a "How we reached this" disclosure; the project id, state and
  roadmap template into "Technical detail". `evidence_refs` still reach the page
  — one click away rather than as the headline.
- **The card now says the trail ends here**, naming the script pre-check as the
  next stage and stating plainly that it is not built.
- **New guard, and it found things.** `t()` falls back to the key when copy is
  missing, which is how raw identifiers reached a creator. `tests/test_result_copy.py`
  walks `FormType`, `Tier`, every `filing_route` value in `policy/*.yaml` and
  every flag literal in `core/classify/`, failing when one has no copy. It
  caught seven flags that would have rendered as keys — `amount_required`,
  `amount_official`, `budget_unknown`, `generation_mode_required`,
  `thresholds_unavailable`, `threshold_boundary_disputed`, `human_review`.
- Verified: `python -m pytest` (483 passed, 3 skipped), `npx tsc --noEmit`
  clean, `python scripts/e2e_check.py --base http://localhost:8000` **ALL CHECKS
  PASSED**, and a T3 run in Chrome reading end to end as English with the
  evidence intact behind the disclosure.
- **`e2e_check.py` needs a freshly started API, and now says so.** Section 17
  asserts the demo creator has exactly one `policy_stale` notice; each run adds
  one more to the same inbox, so a server left running from an earlier run
  reports two failures that say nothing about the code. Confirmed by running the
  same script on stock `HEAD` (identical failures) and on a fresh process (all
  green). The product logic is right — `mark_policy_stale` already guards
  redelivery with `already_stale`. Only the script's docstring changed.
- **Unrelated environment note for anyone verifying in a browser:** Chrome
  serves every Next.js chunk as 403 on `http://127.0.0.1:3000`, so the page
  renders but never hydrates and the form falls back to a native GET submit.
  The same server on `http://localhost:3000` is fine, and `curl` gets 200 on
  both. Use `localhost`.

### A — one story field, suggested genres, and an order that follows the logic

- **`logline` is gone; `synopsis` is the one story field.** Two free-text boxes
  for the same thing was redundant the moment the synopsis landed, and of the
  two only the synopsis has standing — 剧情梗概 is the material the filing form
  asks for. D1a's edge-phrase check and D1b's subject match both read it now.
  `core.teaser` keeps calling its input a logline, which is the right word for
  what a teaser is written from; it is fed the synopsis.
- **One consequence worth watching:** D1a's edge-phrase detection used to run on
  one sentence and now runs on a paragraph, so more text means more chances to
  trip a phrase and land in `NEEDS_HUMAN_FORMTYPE`. That errs toward caution,
  but it will be noisier.
- **Genre keywords move up under the title and gain suggestions.** Twelve common
  ones as chips; the box stays open for anything else. Nothing downstream treats
  a chosen word differently from a typed one — the subject check reads the text
  and has to quote it either way — so the list can be incomplete without making
  an answer wrong.
- **Reordered so each field can be answered when it is asked.** AI generated now
  sits *above* the budget range, because it decides which ranges the dropdown
  shows. The exact figure moves below the range: the range settles the tier, and
  the figure is for the filing form.
- Verified: `python -m pytest` (461 passed, 3 skipped), `npx tsc --noEmit`
  clean, `scripts/e2e_check.py` **ALL CHECKS PASSED**, and in Chrome — picking
  two chips fills the box as `悬疑,科幻`, and a synopsis-only subject hit still
  returns `T1` quoting the creator's own sentence.

### Shared — a budget range now settles a tier, because the ranges are the thresholds

- **`BudgetBand` becomes `AmountBracket`**: `below_lower` / `between` /
  `at_or_above_upper` / `unknown`, replacing `band_a/b/c`. A bracket produces a
  **settled** tier whenever the thresholds behind it are usable, where a band
  could only ever be provisional.
- The difference is not cosmetic. D-003 marked band-derived tiers provisional
  because the bands were invented before any threshold was published. These are
  defined *by* the published figures, so "under the lower line" says exactly what
  a number under 1,000,000 says — and reporting that as provisional understated
  what the creator had told us. Answering honestly ("I don't know the exact
  figure") used to cost them a settled result. See
  [D-036](docs/decisions.md#d-036), superseding that half of D-003.
- **The brackets are relative, not numeric**, because the figures differ by
  production mode — 1,000,000 / 3,000,000 live action, 300,000 / 800,000 AI.
  One enum resolved against whichever set applies; the interface fills in the
  numbers from the AI checkbox, so the same dropdown reads "Under ¥1,000,000" or
  "Under ¥300,000". Verified in Chrome: ticking AI changes all three options.
- **The exact amount stays.** The freeze gate lists `investment_amount_rmb`
  among its required facts, so `amount_required` still appears on a
  bracket-derived classification — it has stopped being a reason to hedge the
  tier, not stopped being wanted.
- `e2e_check.py` had an assertion locking the old semantics — "tier marked
  provisional" on a bracket-only romance fixture. It now asserts the opposite,
  plus that `amount_required` still appears, plus a new case: an **unanswered**
  budget is still provisional and says `budget_unknown`, so "settled from a
  range" has not quietly become "settled from nothing".
- Verified: `python -m pytest` (461 passed, 3 skipped), `npx tsc --noEmit`
  clean, and in Chrome with the amount left blank and only a range chosen:
  `Tier T3`, **no provisional marker**, citing `tier-live-action-2026`, with
  `amount_required` still listed.
- **Known duplication:** `web/lib/enums.ts` carries the figures so the dropdown
  can name them. The tier is computed server-side from the pinned snapshot and
  stays correct if the two drift; the labels would not.

### A — ask what a creator can answer, and what actually decides something

Five changes to what intake asks, from reviewing the form question by question.

- **A working title.** `required_facts` has always included `title`, and the
  wizard sent `title_working: null` — so every project reached the freeze gate
  with a fact it could never have supplied. Asked now.
- **A synopsis, read by the subject stage alongside the logline.** One sentence
  is thin evidence for a special-subject match. Verified end to end: a logline
  of 「两个老朋友在小城重逢」 with the operation described only in the synopsis
  now returns `T1`, quoting the synopsis — and would have read as three-class
  before. The verbatim rule is unchanged; there is simply more of the creator's
  own text for a quote to be found in.
- **`has_finished_film` becomes `production_stage`** (idea / script written /
  shooting / finished). The bool could not say whether shooting had *started*,
  which is the line article 12 draws, and nothing read it. **A one-class project
  already shooting now carries `filing_due_before_shooting`** — the tier does not
  move and no state changes, but a roadmap opening with a step they have passed
  would read as advice when it is a problem.
- **The distribution question is gone.** Nothing in `core/` read
  `domestic_platforms`; asking a first-time creator where they will publish, and
  then ignoring the answer, was the worst of both.
- **The two Circular 35 conditions fold into a disclosure.** Neither is
  answerable at intake — platform promotion is settled after the film exists —
  but deleting them would let a platform-featured 500,000 project read as
  three-class when Circular 35 makes it a key micro-drama. Out of the first
  screen, not out of the model.
- Verified: `python -m pytest` (459 passed, 3 skipped — 3 new), `npx tsc
  --noEmit` clean, and the whole path driven in Chrome with a synopsis-only
  subject hit while already shooting.

### A — the help panel closes when you click away

- Clicking anywhere outside an open `?` panel closes it, and so does Escape.
  Previously the only way out was finding the same `?` again, and with nine of
  them on the page that is worse than having opened it.
- Clicks **inside** the panel do not close it, so the question box can be
  focused and typed into. The listener exists only while a panel is open.
- Verified in Chrome: opening, clicking the question box (stays open, takes
  focus), clicking the page background (closes). `npx tsc --noEmit` clean,
  `python -m pytest` unchanged at 456 passed, 3 skipped.

### A — field help: explain the question instead of reading the answer

- Every intake field gains a `?`: hover the label for a hint, open it for the
  hint plus a worked example, and ask a question answered from the clauses
  behind that field, with clause ids and the snapshot version shown.
- **The two conversational-extraction commits earlier today are reverted.**
  `core/intake_chat.py`, its endpoint and its twenty tests are deleted;
  `POST /v1/intake/turn` becomes `POST /v1/intake/explain`. Reading a creator's
  answer accepts their confusion and copes with it. Explaining the question
  removes it, and leaves them understanding the form they are signing. See
  [D-035](docs/decisions.md#d-035).
- The risk goes with it. The reply schema is `{answer, clause_refs}` — **no
  value field** — so nothing a question says can reach the form, and the
  traceability guard the previous design needed is replaced by the shape of the
  reply. `test_the_reply_has_nowhere_to_put_a_value` holds that line.
- Two disciplines kept: answers come from clause text passed as trusted context,
  and a clause the model names but the snapshot does not carry is dropped; the
  model may say what the tiers are and never which one a project is in.
- The first two layers need no backend at all. Offline the `?` still shows its
  hint and example, and says only the question layer is unavailable.
- **Three defects found by driving it in Chrome, none of which the tests could
  have caught:**
  - The ask box was a `<form>` **nested inside the wizard's form**. React lets
    that into the DOM, the browser warns, and the inner submit reaches the outer
    form: the page reloaded and wiped the answer between the 200 coming back and
    anything rendering it. The request had succeeded every time. Now a `div`
    with a button and an Enter handler.
  - The first answers named the field by its key and rendered 联调门槛 as "joint
    adjustment thresholds", with no figures — correct, sourced, and less use than
    the static hint above it. The form's own label is now sent with the question,
    and the prompt asks for the figure where a clause carries one. The same
    question now answers with 800,000 and 300,000.
  - `platform_promoted` and `voluntary_key_declaration` were mapped to Order 16
    articles 5 and 17, which do not mention sponsor promotion — so the model
    answered that the clauses did not explain the field, which reads as a failure
    rather than as the hint being the whole answer. Both now map to nothing, and
    a field with no clauses **does not reach the model at all**: asking anyway
    invites a paraphrase of half-remembered regulation, which is the one thing
    this must not produce. The panel says so, and names 广电办发〔2024〕35号 as
    the document the snapshot cannot cite yet.
- Verified: `python -m pytest` (456 passed, 3 skipped — 26 extraction tests
  removed, 13 added), `npx tsc --noEmit` clean, and all three paths driven in
  Chrome: a field with clauses answering with figures and a citation, a field
  without them showing the hint-only message, and the static layer with no
  network at all.

### A — the intake turn endpoint, which cannot write

- `POST /v1/intake/turn` takes one sentence and returns proposals: the value,
  the words it was read from, and whether it was quoted or inferred. Creator or
  admin only.
- **Stateless and project-free on purpose.** It does not take a project id, does
  not store, and does not classify. Storing stays
  `POST /v1/projects/{id}/intent`, after a person has looked. As long as this
  endpoint cannot write, no prompt that reaches it can make the product believe
  anything — and there is a test asserting exactly that, because the tempting
  next commit is always "and then apply the patch".
- An empty turn and an oversized one are both refused **before** the model is
  called, and the tests assert the backend recorded no call rather than just
  checking the status code.
- Verified: `python -m pytest` (469 passed, 3 skipped — 6 new), including that a
  scripted backend offering a `tier` has it dropped before the response, and
  that with no backend the endpoint still answers with `intake_chat_pending`
  rather than an empty proposal list that reads as "nothing found".

### A — conversational intake, step 1: reading a turn without believing it

- New `core/intake_chat.py`. One turn in, proposed intake answers out, nothing
  stored and nothing classified. No UI yet, which is the point: every safety
  property lives here and can be attacked before anything is visible.
- Three rules, in order. **Traceable or discarded** — a proposal must quote a
  span of what the person actually typed, and a value with no sentence behind it
  is dropped, because there is nothing to show them for checking. **Verbatim or
  inferred, both kept** — "around a million" becomes 1,000,000 flagged as
  inferred and carrying the words it came from, rather than being thrown away.
  **Intake fields only** — `PROPOSABLE_KEYS` is derived from `IntentProfile`, so
  a tier or a form type cannot be proposed however the model phrases it.
- This deliberately differs from `core/extract.py`, which keeps discarding
  anything not literal. That module reads a document nobody is watching; here the
  person is on the other side of the screen with their own sentence beside the
  field. Same requirement, different response to failing it.
- **Four defects the 20 scripted tests could not have found, all from running it
  against Vertex:**
  - `RESPONSE_SCHEMA` used a union type (`["string","number","boolean","null"]`).
    Vertex rejects a list there, so every scripted test passed while no real call
    could have succeeded. Values now arrive as text and the schema does the
    typing, which it was doing anyway. **`core/extract.py` has the same latent
    bug**, unhit only because fact extraction is not wired up yet.
  - `episode_minutes` is a float, so a creator typing `3` produced `3.0`, whose
    string is absent from "3 minutes each" — flagged as inferred and sent back to
    be checked. `_renderings` now knows an integral float was written without the
    decimal, and that 900000 may have been written 900,000.
  - A single genre offered for `genre_keywords` failed to coerce, because the
    field is a list. A scalar for a list field is now wrapped: that changes the
    shape, not the content.
  - A live model emits **one proposal per keyword**, so two genres in one turn
    produced two entries for the same key and `as_patch()` silently kept the
    last. List fields now merge; a second value for a scalar is set aside as
    `already_answered_in_this_turn` rather than overwriting an answer nobody saw.
- Verified: `python -m pytest` (463 passed, 3 skipped — 20 new) and five turns
  against a live Vertex-backed Gemini, including 「投资九十万，AI 生成的科幻短剧」
  → amount, AI flag and genres all read and flagged, and two injection attempts
  in both languages producing an empty patch.

## 2026-08-28

### Shared — two decisions were sharing an id, and the wizard looked frozen

- **`docs/decisions.md` had two D-026 entries and two D-027 entries**, written the
  same day about different things. Markdown resolves `#d-026` to the first, so
  every link meant to reach "a disputed policy reading is reported provisional"
  landed on "final amount tiers require amount, mode, and thresholds" instead —
  including the reference in D-031, which claims to supersede half of it.
- The second occurrences are renumbered to **D-033** and **D-034**, each carrying
  a note saying what it was published as and why it moved. That bends the
  never-renumber convention, deliberately: the convention exists so references
  stay stable, and here it was the collision breaking them. The first entries
  keep their ids, so nothing that already resolved correctly moved.
- Every reference across `CHANGELOG.md`, `core/`, `tests/` and `docs/` was
  reclassified one at a time — 10 pointed at the renumbered pair, 2 genuinely
  pointed at the originals and were left alone. The index also gained the row
  D-027 never had.
- **The wizard looked frozen for eight to twelve seconds.** The only feedback was
  the submit button's label, and the answer renders below the fold, so a real
  Vertex call read as a hang. There is now a card where the answer will appear,
  saying what is happening and how long it usually takes, and the result scrolls
  itself into view when it lands.
- Verified: `python -m pytest` (443 passed, 3 skipped), `npx tsc --noEmit` clean,
  every decision id unique across 34 entries, and both states checked in Chrome.

## 2026-08-27

### A — the wizard stops asking a first-time creator unanswerable questions

- **The domestic platforms field was prefilled with `hongguo,douyin`.** Nobody
  said that. It is the same defect as the `band_b` default: naming a distribution
  plan the creator never stated, and a first-time creator often has no plan yet.
  Now empty, labelled optional, and carrying the fact that it **does not affect
  the tier or the filing route today** — verified: nothing in `core/` reads
  `domestic_platforms` at all. It is stored for the distribution check that is
  not built.
- The two 广电办发〔2024〕35号 checkboxes said what they were but not what to do
  about them. Added: leave both unticked unless you already know otherwise —
  platform promotion is a commercial arrangement usually settled after the film
  exists, and declaring voluntarily trades the strictest route for a distribution
  licence, which is worth it for awards, priority scheduling and negotiating with
  platforms.
- Verified empty platforms end to end: channels returns 200 with
  `tracks_enabled {china: true, us: false}`, and classification is unaffected.
  `npx tsc --noEmit` clean, `python -m pytest` (443 passed, 3 skipped).

### A — the English UI is now actually English

- All 23 mixed-language strings in `locales/en.json` are English. Most were pure
  noise: `"Special subject 特殊题材 (special subject)"` said the same thing three
  times, and eight material labels followed that shape. A few were Chinese only
  and unreadable to an English speaker: `待补充`, `国家广电总局`.
- Two demo institution names in `app/institution/page.tsx` were hard-coded past
  the locale bundle entirely, so no amount of locale work would have caught them.
- Terms of art are translated rather than kept: 重点微短剧 as "key micro-drama",
  招商主推 / 首页首屏推荐 as "sponsor-promoted, or shown on a home or landing
  screen", 广电办发〔2024〕35号 as "NRTA Circular 35 (2024)".
- The two Chinese strings left in the codebase are **comments** in
  `app/wizard/page.tsx` citing 广电办发〔2024〕35号. They are not user-visible, and
  a citation is exactly where the original document number belongs.
- **This narrows the locked decision in `lib/i18n.ts`** ("the UI is English;
  Chinese legal terms are kept with an English gloss"). The glossing is dropped;
  the plan is a full Chinese bundle later, where those terms belong, rather than
  a mixed one now. See [D-032](docs/decisions.md#d-032).
- Verified: `npx tsc --noEmit` clean, `python -m pytest` (443 passed, 3 skipped),
  and a scan of every `.ts`/`.tsx` under `app/`, `lib/` and `locales/` for CJK
  outside comments returns nothing.

### A — the budget field stopped inventing a number, and says what it is

- The wizard's budget dropdown rendered raw enum values — `band_a`, `band_b`,
  `band_c` — which tell an individual creator nothing. They now read as what they
  mean ("Large — at or above the 重点微短剧 threshold", and so on), from the
  locale bundles rather than hard-coded, and without restating figures the
  snapshot owns.
- **It defaulted to `band_b`.** A creator who never opened that dropdown and left
  the amount blank got a `T2` derived from a medium budget they had not claimed —
  ground rule 3, invented as a default. It now defaults to `unknown`, which the
  chain already handles honestly: it assumes the stricter tier, flags
  `budget_unknown`, and returns the three-tier comparison card.
- Reordered so the exact investment amount comes first and the band reads as the
  fallback it is, with a note saying an exact figure always wins and that a band
  only ever yields a 暂定 tier. The note previously said "the amount above" while
  sitting above the amount field.
- Verified: `npx tsc --noEmit` clean, `python -m pytest` (443 passed, 3 skipped),
  and the form checked in Chrome.

### A — local settings come from .env, via uvicorn rather than the app

- Added a git-ignored `.env` and start the API with
  `python -m uvicorn api.main:app --port 8080 --env-file .env`. No code change
  and no new dependency: `--env-file` is uvicorn's own flag and `python-dotenv`
  ships inside the `uvicorn[standard]` we already declare.
- The application still does **not** read `.env` itself. Settings arrive from the
  environment and the file is one way to fill it, not a second source of truth —
  so `Settings.from_env()` keeps its single path and the test suite keeps running
  with nothing set at all.
- The emulator hosts in `.env.example` are deliberately left out of the working
  `.env`: pointing at an emulator that is not running is worse than leaving
  storage in memory.
- Verified from a shell with all four variables explicitly unset: `healthz`
  reports `llm_backend: vertex`, and `/v1/internal/*` answers 404 for an unknown
  project rather than 403, so the token loaded too.

### A — intake was broken in the browser, and the filing route is now on screen

- **`IntentRequest` was missing `platform_promoted` and `voluntary_key_declaration`.**
  Both reached `IntentProfile` and the wizard form when 广电办发〔2024〕35号's two
  non-money conditions were modelled, but never the API DTO. `ApiModel` sets
  `extra="forbid"`, so the wizard's every submission came back **422** and the
  main flow did not work at all from a browser. Found by driving the UI in
  Chrome; `scripts/e2e_check.py` never caught it because its fixtures do not send
  those two fields.
- Added both to the DTO, plus two tests: one posting them through HTTP, and one
  asserting **every field the domain `IntentProfile` carries is reachable over
  HTTP** — a field the domain models but the DTO omits is invisible until
  someone posts it.
- The wizard now renders `filing_route` under **"Where this files"**: the
  authority, whether a filing is due before shooting, the document produced, and
  a highlighted line saying whether release is blocked until it is granted. New
  keys in `locales/en.json` and `locales/zh.json`.
- Verified in Chrome against a live Vertex-backed API, both halves of the
  contrast: 900,000 RMB **with** AI → `T1` · `tier-ai-generated-2026` ·
  国家广电总局 · pre-shoot filing required · "You cannot publish until this is
  granted"; the **same amount without** AI → `T3` · `tier-live-action-2026` ·
  platform · not required · "The platform reviews this before broadcast". That
  contrast is the demo.
- Verified: `python -m pytest` (443 passed, 3 skipped) and `npx tsc --noEmit`
  clean.

### Shared — a special-subject tier is settled, and the silent T1→T2 relax is gone

- A special-subject hit no longer reports `tier_provisional: true` just because
  its rules carry `expert_pending`. Whether an expert has vetted the trigger
  vocabulary is a fact about the **snapshot**, already reported by
  `policy_verification_status`, and it is settled in the outer loop before
  publication. It is not a statement about whether this project's tier may move.
- This closes **D-029** without touching `recalc_tier`. Recalc only processes
  provisional tiers; subject hits are now outside its reach, so the path that
  relaxed a 缉毒 project from **T1 to T2** on a policy refresh no longer exists.
- `expert_pending` keeps its honest jobs: the `rules_expert_pending` and
  `subject_match_unconfirmed` flags still appear, and `core/review.py` still
  downgrades such findings to `needs_human`. It reports; it no longer decides.
- Verified: `python -m pytest` (441 passed, 3 skipped) and
  `python scripts/e2e_check.py` against a live Vertex-backed API — **ALL CHECKS
  PASSED**, the first fully green run. The two assertions that had been left
  failing on purpose went green **unmodified**, which is the point: they always
  described the correct behaviour. The owner's inbox now carries only
  `policy_stale` and no `tier_recalculated`, because recalc correctly leaves the
  project alone.
- See [D-031](docs/decisions.md#d-031), superseding the subject half of D-033.

- **Found while doing this, not fixed:** `ImpactNode` has only `D1C` and `C1A`,
  so a change to `p2_subject_rules` has no node to declare and `_is_affected`
  returns false — projects classified on an old trigger vocabulary are **not
  even marked stale**. Since that vocabulary is the part most likely to change,
  this is the live gap. Left for T-B3, when `impact_nodes` is first computed for
  real projects rather than living only in the policy loop's memory adapter.
  **B depends on this.**

### Shared — a classification now says where it files, not just what tier it is

- `Classification` gains `filing_route`: the authority a tier reports to, whether
  a filing is due before shooting, what document the process yields, and whether
  release is blocked until that document lands. T1 to 国家广电总局, T2 to 省级以上,
  T3 to the platform's own pre-broadcast review.
- The route is **data in the snapshot** (`p4_process_templates.filing_routes`),
  not logic in the chain, so a policy change is a snapshot change. It is attached
  once in `classify()` alongside the not-yet-in-force check, for the same stated
  reason: every branch decides a tier, so a rule only some branches honour is not
  a rule.
- Cited from **总局令第16号 only** — articles 12, 13, 17 and 34, three of which
  are new clause entries in `p6_legal_clauses`. 广电办发〔2024〕35号 states the
  same three levels, but it is a 规范性文件 and the Order is a 部门规章; citing
  the higher instrument is more defensible, and 35号 has no `SRC-` id in the
  sources-v2 archive anyway. See [D-030](docs/decisions.md#d-030).
- A route whose clauses are absent from the snapshot is **not returned at all**,
  and a tier with no route entry yields `None` rather than a guess. Verified
  against `seed-snapshot-v1.yaml`, which predates the field: routes read as
  absent, not as invented.
- **Product effect:** this closes the half of the question the product could not
  answer. An individual creator's 250,000 RMB AI micro-drama now comes back
  `T3 / platform / pre_shoot_filing: not_required / blocks_release: false` —
  which is the one path open to someone with no 《广播电视节目制作经营许可证》.
- Verified: `python -m pytest` (441 passed, 3 skipped — 5 new) and
  `python scripts/e2e_check.py` against a live Vertex-backed API, where all three
  amount fixtures now also assert their authority. `python
  scripts/materialize_policy_snapshot_v2.py` regenerated the frozen archive copy.

### A — the golden path now exercises amount-based tiering

- `scripts/e2e_check.py` gained three fixtures that supply
  `investment_amount_rmb`: a 3.2M live-action (T1), a 1.5M live-action (T2), and
  a 0.9M **AI** micro-drama (T1). Every previous fixture left the amount unset,
  so the walkthrough only ever exercised D1c's band placeholder and never the
  branch that actually decides a tier once thresholds are published.
- Each asserts three things: the tier, that it is **settled rather than
  provisional** (proving the placeholder was not consulted), and that the
  evidence cites the threshold clause it used.
- The AI fixture is the useful one to demo: **the same 900,000 RMB is T3 as
  live action and T1 as AI**, because 广电总局网络视听司《管理提示（AI微短剧
  分类分层标准）》sets a lower set (T1 ≥ 800,000) than the live-action one
  (T1 ≥ 3,000,000). It cites `tier-ai-generated-2026` rather than
  `tier-live-action-2026`, so the switch is visible in the evidence.
- Correction to the previous entry's framing: the amount path was **not**
  untested. `tests/test_classify.py` covers it well, including the disputed
  boundary. What was missing was end-to-end coverage through the API, which is
  what these fixtures add.
- Verified: `python -m pytest` (436 passed, 3 skipped) and
  `python scripts/e2e_check.py` against a live Vertex-backed API — all 12 new
  checks pass. The run still reports the two D-029 recalc failures, unchanged.

### Shared — policy evidence indexed by tier, and M-001 stops blocking

- Added `docs/policy-library/BY-TIER.md`: the 一类 / 二类 / 三类 evidence index.
  Each tier gets its filing trigger, pre-shoot duty, review step, authority
  level, and whether we hold the original. Clause text is quoted from the
  verified `official_primary` texts of 总局令第16号 (P-001) and 广电办发〔2024〕
  35号 (P-002) only.
- Recorded in `MISSING.md` that **M-001 cannot be obtained from public
  channels**. A site-restricted search of `nrta.gov.cn` returns 35号, Order 16
  and the consultation draft but not the 调整通知; everything findable is a
  republication without a 文号. Cause is instrument rank — 部门规范性文件 have
  no mandatory central publication, and `flk.npc.gov.cn` does not carry
  「广电办发」at all. M-001 is therefore **no longer a blocker**: the goal
  changes from "obtain the original" to "obtain the 文号 plus a source more
  authoritative than a municipal page", and the open questions move to a human
  contact in the industry.
- **Decision: proceed on R-001's numbers** — T1 ¥3,000,000 / T2 ¥1,000,000,
  `thresholds_published: true` unchanged. Order 16 article 5 carries no figures
  of its own, so the amounts must come from a subordinate document, and R-001
  is the best-evidenced one available.
- Verified: `python -m pytest` (436 passed, 3 skipped). Documentation only, no
  code or snapshot change.

### A — the e2e check survives a live model and follows the pinned snapshot

- `scripts/e2e_check.py` timed out against a real Vertex backend. A classify
  call with the model available measured **8.5–11.5s** over ten runs, against a
  hard-coded 10s per-request ceiling. Worse than a flaky FAIL: the ceiling
  raised `TimeoutError`, which aborted the whole script, so every check after
  the first classify never ran and looked like it did not exist. The timeout is
  now `--timeout`, default 60s.
- The three `recalc-tier` calls still sent `snapshot_version: "v1"` while the
  service loads `seed-snapshot-v2.yaml`, so they got `SNAPSHOT_NOT_FOUND` and
  three checks failed for a reason that had nothing to do with recalc. The
  `policy-stale` call beside them already said `"v2"` — the script was half
  migrated when v2 landed (`942ec24`). Every version sent now follows the
  `snapshot_version` that `/healthz` reports, so a v3 needs no edit here.
- Verified: `python -m pytest` (436 passed, 3 skipped) and a full
  `python scripts/e2e_check.py` against a live Vertex-backed API on a fresh
  server — 12 failures before, 2 after, both remaining failures being the
  recalc defect described below rather than script problems.

- **Unfixed and left failing on purpose, for both workstreams to see:**
  `recalc_tier` (`core/workflow_service.py:262`) recomputes a tier from
  `judge_tier` alone and never re-runs the D1b subject stage. A special-subject
  project therefore **relaxes from T1 to T2** on a policy refresh while keeping
  `co_review_required: true`, its subject match, and evidence citing
  `nrta-order-16-article-5` — a tier that no longer follows from its own
  evidence. `e2e_check` reports this as "a non-provisional project is left
  alone" and "stale flag did not touch the classification". Both were being
  masked before: the first by a stale expectation that this project is
  non-provisional (it is provisional now, because the seed's subject rules carry
  `expert_pending`), the second by the abort described above. Making the script
  green would have hidden a real defect, so it stays red pending
  [D-029](docs/decisions.md#d-029). **B depends on this: `/v1/internal/*`
  recalc is the surface T-B3 calls.**

## 2026-08-26

### Shared — a clause carries its own document's effective date

- The snapshot said `effective_from: 2026-08-26` while 微短剧发展管理办法 takes
  effect **2026-09-01**. Changing the snapshot date to match **breaks the
  product**: `latest_version()` only selects snapshots whose date has passed, so
  a future-dated snapshot means nothing classifies at all. Verified, not assumed.
- The two dates answer different questions, and one snapshot legitimately holds
  both — the tier thresholds have applied since January and July, Order 16
  applies from September. `Clause` gains an optional `effective_from` and
  `in_force(as_of)`, which returns `None` for an unknown date: unknown is not
  already in force. Both seeds now record the dates their sources state.
- A classification citing a provision not yet in force carries
  `clause_not_yet_in_force`, and the wizard says which document and from when in
  plain language. The check runs once over the finished classification — the
  first attempt only inspected the subject rules, so a project citing a tier
  clause went silently unflagged.
- **This does not stop the product applying a not-yet-effective provision**, and
  says so: the output is advisory, the alternative is refusing to classify for
  five days, and the flag makes it visible. Reasoning and the revisit condition
  in [D-028](docs/decisions.md#d-028).
- **B:** this adds one optional field to `schemas/policy_snapshot.py::Clause`
  and dates the clauses in both seeds. The frozen archive copy was re-materialised
  with `scripts/materialize_policy_snapshot_v2.py`, and its integrity test caught
  the drift before I did.

Verified: `python -m pytest` — 436 passed, 3 skipped, 4 new;
`npm --prefix web test` — 24 passed; `npm --prefix web run build`. Live against a
running API: a classification citing `nrta-order-16-article-5` comes back with
`clause_not_yet_in_force` among its flags.


### Shared — 广电办发〔2024〕35号 corrects two readings and adds two tier triggers

The original 35号 arrived in the policy library, and reading it changed three
things. Two are corrections to [D-033](docs/decisions.md#d-033), written a day
earlier on weaker evidence. Reasoning in
[D-034](docs/decisions.md#d-034).

- **重点微短剧 has four triggers and two were missing.** 35号 defines it as
  meeting *any one* of: special subject, the investment threshold, **platform
  promotion or front-page placement**, and **voluntary declaration**. A 300,000
  RMB ordinary drama on a platform front page is a 重点微短剧; the product
  called it T3 on amount alone. `IntentProfile` gains `platform_promoted` and
  `voluntary_key_declaration`, the wizard asks both, and either alone returns T1
  without consulting the amount. Unanswered is never treated as true.
- **The threshold boundary is not disputed after all.** 35号 writes
  「达到100万元及以上」 and 「30万元（含）—100万元之间」; the 2026 adjustment uses
  the same pattern and the AI standard has no variant. D-033 flagged every
  equality on the strength of one republished page, which marked the AI
  thresholds uncertain when their source is clear. A threshold set may now carry
  `disputed_boundaries`, and nothing is flagged unless the policy data says so.
- **The special-subject disposal is well founded.** 35号 says 特殊题材 follows
  the 协审工作机制 explicitly, so that is no longer flagged. The remaining
  provisional marking is renamed `subject_match_unconfirmed`, because what is
  unconfirmed is the keyword match, not the disposal.

### Shared — one policy library, and a stray wheel removed

- Added `docs/policy-library/`: the deduplicated set of documents the product's
  policy claims rest on, with `MISSING.md` listing what is still needed and
  where to look for it. Newly archived: **广电办发〔2024〕35号**, 总局令第63号
  《电视剧内容管理规定》, and 《网络短视频内容审核标准细则（2021）》.
- Two documents were already archived as scraped HTML or as a scan; the library
  keeps the official PDF and the copy with a text layer instead. Documents that
  exist unchanged in `docs/partner-review/sources-v2/` are **referenced, not
  copied** — that directory is frozen and has its own integrity tests, so the
  manifest is a single index rather than a second copy.
- Removed `httpx2check/httpx2-2.12.0-py3-none-any.whl`, a 93 KB wheel checked in
  during the `httpx2`-vs-`httpx` investigation. The finding is recorded in the
  CHANGELOG and the status note; the wheel itself served nothing.

Verified: `python -m pytest` — 432 passed, 3 skipped;
`npm --prefix web run build`.


### Shared — two disputed policy readings stop being reported as settled

Verifying the v2 source archive turned up two places where the product asserted
more than its sources support. Both were written down in the archive and
invisible in the running system. Reasoning in
[D-033](docs/decisions.md#d-033).

- **The threshold boundary.** `SRC-002` writes the live-action boundary two ways
  on the same page — 「300万元及以上」(`>=`) and 「300万元以上」(`>`). The code
  picks the inclusive reading, which is fine, but returned it as final: exactly
  ¥3,000,000 gave `T1` with `tier_provisional: False`, with a test locking it
  in. An amount **exactly on** a threshold now returns the same tier with
  `tier_provisional: True` and `threshold_boundary_disputed`. One yuan either
  side is unaffected — only equality is disputed.
- **The special-subject disposal.** A hit set `tier=T1, tier_provisional=False`
  unconditionally, but the cited article says the authority consults *when it
  considers it necessary*. While the rules that produced the hit carry
  `expert_pending`, the tier is now provisional with
  `subject_disposal_unconfirmed`. **Co-review is kept** — of the two readings it
  is the safer one for a creator to plan around, and it is advice about
  preparation rather than a claim about the law.
- Confirmed rules settle both with no code change, and there is a test for that
  path so the provisional marking cannot quietly become permanent.

Also verified, and correct: all 12 checksums in the archive match, the archived
snapshot is byte-identical to `policy/seed-snapshot-v2.yaml` apart from line
endings, and every claim the manifest makes about the source text holds —
including that the 300万 contradiction really is on the page.

Verified: `python -m pytest` — 421 passed, 3 skipped, 2 new in
`tests/test_classify.py` plus updated boundary parametrisation.


### Shared — a malformed material card skips instead of 500ing

- `core/materials.py` read `raw["asset_kind"]` directly after B bound cards to
  asset kinds, so a pack card missing the field raised `KeyError` and an unknown
  value raised `ValueError`. Either one took down `GET /v1/projects/{pid}/materials`
  entirely — **every card disappeared because one was wrong.**
- That contradicted the rule three lines above it, where a card with no
  `material_id` or `name_key` is skipped. A missing or unknown `asset_kind` is
  now treated the same way: one card is absent, the rest still render, and the
  pack author sees the gap.
- The seed v2 pack always supplies `asset_kind`, so nothing was broken in
  practice. The exposure is that the pack is authored by the policy loop:
  publishing one card without the field would have blanked the collection page
  for every project.
- `build_material_cards` docstring now shows `asset_kind` in the pack shape it
  accepts, since it is required.

Verified: `python -m pytest` — 417 passed, 3 skipped, 2 new in
`tests/test_materials.py` covering a card with no kind and a card naming an
unknown one.


### Shared — complete mock-verified policy snapshot v2

- The local default policy snapshot now contains all p1–p6 packs required to
  drive the domestic T1/T2/T3 creator workflow; v1 remains an explicit legacy
  fixture.
- Cross-pack validation rejects unusable thresholds, missing clause references,
  incomplete process templates, and ambiguous material cards before load or
  publication.
- Classifications pin `verification_status` separately from computational tier
  finality, and Wizard, Dashboard, Collection, and Policy Admin visibly label
  `mock_verified` data ([D-027](docs/decisions.md#d-027)).
- Material cards now declare one `asset_kind`; the service rejects wrong-kind
  attachments and Collection selects the latest matching asset.
- Added a deterministic HTTP integration test from default startup through T2
  classification, roadmap, material validation, script pre-check, D3 gate, and
  frozen v2 form. Added the human-only promotion checklist.
- This does not claim cloud deployment, Gate 5-b completion, human policy
  verification, or legal advice.

Verified: `python -m pytest` — 417 passed, 3 skipped; `npm test` — 24 passed;
`npm run typecheck` and `npm run build` — exit 0.

### Shared — exact-amount, mode-specific tier runtime

- Intake and the Wizard now accept `investment_amount_rmb` as an optional,
  non-negative whole-RMB value.
- D1c selects `live_action` or `ai_generated` threshold data from the pinned p3
  pack. A missing amount, missing generation mode, or flag-only publication
  remains provisional ([D-026](docs/decisions.md#d-026)).
- Final amount tiers and recalculation carry the selected pack `clause_ref`
  instead of always citing the hard-coded future NRTA article.
- This changes the shared intake and policy-pack seam. It does not activate a
  static v2 seed or change Gate 5-b.

### A — every long job is a task, and where it runs is now a choice

- Fact extraction and script review ran inline and recorded nothing, so
  `GET /tasks` was empty for projects that had had work done to them. Both now
  write a `WorkflowTask` with its key, status, and result
  ([D-025](docs/decisions.md#d-025)).
- Added `core/jobs.py`: `InlineRunner` does the work now and answers in the
  response, `QueuedRunner` publishes and leaves the task `queued`. Local
  development and the tests use inline, so a demo still needs no queue.
- Added `workers/jobs.JobWorker`, which finishes a queued task. A task already
  in a terminal state is acknowledged and dropped — Pub/Sub delivers at least
  once, and a redelivered review must not write a second set of findings. A job
  type the worker does not know is recorded `failed` with the reason rather than
  silently discarded.
- **Idempotency is now enforced in one place for every job type** on
  `{project_id}:{task_type}:{asset_version}`. It was previously load-bearing
  only for the teaser, since nothing else created a task.
- **Fixed while adding it:** `review_incremental` was chosen when findings
  already existed for the version under review, so re-running a review of the
  same version flipped the job type, changed the key, and let the replay review
  the same script twice. Incremental now means *relative to an earlier version*.
- A queued review answers with no findings and `backend: "queued"`, so "nothing
  has happened yet" is distinguishable from "the script is clean".

Verified: `python -m pytest` — 375 passed, 3 skipped, 14 new in
`tests/test_jobs.py`. Driven against the 30-minute fixture both ways: inline
returns 9 findings in the response; queued returns 0 with `backend: "queued"`,
the worker then produces the same 9, and a redelivery leaves them at 9.

## 2026-08-25

### A — Veo teaser behind FLAG_VEO_TEASER

- `POST /v1/projects/{pid}/teaser` queues a `teaser` task. The flag is off by
  default and the route says so — a disabled feature is a fact worth telling the
  caller, not a 404.
- **A teaser is promotional material and carries no compliance meaning.** The
  prompt is built from the logline alone: no tier, no clause, no filing status.
  The task records `promotional_only: true` beside the uri and pins the snapshot
  and prompt version, so a generated file cannot later be mistaken for a
  reviewed artifact.
- The logline is wrapped in `<<<DOC>>>` like every other user-supplied document,
  so an instruction inside a logline cannot steer generation. Tested.
- **No backend means no teaser.** With Veo unconfigured the task is
  `needs_human` with `teaser_backend_unavailable` and no result — never a
  placeholder uri, which would look like output. A backend that raises is
  recorded `failed` with the reason rather than swallowed.
- Idempotent on `{project_id}:teaser:{asset_version}` like every other job: a
  repeated request returns the first task and does not generate twice.
- `VideoBackend` is a port with `UnavailableVideo` as the default, mirroring the
  LLM seam, so tests and local runs need no credentials.
- `scripts/e2e_check.py` gains step 18, which now reports rather than listing
  the step as pending.

Verified: `python -m pytest` — 361 passed, 3 skipped, 13 new in
`tests/test_teaser.py` covering the flag, the offline path, prompt injection in a
logline, idempotency, a failing backend, and the absence of any compliance claim
in the generated request.


### A — scene attribution in C1-a, found by B's synthetic scripts

Running the three fixtures from #27 through the real reviewer exposed four
faults in the scene parser. None were visible against the one-line-per-scene
scripts the harness shipped with.

- **Findings attributed to bare lines.** Only lines that themselves carried a
  heading got an episode and scene; everything else reported `None`. A finding a
  creator cannot navigate to is not much use. A line now inherits the episode
  and scene it sits inside, and the markdown form — `### 第N集` followed by
  `**内景·…**` slug lines — is supported alongside `第一集 场景二`.
- **The documents' own disclaimers were reviewed.** The judicial fixture's
  blockquote mentions 庭审 and 审判, so the file's warning that it is synthetic
  produced a finding. Blockquotes and everything above the first episode heading
  are commentary about a script, not script.
- **`第47版` became scene 47.** The 场 in the scene pattern was optional, so any
  `第N…` line reset the scene number.
- **Appendix text was filed under episode 7.** A section heading that is not an
  episode now closes the one before it.

Effect on the long fixture: 38 findings down to 25, every one carrying an
episode, and all seven scenes the fixture names as expected are covered.

A plain script with no episode headings is still reviewed whole, so nothing that
worked before stopped working.

### A — one C1-a finding per scene, with every matching line kept

- Findings deduplicated per matching *line*, so a courtroom scene naming the
  judge in eleven lines produced eleven findings — eleven rows to dismiss for one
  rewrite decision, and eleven clicks to waive it. They now group on
  `(category, episode, scene)`: the long fixture goes from 25 findings to 14.
- **Deduping does not lose the way back.** `Locator` gained `line` (the 1-based
  position of the quoted line) and `match_lines` (every line in the scene that
  matched), so one row per scene still opens onto each individual line. The
  collection UI lists them under the quote. Reasoning and limits in
  [D-024](docs/decisions.md#d-024).
- **B: this adds two optional fields to `schemas/findings.py`**, the shared
  contract boundary. Both default, nothing existing breaks, and the policy loop
  never reads `Locator` — flagged for awareness rather than assumed.

Verified: `python -m pytest` — 348 passed, 3 skipped, 16 new in
`tests/test_scene_parsing.py`. Each case came from running the fixtures, not
from imagination; four assert the statements written into the fixtures
themselves so a fixture and the reviewer cannot drift apart silently; and one
resolves every recorded line number back to a line that really matched.


### A — institution console, the way back from a return, and task reads

- New `/institution` page: the demo registry, submission with its licence
  verdict, the institution's accept/return decision, and filing. The licence
  verdict renders as `mock check passed` / `mock check did not pass` beside a
  `mock` chip and a plain-English disclaimer, and an unknown institution reads
  "Unknown, not approved" rather than looking like a failure or a pass.
- **Closed a dead end:** `INSTITUTION_RETURNED` had no exit. The state table
  allowed the way back to `REVISION_LOOP` but nothing performed it, so a
  returned project could never be corrected and resubmitted. Added
  `POST /v1/projects/{pid}/institution/resume`.
- Added `GET /v1/projects/{pid}/institution` so a creator can read the verdict
  and the return comments on their own project, and
  `GET /v1/projects/{pid}/tasks` for contract step 17. The task list is
  genuinely empty — nothing queues async work yet — and the test says so rather
  than implying coverage.
- `TaskStore` gained `list(project_id)`, with the in-memory adapter.
- Loading the demo registry is offered only to an administrator; other roles see
  why instead of a 403 from a button that should not have been there.
- New `.button-group` style so buttons belonging to one decision sit together
  rather than being pushed to opposite edges by `.action-row`.

Verified: `python -m pytest` — 332 passed, 3 skipped, 6 new;
`npm --prefix web test` — 17 passed; `npm --prefix web run build`. Then driven
in a real browser against a live API: loaded the registry as admin, submitted to
an institution outside it and saw "Unknown, not approved", switched to the
licensed one, accepted as the institution role, recorded a filing, and watched
the badge reach `FILED`.


### A — institution review and filing

- `GET /v1/institutions`, `PUT /v1/admin/institutions`,
  `POST /v1/projects/{pid}/institution/submit`, `.../institution/decide`, and
  `POST /v1/projects/{pid}/filing` complete contract steps 12-14.
- **The registry ships empty and the licence check is always mock**
  ([D-023](docs/decisions.md#d-023)). An institution the registry does not know
  reports `institution_not_in_registry` with both sub-checks `None` — unknown,
  not passed and not failed. Nothing in the repository asserts that a real
  company exists or holds a licence.
- A mock check that failed still stops the flow: accepting requires a check that
  passed, so a foreign-invested demo institution cannot accept a project.
  Accepting also requires the signed agreement; returning requires comments.
- The creator submits and the institution decides; neither may do the other's
  act. Re-submitting while under review switches institutions and leaves the
  frozen form untouched.
- **The registration number is input, never output.** `POST .../filing` refuses
  a blank one and stores what a human supplies, verbatim. Filing never rewrites
  the frozen form — its hash is unchanged after `FILED`, which is tested.

Verified: `python -m pytest` — 326 passed, 3 skipped, 21 new in
`tests/test_institution.py`. Driven against a live API from an empty registry
through to `FILED`: unknown institution reported as unverifiable, bare accept
refused, accept into `READY_FOR_EXTERNAL_FILING`, blank registration number
refused, filing recorded, and the frozen form's hash unchanged afterwards.


### A — gate passage, form preview, field confirmation, and freeze

- `POST /v1/projects/{pid}/gate/pass` moves a project to `GATE_D3_PASSED` or
  refuses with the machine-readable gaps. `GET .../form`,
  `POST .../form/fields/{key}/confirm`, and `POST .../form/freeze` complete
  contract step 11.
- A field is filled only from a confirmed fact and carries that fact's
  `SourceRef`; conflicting facts leave it in `conflict` with neither value
  shown; everything else renders as `待补充`
  ([D-022](docs/decisions.md#d-022)). Freezing requires the gate to have passed
  and no field left pending, then hashes values, provenance, and the snapshot
  version. A frozen form cannot be edited and re-freezing returns the same hash.
- **Two dead ends in the state path, found by needing to reach the gate**
  ([D-021](docs/decisions.md#d-021)): `ROADMAP_CONFIRMED` had no exit because
  its natural trigger is attaching a material card and `p5` publishes none, so
  confirming the roadmap now starts collection in the same call, recording both
  transitions. And the gate refused with `transition COLLECTING_MATERIALS ->
  GATE_D3_PASSED is not allowed`, which tells a creator nothing; it now says the
  pre-check must run first.
- The pre-check now advances the review loop from `COLLECTING_MATERIALS` to
  `REVIEW_RUNNING`, and to `REVISION_LOOP` when blocking findings exist. T-A4
  deferred this rather than invent a path while the packs were empty.

Verified: `python -m pytest` — 305 passed, 3 skipped, 20 new in
`tests/test_form_freeze.py`. The whole golden path driven against a live API:
classify T3, roadmap into `COLLECTING_MATERIALS`, pre-check into
`REVIEW_RUNNING`, gate refused with `facts_missing`, freeze refused with
`STATE_INVALID`, five fields confirmed, gate passed, form frozen with a 64-char
hash, and a post-freeze edit refused with `CONFLICT`.


### A — finding actions and incremental review

- `POST /v1/projects/{pid}/findings/{fid}/action` takes `accept`, `resolve`,
  `waive`, `reject`, or `choose_option`. `waive` and `reject` require a reason,
  recorded on the finding and the timeline.
- **`accept` acknowledges without releasing the gate** ([D-019](docs/decisions.md#d-019)):
  agreeing that a scene is a problem does not make it stop being one.
- `choose_option` dispatches an alert finding's five-field alert. An option that
  was not offered is refused, and a finding with no alert cannot be dispatched.
- Re-reviewing a new script version carries findings forward
  ([D-020](docs/decisions.md#d-020)): a quote still in the script keeps its
  decision and moves to the new version; a vanished quote becomes `self_fixed`
  rather than being deleted. Alert findings are exempt — they come from the
  intent profile, not the script.
- Noted while testing: **the seed's synthesized subject rules never set
  `is_edge_case`, so the edge-case alert path is unreachable with the
  placeholder pack.** The alert tests publish an explicit `subject_rules` pack —
  the shape the policy loop will publish — rather than skipping.

Verified: `python -m pytest` — 285 passed, 3 skipped, 16 new in
`tests/test_finding_actions.py` covering each action, the gate consequence of
each, alert dispatch and its refusals, carry-forward, self-fix, and the timeline.


### A — collection UI, and the CORS bug it found

- New `/collection` page: upload an asset, see the version chain and its sha256,
  extract facts, work the material cards, confirm the roadmap, run the C1-a
  pre-check, and read the findings with their clause citations.
- **Fixed: `PUT` was missing from `allow_methods` in the API's CORS config**, so
  every upload failed in a browser while all 268 tests passed. Found by driving
  the page in a real browser, not by a test. `tests/test_uploads.py` now
  preflights `PUT /v1/uploads/{tid}` so it cannot regress silently.
- Pending flags render as visible warnings rather than being swallowed:
  `roadmap_template_pending`, `fact_extraction_pending`, and
  `script_semantic_check_pending` each say in plain English that the result is
  not clean, matching what the API reports.
- An empty pack renders as "the policy snapshot defines none yet", never as an
  empty-looking success.
- New keys registered in `web/locales/en.json` and `zh.json`.

Verified: `python -m pytest` — 269 passed, 3 skipped; `npm --prefix web test` —
17 passed; `npm --prefix web run build`. Then driven end to end in a real
browser against a live API: upload a script, run the pre-check, and see two
`public_security` findings at `needs_human` citing `nrta-order-16-article-5`,
with both pending-flag warnings visible.

## 2026-08-24

### A — C1-a script pre-check and the golden-sample harness

- `POST /v1/projects/{pid}/review` runs the pre-check over the latest uploaded
  script; `GET /v1/projects/{pid}/findings` lists what it found. Institutions
  and admins may read findings; only the owner triggers a review.
- Stage 1 matches the published p2 rules scene by scene, parsing 第N集/场景N
  headings into `Locator.episode` and `Locator.scene`. Stage 2 is one semantic
  pass that may only report categories the pack publishes, and whose quote must
  occur verbatim in the script — anything else lands in `discarded`.
- **Severity comes from the rule, never the model.** While the p2 keywords are
  the placeholder list, every finding is `needs_human`, not `block`. Each one
  carries an `EvidenceRef` into the pinned snapshot, so ground rule 2 holds by
  construction rather than by review. The ceiling and the condition for changing
  it are recorded in [D-018](docs/decisions.md#d-018): it is revisited after the
  first test against partner-confirmed rules, not tuned on speculation before.
- No backend means `script_semantic_check_pending`. Patterns finding nothing is
  never rendered as a clean script.
- A pre-check reports and does not move project state; the revision loop that
  consumes findings is T-A5. Re-running does not duplicate findings for the same
  asset version.
- Added the golden-sample harness (`tests/test_golden_samples.py`,
  `tests/golden/SCHEMA.md`). It runs synthetic scripts to prove the machinery,
  and rejects any golden sample lacking `provenance` and `reviewed_by`. With no
  samples present it **skips with a reason** — an empty corpus is not evidence
  of accuracy.
- Prompt contract in `prompts/c1a-script-review.v1.md`.

Verified: `python -m pytest` — 268 passed, 3 skipped (the empty golden corpus),
16 new in `tests/test_script_review.py`. Live against the real seed: a
two-scene script yields two `public_security` findings at `needs_human`, each
citing `nrta-order-16-article-5`, and the gate reports them under
`findings_needs_human`.


### A — roadmap preview and confirmation

- `GET /v1/projects/{pid}/roadmap` builds the plan from
  `p4_process_templates` for the template the classification chain already
  chose; `POST .../roadmap/confirm` accepts it and moves the project to
  `ROADMAP_CONFIRMED`.
- An empty template yields no steps and a `roadmap_template_pending` flag rather
  than an invented plan — a creator follows a roadmap, so inventing one is worse
  than showing none. Confirming an empty roadmap is allowed on purpose: refusing
  would block collection, review, and the gate on unpublished policy.
- Confirming twice is one event, not two. An unclassified project is refused.
- The pending flag rides on the API response, not the `Roadmap` document, so
  `schemas/` is unchanged.
- **B: this proposes a shape for `p4_process_templates`** and writes it into the
  seed with empty contents. See [D-017](docs/decisions.md#d-017) — it needs your
  review, along with [D-016](docs/decisions.md#d-016), before real content is
  published into either pack.

Verified: `python -m pytest` — 249 passed, 10 new in `tests/test_roadmap.py`.
Live against the real seed: `T3_4steps` with no steps and
`roadmap_template_pending`, confirm moves the state and keeps the flag.


### A — fact extraction from uploaded assets

- `POST /v1/projects/{pid}/assets/{vid}/extract-facts` reads one asset and
  stores only the facts the document backs verbatim; `GET .../facts` lists them.
- Kept honest three ways, each tested: a quote must occur in the document, the
  value must occur inside its own quote, and a null or blank value is dropped
  rather than stored. Rejected proposals come back in `discarded`.
- With no Vertex backend the response carries `fact_extraction_pending` and
  writes nothing, so an empty list is never read as "the document held nothing".
- Every stored fact carries `SourceRef(type=asset, asset_version, locator=quote)`,
  so a form field rendered from it traces back to the line that produced it.
- Wanted keys come from `p5_form_templates.required_facts` when the pack defines
  them, otherwise the `core.gate` defaults.
- Prompt contract in `prompts/fact-extract.v1.md`.

Verified: `python -m pytest` — 239 passed, 11 new in
`tests/test_fact_extraction.py`, covering the offline pending path, verbatim
rejection, value-not-in-quote rejection, null values, prompt injection inside an
uploaded document, gate gap closure, and role scoping.


### A — policy notifications reach the creator

- `WorkflowService` now writes an inbox entry when a policy update sets
  `policy_stale` or actually changes a tier. A recalculation that changes
  nothing stays silent, and a repeated stale flag notifies once, so consumer
  redelivery cannot refill the inbox. Reasoning in
  [D-014](docs/decisions.md#d-014).
- Added `GET /v1/notifications` (with `unread_only`) and
  `POST /v1/notifications/{nid}/read`. Each caller reads only their own inbox;
  another creator gets 403 on a read receipt and an empty list on a read.
- Added `NotificationStore.get()` to the port and the in-memory adapter, and
  made `list()` return newest first.
- Notification text stays keys plus a flat `params` map. Registered
  `notification.policy_stale.*` and `notification.tier_recalculated.*` in
  `web/locales/en.json` and `zh.json`, added `format()` to `web/lib/i18n.ts`
  for placeholder substitution, and rendered the inbox on `/dashboard`.
- **B depends on this.** It closes the product half of B P0 item 9. The policy
  consumer does not call any notification route: it keeps calling
  `/v1/internal/projects/{pid}/policy-stale` and `.../recalc-tier`, and the
  notification is written inside those calls. Nothing on the B side needs to
  change, and Gate 5-b fan-out now has a visible effect for the creator.

Verified: `python -m pytest` — 202 passed (9 new in `tests/test_notifications.py`,
including the publish-v2 → recalc → notified path); `npm --prefix web test` — 17
passed (5 new); `npm --prefix web run build`; and `python scripts/e2e_check.py`
against a live API on port 8082 with `INTERNAL_TOKEN` set — ALL CHECKS PASSED,
including the six new checks under `17. the creator inbox`. No cloud
credentials, no emulator, no network.

### Shared — one router directory

- `api/routes/admin_policy.py` moved to `api/routers/admin_policy.py` and the
  now-empty `api/routes/` package was deleted. The two directories were the same
  concept one letter apart, left over from the workstream merge.
- The moved file is unchanged apart from its location: it keeps its absolute
  `api.…` imports and its own style, so the diff is a rename plus one import
  line in `api/main.py`. No route path, response, guard, or contract changed.
- **B should know.** This moves a B-owned file. Nothing in `workers/policy/` or
  `web/app/admin/policy/` was touched, and `/v1/admin/policy/*` behaves exactly
  as before, but an in-flight branch that edits `api/routes/admin_policy.py`
  will need to re-target the new path. Reasoning in
  [D-011](docs/decisions.md#d-011).
- The other half of D-011 is deliberately **not** done: `require_admin` and
  `Principal` still coexist, because consolidating them changes how a policy
  route authorizes and that wants B's agreement, not just B's awareness.

Verified: `python -m pytest` — 193 passed, including
`tests/policy/test_admin_routes.py`, which exercises the moved router through
the app factory.

### A — material collection card lifecycle

- `GET /v1/projects/{pid}/materials` builds the card list from the
  `p5_form_templates` pack; `POST .../{mid}/attach`, `.../validate`, and
  `.../waive` move a card through its statuses.
- The D3 gate now materialises cards itself, so a pack-defined required card
  blocks the gate even if nobody has opened the collection page.
- Validation is deterministic only — asset attached, asset exists, bytes
  present. Nothing in it is a compliance judgement.
- A waiver requires a reason and records it; a waived card stops blocking.
- Card loading lives in `core/materials.py`, the only module that knows the pack
  layout.
- **B: this proposes a shape for `p5_form_templates`** and writes it into the
  seed with empty contents. See [D-016](docs/decisions.md#d-016) — it needs your
  review before real content is published into that pack. An empty pack yields
  no cards, and a card whose `why_clause_id` is not in the pinned snapshot keeps
  no clause rather than pointing at a missing one.

Verified: `python -m pytest` — 219 passed, 15 new in `tests/test_materials.py`.
Live check against the real seed on a running API: the empty pack returns `[]`
cards and the gate reports only fact gaps — no invented obligations.

### A — upload tickets and immutable asset versions

- `POST /v1/projects/{pid}/assets/upload-url` issues a one-shot ticket;
  `PUT /v1/uploads/{tid}` takes the bytes and writes one `AssetVersion` with its
  own sha256. `GET .../assets` lists them, `GET .../assets/{vid}/content` serves
  the bytes back.
- The ticket names its `backend`: `local` with no bucket configured, `gcs` once
  `GCS_BUCKET` is set. A missing cloud backend is reported, never disguised as a
  cloud upload. Signed-URL issuance slots in behind the same response shape.
- A ticket is single-use — a replayed upload is a 409, not a silent second
  version. A new version of the same `kind` chains onto the previous one via
  `parent_version`; different kinds never chain together.
- Added `BlobStore` and `UploadTicketStore` ports with in-memory adapters, and
  the `UploadTicket` document to `schemas/assets.py`.
- Deliberately **not** here: the material-card list and fact extraction. Both
  need `p4`/`p5` pack content, which is empty. This is the mechanism half only.

Verified: `python -m pytest` — 204 passed, 11 new in `tests/test_uploads.py`
covering sha256, single-use tickets, version chaining, per-kind isolation,
owner scoping, empty-upload rejection, and the timeline entry.


### Shared — Gate 5-a published snapshot read bridge

- Added a narrow policy snapshot repository read seam and a repository-backed
  implementation of the existing product `SnapshotService`.
- Unified FastAPI composition now shares published inline snapshots between
  admin publication and product recalculation while preserving explicit context
  injection and the file-backed standalone fallback.
- Added local HTTP acceptance for `publish v2 -> recalc-tier v2`; event fan-out,
  cloud deployment, and GCS pack resolution remain outside this gate.

Verified: 193 Python tests via `.venv/bin/python -m pytest`; 12 Vitest tests;
Next production build; `compileall`; `pip check`; and wheel packaging including
the new adapter. The live NRTA source smoke returned `PASS`; cloud smoke returned
`SKIP` (`POLICY_CLOUD_CONFIG_MISSING`), so this is not deployed-cloud evidence.

### B — policy loop Gate 4: real cloud adapters and bounded source ingestion

- Added the HTTPS source adapter with a 20-second total timeout, redirect
  validation, streaming 5 MiB limit, and last-known-good preservation on
  failures.
- Added GCS blob storage, Firestore policy state and outbox persistence, Gemini
  structured proposal drafting, and Pub/Sub `policy.updated` publishing behind
  the existing policy-loop interfaces.
- Added environment-based cloud runtime assembly and explicit source/cloud
  smoke commands. A missing named project, resource, credential, or Gemini model
  is reported as `SKIP`, never as cloud success.
- Kept the Gate 4 persistence scope within B-owned collections. **No shared
  schema or product-workflow persistence contract changed in this gate.**

Verified after merging `origin/main`: 186 Python tests via
`.venv/bin/python -m pytest -q`; 12 Vitest tests via `npm --prefix web test`;
`npm --prefix web run build`; `compileall`; `pip check`; and a wheel containing
the policy source, seed snapshot, and proposal prompt. The live NRTA source
smoke returned `PASS`. The cloud smoke returned `SKIP`
(`POLICY_CLOUD_CONFIG_MISSING`), so this is not deployed-cloud evidence.

## 2026-08-23

### A — an unknown snapshot version returned 500 instead of the error envelope (fixed)

`SnapshotNotFoundError` is a `LookupError`, not an `AppError`, so asking
`recalc-tier` for a version the product cannot read crashed the request. It now
returns a 404 in the contract envelope. Found by manually driving the merged
demo: publish v2 through the policy console, then call `recalc-tier` with
`snapshot_version: v2`.

**Shared, and blocking the closed loop:** that call is *supposed* to succeed. The
product reads policy through `FileSnapshotService`, which only knows
`policy/seed-snapshot-v1.yaml`, while the policy loop publishes new snapshots
into its own repository. Nothing yet bridges the two, so a published v2 is
invisible to the product side. See [D-012](docs/decisions.md#d-012).


### Shared — policy loop merged with the product workflow (PR #7)

Both workstreams now run as one FastAPI process and one Next.js app.

- `create_app` is keyword-only: `create_app(*, context=None, policy_state=None)`.
  Product and policy state no longer compete for the first positional argument.
  **Breaking for callers:** three call sites in `tests/policy/test_admin_routes.py`
  were updated. See [D-008](docs/decisions.md#d-008).
- The web app is unified: Richard's `globals.css` design system is the base, the
  product shell (top bar, role switcher, disclaimer) wraps every page including
  the policy console. React moves to 19.2.8; Next stays 16.3.2.
- Dependencies merged. `fastapi` and `uvicorn` became base dependencies, so the
  `api` extra is gone: install with `pip install -e ".[test]"`.
- **The policy UI now calls port 8080**, not 8000. One process serves both
  sides, and 8080 is the port in contract section 8. The client falls back
  through `NEXT_PUBLIC_POLICY_API_BASE_URL`, `NEXT_PUBLIC_API_BASE`, then
  `http://localhost:8080`. See [D-009](docs/decisions.md#d-009).

Verified: 114 Python tests, 12 vitest tests, `next build` produces all routes
from both workstreams, and one process answers `/v1/projects/...` and
`/v1/admin/policy/...` with the shared error envelope.

### B — `FileBlobStore` could not read its own URIs on Windows (fixed)

`_path_from_uri` built its path from `urlparse(uri).path`, which on Windows
keeps the slash before the drive letter. `Path("/D:/x")` is then read as the
drive-relative `D:x`, every containment check failed, and 11 policy tests
errored. Reproduced on an unmodified `origin/main` worktree, so it predates the
merge. Fixed with `url2pathname`, correct on both platforms.

Verified: the 11 failures became passes; the full suite is green on Windows.

### B — `httpx2` did not satisfy Starlette's test client (fixed)

The test extra declared `httpx2>=2.12`. That distribution ships a module named
`httpx2`, while Starlette's `TestClient` imports `httpx`, so the policy tests
could not run from a clean clone — which is a Devpost reproducibility
requirement. The extra now declares `httpx>=0.27,<1`.

### A — product workflow core, intake and classification API (T-A0, T-A1, T-A2)

- **T-A0**: FastAPI app with the contract error envelope and `GET /healthz`,
  settings for every variable in contract section 8, `docker-compose.yml` for
  the Firestore and Pub/Sub emulators, `python -m workers.hello` as the Vertex
  wiring check, and the Next.js shell (`/wizard`, `/dashboard`, `/admin`).
- **T-A1**: the full enum table in `schemas/enums.py` (mirrored in
  `web/lib/enums.ts`), every TDD section 2 document, the 21-state machine with
  entry guards and audit plus timeline on each transition, and the D3 gate as a
  pure function returning machine-readable gaps. Storage ports with an
  in-memory adapter.
- **T-A2**: D1a, D1b, and D1c with the chain that pins one snapshot version;
  routes for intent, channels, classify, tier-choice, gate, and timeline.
- **Ahead of plan, and B depends on it:** `/v1/internal/projects/{pid}/recalc-tier`
  is a real implementation rather than the stub the plan asked for by D5. It
  recalculates only provisional tiers and refuses to touch frozen,
  institution-stage, or filed projects. The policy consumer can call it directly
  instead of its fake adapter. Needs `X-Internal-Token`; returns
  `{tier, tier_provisional, changed}`.
- New top-level packages `core/` and `store/`; see [D-001](docs/decisions.md#d-001).

Verified: 67 tests at the time of the commit, no credentials or network needed.
`scripts/e2e_check.py` walks the golden path against a running API and reports
each contract section 7 step as PASS, FAIL, or PENDING with its owning task.

Not verified: the real Gemini call and the emulator stack. Neither gcloud nor
Docker is installed on the development machine.

### A — D1c reads `thresholds_published` from the p3 pack

The seed snapshot now carries `thresholds_published` inside `p3_tier_thresholds`.
D1c and the workflow service read that key alongside the older
`official_published` spelling, so a published-threshold snapshot flips
provisional tiers as intended.

### B — policy loop Gate 3: administration API and UI (PR #6)

`/v1/admin/policy` exposes launch-refresh, run status, proposal list and detail,
publish, discard, and snapshot history, guarded by `X-Mock-Role: admin`. The
Next.js console lists proposals and shows a side-by-side diff with a publish
control. Run failure details are redacted before they reach a response.

Scope limit stated by the author: deterministic fixture data, mock
authorization, and process-local state that resets to seed v1 on restart.

### B — policy loop Gate 2: offline refresh, proposal, publish (PR #5)

Fixture fetch, normalization, diff, proposal creation, publish with an outbox,
outbox dispatch, and an idempotent `policy.updated` consumer. A twelve-step
offline acceptance test covers the loop end to end.

**Still open for B:** the consumer calls a fake recalc adapter rather than the
live A-line endpoint above. Wiring it is the demo's highlight shot.

### B — policy loop Gate 1: shared contracts and seed snapshot (PR #4)

`schemas/policy_snapshot.py`, `policy/seed-snapshot-v1.yaml`, the
`SnapshotService` read interface with a file adapter, and the contract tests.
This is the one hard dependency between the workstreams, and it landed first as
planned.

## 2026-08-22

### Shared — repository scaffold (PR #1, PR #2)

Directory ownership, boundary rules, and the workstream split.
