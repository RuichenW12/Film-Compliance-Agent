# Web

Next.js (App Router) UI for the whole product: the creator workflow and the policy administration console.

Locked decisions that shape this app:

- **English UI**, with Chinese legal terms kept and glossed, e.g. "备案公示 (Registration Publicity)". Sample scripts and materials stay Chinese.
- **No real application identity.** A role switcher in the top bar writes the role to `localStorage`; every request sends `X-Mock-Role` and `X-User-Id`. All of it is isolated in [`lib/demoAuth.ts`](lib/demoAuth.ts) so a real identity provider can replace it. The deployed services sit behind Google IAP, but IAP is only the outer access gate and does not replace the in-app demo roles.

## Layout

| Path | Owner | Purpose |
|---|---|---|
| `app/page.tsx` | Maxine | Main upload-first creator review: Upload, Confirm details, Review results |
| `app/v1/[...path]` | Maxine | Same-origin Cloud Run proxy from the browser-facing web service to the private API |
| `app/wizard` | Maxine | Legacy S1/S2 intake and classification route, retained outside the recording path |
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

The upload-first demo can use configured Vertex or the fixture-bounded local adapter in `scripts/review_demo_server.py`. The policy console remains backed by deterministic fixture data, mock authorization, and process-local API state; it is an administration demo, not a claim that the full policy loop is deployed and scheduled.
