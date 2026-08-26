# Policy v2 Evidence Archive and Snapshot Materialization Design

**Date:** 2026-08-26

**Status:** Approved

**Owner:** Richard

## Outcome

Replace the thin three-page evidence bundle with a reviewable archive that
contains formal policy documents, current government service guides, public
form templates, and clearly separated reference-only material. Rebuild the v2
snapshot from that evidence without promoting it beyond `mock_verified`.

## Boundaries

- Government publication status and product mapping status are separate facts.
- The snapshot remains `published_by: mock_seed` and
  `verification_status: mock_verified` until a human review explicitly
  authorizes promotion.
- The 2026 NRTA Order No. 16 takes effect on 2026-09-01. Before that date the
  v2 seed is integration data for the upcoming regime, not a claim about the
  currently effective regime.
- Provincial service guides ground concrete fields and workflow examples but
  are not silently generalized into national rules.
- Old thresholds in historical guides and group standards are retained only as
  `reference_only`; they never replace the v2 threshold candidates.
- Forms generated only after authentication are recorded as
  `external_system_generated`; an unavailable blank form is not invented.
- No generic policy DSL, automatic legal approval, or new cloud resource is
  introduced.

## Archive layout

`docs/partner-review/sources-v2/` keeps the existing raw/text/header evidence
and adds four explicit review zones:

- `authoritative/`: national regulations and current government service guides;
- `forms/`: real public blank/example forms downloaded from government portals;
- `reference-only/`: industry/self-regulatory or historical material that must
  not drive current thresholds;
- `system-generated/`: a README identifying login-generated forms that cannot
  be archived publicly.

`manifest.json` is the machine-readable source catalog. Every archived file has
a SHA-256 value, an authority classification, a mapping status, applicability,
and any known date or threshold caveat.

## Snapshot mapping

The v2 runtime shape remains compatible with the existing six packs.

- p1/p2/p3 retain the current integration behavior and explicit mock status.
- p4 keeps the three runtime template names consumed by Maxine, but records the
  national/provincial source basis and the jurisdiction limitation. Its steps
  cover planning filing, review/permission, and the T3 broadcaster path.
- p5 exposes public-guide field names and groups filing documents into existing
  asset kinds. Exact system-generated form bytes remain pending.
- p6 adds the national clauses that directly support filing and review
  materials.

Because the current material contract accepts one `asset_kind` per card, the
MVP groups administrative documents under `supporting_document`. It does not
create many new document-kind enums merely to mirror one provincial portal.

## Reproducible materialization

`scripts/materialize_policy_snapshot_v2.py` validates three things before
updating the frozen archive copy:

1. the seed passes the shared Pydantic and semantic validators;
2. every source ID cited by p4/p5 exists in `manifest.json`;
3. every file listed by the manifest exists and matches its SHA-256 digest.

The command then copies the canonical seed to
`docs/partner-review/sources-v2/snapshot/seed-snapshot-v2.yaml` and records its
digest in the manifest. A `--check` mode performs the same validation without
writing and fails if the frozen copy has drifted.

Gemini is not used to authorize or silently rewrite legal mappings in this
flow. The model-assisted proposal loop remains a separate, review-gated path.

## Verification

- RED/GREEN tests cover source-ID resolution, archive hashes, frozen-snapshot
  drift, real p4/p5 content, and continued `mock_verified` status.
- Focused policy tests, the full Python suite, frontend tests, typecheck, and
  production build run before push.
- Only intended paths are staged; existing `.DS_Store` files and the user's
  pre-existing ZIP remain untouched.
