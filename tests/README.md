# Tests

This directory is reserved for verification shared across the product and policy workstreams.

| Path | Purpose |
|---|---|
| [`contract/`](contract/README.md) | A/B interface and event compatibility |
| [`fixtures/policy/`](fixtures/policy/README.md) | Deterministic policy source and update scenarios |
| [`golden/`](golden/README.md) | Expert-reviewed product and compliance examples |
| `policy/` | Pure, module, and offline end-to-end tests for the policy loop |

Tests should distinguish local fixture behavior from live cloud verification. Passing a fixture or emulator test must not be reported as proof that a deployed external integration works.

## Current suites

| File | Covers |
|---|---|
| `conftest.py` | Fixed clock, in-memory stores, seed snapshot, and the three fixed intent profiles |
| `test_snapshot_service.py` | Snapshot reads, clause lookup, pack normalization (T-A0) |
| `test_guards.py` | State machine transitions, audit entries, and every D3 gate branch (T-A1) |
| `test_classify.py` | D1a/D1b/D1c chain, prompt-injection resistance, quote verification (T-A2) |
| `test_api_intake.py` | Intake and classification routes, role checks, error envelope, internal recalc-tier |
| `test_app_policy_snapshot_bridge.py` | Local Gate 5-a admin publish → product recalc snapshot visibility |
| `contract/test_policy_contract.py` | Shared policy contracts and the `policy.updated` fixture |
| `policy/` | Gate 2 offline loop, Gate 3 administration API, and Gate 4 adapter/orchestration tests |

Run everything from the repository root:

```bash
python -m pytest          # product and policy Python suites
npm --prefix web test     # policy administration UI (vitest)
```

Gate 4 also provides two explicit smoke modes:

```bash
.venv/bin/python scripts/policy_gate4_smoke.py --source
.venv/bin/python scripts/policy_gate4_smoke.py --cloud
```

The source command uses the real public NRTA page with temporary file and in-memory state. The cloud command needs the cloud extra, required environment settings, credentials, a named Google Cloud project, and an explicitly designated smoke Pub/Sub topic. Its per-adapter statuses are `PASS`, `FAIL`, or `SKIP`; only a real named-project run with every external adapter at `PASS` is cloud evidence.

The Python suite runs with no credentials, no emulator, and no network. `scripts/e2e_check.py` is the manual counterpart: it drives a running API over HTTP and reports each step of the golden sequence as PASS, FAIL, or PENDING with the task that will deliver it.

`test_app_policy_snapshot_bridge.py` is the local Gate 5-a closure: it publishes
v2 through the admin API and recalculates a provisional v1 project through the
internal API against that same v2 snapshot. It is not cloud or event-fan-out
evidence.

Scope limits worth stating plainly: the Gate 3 browser acceptance exercises the deterministic local review-and-publish path against `fixture://policy-v2`. It proves only that local path, not production authentication, durable cloud storage, model quality, GCP deployment, or external event delivery. Gate 4 unit tests use injected clients, and the product suite likewise proves workflow logic rather than a real Gemini call.
