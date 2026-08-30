# Deployment

How the deployed system is put together, how to build and ship a change, and
the handful of things that behave differently in the cloud than on a laptop.

Written for anyone touching this repository — human or agent — not only whoever
set it up. If you are the person who has to run a step by hand, the shorter
[`deploy-manual-steps.md`](deploy-manual-steps.md) is the checklist; this file
is the reference behind it.

Everything here was verified against the running system on 2026-08-30. Where
something is unfinished it says so rather than describing an intention.

---

## 1. What is running

**Use this URL. It is the product.**

```
https://web-827776020662.us-east1.run.app
```

Sign in with any Google account. No allow-list, no shared password.

| | |
|---|---|
| GCP project | `film-compliance-agent` · number `827776020662` |
| Region | `us-east1` (Firestore's location is **permanent**) |
| Firestore | `(default)`, Native mode; provisioned but not used by the current recording API |
| Image registry | `us-east1-docker.pkg.dev/film-compliance-agent/app` |

Two Cloud Run services, both scaling to zero:

| Service | Purpose | URL |
|---|---|---|
| `web` | Next.js. **What people open.** | `https://web-827776020662.us-east1.run.app` |
| `api` | FastAPI. Reached by `web`, not by browsers. | `https://api-827776020662.us-east1.run.app` |

The API also serves `/privacy` and `/terms`, which the OAuth consent screen
links to — so it stays browser-reachable even though the app does not need it
to be.

### Environment

Set on the service, not in the image. Nothing here is secret.

**`api`**

| Variable | Value |
|---|---|
| `GOOGLE_CLOUD_PROJECT` | `film-compliance-agent` |
| `REGION` | `us-east1` |
| `VERTEX_MODEL_GEMINI` | `gemini-2.5-flash` |
| `STORE_BACKEND` | `memory` |

**`web`**

| Variable | Value |
|---|---|
| `API_UPSTREAM` | `https://api-827776020662.us-east1.run.app` |
| `IAP_AUDIENCE` | `827776020662-ov9ncgq0skiqdk8rfkp1jh0pumv6jdpl.apps.googleusercontent.com` |

`IAP_AUDIENCE` is an OAuth **client ID**, not a secret — it appears in every
sign-in redirect. The matching *secret* lives only in IAP's configuration and
must never enter this repository.

---

## 2. How a browser request reaches the database

```
browser ──▶ IAP ──▶ web (Next.js)
                     │  server-side, with an identity token
                     ▼
                    IAP ──▶ api (FastAPI) ──▶ process-local stores
                                           └▶ Vertex AI
```

**The browser only ever talks to the `web` origin.** That is the single most
important fact about this deployment, and the reason for the piece of code most
likely to look redundant.

### Why the API is not called directly

A browser on the `web` host calling the `api` host fails twice over:

- **CORS.** `WEB_ORIGINS` in `api/main.py` lists `localhost:3000` only, so the
  deployed origin is refused.
- **IAP.** Its session cookie is scoped to one service. A page served from
  `web` calling `api` arrives without `api`'s cookie and is answered with a
  Google sign-in redirect *in the middle of a `fetch`* — which surfaces as an
  opaque network error, not a login prompt.

So `web/app/v1/[...path]/route.ts` relays `/v1/*` server-side. One origin, one
IAP session, no CORS.

### Why it is a route handler and not a rewrite

A `next.config` rewrite is less code and cannot work here: it forwards the
request untouched, and IAP rejects a request carrying no credential. The
handler exists to mint one, from the Cloud Run metadata server.

**The audience must be the IAP OAuth client ID, not the service URL.** A token
minted for `https://api-…run.app` is refused. This is the detail that costs an
afternoon if you get it wrong, and the handler logs `UPSTREAM_AUTH_FAILED`
rather than passing a sign-in redirect back to the browser, so the failure
names itself.

### Local development is unaffected

`NEXT_PUBLIC_API_BASE` is set locally, so the browser calls the API directly
and CORS allows `localhost:3000`. The proxy path is never taken. Nothing about
running the product on your machine changed — see
[`manual-test-guide.md`](manual-test-guide.md).

---

## 3. Things that behave differently in the cloud

Read this section before debugging anything. Each item cost real time to find.

### `/healthz` does not exist in the cloud

Google's front end answers `/healthz` with a **404 of its own**; the request
never reaches the container. Verified: `/zzz-not-a-route` reaches the app and
uvicorn logs its 404, while `/healthz` appears in no log line at all —
unauthenticated, through the proxy, and signed in through a browser.

**Use `/health`.** Both paths are served and return the same payload;
only one survives deployment. `scripts/e2e_check.py` uses `/health` for exactly
this reason.

### `PORT` must be honoured

Cloud Run supplies `PORT` and does not promise 8080 or 3000. A container
listening on a fixed port is marked unhealthy and never receives traffic. Both
Dockerfiles read it.

### The recording API is intentionally ephemeral

The current API uses `STORE_BACKEND=memory`. The upload route accepts screenplay
files up to 5 MiB, but their bytes, normalized text, review sessions, and
generated artifacts live only in the API process. Scale-to-zero, restart, or
redeploy can remove them. A Firestore database and adapter exist, but the new
ReviewSession aggregate has not been accepted as durably persisted there, so
the recording deployment makes no persistence claim.

### Console status is not evidence

Both the Cloud Run Security tab and the IAP page reported IAP *enabled* and
*Ready* for hours while the service returned 502, because the OAuth client was
unset and no console page exposes that field. Trust a request, not a checkbox.

### There is no `web/public`

The app's favicon is a route (`/icon.svg`), not a static file, so
`infra/web.Dockerfile` copies no `public/`. **Add the copy back the moment a
static asset appears** — a missing `public/` is a silent 404, not a build
failure.

---

## 4. Shipping a change

Prerequisites: `gcloud` authenticated on the `film-compliance-agent` project.
See [`deploy-manual-steps.md` §1](deploy-manual-steps.md).

Always run the suite first — `CLAUDE.md` requires green before a commit:

```powershell
python -m pytest
```

### API

```powershell
$IMG = "us-east1-docker.pkg.dev/film-compliance-agent/app/api:TAG"
gcloud builds submit --config infra/cloudbuild.api.yaml `
  --substitutions="_IMAGE=$IMG" --region=us-east1 --project=film-compliance-agent
gcloud run deploy api --image=$IMG --region=us-east1 --project=film-compliance-agent
```

### Web

```powershell
$IMG = "us-east1-docker.pkg.dev/film-compliance-agent/app/web:TAG"
gcloud builds submit --config infra/cloudbuild.web.yaml `
  --substitutions="_IMAGE=$IMG" --region=us-east1 --project=film-compliance-agent
gcloud run deploy web --image=$IMG --region=us-east1 --project=film-compliance-agent
```

Use a real tag (`api:add-scene-list`), not `latest`. Rolling back is then
`gcloud run deploy` with the previous tag, and the revision list stays readable.

Both builds take their context from the repository root; the Dockerfiles live
in `infra/` and are named with `-f`. `.gcloudignore` keeps the upload at ~10 MB
instead of 244 MB — it **replaces** `.gitignore` for uploads, so anything that
must stay out has to be named there even if git already ignores it.

### Rolling back

```powershell
gcloud run revisions list --service=api --region=us-east1 --project=film-compliance-agent
gcloud run services update-traffic api --to-revisions=REVISION=100 `
  --region=us-east1 --project=film-compliance-agent
```

A revision that fails to start never receives traffic — Cloud Run keeps the
previous one serving. That is not a reason to skip checking after a deploy.

---

## 5. Storage

Three backends behind the fourteen ports in `core/repositories.py`, chosen by
`STORE_BACKEND`:

| Value | Use | Survives |
|---|---|---|
| `memory` | tests, a throwaway run | nothing |
| `sqlite` | a local demo | a restart, not a container |
| `firestore` | durable cloud validation after the flow is accepted | configured Firestore data |

An unknown value raises rather than falling back — silently running in memory
when someone asked for durability is the surprise that error exists to prevent.
The present production choice is deliberately `memory` so the upload-first demo
can be recorded without claiming that the new aggregate is Firestore-complete.

**A change to any store must pass `tests/test_store_conformance.py` against all
three.** That file is what makes the ports real; a port with one implementation
is an untested interface.

Firestore does not run there by default — it needs a database. Two ways to
switch it on:

```powershell
# real database, namespaced per test and cleaned up afterwards
$env:FIRESTORE_TEST_PROJECT = "film-compliance-agent"
python -m pytest tests/test_store_conformance.py

# or an emulator, which needs a working JRE
gcloud emulators firestore start --host-port=localhost:8791
$env:FIRESTORE_EMULATOR_HOST = "localhost:8791"
```

Expect **77 passed**: 25 conformance tests across three backends, plus two that
are not parametrised. Against the real database each test gets its own
collection prefix and deletes only its own namespace, so it cannot touch
product data.

> The emulator needs Java 8+. On the machine this was built on, the Oracle
> `javapath` shims exist but the runtime behind them is gone — `java -version`
> exits 9 printing nothing, and gcloud reports "unable to execute the java that
> was found on your PATH". Install a real JRE or use `FIRESTORE_TEST_PROJECT`.

---

## 6. Access

IAP in front of both services, open to any Google account. No application code
is involved — `api/deps/demo_auth.py` is untouched, so the role switcher
behaves exactly as it does locally, behind the sign-in.

Five things are required, and four of them look sufficient while the service
still returns 502:

1. `--iap` on the service;
2. `roles/run.invoker` for the IAP service agent;
3. `roles/iap.httpsResourceAccessor` for `allAuthenticatedUsers`;
4. the Cloud Run invoker IAM check left **on**;
5. **a custom OAuth client given to IAP via `gcloud iap settings set`** — no
   console page exposes this, and it is required for any project outside an
   Organization.

`web`'s service account additionally holds `roles/iap.httpsResourceAccessor`
on `api`, which is what lets the proxy through.

This is demo access control, not authentication. Anyone signed in can switch to
the institution or admin role. Real identity is deliberately not built: it is
contained in one file for whenever it is needed.

---

## 7. Verifying a deployment

```powershell
python scripts/e2e_check.py --base http://localhost:8080
```

Against the deployed API this needs credentials the script does not carry, so
the practical check is a browser: open the web URL, sign in, upload a script,
confirm the editable details, and reach Review results. That verifies the
browser, IAP, proxy, API, and configured Vertex path for that request. It does
not verify durable persistence or the separate policy-refresh cloud loop.

The deterministic upload-first browser suite is the repeatable local
acceptance path. The older scenarios in
[`manual-test-guide.md`](manual-test-guide.md) exercise the retained multi-page
workflow; they are useful regression checks but are not the current recording
script.

---

## 8. Troubleshooting

| Symptom | Cause |
|---|---|
| `404`, empty body, on a path that works locally | `/healthz` — use `/health` |
| `502` with `x-goog-iap-generated-response: true` | IAP has no usable OAuth client |
| `302` to `accounts.google.com` from a `fetch` | a browser is calling the API host directly; it must go through the web origin |
| `UPSTREAM_AUTH_FAILED` from the proxy | `IAP_AUDIENCE` wrong, or `web`'s service account lacks access to `api` |
| Container failed to start after a config change | usually a new env value the deployed image predates — read the revision's logs, the error names it |
| CORS error in the console | something is calling the API host cross-origin; route it through `/v1/*` |

Logs for a specific revision:

```powershell
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.revision_name="REVISION"' `
  --project=film-compliance-agent --limit=20 --format="value(textPayload)"
```

---

## 9. Not done yet

Honest list. None of it is blocking a demo.

| | Consequence today |
|---|---|
| **Durable ReviewSession persistence** | scale-to-zero, restart, or API redeploy can remove current demo sessions and downloads |
| **Cloud Storage for uploads** | screenplay upload is capped at 5 MiB; no finished-film upload |
| **Pub/Sub jobs and a push worker** | the API runs jobs inline; a long review could hit the request timeout |
| **Cloud Scheduler for the policy refresh** | the policy loop does not run on its own in the cloud |
| **Snapshot seeding into Firestore** | the API still reads the seed YAML from disk at startup |
| **Institution registry** | empty; fictional demo companies are agreed but not yet seeded (Q-3) |
| **Terraform** | every resource here was created by a command, not a definition |
| **Real identity** | deliberately cut — the access gate is IAP, not the app |

---

## 10. If you are changing product code

Nothing in this deployment requires you to write cloud-specific code, and none
of it should leak into a router or a component. Four rules cover it:

1. **Talk to the API through `/v1/*` on the app's own origin.** Never build a
   URL pointing at the API host in browser code.
2. **Go through the ports.** `core/repositories.py`, not a storage client. If
   you add a method to a port, add it to all three backends and to the
   conformance suite.
3. **Health checks use `/health`.**
4. **No secrets in the repository.** Configuration is set on the service;
   secrets live in Secret Manager or IAP's own configuration.

Everything else — the state machine, evidence rules, the `待补充` discipline in
[`CLAUDE.md`](../CLAUDE.md) — is unchanged by deployment and still binding.
