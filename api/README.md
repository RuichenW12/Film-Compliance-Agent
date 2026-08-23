# API

This directory contains the product-facing and internal HTTP API boundary.

Planned product-workstream responsibilities include:

- project intake and classification endpoints;
- roadmap, material, review, gate, and form endpoints;
- institution review and filing-state endpoints;
- task, notification, and timeline reads;
- internal `recalc-tier` called by the policy update consumer;
- policy administration endpoints used by `web/app/admin/policy/`.

The API imports shared models from `schemas/`. It must not depend on the internal implementation of `workers/policy/`; policy data is accessed through the snapshot contract.

## Gate 3 local policy API

Gate 3 implements the policy administration endpoints needed by Richard's local UI:

- launch the deterministic `fixture://policy-v2` refresh and read run status;
- list and review proposals;
- publish or discard a proposal;
- list published snapshot history.

Run the API from the repository root:

```bash
.venv/bin/uvicorn api.main:app --reload --port 8000
```

The local demo uses the `X-Mock-Role: admin` header. Its repository is process-local and resets to the seed v1 snapshot whenever the API restarts. This is deliberate fixture behavior, not production authentication or persistence.
