# Partner review package generators

One-shot tooling that renders the policy review brief sent to the film partner:
a Chinese PDF explaining what in the snapshot is mock and why, and an XLSX the
partner fills in with their confirmations.

**These are not part of the product.** Nothing in `api/`, `core/`, `workers/`, or
`web/` imports them, no test depends on them, and the running system never calls
them. They live here rather than in `scripts/` so that the difference is visible:
`scripts/` holds things the workflow uses, this holds things a person runs by
hand when a document needs regenerating.

The artefacts they produce are checked in under `docs/partner-review/`. The
generators are kept so those artefacts can be rebuilt when the snapshot changes,
rather than hand-edited out of sync with it.

## Running them

Both need dependencies that the product itself does not:

```bash
pip install -e ".[partner-review]"      # reportlab, for the PDF
python tools/partner-review/build_pdf.py

npm install @oai/artifact-tool          # for the workbook
node tools/partner-review/build_workbook.mjs
```

The extra exists so a regeneration is reproducible without adding a PDF library
to the runtime dependencies of a compliance API.

## What stayed in `scripts/`

`scripts/materialize_policy_snapshot_v2.py` is **not** one of these. It validates
and freezes the evidence archive, `tests/policy/test_snapshot_materialization.py`
imports it, and `policy/README.md` documents `--check` as the way to verify the
archive. It is part of the integrity loop and belongs with the other operational
scripts.
