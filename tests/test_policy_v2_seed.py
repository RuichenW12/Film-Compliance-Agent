from pathlib import Path

import yaml

from schemas.policy_snapshot import PackName, PolicySnapshot, VerificationStatus


ROOT = Path(__file__).parents[1]
V2 = ROOT / "policy" / "seed-snapshot-v2.yaml"


def _snapshot() -> PolicySnapshot:
    return PolicySnapshot.model_validate(yaml.safe_load(V2.read_text(encoding="utf-8")))


def test_v2_seed_is_complete_and_mock_verified() -> None:
    snapshot = _snapshot()

    assert snapshot.version == "v2"
    assert snapshot.verification_status is VerificationStatus.MOCK_VERIFIED
    for name in PackName:
        assert getattr(snapshot.packs, name.value)


def test_v2_contains_all_runtime_templates_and_cards() -> None:
    snapshot = _snapshot()
    p4 = snapshot.packs.p4_process_templates
    p5 = snapshot.packs.p5_form_templates

    assert set(p4["templates"]) == {"T1_7steps", "T2_5steps", "T3_4steps"}
    assert {card["asset_kind"] for card in p5["material_cards"]} == {
        "synopsis",
        "script",
        "supporting_document",
        "prompts",
        "subtitle_sheet",
    }
