# Golden sample format

One YAML file per sample, loaded by `tests/test_golden_samples.py`. A sample is
only golden once every field below is filled by a named human — the harness
refuses a file that omits `provenance` or `reviewed_by`, so an unreviewed draft
cannot quietly become an assertion about the law.

```yaml
sample_id: gs-001
provenance: "Partner X, filing accepted 2026-05, redacted"   # where it came from
reviewed_by: "name or role of the human who confirmed it"
reviewed_at: 2026-05-20
script: |
  第一集 场景一：...
expected:
  categories: [public_security]        # categories the pre-check must report
  min_findings: 1                      # fewest findings that count as a pass
  must_not_report: [military]          # categories that would be false positives
notes: "why this sample is interesting"
```

`expected.categories` is what the deterministic stage must find with the rules
published in the pinned snapshot. When the placeholder keyword list is replaced
by partner-confirmed rules, samples that start failing are the point — they show
what the new rules changed.

There are no golden samples in the repository yet. `tests/fixtures/scripts/`
holds synthetic scripts that exercise the harness; they are not evidence about
any real filing.
