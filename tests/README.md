# Tests

This directory is reserved for verification shared across the product and policy workstreams.

| Path | Purpose |
|---|---|
| [`contract/`](contract/README.md) | A/B interface and event compatibility |
| [`fixtures/policy/`](fixtures/policy/README.md) | Deterministic policy source and update scenarios |
| [`golden/`](golden/README.md) | Expert-reviewed product and compliance examples |

Tests should distinguish local fixture behavior from live cloud verification. Passing a fixture or emulator test must not be reported as proof that a deployed external integration works.

## Current suites

| File | Covers |
|---|---|
| `conftest.py` | Fixed clock, in-memory stores, seed snapshot, and the three fixed intent profiles |
| `test_snapshot_service.py` | Snapshot reads, clause lookup, pack normalization (T-A0) |
| `test_guards.py` | State machine transitions, audit entries, and every D3 gate branch (T-A1) |
| `test_classify.py` | D1a/D1b/D1c chain, prompt-injection resistance, quote verification (T-A2) |
| `test_api_intake.py` | Intake and classification routes, role checks, error envelope, internal recalc-tier |
| `contract/test_policy_contract.py` | Shared policy contracts and the `policy.updated` fixture |

Run everything with `python -m pytest`. The whole suite runs with no credentials, no emulator, and no network.

`scripts/e2e_check.py` is the manual counterpart: it drives a running API over HTTP and reports each step of the golden sequence as PASS, FAIL, or PENDING with the task that will deliver it.
