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

No API implementation exists in this scaffold.
