# Policy Data and Configuration

Owner: Richard

This directory contains non-executable inputs and versioned policy assets consumed through the shared snapshot contract.

Contents:

- `policy_sources.yaml` for the small configured set of official source pages;
- `seed-snapshot-v2.yaml` as the complete local-default integration snapshot;
- `seed-snapshot-v1.yaml` as an explicit legacy contract fixture;
- reviewed policy packs for form definitions, subject rules, tier thresholds, process templates, form templates, and legal clauses.

Executable fetching, diffing, proposal generation, publishing, and update consumption belong in [`workers/policy/`](../workers/policy/README.md).

Policy facts must retain source and effective-time information. AI-drafted placeholders must remain visibly unconfirmed until reviewed; missing amounts, contacts, or form fields must not be invented.

`policy_sources.yaml` currently enables the official NRTA micro-drama management-measures page and requires an HTTPS URL plus a non-empty content selector. `seed-snapshot-v2.yaml` is complete enough for deterministic local integration, but every pack is still `mock_verified`; it is not human-reviewed policy or legal advice. `seed-snapshot-v1.yaml` remains available only as the legacy A/B handshake fixture.

The YAML files are packaged runtime assets and are loaded through `importlib.resources`; cloud startup does not assume a repository checkout path.

Mock-to-human promotion applies to the whole snapshot, not individual packs.
Automated checks cannot promote it. A human reviewer must complete
[`docs/policy-v2-human-review-checklist.md`](../docs/policy-v2-human-review-checklist.md),
record the supporting evidence, and explicitly authorize
`verification_status=human_verified`.

Within `p3_tier_thresholds`, `thresholds_published` is the pack-level source of truth. Publisher mirrors the merged boolean into the snapshot and policy.updated event top-level fields without inventing unpublished threshold amounts.

Gate 4 archives fetched raw HTML, normalized text, diffs, and future pack blobs outside this package. Generated data is not committed back into `policy/`, and an AI proposal remains pending until Richard reviews and publishes it through the administration boundary.
