# Deployment — the parts that need you

Everything in this file is something I cannot or should not do unattended:
an irreversible choice, an interactive login, or a secret value only you should
see. Everything *not* in this file, I am doing myself.

Written for Windows PowerShell. Updated 2026-08-30.

Related: [the design overview](https://claude.ai/code/artifact/746a003c-f4ea-4e16-a5a9-34d8badaac30)
· [manual test guide](manual-test-guide.md)

---

## 0. Already done — do not redo

Checked or performed on 2026-08-30. Listed so you don't repeat any of it.

| | |
|---|---|
| Project | `film-compliance-agent` · number `827776020662` · ACTIVE |
| Billing | `01CE31-A7C20B-F215BA` — attached and open (your free-credit account) |
| APIs enabled | `aiplatform` `firestore` `run` `pubsub` `cloudbuild` `artifactregistry` `secretmanager` `cloudscheduler` `storage` `logging` `monitoring` `cloudtrace` |
| gcloud | 582.0.0, installed at `%LOCALAPPDATA%\Google\Cloud SDK` |
| Emulators | `cloud-firestore-emulator` and `pubsub-emulator` installed |
| Java | present — the Firestore emulator needs it |
| Signed in as | `maxma0223@gmail.com`, ADC refreshed 2026-08-27 |
| Resources | **none yet** — no database, no buckets, no services |

Docker is **not** installed and does not need to be. Cloud Build builds from
source, and the emulators come from gcloud rather than from `docker-compose`.

---

## 1. Make `gcloud` reachable — do this first

`gcloud` is installed but **not on PATH**, which is why `gcloud` alone gives
"not recognized". Everything below assumes you have fixed that.

**For one terminal:**

```powershell
$env:Path = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin;$env:Path"
gcloud version
```

**Permanently, for your user** (reopen the terminal afterwards):

```powershell
$sdk = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin"
$current = [Environment]::GetEnvironmentVariable("Path", "User")
if ($current -notlike "*$sdk*") {
  [Environment]::SetEnvironmentVariable("Path", "$sdk;$current", "User")
  "added"
} else { "already there" }
```

### Keep this project separate from your other work

Your active gcloud config currently points at `gen-lang-client-0338256795`
(*incharacter*). Rather than switching it back and forth, make a named
configuration for this project:

```powershell
gcloud config configurations create film --activate
gcloud config set project film-compliance-agent
gcloud config set account maxma0223@gmail.com
gcloud config set run/region us-east1
```

Switch between them any time:

```powershell
gcloud config configurations activate film       # this project
gcloud config configurations activate default    # incharacter
gcloud config configurations list
```

> **If `gcloud components install` ever fails with exit 1** and a message about
> `FOR /F` and `CLOUDSDK_PYTHON`, this is the fix:
>
> ```powershell
> $env:CLOUDSDK_PYTHON = (gcloud components copy-bundled-python | Select-Object -Last 1)
> ```

---

## 2. Create the Firestore database — the one irreversible step

**A Firestore database's location is fixed at creation and can never be
changed.** Moving later means a new database and a data migration. This is the
only command in this file that you cannot undo, which is why it is yours.

You chose `us-east1`. Before running it, one genuine either/or:

| | `us-east1` | `nam5` |
|---|---|---|
| Kind | single region | US multi-region |
| Availability | one region | survives a region outage |
| Storage cost | baseline | roughly 2× |
| Right for | a judged demo | a service with real users |

**My recommendation: `us-east1`.** Take the multi-region only if this outlives
the demo — and it is equally unrevisitable either way.

```powershell
gcloud firestore databases create `
  --location=us-east1 `
  --type=firestore-native `
  --project=film-compliance-agent
```

Confirm it landed:

```powershell
gcloud firestore databases list --project=film-compliance-agent `
  --format="table(name,locationId,type)"
```

Expect one row, `(default)`, `us-east1`, `FIRESTORE_NATIVE`.

---

## 3. Credentials — only you can do these

I never handle passwords or run interactive logins. These are yours whenever
they come up.

**If application-default credentials expire** (symptom: local Vertex calls start
failing, or `/healthz` reports `llm_available: false` on a machine where it
previously worked):

```powershell
gcloud auth application-default login
```

**If gcloud itself says you are not authenticated:**

```powershell
gcloud auth login
```

**Point application-default credentials at this project** — worth doing once, so
quota and billing land on the right project:

```powershell
gcloud auth application-default set-quota-project film-compliance-agent
```

---

## 4. The demo access code — you choose the value

The deployment is private behind a single shared code rather than Google
sign-in, so anyone you hand it to gets the whole product without you having to
grant their account anything.

**Pick a value and create the secret yourself.** Do not paste it into this chat
or into any file in the repository.

```powershell
# Type your chosen code, press Enter, then Ctrl+Z and Enter to finish.
gcloud secrets create demo-access-code `
  --replication-policy=automatic `
  --project=film-compliance-agent `
  --data-file=-
```

Check it exists without revealing it:

```powershell
gcloud secrets versions list demo-access-code --project=film-compliance-agent
```

To change it later:

```powershell
gcloud secrets versions add demo-access-code `
  --project=film-compliance-agent --data-file=-
```

Something memorable and not guessable is right here. This is a demo gate, not a
password protecting anything real — but it is the only thing between the
internet and an admin role switcher, so do not make it `demo`.

---

## 5. Watching the spend

There is no CLI for the free-credit balance; it is console only:

<https://console.cloud.google.com/billing/01CE31-A7C20B-F215BA>

Everything in the design scales to zero. The only charges that accrue with no
traffic are Artifact Registry image storage and the Firestore database existing
— cents per month at this size. The one that could actually bite is Vertex, so
it is worth a budget alert:

<https://console.cloud.google.com/billing/01CE31-A7C20B-F215BA/budgets>

Set it to whatever number would make you want to know. This is a console click,
not a command.

---

## 6. When I ask you to look at something

Two checks I cannot do for you, both after the first deploy:

1. **Open the deployed URL and confirm the gate page reads sensibly** to someone
   who has never seen the product. I can assert it returns the right status
   code; I cannot judge whether it reads as deliberate rather than broken.
2. **Walk the nine scenarios** in [`manual-test-guide.md`](manual-test-guide.md)
   against the deployed URL instead of localhost. The expectations are identical
   — the point is confirming that nothing behaves differently once state lives in
   Firestore rather than in memory.

---

## 7. What I am doing without you

For context, so you know what is not waiting on this file:

| Phase | Work | Needs you? |
|---|---|---|
| 5a | `store/firestore.py` — the 14 storage ports, verified against the local emulator | no |
| 5b | GCS blob store and signed upload URLs | no |
| 5c | The access gate middleware, and moving the policy admin routes behind the internal token | only §4 |
| 5d | Terraform, Dockerfiles, Cloud Build, first deploy | needs §2 |
| 5e | Snapshot seeding job; the fictional institution registry | no |
| 5f | Pub/Sub jobs, the push worker, the policy schedule | no |

Real identity (Identity Platform) is **cut**, not deferred — the access code
covers the demo, and everything auth-shaped stays contained in
`api/deps/demo_auth.py` for whenever it is genuinely needed.

---

## The short version

If you only do two things:

```powershell
# 1. gcloud on PATH, permanently
$sdk = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin"
$current = [Environment]::GetEnvironmentVariable("Path", "User")
if ($current -notlike "*$sdk*") { [Environment]::SetEnvironmentVariable("Path", "$sdk;$current", "User") }

# 2. the database (reopen your terminal first)
gcloud firestore databases create --location=us-east1 --type=firestore-native --project=film-compliance-agent
```

Everything else in this file can wait until the phase that needs it.
