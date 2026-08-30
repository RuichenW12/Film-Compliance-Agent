# API

This directory contains the product-facing and internal HTTP API boundary.

Planned product-workstream responsibilities include:

- project intake and classification endpoints;
- roadmap, material, review, gate, and form endpoints;
- institution review and filing-state endpoints;
- task, notification, and timeline reads;
- internal `recalc-tier` called by the policy update consumer;
- policy administration endpoints used by `web/app/admin/policy/`.

Product routers and workflow logic import policy models and reads only through
the shared `schemas/` snapshot contract. The top-level application composition
may assemble a `workers/policy/` adapter, but that storage dependency does not
cross into product logic.

## Current implementation

Product workstream (A):

- `main.py` builds the app, mounts every router, and renders each non-2xx response as the contract error envelope.
- `settings.py` reads the environment variables in contract section 8.
- `deps/demo_auth.py` holds the product side of the demo auth (locked decision 2): role headers and the internal-token guard.
- `deps/services.py` is the product composition root: store, snapshot service, clock, LLM backend.
- `routers/health.py` — `GET /health`, and `GET /healthz` as an alias. Google's
  front end intercepts `/healthz` on Cloud Run, so a deployed check must use
  `/health`.
- `routers/projects.py` — create/read project, S1 intent, S2 channels, classify, tier-choice, gate, timeline, roadmap preview and confirm ([D-017](../docs/decisions.md#d-017)).
- `routers/internal.py` — `recalc-tier` and `policy-stale`, guarded by `X-Internal-Token`. Both write the creator's notification as part of the same call ([D-014](../docs/decisions.md#d-014)).
- `routers/notifications.py` — `GET /v1/notifications` and `POST /v1/notifications/{nid}/read`, each caller scoped to their own inbox.

- `routers/assets.py` — upload tickets, `PUT /v1/uploads/{tid}`, asset listing and content reads ([D-015](../docs/decisions.md#d-015)).

- `routers/materials.py` — collection cards from `p5_form_templates`: list, attach, validate, waive ([D-016](../docs/decisions.md#d-016)).

- `routers/assets.py` also serves `extract-facts` and the project fact list.

- `routers/review.py` — C1-a pre-check, the project finding list, and finding actions ([D-019](../docs/decisions.md#d-019)).

- `routers/forms.py` — gate passage, form preview, field confirmation, and freeze ([D-022](../docs/decisions.md#d-022)).

- `routers/institution.py` — the demo registry, submission, the institution's decision, and filing ([D-023](../docs/decisions.md#d-023)).

- `routers/teaser.py` — the Veo teaser, behind `FLAG_VEO_TEASER`.

Still to build: running the async jobs behind the task list out of process.

Policy workstream (B):

- `routers/admin_policy.py` — `/v1/admin/policy`: launch the deterministic `fixture://policy-v2` refresh, read run status, list and review proposals, publish or discard, and list snapshot history.
- `deps/policy.py` builds the process-local policy state during lifespan startup and guards the routes with `X-Mock-Role: admin`.
- `errors.py` renders `PolicyApiError` into the same error envelope.

Run the whole API from the repository root:

```bash
uvicorn api.main:app --reload --port 8080
```

The policy repository is process-local and resets to the seed v1 snapshot on every restart. That is deliberate fixture behavior, not production authentication or persistence.

In the unified app, lifespan startup creates the policy state first and builds
the default `AppContext` with a repository-backed `SnapshotService`. Supplying
an explicit `AppContext` keeps that context unchanged; standalone composition
continues to default to `FileSnapshotService`.

Routing rule for both sides: routers never mutate state directly. Product routes call `core.workflow_service.WorkflowService`; policy routes call the workers in `workers/policy/`.
