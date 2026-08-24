# D1a edge-phrase and continuity check — v1

Implementation: `core.classify.d1a` (`prompt_id = d1a_edge_phrase`).
The LLM never decides the form type. Pure rules decide; this call only reads the
logline for phrases whose format is genuinely unsettled and for a continuity
claim.

Instruction:

```
Decide two things about the logline. (1) Does it contain any of the listed
edge phrases whose format is unsettled? Quote them verbatim. (2) Does it
claim a continuous plot across episodes? Do not infer legal conclusions.
```

Response schema: `{edge_phrases: [{phrase, quote}], continuous_plot_claimed: bool, continuity_quote?}`.

Post-processing: an edge phrase is kept only when its quote occurs in the
logline. Any hit routes the project to `NEEDS_HUMAN_FORMTYPE`.
