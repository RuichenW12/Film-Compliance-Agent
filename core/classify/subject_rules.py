"""Normalize the p2 subject pack into one rule shape.

Two pack shapes are supported:

1. an explicit rule list (`subject_rules: [...]`), the shape the policy loop
   will publish once the partner-reviewed library lands;
2. the v1 seed shape (`special_subject.subjects: [...]`), which names the nine
   statutory categories without trigger text.

For shape 2 we attach an operational keyword list so the demo can match text at
all. Those rules carry `expert_pending=True` (locked decision 5a): the UI shows
a "rules pending expert confirmation" badge and the flag never becomes evidence
on its own - the clause reference does.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Placeholder trigger vocabulary per statutory category. Partner-reviewed rules
# replace this wholesale; nothing here is a legal conclusion by itself.
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "political": ("国家领导人", "党代会", "阅兵", "党委", "政府机关", "换届", "政治运动"),
    "military": ("军队", "部队", "解放军", "军人", "军演", "军衔", "战役", "武警"),
    "diplomatic": ("外交", "大使馆", "领事馆", "建交", "国际谈判", "外事"),
    "national_security": ("国家安全", "间谍", "反间谍", "情报机关", "国家机密", "特工"),
    "united_front": ("统战", "港澳台", "侨务", "民主党派", "政协"),
    "ethnic": ("民族", "少数民族", "民族习俗", "民族地区"),
    "religious": ("宗教", "寺庙", "教堂", "佛教", "道教", "伊斯兰", "基督教", "僧人"),
    "judicial": ("法院", "检察院", "法官", "检察官", "审判", "监狱", "看守所", "庭审"),
    "public_security": ("公安", "警察", "民警", "刑警", "缉毒", "卧底", "派出所", "抓捕", "禁毒"),
}

# Practical contact per category, for the five-field alert. Placeholder text.
CATEGORY_DEPT: dict[str, dict[str, str]] = {
    "political": {"name": "宣传主管部门", "practical_contact": "属地党委宣传部"},
    "military": {"name": "军队政治工作部门", "practical_contact": "属地军事主管机关"},
    "diplomatic": {"name": "外事主管部门", "practical_contact": "属地外办"},
    "national_security": {"name": "国家安全主管部门", "practical_contact": "属地国安机关"},
    "united_front": {"name": "统战主管部门", "practical_contact": "属地统战部"},
    "ethnic": {"name": "民族事务主管部门", "practical_contact": "属地民宗委"},
    "religious": {"name": "宗教事务主管部门", "practical_contact": "属地民宗委"},
    "judicial": {"name": "司法主管部门", "practical_contact": "属地司法行政机关"},
    "public_security": {"name": "公安主管部门", "practical_contact": "属地公安局宣传部门"},
}

DEFAULT_CLAUSE_REF = "nrta-order-16-article-5"


@dataclass(frozen=True)
class SubjectRule:
    rule_id: str
    category: str
    trigger_patterns: tuple[str, ...]
    is_edge_case: bool = False
    tier_effect: str = "T1_mandatory"
    dept_mapping: dict[str, str] = field(default_factory=dict)
    clause_ref: str = DEFAULT_CLAUSE_REF
    expert_pending: bool = False


def _rule_id_for(category: str, index: int) -> str:
    return f"SR-{index:03d}"


def load_subject_rules(pack: dict) -> list[SubjectRule]:
    """Return the rule list for whichever pack shape was published."""

    explicit = pack.get("subject_rules")
    if explicit:
        rules: list[SubjectRule] = []
        for index, raw in enumerate(explicit, start=1):
            category = str(raw.get("category", "unknown"))
            expert_pending = bool(raw.get("expert_pending", False))
            trigger_patterns = list(raw.get("trigger_patterns", ()))
            if expert_pending:
                # An explicit but still-unreviewed rule is not the wholesale
                # partner replacement described above yet. Keep the checked-in
                # operational vocabulary so synthetic fixture coverage does not
                # collapse from "民警/派出所" to the single word "公安". Once the
                # policy loop publishes expert_pending=false, only its reviewed
                # trigger list is used.
                trigger_patterns.extend(CATEGORY_KEYWORDS.get(category, ()))
            rules.append(
                SubjectRule(
                    rule_id=str(raw.get("rule_id") or _rule_id_for(category, index)),
                    category=category,
                    trigger_patterns=tuple(dict.fromkeys(trigger_patterns)),
                    is_edge_case=bool(raw.get("is_edge_case", False)),
                    tier_effect=str(raw.get("tier_effect", "T1_mandatory")),
                    dept_mapping=dict(
                        raw.get("dept_mapping") or CATEGORY_DEPT.get(category, {})
                    ),
                    clause_ref=str(raw.get("clause_ref") or DEFAULT_CLAUSE_REF),
                    expert_pending=expert_pending,
                )
            )
        return rules

    special = pack.get("special_subject") or {}
    subjects = special.get("subjects") or []
    clause_ref = str(special.get("clause_ref") or DEFAULT_CLAUSE_REF)
    rules = []
    for index, category in enumerate(subjects, start=1):
        category = str(category)
        rules.append(
            SubjectRule(
                rule_id=_rule_id_for(category, index),
                category=category,
                trigger_patterns=CATEGORY_KEYWORDS.get(category, ()),
                is_edge_case=False,
                tier_effect="T1_mandatory",
                dept_mapping=CATEGORY_DEPT.get(category, {}),
                clause_ref=clause_ref,
                expert_pending=True,
            )
        )
    return rules
