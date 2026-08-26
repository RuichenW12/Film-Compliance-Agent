"""Cross-pack policy snapshot invariants that schema validation cannot express."""

from __future__ import annotations

from schemas.policy_snapshot import PackName, PolicySnapshot


class SnapshotSemanticError(ValueError):
    """A snapshot is structurally valid but internally inconsistent."""


SUPPORTED_MATERIAL_ASSET_KINDS = {
    "synopsis",
    "script",
    "supporting_document",
    "prompts",
    "subtitle_sheet",
}


def _complete_version(version: str) -> bool:
    return int(version[1:]) >= 2


def validate_snapshot(snapshot: PolicySnapshot) -> PolicySnapshot:
    """Return the snapshot or fail closed on a cross-pack inconsistency."""

    packs = snapshot.packs.model_dump(mode="python")
    clauses = {
        str(item["clause_id"])
        for item in packs[PackName.P6_LEGAL_CLAUSES.value].get("clauses", [])
        if item.get("clause_id")
    }
    cards = packs[PackName.P5_FORM_TEMPLATES.value].get("material_cards", []) or []
    card_ids = [str(card.get("material_id", "")) for card in cards]
    if len(card_ids) != len(set(card_ids)):
        raise SnapshotSemanticError("duplicate material_id")

    for card in cards:
        kind = card.get("asset_kind")
        if kind not in SUPPORTED_MATERIAL_ASSET_KINDS:
            raise SnapshotSemanticError("unsupported or missing asset_kind")

    referenced_clauses: list[str] = []
    p1 = packs[PackName.P1_FORM_DEFINITION.value]
    if p1.get("clause_ref"):
        referenced_clauses.append(str(p1["clause_ref"]))
    for rule in packs[PackName.P2_SUBJECT_RULES.value].get("subject_rules", []) or []:
        if rule.get("clause_ref"):
            referenced_clauses.append(str(rule["clause_ref"]))

    p3 = packs[PackName.P3_TIER_THRESHOLDS.value]
    for threshold_set in (p3.get("threshold_sets") or {}).values():
        if p3.get("thresholds_published"):
            missing_fields = {
                "T1_min_rmb",
                "T2_min_rmb",
                "clause_ref",
            } - set(threshold_set)
            if missing_fields:
                raise SnapshotSemanticError(
                    f"published threshold set missing: {sorted(missing_fields)}"
                )
        if threshold_set.get("clause_ref"):
            referenced_clauses.append(str(threshold_set["clause_ref"]))
        if int(threshold_set.get("T1_min_rmb", -1)) < int(
            threshold_set.get("T2_min_rmb", -1)
        ):
            raise SnapshotSemanticError("T1_min_rmb must be >= T2_min_rmb")

    for card in cards:
        if card.get("why_clause_id"):
            referenced_clauses.append(str(card["why_clause_id"]))
    missing = sorted(set(referenced_clauses) - clauses)
    if missing:
        raise SnapshotSemanticError(f"missing clause references: {missing}")

    templates = packs[PackName.P4_PROCESS_TEMPLATES.value].get("templates", {}) or {}
    for name, definition in templates.items():
        for step in definition.get("steps", []) or []:
            unknown = sorted(set(step.get("material_refs", []) or []) - set(card_ids))
            if unknown:
                raise SnapshotSemanticError(
                    f"{name} references missing material: {unknown}"
                )

    if _complete_version(snapshot.version):
        for required in ("T1_7steps", "T2_5steps", "T3_4steps"):
            if not (templates.get(required) or {}).get("steps"):
                raise SnapshotSemanticError(f"missing roadmap template: {required}")
        if not packs[PackName.P5_FORM_TEMPLATES.value].get("required_facts"):
            raise SnapshotSemanticError("v2 requires required_facts")
        if not any(card.get("required") for card in cards):
            raise SnapshotSemanticError("v2 requires at least one required material")
        if p3.get("thresholds_published") and not p3.get("threshold_sets"):
            raise SnapshotSemanticError("published thresholds require threshold_sets")
    return snapshot
