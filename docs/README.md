# Documentation

This directory contains durable project documentation.

Document groups include:

- architecture and workflow explanations;
- accepted design specifications and implementation plans;
- environment and deployment runbooks;
- API and event contracts;
- demo, verification, and submission notes.

## Current documents

- [Decision log](decisions.md) — cross-workstream decisions and their reasons

- [Richard policy loop v1 scope](superpowers/specs/2026-08-22-richard-policy-loop-v1-design.md)
- [Richard policy loop v1 technical design](technical/policy-loop-v1-tdd.md)
- [Policy loop Gate 1 implementation plan](superpowers/plans/2026-08-23-policy-loop-gate1.md)
- [Product workflow v1 implementation status](technical/product-workflow-v1-status.md)
- [Policy loop Gate 2 implementation plan](superpowers/plans/2026-08-23-policy-loop-gate2.md)
- [Policy loop Gate 3 design](superpowers/specs/2026-08-23-policy-loop-gate3-design.md)
- [Policy loop Gate 3 implementation plan](superpowers/plans/2026-08-23-policy-loop-gate3.md)
- [Policy loop Gate 4 design](superpowers/specs/2026-08-24-policy-loop-gate4-design.md)
- [Policy loop Gate 4 implementation plan](superpowers/plans/2026-08-24-policy-loop-gate4.md)
- [Policy loop Gate 5-a snapshot bridge design](superpowers/specs/2026-08-24-policy-loop-gate5a-snapshot-bridge-design.md)
- [Implementation status by owner (2026-08-24)](technical/implementation-status-2026-08-24.md)
- [Manual test guide](manual-test-guide.md)
- [Deployment](deployment.md) — **how the deployed system works**: topology,
  configuration, how to ship a change, what behaves differently in the cloud,
  and what is not built yet. Start here if you are changing product code.
- [Maxine demo recording handoff](maxine-demo-recording-handoff.md) — current
  production baseline, accepted fixture result, four-minute operating plan,
  factual boundaries, and release checklist for the final recording.
- [Deployment — the parts that need you](deploy-manual-steps.md) — the human
  steps only: irreversible choices, interactive logins, and secret values
- [Illustrated walkthrough](walkthrough.html) — architecture, the classification
  mechanism, the lifecycle, the policy loop, current status, and a worked
  end-to-end run

### About `walkthrough.html`

It is the source of a published page:
<https://claude.ai/code/artifact/2983067b-2a58-4d8a-9cb8-41c19b789ef2>

The file is deliberately a **fragment** — no `<!doctype>`, `<html>`, `<head>`
or `<body>`, because the publisher supplies those. Keep it that way so the file
stays republishable to the same URL unchanged. Browsers render it correctly
from disk regardless.

Its last three sections (*Start it*, *Nine projects*, *Run one project all the
way through*) cover the same ground as [`manual-test-guide.md`](manual-test-guide.md).
**The Markdown guide is canonical** — it is the one kept current against a live
API and the one a test run should follow. When the two disagree, the Markdown
is right and the HTML needs updating.

Documentation must distinguish proposed design, local verification, deployed verification, and unresolved assumptions.

Implementation status must be read from the linked documents and repository history; a documented design is not proof of a running system.

## Gate 4 evidence boundary

The Gate 4 design and plan define two separate completion terms:

- **implementation complete**: five adapters implemented, default tests and packaging clean, real NRTA source smoke passing with last-known-good preservation, and independent review free of unresolved Critical or Important findings;
- **Gate passed**: implementation complete plus a named-project full-cloud smoke where GCS, Firestore, Gemini, and Pub/Sub all report `PASS`.

At the time of this implementation, the real-source mode is `PASS` and the credential-gated cloud mode is `SKIP` because required cloud configuration is not present. A fixture, fake, emulator, or skipped command must not be substituted for deployed-cloud evidence.
