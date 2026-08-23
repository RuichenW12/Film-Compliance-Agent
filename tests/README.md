# Tests

This directory is reserved for verification shared across the product and policy workstreams.

| Path | Purpose |
|---|---|
| [`contract/`](contract/README.md) | A/B interface and event compatibility |
| [`fixtures/policy/`](fixtures/policy/README.md) | Deterministic policy source and update scenarios |
| [`golden/`](golden/README.md) | Expert-reviewed product and compliance examples |
| `policy/` | Pure, module, and offline end-to-end tests for the policy loop |

Tests should distinguish local fixture behavior from live cloud verification. Passing a fixture or emulator test must not be reported as proof that a deployed external integration works.

Gate 1 contract tests and Gate 2 local policy-loop tests are implemented. They do not prove live website, Gemini, GCP, API, or browser behavior.
