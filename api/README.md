# API

This directory is reserved for the product-facing and internal HTTP API.

Planned responsibilities include:

- project intake and classification endpoints;
- roadmap, material, review, gate, and form endpoints;
- institution review and filing-state endpoints;
- task, notification, and timeline reads;
- internal `recalc-tier` called by the policy update consumer;
- policy administration endpoints used by `web/app/admin/policy/`.

The API imports shared models from `schemas/`. It must not depend on the internal implementation of `workers/policy/`; policy data is accessed through the snapshot contract.

## Current implementation

- `main.py` builds the app, mounts routers, and renders every non-2xx response as the contract error envelope.
- `settings.py` reads the environment variables in contract section 8.
- `deps/demo_auth.py` holds all auth-shaped code (locked decision 2): role headers and the internal-token guard.
- `deps/services.py` is the composition root: store, snapshot service, clock, LLM backend.
- `routers/health.py` — `GET /healthz`.
- `routers/projects.py` — create/read project, S1 intent, S2 channels, classify, tier-choice, gate, timeline.
- `routers/internal.py` — `recalc-tier` and `policy-stale`, guarded by `X-Internal-Token`.

Still to build: materials and uploads, review triggers, findings actions, form preview/freeze, institution console, tasks and notifications.

Routing rules stay the same: routers never mutate a project directly; they call `core.workflow_service.WorkflowService`.
