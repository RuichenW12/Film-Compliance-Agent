# Web

Next.js (App Router) UI for the whole product: the creator workflow and the policy administration console.

Locked decisions that shape this app:

- **English UI**, with Chinese legal terms kept and glossed, e.g. "备案公示 (Registration Publicity)". Sample scripts and materials stay Chinese.
- **No real auth.** A role switcher in the top bar writes the role to `localStorage`; every request sends `X-Mock-Role` and `X-User-Id`. All of it is isolated in [`lib/demoAuth.ts`](lib/demoAuth.ts) so a real identity provider can replace it.

## Layout

| Path | Owner | Purpose |
|---|---|---|
| `app/wizard` | Maxine | S1/S2 intake and the classification card |
| `app/collection` | Maxine | Uploads, material cards, roadmap, and the C1-a pre-check |
| `app/institution` | Maxine | Demo registry, submission, the institution's decision, and filing |
| `app/dashboard` | Maxine | Project state, gate gaps, notifications, and the audit timeline |
| `app/admin/policy` | Richard | Policy proposals, diff view, publish gate |
| `components/policy/` | Richard | Policy administration components |
| `lib/api.ts` | Maxine | Product API client, sends the demo role headers |
| `lib/policy-api.ts` | Richard | Typed policy administration client |
| `lib/enums.ts` | shared | Mirror of `schemas/enums.py`; change both together |
| `locales/` | shared | Message keys returned by the API; whoever adds a key registers it here |

## Local run

```bash
npm --prefix web install
npm --prefix web run dev     # http://localhost:3000, expects the API on :8080
npm --prefix web test        # vitest
```

Both clients default to `http://localhost:8080`, the API port in contract section 8. `NEXT_PUBLIC_API_BASE` overrides it for the product routes and `NEXT_PUBLIC_POLICY_API_BASE_URL` for the policy routes.

The policy console is backed by deterministic fixture data, mock authorization, and process-local API state. It is an administration demo, not a deployed policy service.
