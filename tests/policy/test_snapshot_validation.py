from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from policy.validation import SnapshotSemanticError, validate_snapshot
from schemas.policy_snapshot import PolicySnapshot


ROOT = Path(__file__).parents[2]
V1 = ROOT / "policy" / "seed-snapshot-v1.yaml"
V2 = ROOT / "policy" / "seed-snapshot-v2.yaml"


def _payload() -> dict:
    return yaml.safe_load(V2.read_text(encoding="utf-8"))


def _validate(payload: dict) -> PolicySnapshot:
    return validate_snapshot(PolicySnapshot.model_validate(payload))


def test_complete_v2_passes_semantic_validation() -> None:
    snapshot = PolicySnapshot.model_validate(_payload())

    assert validate_snapshot(snapshot) is snapshot


def test_missing_clause_fails_closed() -> None:
    payload = _payload()
    payload["packs"]["p6_legal_clauses"]["clauses"] = []

    with pytest.raises(SnapshotSemanticError, match="missing clause"):
        _validate(payload)


def test_missing_material_fails_closed() -> None:
    payload = _payload()
    payload["packs"]["p4_process_templates"]["templates"]["T2_5steps"][
        "steps"
    ][0]["material_refs"].append("mat_unknown")

    with pytest.raises(SnapshotSemanticError, match="missing material"):
        _validate(payload)


def test_duplicate_material_id_fails_closed() -> None:
    payload = _payload()
    cards = payload["packs"]["p5_form_templates"]["material_cards"]
    cards.append(deepcopy(cards[0]))

    with pytest.raises(SnapshotSemanticError, match="duplicate material_id"):
        _validate(payload)


def test_missing_asset_kind_fails_closed() -> None:
    payload = _payload()
    del payload["packs"]["p5_form_templates"]["material_cards"][0]["asset_kind"]

    with pytest.raises(SnapshotSemanticError, match="asset_kind"):
        _validate(payload)


def test_unsupported_asset_kind_fails_closed() -> None:
    payload = _payload()
    payload["packs"]["p5_form_templates"]["material_cards"][0][
        "asset_kind"
    ] = "unknown_kind"

    with pytest.raises(SnapshotSemanticError, match="asset_kind"):
        _validate(payload)


def test_inverted_thresholds_fail_closed() -> None:
    payload = _payload()
    threshold = payload["packs"]["p3_tier_thresholds"]["threshold_sets"][
        "live_action"
    ]
    threshold["T1_min_rmb"] = threshold["T2_min_rmb"] - 1

    with pytest.raises(SnapshotSemanticError, match="T1_min_rmb"):
        _validate(payload)


def test_published_threshold_missing_boundary_fails_closed() -> None:
    payload = _payload()
    del payload["packs"]["p3_tier_thresholds"]["threshold_sets"][
        "live_action"
    ]["T2_min_rmb"]

    with pytest.raises(SnapshotSemanticError, match="T2_min_rmb"):
        _validate(payload)


def test_missing_roadmap_fails_closed() -> None:
    payload = _payload()
    del payload["packs"]["p4_process_templates"]["templates"]["T2_5steps"]

    with pytest.raises(SnapshotSemanticError, match="T2_5steps"):
        _validate(payload)


def test_missing_required_facts_fails_closed() -> None:
    payload = _payload()
    payload["packs"]["p5_form_templates"]["required_facts"] = []

    with pytest.raises(SnapshotSemanticError, match="required_facts"):
        _validate(payload)


def test_missing_required_material_fails_closed() -> None:
    payload = _payload()
    for card in payload["packs"]["p5_form_templates"]["material_cards"]:
        card["required"] = False

    with pytest.raises(SnapshotSemanticError, match="required material"):
        _validate(payload)


def test_v1_may_keep_empty_process_and_form_packs() -> None:
    payload = yaml.safe_load(V1.read_text(encoding="utf-8"))
    snapshot = PolicySnapshot.model_validate(payload)

    assert validate_snapshot(snapshot) is snapshot
