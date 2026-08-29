"""D1a FormTypeJudge (TDD 4.3). Pure rules; the LLM only reads the synopsis for
edge phrases and a continuity claim, and only ever returns quotes."""

from __future__ import annotations

from dataclasses import dataclass, field

from schemas.enums import ClaimedFormType, FormType
from schemas.project import IntentProfile

from ..errors import UpstreamLLMError
from ..llm import LLMClient, LLMRequest

PROMPT_ID = "d1a_edge_phrase"
PROMPT_VERSION = "v1"

# Phrases whose form type is genuinely unsettled; they go to a human, not a guess.
EDGE_PHRASES: tuple[str, ...] = ("切片", "付费合集", "互动剧", "竖屏电影", "微综艺")

EDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "edge_phrases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "phrase": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["phrase", "quote"],
            },
        },
        "continuous_plot_claimed": {"type": "boolean"},
        "continuity_quote": {"type": "string"},
    },
    "required": ["edge_phrases", "continuous_plot_claimed"],
}

INSTRUCTION = (
    "Decide two things about the synopsis. (1) Does it contain any of the listed "
    "edge phrases whose format is unsettled? Quote them verbatim. (2) Does it "
    "claim a continuous plot across episodes? Do not infer legal conclusions."
)


@dataclass
class FormTypeDecision:
    form_type: FormType
    outcome: str  # micro_drama | exit_non_drama | exit_sister_path | needs_human | ask_back
    missing: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    pending_flags: list[str] = field(default_factory=list)
    edge_quotes: list[dict] = field(default_factory=list)


def _pack_limits(pack: dict) -> tuple[float, int]:
    max_minutes = pack.get("episode_max_minutes_exclusive", pack.get("episode_max_minutes", 20))
    min_episodes = pack.get("min_episodes", 3)
    return float(max_minutes), int(min_episodes)


def _detect_edge_phrases(text: str) -> list[dict]:
    hits = []
    for phrase in EDGE_PHRASES:
        if phrase in text:
            hits.append({"phrase": phrase, "quote": phrase, "stage": "pattern"})
    return hits


def judge_form_type(
    intent: IntentProfile,
    pack1: dict,
    llm: LLMClient | None = None,
) -> FormTypeDecision:
    max_minutes, min_episodes = _pack_limits(pack1)
    synopsis = intent.synopsis or ""

    missing = intent.missing_fields()
    if "episode_count" in missing or "episode_minutes" in missing:
        return FormTypeDecision(
            form_type=FormType.UNDETERMINED,
            outcome="ask_back",
            missing=[key for key in missing if key != "synopsis"],
            reasons=["intent.missing_required_fields"],
        )

    edge_hits = _detect_edge_phrases(synopsis)
    pending_flags: list[str] = []
    if llm is not None and llm.available() and synopsis:
        try:
            reply = llm.structured(
                LLMRequest(
                    prompt_id=PROMPT_ID,
                    prompt_version=PROMPT_VERSION,
                    instruction=INSTRUCTION,
                    document=synopsis,
                    response_schema=EDGE_SCHEMA,
                    temperature=0.2,
                    context={"edge_phrases": list(EDGE_PHRASES)},
                )
            )
        except UpstreamLLMError:
            pending_flags.append("edge_phrase_check_pending")
        else:
            for hit in reply.get("edge_phrases", []):
                quote = str(hit.get("quote", ""))
                # Anti-hallucination: the model may only report text that exists.
                if quote and quote in synopsis:
                    edge_hits.append(
                        {
                            "phrase": str(hit.get("phrase", quote)),
                            "quote": quote,
                            "stage": "semantic",
                        }
                    )
    elif synopsis:
        pending_flags.append("edge_phrase_check_pending")

    if edge_hits:
        return FormTypeDecision(
            form_type=FormType.UNDETERMINED,
            outcome="needs_human",
            reasons=["form_type.edge_phrase"],
            pending_flags=pending_flags,
            edge_quotes=edge_hits,
        )

    if (
        intent.episode_minutes is not None and intent.episode_minutes >= max_minutes
    ) or intent.form_type_claimed is ClaimedFormType.WEB_FILM:
        return FormTypeDecision(
            form_type=FormType.WEB_FILM,
            outcome="exit_sister_path",
            reasons=["form_type.episode_minutes_over_limit"],
            pending_flags=pending_flags,
        )

    if intent.episode_count is not None and intent.episode_count < min_episodes:
        return FormTypeDecision(
            form_type=FormType.NON_DRAMA,
            outcome="exit_non_drama",
            reasons=["form_type.episode_count_below_minimum"],
            pending_flags=pending_flags,
        )

    return FormTypeDecision(
        form_type=FormType.MICRO_DRAMA,
        outcome="micro_drama",
        reasons=["form_type.micro_drama"],
        pending_flags=[*pending_flags, "script_verify"],
    )
