# Policy Data and Configuration

Owner: Richard

This directory contains non-executable inputs and versioned policy assets consumed through the shared snapshot contract.

Planned contents:

- `policy_sources.yaml` for the small configured set of official source pages;
- `seed-snapshot-v1.yaml` as the development fixture for both workstreams;
- reviewed policy packs for form definitions, subject rules, tier thresholds, process templates, form templates, and legal clauses.

Executable fetching, diffing, proposal generation, publishing, and update consumption belong in [`workers/policy/`](../workers/policy/README.md).

Policy facts must retain source and effective-time information. AI-drafted placeholders must remain visibly unconfirmed until reviewed; missing amounts, contacts, or form fields must not be invented.

No policy source file or seed data is included in this scaffold.
