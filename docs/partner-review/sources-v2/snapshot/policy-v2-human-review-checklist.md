# Policy Snapshot v2 Human Review Checklist

The current v2 is `mock_verified`. Automated tests cannot check any box below.
The snapshot remains mock until every item is reviewed and evidence is recorded.

## p1 form definition

- [ ] Definition wording matches the cited original.
- [ ] Applicability, jurisdiction, and effective date are confirmed.

## p2 subject rules

- [ ] All nine triggers and edge cases are confirmed by the film partner.
- [ ] T1 and co-review outcomes are confirmed.

## p3 tier thresholds

- [ ] Live-action amounts and applicability are confirmed.
- [ ] AI-generated amounts and applicability are confirmed.
- [ ] Publication and effective dates are confirmed.

## p4 process templates

- [ ] Step order and owners are confirmed.
- [ ] Mandatory steps and any published durations are confirmed.
- [ ] Shanghai operational steps are either jurisdiction-gated or explicitly
  approved as the demo default; they are not represented as nationwide rules.

## p5 form and materials

- [ ] Actual field names and requiredness are confirmed.
- [ ] Material names, templates, and asset-kind mappings are confirmed.
- [ ] Every `reference_fields` item is checked against the post-2026-09-01
  production filing system before moving it into `required_facts`.
- [ ] The current system-generated filing/review forms are exported or captured
  from the authenticated system and compared with the archived public forms.
- [ ] Grouping several administrative files as `supporting_document` is accepted
  for MVP integration or replaced by an approved shared contract change.
- [ ] Completed-film and subtitle requirements are applied at content review,
  not used to block the pre-shoot Gate.

## p6 clauses and evidence

- [ ] Original wording and official URLs are confirmed.
- [ ] Every rule-to-clause mapping is confirmed.
- [ ] Historical and reference-only documents are not used to override current
  tier thresholds or the 2026 Order No. 16.

## Promotion

- [ ] The 2026-09-01 regime effective-time boundary is handled explicitly.
- [ ] All mock content identified above has been replaced or confirmed.
- [ ] Full Python and frontend verification passes unchanged.
- [ ] A human reviewer authorizes `verification_status=human_verified`.
