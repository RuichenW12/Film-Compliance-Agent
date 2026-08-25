# C1-a script pre-check — v1

Implementation: `core.review` (`prompt_id = c1a_script_review`). Stage 1 is a
deterministic pattern match over the p2 subject rules, scene by scene. This call
is stage 2 and may only report categories the pack already publishes.

Instruction:

```
Review the script for scenes touching the listed special-subject categories.
Report a hit only when the script itself shows it, and quote the scene verbatim.
Use only category values from the provided list. Report nothing if nothing
matches.
```

Context (trusted): `{categories: [...]}` from the pinned p2 pack.

Response schema: `{hits: [{category, quote, reason}]}`.

Post-processing, applied before any finding is written:

1. an unknown `category` is discarded — the model may not invent a subject;
2. a `quote` that does not occur verbatim in the script is discarded;
3. a scene already reported by stage 1 is not reported twice.

Severity comes from the rule, never from the model. While the p2 keywords are
the placeholder list (`expert_pending`), every finding is `needs_human` rather
than `block` or `co_review_required`: an unconfirmed rule may not assert a
compliance conclusion. Each finding carries an `EvidenceRef` to the rule's
clause in the pinned snapshot, so ground rule 2 holds by construction.

With no backend configured the response carries `script_semantic_check_pending`.
"Patterns found nothing" is never rendered as "the script is clean".
