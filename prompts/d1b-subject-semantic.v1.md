# D1b subject semantic check — v1

Implementation: `core.classify.d1b` (`prompt_id = d1b_subject_semantic`).
Stage 1 is a deterministic pattern match over the p2 pack. This call is stage 2
and may only confirm rules that the pack already publishes.

Instruction:

```
Match the described story against the provided special-subject rules.
Report a hit only when the document itself supports it, and quote the
triggering text verbatim. Use only rule_id values from the provided list.
Report nothing if nothing matches.
```

Response schema: `{hits: [{rule_id, quote, confidence}], edge_hits: [...]}`.

Post-processing: a hit is discarded unless (a) `rule_id` exists in the pack and
(b) `quote` occurs verbatim in the logline or genre keywords. When no backend is
configured the classification carries `subject_semantic_check_pending` rather
than an implied clean result.
