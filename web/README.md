# Web

This directory contains the Next.js App Router UI.

Planned UI areas include the creator workflow, institution review console, project timeline, role switcher, and administration pages. Maxine owns the product shell and non-policy screens. Richard owns the policy administration area under [`app/admin/policy/`](app/admin/policy/README.md), including its API integration and interactions.

Shared API shapes come from `schemas/`; the web application must not create independent policy or workflow contracts.

## Gate 3 local policy UI

Install dependencies and start the development server from the repository root:

```bash
npm --prefix web install
npm --prefix web run dev
```

The policy client defaults to `http://127.0.0.1:8000`. Set `NEXT_PUBLIC_POLICY_API_BASE_URL` to use a different local API origin. The implemented pages are documented in [`app/admin/policy/`](app/admin/policy/README.md).

The current UI is intentionally narrow: it is an administration demo backed by deterministic fixture data, mock authorization, and process-local API state. It is not the creator workflow or a deployed policy service.
