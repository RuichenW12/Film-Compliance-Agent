# Documentation

This directory is reserved for durable project documentation.

Planned document groups include:

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

Documentation must distinguish proposed design, local verification, deployed verification, and unresolved assumptions.

Implementation status must be read from the linked documents and repository history; a documented design is not proof of a running system.

## Gate 4 evidence boundary

The Gate 4 design and plan define two separate completion terms:

- **implementation complete**: five adapters implemented, default tests and packaging clean, real NRTA source smoke passing with last-known-good preservation, and independent review free of unresolved Critical or Important findings;
- **Gate passed**: implementation complete plus a named-project full-cloud smoke where GCS, Firestore, Gemini, and Pub/Sub all report `PASS`.

At the time of this implementation, the real-source mode is `PASS` and the credential-gated cloud mode is `SKIP` because required cloud configuration is not present. A fixture, fake, emulator, or skipped command must not be substituted for deployed-cloud evidence.
