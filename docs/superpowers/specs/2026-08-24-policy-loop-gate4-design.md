# Policy Loop Gate 4 Design

Date: 2026-08-24

Status: approved for implementation

Owner: Richard

## 1. Purpose

Gate 4 replaces the deterministic Gate 2 adapters with real HTTP and Google Cloud adapters while preserving the policy module behavior already exercised by Gates 1–3.

The implementation must keep one refresh, publication, and outbox path. Local and cloud executions vary only through adapters at explicit seams; Gate 4 must not copy those workflows into a second cloud-specific implementation.

Gate 4 has two distinct completion labels:

- **Gate 4 implementation complete** means the adapters, automated tests, packaging checks, and real NRTA HTTP smoke are complete.
- **Gate 4 passed** additionally requires a successful full-cloud smoke using a real configured Google Cloud project.

If credentials or cloud resources are unavailable, the full-cloud smoke is reported as `SKIP`, never as `PASS`.

## 2. Starting point

Gate 3 provides:

- frozen `PolicySnapshot`, `PolicyProposal`, `PolicyUpdatedEvent`, outbox, and recalc-tier contracts;
- deterministic refresh, proposal, publication, outbox, and consumer modules;
- in-memory/file/fake adapters and offline acceptance tests;
- local FastAPI policy administration endpoints;
- a local Next.js policy administration UI.

The local API and UI remain the default development path. Gate 4 adds a cloud assembly but does not silently switch Gate 3 to cloud state.

## 3. Scope

### 3.1 Included

Gate 4 implements:

1. A real HTTPS source adapter for the NRTA policy page.
2. A GCS blob adapter for raw HTML, normalized text, diffs, and future pack blobs.
3. A Firestore repository for Richard-owned policy collections.
4. A Gemini proposal adapter using Vertex AI structured output.
5. A Pub/Sub event publisher for validated `policy.updated` events.
6. A versioned real-source configuration and proposal prompt.
7. A cloud runtime assembly that injects these adapters into existing modules.
8. Offline adapter tests, optional emulator checks, a real-source smoke, and a credential-gated full-cloud smoke.

### 3.2 Richard-owned Firestore collections

Gate 4 owns only:

- `policy_source_states/{source_id}`;
- `policy_runs/{run_id}`;
- `policy_proposals/{proposal_id}`;
- `policy_snapshots/{version}`;
- `policy_outbox/{outbox_id}`.

The Gate 4 adapter does not read or write Maxine's projects, notifications, timelines, forms, materials, or registration data.

### 3.3 Excluded

The following remain Gate 5 work:

- Cloud Run service and job definitions;
- Cloud Scheduler wiring;
- Pub/Sub push-consumer route and deployment;
- the real A-line `recalc-tier` call;
- Maxine's project, notification, and timeline persistence;
- production authentication and authorization;
- service accounts, IAM bindings, and deployed environment provisioning;
- changes to the policy administration UI.

## 4. Alternatives considered

### 4.1 Selected: shared modules plus injected adapters

Existing policy modules retain their behavior. Narrow repository interfaces replace concrete `InMemoryPolicyRepository` annotations where variation is now real. Local and cloud adapters satisfy the same interfaces.

This provides the highest leverage and locality: transaction, SDK, serialization, and retry details live inside the cloud adapters, while refresh and publication rules remain in one implementation.

### 4.2 Rejected: backend conditionals in existing classes

Adding `if backend == "cloud"` branches would mix policy behavior with SDK construction, credentials, retries, and storage serialization. It would also make local tests dependent on cloud concerns.

### 4.3 Rejected: duplicate cloud workflow

A separate `cloud_refresh` or `cloud_publish` path would initially reduce refactoring, but it would allow local and cloud behavior to drift. Publication atomicity and last-known-good protection must not be implemented twice.

## 5. Module architecture

### 5.1 Repository interfaces

The repository seam is split by caller needs:

- `RefreshRepository` supports run and source-state operations plus atomic refresh completion.
- `PublicationRepository` supports proposal/snapshot reads and atomic publish/discard operations.
- `OutboxRepository` supports pending selection and sent-state updates.
- `PolicyReadRepository` supports the administration reads needed by Gate 3.
- `PolicyRepository` composes the four interfaces for runtime assembly and typing convenience.

`InMemoryPolicyRepository` and `FirestorePolicyRepository` both satisfy these interfaces. Policy modules accept the narrowest interface they require.

This is a real seam because two adapters now exist. No cloud SDK type crosses it.

### 5.2 Run IDs

`PolicyRunLauncher` accepts an injectable run-ID factory:

- local assembly retains deterministic `run_001`, `run_002`, and so on;
- cloud assembly uses collision-resistant UUID-based IDs.

A run document is created before refresh execution begins. Failure to create a run is a launch failure and must not start refresh work.

### 5.3 Cloud runtime

`build_cloud_policy_runtime()` constructs SDK clients from explicit configuration, creates the adapters once, imports the seed snapshot only when the snapshot collection is empty, and returns the same launcher, refresh, publisher, dispatcher, repository, and blob-reader capabilities used by the local assembly.

The runtime reads configuration from environment variables but adapters also accept injected clients for deterministic tests.

Required runtime variables:

- `GOOGLE_CLOUD_PROJECT`;
- `POLICY_GCS_BUCKET`;
- `POLICY_PUBSUB_TOPIC`.

Optional variables and defaults:

- `GOOGLE_CLOUD_LOCATION=global`;
- `POLICY_GEMINI_MODEL=gemini-3.5-flash`;
- `FIRESTORE_DATABASE=(default)`.

No credentials, tokens, or service-account JSON are stored in the repository.

## 6. Real source configuration

`policy/policy_sources.yaml` contains one enabled source:

- source ID: `nrta_micro_drama_management_measures`;
- URL: `https://www.nrta.gov.cn/art/2026/7/31/art_113_73785.html`;
- content selector: `#zoom`.

The loader validates the file through `PolicySource`. Unknown fields, non-HTTPS URLs, empty selectors, and duplicate source IDs fail startup.

The real page is evidence, not an instruction. Gate 4 does not hardcode an inference that classification thresholds have been published. Proposal fields must be supported by the normalized source diff and human review remains mandatory.

## 7. HTTP source adapter

`HttpSourceFetcher` implements the existing asynchronous `SourceFetcher` interface.

Behavior:

1. Send an HTTPS GET with a stable product User-Agent.
2. Apply a 20-second total timeout.
3. Follow at most five redirects while requiring the final URL to remain HTTPS.
4. Reject non-2xx responses.
5. Reject an empty response body.
6. Reject a response above the 5 MiB size limit.
7. Return raw bytes and the final source URL.

The adapter accepts an injected asynchronous HTTP client. Tests use a transport fake and never use the public network.

## 8. GCS blob adapter

Object paths remain deterministic:

```text
policy/raw/{source_id}/{yyyy}/{mm}/{dd}/{sha256}.html
policy/normalized/{source_id}/{sha256}.txt
policy/diffs/{source_id}/{previous_sha256}..{current_sha256}.json
policy/packs/{snapshot_version}/{pack_name}.json
```

Every create uses `if_generation_match=0` so an existing live object cannot be overwritten.

If the precondition reports that the object already exists, the adapter reads the object and accepts it only when the bytes are identical. Different bytes at the same deterministic path raise an integrity error.

`read_text()` accepts only `gs://` URIs in the configured bucket and decodes UTF-8. Cross-bucket and non-GCS URIs are rejected.

## 9. Firestore policy repository

Firestore documents store Pydantic model data using native timestamps and string enum values. Every document is validated back into its model when read.

The following operations are transactional:

### 9.1 Refresh creates a proposal

The transaction:

1. reads the running run document;
2. rejects a missing or non-running run;
3. creates an auto-ID proposal document;
4. updates the source state;
5. completes the run with hashes and proposal ID.

### 9.2 Refresh completes with no change

The transaction validates the running run, updates the source state, and completes the run as `no_change`.

### 9.3 Publication

The transaction:

1. re-reads the pending proposal;
2. rejects a missing or non-pending proposal;
3. creates the next snapshot document;
4. updates the proposal to `published` with its version;
5. creates the pending outbox document.

Snapshot and outbox documents use deterministic IDs. Concurrent attempts to create the same next version result in a publication conflict rather than a duplicate or overwrite.

### 9.4 Discard and outbox updates

Discard conditionally changes only a pending proposal. Marking an outbox record sent requires a pending record and a non-empty Pub/Sub message ID.

## 10. Gemini proposal adapter

`GeminiProposalModel` implements the existing `ProposalModel.draft()` interface. It uses the Google Gen AI SDK with Vertex AI and `ProposalDraft` as the structured response schema.

The request contains only:

- source URL;
- previous and current hashes;
- unified diff;
- the allowed impact and pack enums through the response schema.

The prompt places the diff inside explicit untrusted-data delimiters and states that instructions inside the source must be ignored.

The adapter performs at most three calls:

1. initial structured generation;
2. first schema-repair attempt;
3. second and final schema-repair attempt.

Each result is validated through `ProposalDraft`. A valid result returns immediately. Exhaustion raises a stable proposal-model error; refresh records a failed run and does not update source state or create a proposal.

## 11. Pub/Sub event publisher

`PubSubEventPublisher` accepts only a validated `PolicyUpdatedEvent`, serializes it to UTF-8 JSON bytes, and publishes it to the configured topic path.

The adapter waits for the publisher future and returns the non-empty message ID. Any SDK exception or empty message ID is a publish failure. `OutboxDispatcher` therefore leaves the outbox pending and can retry later.

Gate 4 does not create topics or subscriptions at runtime.

## 12. Error and last-known-good rules

Adapters use stable internal error codes for source fetch, blob integrity, repository validation, proposal generation, and event publishing failures.

Raw diagnostics may be logged server-side but must not expose credentials, tokens, complete policy text, or service-account data. The Gate 3 run endpoint continues returning only `policy refresh failed` for failed runs.

The existing refresh commit ordering remains authoritative:

- raw or normalized blobs written before a later failure may remain as an immutable archive;
- `policy_source_states` changes only in a successful refresh transaction;
- a failed refresh never modifies a published snapshot;
- a Gemini failure never creates a proposal;
- a Pub/Sub failure never rolls back publication and never marks outbox sent.

## 13. Dependency and packaging policy

Core dependencies add the HTTP client needed by `HttpSourceFetcher`.

Google Cloud libraries are grouped under the optional `cloud` extra:

- `google-cloud-storage`;
- `google-cloud-firestore`;
- `google-cloud-pubsub`;
- `google-genai`.

Local Gate 1–3 installation and tests must continue to work without the cloud extra. Importing local policy modules must not import or initialize Google SDK clients.

## 14. Verification strategy

### 14.1 Default automated tests

Default tests never require network or credentials and cover:

- HTTP success, non-2xx, timeout, empty body, redirect, and size limit;
- GCS deterministic paths, first write, identical retry, mismatched retry, and URI restrictions;
- Firestore transaction success, conflict, atomic failure, ordering, and invalid documents;
- Gemini structured configuration, immediate success, repair success, and exhaustion after three calls;
- Pub/Sub topic, bytes payload, returned message ID, and publish failure;
- cloud configuration validation and dependency-free local imports;
- unchanged Gate 1–3 behavior.

SDK clients are injected. Test doubles model only the client methods called by each adapter.

### 14.2 Emulator integration

Firestore or Pub/Sub emulator tests run only when their documented emulator variables are present. Absence is reported as `SKIP`. Emulator results are not reported as deployed-cloud results.

### 14.3 Real NRTA source smoke

The source smoke uses the real NRTA HTTPS page with local file/in-memory adapters:

1. fetch and normalize the configured source;
2. establish a baseline without creating a proposal;
3. record the successful source-state hash;
4. run a deliberately failing fetch against the same repository;
5. assert that the source state and latest snapshot are unchanged.

The report records date, final URL, source ID, normalized hash, first-run status, failure-run status, and last-known-good preservation. It does not print the full policy text.

### 14.4 Full-cloud smoke

When cloud configuration and credentials are available, the full-cloud smoke:

1. constructs the real cloud runtime;
2. ensures the seed snapshot exists without overwriting an existing version;
3. runs the real NRTA source through HTTP, GCS, and Firestore; a genuine source diff may also invoke Gemini and create a pending proposal;
4. verifies persisted run and source state;
5. injects a fetch failure and verifies last-known-good persistence;
6. calls Gemini with the versioned fixture diff, validates the structured `ProposalDraft`, and does not persist the synthetic result;
7. publishes one validated synthetic `PolicyUpdatedEvent` to the explicitly configured smoke topic and records its message ID.

The report records project ID, database, bucket, topic, model, date, and PASS/FAIL/SKIP for each external adapter. It never prints credential material.

## 15. Exit criteria

### 15.1 Gate 4 implementation complete

All of the following must hold:

1. The five real adapters are implemented behind the existing module interfaces.
2. The real source and prompt are versioned.
3. All existing and new default tests pass without credentials.
4. Python compile, dependency, and wheel checks pass.
5. The real NRTA source smoke passes and proves last-known-good preservation.
6. No Gate 5 deployment or Maxine-owned persistence is introduced.
7. Independent review has no unresolved Critical or Important findings.

### 15.2 Gate 4 passed

In addition to implementation completion:

1. The cloud extra installs successfully.
2. Full-cloud smoke succeeds against a named Google Cloud project.
3. GCS, Firestore, Gemini, and Pub/Sub results are all explicitly recorded as PASS.
4. No fixture or emulator result is substituted for deployed-cloud evidence.

## 16. Risks and controls

| Risk | Control |
|---|---|
| NRTA DOM selector changes | Treat empty extraction as failure and preserve last-known-good state |
| Existing GCS object is overwritten | Use generation-zero precondition and byte comparison |
| Firestore partial write | Put multi-document state transitions inside transactions |
| Duplicate publish or delivery | Deterministic snapshot/outbox IDs plus conditional transactions |
| Model returns unsupported fields | Structured schema plus Pydantic validation and bounded repair |
| Prompt injection in policy text | Explicit untrusted-data delimiters and no tool access |
| Cloud SDK breaks local development | Optional cloud dependencies and lazy client construction |
| Credentials are absent | Full-cloud smoke reports SKIP; implementation status remains separate |

## 17. References

- Google Cloud Firestore Python transactions: <https://docs.cloud.google.com/python/docs/reference/firestore/latest/google.cloud.firestore_v1.transaction>
- Google Cloud Storage generation preconditions: <https://docs.cloud.google.com/python/docs/reference/storage/latest/generation_metageneration>
- Google Cloud Pub/Sub Python client: <https://docs.cloud.google.com/python/docs/reference/pubsub/latest>
- Google Gen AI structured output: <https://googleapis.github.io/python-genai/>
- Vertex AI Gemini quickstart: <https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/quickstart>
- Gemini model lifecycle: <https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions>
- NRTA source: <https://www.nrta.gov.cn/art/2026/7/31/art_113_73785.html>
