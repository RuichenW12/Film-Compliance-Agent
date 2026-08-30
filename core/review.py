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
from .errors import UpstreamLLMError
from .llm import LLMClient, LLMRequest

SCRIPT_REVIEW_PROMPT_ID = "c1a_script_review"
SCRIPT_REVIEW_PROMPT_VERSION = "v1"
PENDING_FLAG = "script_semantic_check_pending"

_CN = "0-9一二三四五六七八九十"
_CN_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

# Both heading styles the sample scripts use:
#   "第一集 场景二"  — episode and scene on one line
#   "### 第1集《…》" then "**内景·…**"  — episode heading, then scene markers
_ONE_LINE = re.compile(rf"第\s*([{_CN}]+)\s*集.{{0,4}}?场景\s*([{_CN}]+)")
_EPISODE = re.compile(rf"^#*\s*第\s*([{_CN}]+)\s*集")
_ONE_LINE_EN = re.compile(
    r"^###\s+Episode\s+(\d+)\s+Scene\s+(\d+)\s*:\s*\S.*$",
    re.IGNORECASE,
)
_EPISODE_EN = re.compile(
    r"^##\s+Episode\s+(\d+)\s*:\s*\S.*$", re.IGNORECASE
)
_SCENE_NUMBERED = re.compile(
    rf"^#*\s*\**\s*(?:场景\s*([{_CN}]+)|第\s*([{_CN}]+)\s*场)"
)
# A screenplay slug line: 内景/外景 (INT/EXT) opens a new scene.
_SCENE_SLUG = re.compile(r"^[*#\s]*(内景|外景|内|外)[·、．.:：]")
# Commentary, not script content.
_BLOCKQUOTE = re.compile(r"^\s*>")
# Any markdown section heading, used to tell an episode from an appendix.
_SECTION = re.compile(r"^#+\s*\S")

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
    line: int | None = None


@dataclass
class ProposedFinding:
    category: str
    scene: Scene
    severity: FindingSeverity
    clause_id: str
    suggestion: str | None = None
    expert_pending: bool = False
    match_lines: list[int] = field(default_factory=list)


@dataclass
class ReviewResult:
    findings: list[ProposedFinding] = field(default_factory=list)
    discarded: list[str] = field(default_factory=list)
    pending_flags: list[str] = field(default_factory=list)
    backend: str = "unavailable"


def split_scenes(document: str) -> list[Scene]:
    """Every content line, carrying the episode and scene it sits inside.

    A line is quoted verbatim so the evidence rule still holds, but its episode
    and scene come from the last headings above it. Attributing a finding to the
    bare line loses the location a creator needs to find the scene again.

    Two things are deliberately not reviewed:

    - **blockquotes**, which are commentary in these documents;
    - **everything above the first episode heading**, which is a title page,
      test metadata, or a synopsis rather than script content. A document with
      no episode headings at all is reviewed whole, so a plain text script is
      unaffected.
    """

    lines = document.splitlines()
    has_episodes = any(
        _EPISODE.match(line.strip())
        or _ONE_LINE.search(line.strip())
        or _EPISODE_EN.fullmatch(line.strip())
        or _ONE_LINE_EN.fullmatch(line.strip())
        for line in lines
    )

    scenes: list[Scene] = []
    episode: int | None = None
    scene: int | None = None
    started = not has_episodes

    for number, line in enumerate(lines, start=1):
        text = line.strip()
        if not text or _BLOCKQUOTE.match(text):
            continue

        one_line = _ONE_LINE.search(text)
        one_line_en = _ONE_LINE_EN.fullmatch(text)
        episode_en = _EPISODE_EN.fullmatch(text)
        if one_line:
            episode = _number(one_line.group(1))
            scene = _number(one_line.group(2))
            started = True
        elif one_line_en:
            episode = int(one_line_en.group(1))
            scene = int(one_line_en.group(2))
            started = True
        elif _EPISODE.match(text):
            episode = _number(_EPISODE.match(text).group(1))
            scene = None
            started = True
            continue
        elif episode_en:
            episode = int(episode_en.group(1))
            scene = None
            started = True
            continue
        elif has_episodes and _SECTION.match(text):
            # A section heading that is not an episode closes the one before it.
            # Everything under "附录" belongs to the appendix, not to episode 7.
            episode = None
            scene = None
            started = False
            continue
        elif started and _SCENE_SLUG.match(text):
            scene = (scene or 0) + 1
        elif started:
            numbered = _SCENE_NUMBERED.match(text)
            if numbered:
                found = _number(numbered.group(1) or numbered.group(2))
                if found is not None:
                    scene = found

        if not started:
            continue
        scenes.append(
            Scene(quote=text, episode=episode, scene=scene, line=number)
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

    # One finding per category per scene. A courtroom scene mentioning the judge
    # in four lines is one rewrite decision, not four, and five alerts pointing
    # into the same scene give a creator four rows to dismiss rather than four
    # decisions to make. Every matching line number is kept on the finding so
    # the scene can still be traced back line by line.
    grouped: dict[tuple[str, int | None, int | None], ProposedFinding] = {}
    for scene in scenes:
        for rule in rules:
            if not any(pattern in scene.quote for pattern in rule.trigger_patterns):
                continue
            key = (rule.category, scene.episode, scene.scene)
            existing = grouped.get(key)
            if existing is None:
                proposal = _proposal(rule, scene)
                proposal.match_lines = [scene.line] if scene.line else []
                grouped[key] = proposal
            elif scene.line:
                existing.match_lines.append(scene.line)
    result.findings.extend(grouped.values())
    seen = set(grouped)

    if llm is None or not llm.available():
        result.pending_flags.append(PENDING_FLAG)
        return result

    result.backend = llm.name
    try:
        _semantic_pass(scenes, rules, llm, result, seen)
    except UpstreamLLMError:
        result.pending_flags.append(PENDING_FLAG)
    return result


def _semantic_pass(
    scenes: list[Scene],
    rules: list[SubjectRule],
    llm: LLMClient,
    result: ReviewResult,
    seen: set[tuple[str, int | None, int | None]],
) -> None:
    by_category = {rule.category: rule for rule in rules}
    reviewable_document = "\n".join(scene.quote for scene in scenes)
    reply = llm.structured(
        LLMRequest(
            prompt_id=SCRIPT_REVIEW_PROMPT_ID,
            prompt_version=SCRIPT_REVIEW_PROMPT_VERSION,
            instruction=INSTRUCTION,
            document=reviewable_document,
            response_schema=RESPONSE_SCHEMA,
            context={"categories": sorted(by_category)},
        )
    )

    for raw in reply.get("hits") or []:
        category = str(raw.get("category") or "").strip()
        quote = str(raw.get("quote") or "").strip()
        rule = by_category.get(category)
        # Unknown category, or a quote outside reviewable scene content: discarded.
        if rule is None or not quote or quote not in reviewable_document:
            if category:
                result.discarded.append(category)
            continue
        scene = _scene_for(quote, scenes)
        if scene is None:
            result.discarded.append(category)
            continue
        key = (category, scene.episode, scene.scene)
        if key in seen:
            # The deterministic stage already reported this scene.
            continue
        seen.add(key)
        proposal = _proposal(rule, scene, raw.get("reason"))
        proposal.match_lines = [scene.line] if scene.line else []
        result.findings.append(proposal)


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


def _scene_for(quote: str, scenes: list[Scene]) -> Scene | None:
    for scene in scenes:
        if quote in scene.quote or scene.quote in quote:
            return scene
    return None


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
