"""D1b SubjectJudge (TDD 4.4): deterministic pattern match, then one semantic pass."""

from __future__ import annotations

from dataclasses import dataclass, field

from schemas.project import IntentProfile, MatchedRule

from ..errors import UpstreamLLMError
from ..llm import LLMClient, LLMRequest
from .subject_rules import SubjectRule, load_subject_rules

PROMPT_ID = "d1b_subject_semantic"
PROMPT_VERSION = "v1"

SUBJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "hits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string"},
                    "quote": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["rule_id", "quote", "confidence"],
            },
        },
        "edge_hits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string"},
                    "quote": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["rule_id", "quote", "confidence"],
            },
        },
    },
    "required": ["hits", "edge_hits"],
}

INSTRUCTION = (
    "Match the described story against the provided special-subject rules. "
    "Report a hit only when the document itself supports it, and quote the "
    "triggering text verbatim. Use only rule_id values from the provided list. "
    "Report nothing if nothing matches."
)

QUOTE_WINDOW = 24


@dataclass
class SubjectDecision:
    special_subject_hit: bool = False
    edge_case_hit: bool = False
    matched_rules: list[MatchedRule] = field(default_factory=list)
    edge_rules: list[MatchedRule] = field(default_factory=list)
    dept: dict | None = None
    clause_refs: list[str] = field(default_factory=list)
    pending_flags: list[str] = field(default_factory=list)
    expert_pending: bool = False
    confidence: float = 0.0


def _quote_around(text: str, pattern: str) -> str:
    index = text.find(pattern)
    if index < 0:
        return pattern
    start = max(0, index - QUOTE_WINDOW)
    end = min(len(text), index + len(pattern) + QUOTE_WINDOW)
    return text[start:end].strip()


def _pattern_stage(
    rules: list[SubjectRule], haystacks: dict[str, str]
) -> list[tuple[SubjectRule, MatchedRule]]:
    hits: list[tuple[SubjectRule, MatchedRule]] = []
    for rule in rules:
        for pattern in rule.trigger_patterns:
            if not pattern:
                continue
            for source, text in haystacks.items():
                if pattern and pattern in text:
                    hits.append(
                        (
                            rule,
                            MatchedRule(
                                rule_id=rule.rule_id,
                                quote=_quote_around(text, pattern)
                                if source == "logline"
                                else pattern,
                                confidence=1.0,
                                stage=f"pattern:{source}",
                            ),
                        )
                    )
                    break
            else:
                continue
            break
    return hits


def judge_subject(
    intent: IntentProfile,
    pack2: dict,
    llm: LLMClient | None = None,
) -> SubjectDecision:
    rules = load_subject_rules(pack2)
    by_id = {rule.rule_id: rule for rule in rules}
    logline = intent.logline or ""
    keywords = " ".join(intent.genre_keywords)
    haystacks = {"logline": logline, "genre_keywords": keywords}

    decision = SubjectDecision()
    matched: dict[str, tuple[SubjectRule, MatchedRule]] = {}

    for rule, hit in _pattern_stage(rules, haystacks):
        matched.setdefault(rule.rule_id, (rule, hit))

    if llm is not None and llm.available() and (logline or keywords):
        try:
            reply = llm.structured(
                LLMRequest(
                    prompt_id=PROMPT_ID,
                    prompt_version=PROMPT_VERSION,
                    instruction=INSTRUCTION,
                    document=f"{logline}\n{keywords}".strip(),
                    response_schema=SUBJECT_SCHEMA,
                    temperature=0.2,
                    context={
                        "rules": [
                            {
                                "rule_id": rule.rule_id,
                                "category": rule.category,
                                "is_edge_case": rule.is_edge_case,
                            }
                            for rule in rules
                        ]
                    },
                )
            )
        except UpstreamLLMError:
            decision.pending_flags.append("subject_semantic_check_pending")
        else:
            document = f"{logline}\n{keywords}"
            for raw in reply.get("hits", []) + reply.get("edge_hits", []):
                rule = by_id.get(str(raw.get("rule_id", "")))
                quote = str(raw.get("quote", ""))
                # Only rules we published, only text that really appears.
                if rule is None or not quote or quote not in document:
                    continue
                matched.setdefault(
                    rule.rule_id,
                    (
                        rule,
                        MatchedRule(
                            rule_id=rule.rule_id,
                            quote=quote,
                            confidence=float(raw.get("confidence", 0.5)),
                            stage="semantic",
                        ),
                    ),
                )
    elif logline or keywords:
        decision.pending_flags.append("subject_semantic_check_pending")

    for rule, hit in matched.values():
        if rule.is_edge_case:
            decision.edge_case_hit = True
            decision.edge_rules.append(hit)
        else:
            decision.special_subject_hit = True
            decision.matched_rules.append(hit)
        if rule.expert_pending:
            decision.expert_pending = True
        if rule.clause_ref and rule.clause_ref not in decision.clause_refs:
            decision.clause_refs.append(rule.clause_ref)
        if decision.dept is None and rule.dept_mapping:
            decision.dept = dict(rule.dept_mapping)

    all_hits = decision.matched_rules + decision.edge_rules
    decision.confidence = max((hit.confidence for hit in all_hits), default=0.0)
    if decision.expert_pending:
        decision.pending_flags.append("rules_expert_pending")
    return decision
