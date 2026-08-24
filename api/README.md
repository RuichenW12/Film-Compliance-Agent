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

## Current implementation

Product workstream (A):

- `main.py` builds the app, mounts every router, and renders each non-2xx response as the contract error envelope.
- `settings.py` reads the environment variables in contract section 8.
- `deps/demo_auth.py` holds the product side of the demo auth (locked decision 2): role headers and the internal-token guard.
- `deps/services.py` is the product composition root: store, snapshot service, clock, LLM backend.
- `routers/health.py` — `GET /healthz`.
- `routers/projects.py` — create/read project, S1 intent, S2 channels, classify, tier-choice, gate, timeline.
- `routers/internal.py` — `recalc-tier` and `policy-stale`, guarded by `X-Internal-Token`.

Still to build: materials and uploads, review triggers, findings actions, form preview/freeze, institution console, tasks and notifications.

Policy workstream (B):

- `routes/admin_policy.py` — `/v1/admin/policy`: launch the deterministic `fixture://policy-v2` refresh, read run status, list and review proposals, publish or discard, and list snapshot history.
- `deps/policy.py` builds the process-local policy state during lifespan startup and guards the routes with `X-Mock-Role: admin`.
- `errors.py` renders `PolicyApiError` into the same error envelope.

Run the whole API from the repository root:

```bash
uvicorn api.main:app --reload --port 8080
```

The policy repository is process-local and resets to the seed v1 snapshot on every restart. That is deliberate fixture behavior, not production authentication or persistence.

Routing rule for both sides: routers never mutate state directly. Product routes call `core.workflow_service.WorkflowService`; policy routes call the workers in `workers/policy/`.
