# Fact extraction — v1

Implementation: `core.extract` (`prompt_id = fact_extract`). Called from
`WorkflowService.extract_asset_facts` on one uploaded asset version.

Instruction:

```
Extract registration facts from the document. For each fact, return the value
exactly as the document writes it and quote the surrounding text verbatim.
Extract only what the document states. If a fact is absent, omit it — do not
infer, translate, summarise, or supply a placeholder.
```

Context (trusted): `{wanted_keys: [...]}`, taken from
`p5_form_templates.required_facts` when the pack defines it, otherwise the
`core.gate` defaults.

Response schema: `{facts: [{key, value, quote}]}`.

Post-processing, applied before anything is stored:

1. `quote` must occur verbatim in the document;
2. the rendered `value` must occur inside `quote` — a quote that does not
   contain its own value is a paraphrase;
3. a null or blank value is dropped, because a confirmed fact may not carry a
   null value and `待补充` is the honest rendering.

A proposal failing any of these is reported in `discarded` and never written.
With no backend configured the response carries `fact_extraction_pending` and no
facts, so an empty list is never read as "the document held nothing".

Every stored fact gets `SourceRef(type=asset, asset_version, locator=quote)`, so
a form field rendered from it can always be traced back to the line that
produced it.
