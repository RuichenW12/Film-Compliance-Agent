# Tests

This directory is reserved for verification shared across the product and policy workstreams.

| Path | Purpose |
|---|---|
| [`contract/`](contract/README.md) | A/B interface and event compatibility |
| [`fixtures/policy/`](fixtures/policy/README.md) | Deterministic policy source and update scenarios |
| [`golden/`](golden/README.md) | Expert-reviewed product and compliance examples |

Tests should distinguish local fixture behavior from live cloud verification. Passing a fixture or emulator test must not be reported as proof that a deployed external integration works.

No test implementation exists in this scaffold.
