# Policy v2 Evidence Archive Implementation Plan

> Implement the approved evidence/archive design with TDD and preserve the
> whole-snapshot mock verification boundary.

**Goal:** Archive substantive official sources and public forms, ground p4/p5
with them, and materialize a reproducible v2 snapshot for Maxine integration.

**Architecture:** The YAML seed remains the canonical human-reviewable policy
candidate. A small Python materializer checks the source catalog, archived file
digests, and snapshot semantics before refreshing the frozen partner-review
copy. Runtime consumers continue reading the existing six-pack contract.

**Tech stack:** Python 3.14, Pydantic, PyYAML, pytest, static PDF/DOCX/HTML
evidence, Next.js/Vitest.

## Task 1: Add failing evidence/materialization tests

**Files:**

- Create: `tests/policy/test_snapshot_materialization.py`
- Modify: `tests/test_policy_v2_seed.py`

Test that p4/p5 cite catalogued sources, p5 includes public real-form metadata
and the `final_film` runtime kind, materialization detects unknown source IDs,
and `--check` detects a stale archive copy. Run the tests and retain the
expected RED result before adding the script/data.

## Task 2: Archive source documents and forms

**Files:**

- Modify: `docs/partner-review/sources-v2/README.md`
- Modify: `docs/partner-review/sources-v2/manifest.json`
- Modify: `docs/partner-review/sources-v2/.gitattributes`
- Create: files under `authoritative/`, `forms/`, `reference-only/`, and
  `system-generated/`

Download byte-for-byte government documents/forms. Record their original URLs,
hashes, authority category, jurisdiction, mapping status, and caveats. Mark the
group standard and old threshold content reference-only.

## Task 3: Ground p4/p5 and p6

**Files:**

- Modify: `policy/seed-snapshot-v2.yaml`
- Modify: `policy/README.md`
- Modify: `web/locales/en.json`
- Modify: `web/locales/zh.json`

Keep the existing runtime template identifiers while replacing generic step
copy with sourced filing/review stages. Add the concrete public-guide fields,
grouped material requirements, public form URLs, and national Articles 14, 17,
19, and 20. Preserve the mock status and future-regime warning.

## Task 4: Implement and run the materializer

**Files:**

- Create: `scripts/materialize_policy_snapshot_v2.py`
- Modify: `docs/partner-review/sources-v2/snapshot/seed-snapshot-v2.yaml`
- Modify: `docs/partner-review/sources-v2/manifest.json`

Implement pure validation helpers first, then the CLI. Run the materializer in
write mode, followed by `--check`, and turn the RED tests GREEN.

## Task 5: Verify and publish

Run focused and full Python tests, frontend tests/typecheck/build, manifest hash
verification, `git diff --check`, and status inspection. Commit only intended
paths, push the branch, and create a new PR against `main` because PR #33 is
already merged.
