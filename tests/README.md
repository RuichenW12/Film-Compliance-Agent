# Tests

This directory is reserved for verification shared across the product and policy workstreams.

| Path | Purpose |
|---|---|
| [`contract/`](contract/README.md) | A/B interface and event compatibility |
| [`fixtures/policy/`](fixtures/policy/README.md) | Deterministic policy source and update scenarios |
| [`golden/`](golden/README.md) | Expert-reviewed product and compliance examples |
| `policy/` | Pure, module, and offline end-to-end tests for the policy loop |

Tests should distinguish local fixture behavior from live cloud verification. Passing a fixture or emulator test must not be reported as proof that a deployed external integration works.

Gate 1 contract tests, Gate 2 local policy-loop tests, and Gate 3 API/UI tests are implemented. Run them from the repository root:

```bash
.venv/bin/pytest -q
npm --prefix web test
```

The Gate 3 browser acceptance exercises the local FastAPI and Next.js flow against `fixture://policy-v2`. It proves only that the deterministic local review-and-publish path works; it does not prove live website access, model output, production authentication, durable storage, GCP deployment, or external event delivery.
