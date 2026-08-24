# Tests

This directory is reserved for verification shared across the product and policy workstreams.

| Path | Purpose |
|---|---|
| [`contract/`](contract/README.md) | A/B interface and event compatibility |
| [`fixtures/policy/`](fixtures/policy/README.md) | Deterministic policy source and update scenarios |
| [`golden/`](golden/README.md) | Expert-reviewed product and compliance examples |
| `policy/` | Pure, module, and offline end-to-end tests for the policy loop |

Tests should distinguish local fixture behavior from live cloud verification. Passing a fixture or emulator test must not be reported as proof that a deployed external integration works.

Gate 1 contract tests, Gate 2 local policy-loop tests, Gate 3 API/UI tests, and Gate 4 adapter/orchestration tests are implemented. Run them from the repository root:

```bash
.venv/bin/pytest -q
npm --prefix web test
```

Gate 4 also provides two explicit smoke modes:

```bash
.venv/bin/python scripts/policy_gate4_smoke.py --source
.venv/bin/python scripts/policy_gate4_smoke.py --cloud
```

The source command uses the real public NRTA page with temporary file and in-memory state. The cloud command needs the cloud extra, required environment settings, credentials, a named Google Cloud project, and an explicitly designated smoke Pub/Sub topic. Its per-adapter statuses are `PASS`, `FAIL`, or `SKIP`; only a real named-project run with every external adapter at `PASS` is cloud evidence.

The Gate 3 browser acceptance exercises the local FastAPI and Next.js flow against `fixture://policy-v2`. It proves only that the deterministic local review-and-publish path works. Gate 4 unit tests use injected clients and likewise do not prove production authentication, durable cloud storage, model quality, GCP deployment, or external event delivery.
