# Web

Next.js (App Router) UI for the compliance workflow.

Locked decisions that shape this app:

- **English UI**, with Chinese legal terms kept and glossed, e.g. "备案公示 (Registration Publicity)". Sample scripts and materials stay Chinese.
- **No real auth.** A role switcher in the top bar writes the role to `localStorage`; every request sends `X-Mock-Role` and `X-User-Id`. All of it is isolated in [`lib/demoAuth.ts`](lib/demoAuth.ts) so a real identity provider can replace it.

## Layout

| Path | Owner | Purpose |
|---|---|---|
| `app/wizard` | Maxine | S1/S2 intake and the classification card |
| `app/dashboard` | Maxine | Project state, gate gaps, and the audit timeline |
| `app/admin` | Maxine | Administration shell |
| `app/admin/policy` | Richard | Policy proposals, diff view, publish gate |
| `lib/enums.ts` | shared | Mirror of `schemas/enums.py`; change both together |
| `locales/` | shared | Message keys returned by the API; whoever adds a key registers it here |

## Local run

```bash
cd web
npm install
npm run dev          # http://localhost:3000, expects the API on :8080
```

Set `NEXT_PUBLIC_API_BASE` to point at a deployed API instead.
