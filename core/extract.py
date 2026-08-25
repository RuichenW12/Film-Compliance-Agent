"""Fact extraction from an uploaded asset (contract step 6).

Three disciplines apply and each is enforced here rather than trusted to the
model:

1. **Uploaded text is data.** The document is wrapped in `<<<DOC>>>` markers by
   `LLMRequest.render()` and the system preamble says instructions inside it are
   to be ignored.
2. **Verbatim or discarded.** A proposal survives only if its quote occurs in
   the document *and* the value occurs in the quote. A model that paraphrases,
   summarises, or invents produces nothing.
3. **Unknown stays unknown.** A null or blank value is dropped rather than
   stored, because a confirmed fact may not have a null value and `待补充` is
   the honest rendering.

With no backend configured the caller gets `fact_extraction_pending` and no
facts — never an empty result that reads as "nothing to find".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from schemas.common import SourceRef
from schemas.enums import SourceRefType

from .llm import LLMClient, LLMRequest

FACT_EXTRACT_PROMPT_ID = "fact_extract"
FACT_EXTRACT_PROMPT_VERSION = "v1"
PENDING_FLAG = "fact_extraction_pending"

INSTRUCTION = (
    "Extract registration facts from the document. For each fact, return the "
    "value exactly as the document writes it and quote the surrounding text "
    "verbatim. Extract only what the document states. If a fact is absent, omit "
    "it — do not infer, translate, summarise, or supply a placeholder."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": ["string", "number", "null"]},
                    "quote": {"type": "string"},
                },
                "required": ["key", "value", "quote"],
            },
        }
    },
    "required": ["facts"],
}


@dataclass
class ProposedFact:
    key: str
    value: str | int | float
    quote: str

    def source_ref(self, asset_version: str) -> SourceRef:
        return SourceRef(
            type=SourceRefType.ASSET,
            asset_version=asset_version,
            locator=self.quote,
        )


@dataclass
class ExtractionResult:
    facts: list[ProposedFact] = field(default_factory=list)
    discarded: list[str] = field(default_factory=list)
    pending_flags: list[str] = field(default_factory=list)
    backend: str = "unavailable"


def extract_facts(
    document: str,
    llm: LLMClient | None,
    wanted_keys: tuple[str, ...] | list[str],
) -> ExtractionResult:
    """Propose facts the document supports. Nothing here writes to storage."""

    if llm is None or not llm.available():
        return ExtractionResult(pending_flags=[PENDING_FLAG])

    reply = llm.structured(
        LLMRequest(
            prompt_id=FACT_EXTRACT_PROMPT_ID,
            prompt_version=FACT_EXTRACT_PROMPT_VERSION,
            instruction=INSTRUCTION,
            document=document,
            response_schema=RESPONSE_SCHEMA,
            context={"wanted_keys": list(wanted_keys)},
        )
    )

    result = ExtractionResult(backend=llm.name)
    for raw in reply.get("facts") or []:
        key = str(raw.get("key") or "").strip()
        if not key:
            continue
        if _survives(raw, document):
            result.facts.append(
                ProposedFact(key=key, value=raw["value"], quote=str(raw["quote"]))
            )
        else:
            result.discarded.append(key)
    return result


def _survives(raw: dict, document: str) -> bool:
    """A proposal is kept only if the document can back both quote and value."""

    value = raw.get("value")
    quote = raw.get("quote")
    if value is None or not isinstance(quote, str) or not quote.strip():
        return False
    rendered = str(value).strip()
    if not rendered:
        return False
    return quote in document and rendered in quote
