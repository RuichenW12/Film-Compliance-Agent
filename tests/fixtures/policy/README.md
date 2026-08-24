# Policy Fixtures

Owner: Richard

This directory is reserved for deterministic policy-loop scenarios. The initial pair will represent a prior snapshot with unpublished thresholds and a reviewed update with published thresholds.

Fixtures exist to exercise crawl, diff, proposal, publish, and event-consumer behavior without depending on a live website during every test. They must clearly identify synthetic values and must not be presented as current policy facts.

Gate 2 includes `source-v1.html` and `source-v2.html`. Their policy wording and threshold-publication transition are synthetic test data, not current policy facts.
