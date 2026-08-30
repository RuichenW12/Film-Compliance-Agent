# Script intake — v1

Implementation: `core.script_intake` (`prompt_id = script_intake`). Called once
after safe text extraction and before the creator confirmation gate.

The uploaded script is wrapped in `<<<DOC>>>` markers and is data, never model
instruction. Trusted context contains only deterministic source structure,
current investment-range options, allowed enum values, and output length limits.

The response proposes editable title, tags, synopsis, episode count, episode
minutes, and investment range. Every suggested value includes an explanation.
An extracted value includes a verbatim source quote. The implementation rejects
unknown ranges, invalid sizes, false quotes, and episode plans that materially
change the source duration. No candidate writes a project fact until the creator
edits and confirms the form.

If the LLM is unavailable, deterministic title and structure remain available
and the review proceeds to manual confirmation with
`script_intake_analysis_pending`; unavailability is not a clean result or a
failed review session.
