"""C1-a script pre-check (contract step 8).

Stage 1 is a deterministic pattern match over the published subject rules, scene
by scene. Stage 2 is one semantic pass that may only report categories the pack
already publishes. Neither stage is trusted to be honest on its own:

- a hit is kept only if its quote occurs verbatim in the script;
- a rule flagged `expert_pending` produces `needs_human`, never `block` — the
  seed's keywords are an operational placeholder, not a confirmed rule;
- with no backend the caller gets `script_semantic_check_pending`, so "patterns
  found nothing" is never rendered as "the script is clean".

Scenes are split on the episode/scene headings the sample scripts use. A line
that does not parse still gets reviewed; it simply carries no episode or scene
number rather than a guessed one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from schemas.common import EvidenceRef
from schemas.enums import FindingSeverity

from .classify.subject_rules import SubjectRule
from .llm import LLMClient, LLMRequest

SCRIPT_REVIEW_PROMPT_ID = "c1a_script_review"
SCRIPT_REVIEW_PROMPT_VERSION = "v1"
PENDING_FLAG = "script_semantic_check_pending"

# 第一集 场景二 / 第1集 场景2 — the heading form the sample scripts use.
_HEADING = re.compile(r"第\s*([0-9一二三四五六七八九十]+)\s*集.{0,4}?场景\s*([0-9一二三四五六七八九十]+)")
_CN_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

INSTRUCTION = (
    "Review the script for scenes touching the listed special-subject "
    "categories. Report a hit only when the script itself shows it, and quote "
    "the scene verbatim. Use only category values from the provided list. "
    "Report nothing if nothing matches."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "hits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "quote": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["category", "quote", "reason"],
            },
        }
    },
    "required": ["hits"],
}


@dataclass
class Scene:
    quote: str
    episode: int | None = None
    scene: int | None = None


@dataclass
class ProposedFinding:
    category: str
    scene: Scene
    severity: FindingSeverity
    clause_id: str
    suggestion: str | None = None
    expert_pending: bool = False


@dataclass
class ReviewResult:
    findings: list[ProposedFinding] = field(default_factory=list)
    discarded: list[str] = field(default_factory=list)
    pending_flags: list[str] = field(default_factory=list)
    backend: str = "unavailable"


def split_scenes(document: str) -> list[Scene]:
    """One scene per non-empty line, numbered from its heading when it has one."""

    scenes: list[Scene] = []
    for line in document.splitlines():
        text = line.strip()
        if not text:
            continue
        match = _HEADING.search(text)
        scenes.append(
            Scene(
                quote=text,
                episode=_number(match.group(1)) if match else None,
                scene=_number(match.group(2)) if match else None,
            )
        )
    return scenes


def review_script(
    document: str,
    rules: list[SubjectRule],
    llm: LLMClient | None,
) -> ReviewResult:
    """Propose findings the script supports. Nothing here writes to storage."""

    scenes = split_scenes(document)
    result = ReviewResult()
    seen: set[tuple[str, str]] = set()

    for scene in scenes:
        for rule in rules:
            if any(pattern in scene.quote for pattern in rule.trigger_patterns):
                key = (rule.category, scene.quote)
                if key in seen:
                    continue
                seen.add(key)
                result.findings.append(_proposal(rule, scene))

    if llm is None or not llm.available():
        result.pending_flags.append(PENDING_FLAG)
        return result

    result.backend = llm.name
    _semantic_pass(document, scenes, rules, llm, result, seen)
    return result


def _semantic_pass(
    document: str,
    scenes: list[Scene],
    rules: list[SubjectRule],
    llm: LLMClient,
    result: ReviewResult,
    seen: set[tuple[str, str]],
) -> None:
    by_category = {rule.category: rule for rule in rules}
    reply = llm.structured(
        LLMRequest(
            prompt_id=SCRIPT_REVIEW_PROMPT_ID,
            prompt_version=SCRIPT_REVIEW_PROMPT_VERSION,
            instruction=INSTRUCTION,
            document=document,
            response_schema=RESPONSE_SCHEMA,
            context={"categories": sorted(by_category)},
        )
    )

    for raw in reply.get("hits") or []:
        category = str(raw.get("category") or "").strip()
        quote = str(raw.get("quote") or "").strip()
        rule = by_category.get(category)
        # Unknown category, or a quote the script does not contain: discarded.
        if rule is None or not quote or quote not in document:
            if category:
                result.discarded.append(category)
            continue
        key = (category, quote)
        if key in seen:
            continue
        seen.add(key)
        result.findings.append(
            _proposal(rule, _scene_for(quote, scenes), raw.get("reason"))
        )


def _proposal(
    rule: SubjectRule, scene: Scene, suggestion: str | None = None
) -> ProposedFinding:
    return ProposedFinding(
        category=rule.category,
        scene=scene,
        # An unconfirmed rule may not assert a block; a human decides instead.
        severity=(
            FindingSeverity.NEEDS_HUMAN
            if rule.expert_pending
            else FindingSeverity.CO_REVIEW_REQUIRED
        ),
        clause_id=rule.clause_ref,
        suggestion=suggestion,
        expert_pending=rule.expert_pending,
    )


def _scene_for(quote: str, scenes: list[Scene]) -> Scene:
    for scene in scenes:
        if quote in scene.quote or scene.quote in quote:
            return scene
    return Scene(quote=quote)


def evidence_for(clause_id: str, version: str) -> EvidenceRef:
    return EvidenceRef(snapshot_version=version, clause_id=clause_id)


def _number(raw: str) -> int | None:
    if raw.isdigit():
        return int(raw)
    if len(raw) == 1:
        return _CN_DIGITS.get(raw)
    if raw.startswith("十"):
        return 10 + _CN_DIGITS.get(raw[1:], 0)
    if raw.endswith("十"):
        return _CN_DIGITS.get(raw[0], 0) * 10
    if "十" in raw:
        tens, ones = raw.split("十", 1)
        return _CN_DIGITS.get(tens, 0) * 10 + _CN_DIGITS.get(ones, 0)
    return None
