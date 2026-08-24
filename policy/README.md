# Policy Data and Configuration

Owner: Richard

This directory contains non-executable inputs and versioned policy assets consumed through the shared snapshot contract.

Planned contents:

- `policy_sources.yaml` for the small configured set of official source pages;
- `seed-snapshot-v1.yaml` as the development fixture for both workstreams;
- reviewed policy packs for form definitions, subject rules, tier thresholds, process templates, form templates, and legal clauses.

Executable fetching, diffing, proposal generation, publishing, and update consumption belong in [`workers/policy/`](../workers/policy/README.md).

Policy facts must retain source and effective-time information. AI-drafted placeholders must remain visibly unconfirmed until reviewed; missing amounts, contacts, or form fields must not be invented.

Gate 1 includes `seed-snapshot-v1.yaml`, the reviewed static handshake fixture. Source crawling and generated policy assets are not part of Gate 1.

The seed is repository-level configuration supplied explicitly to `FileSnapshotService`; it is not Python wheel package data.

Within `p3_tier_thresholds`, `thresholds_published` is the pack-level source of truth. Publisher mirrors the merged boolean into the snapshot and policy.updated event top-level fields without inventing unpublished threshold amounts.
