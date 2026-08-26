from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from api.main import create_app
from policy.validation import SnapshotSemanticError
from schemas.policy_snapshot import PackName, PolicySnapshot, VerificationStatus
from schemas.snapshot import FileSnapshotService


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


def test_file_service_rejects_semantically_invalid_v2(tmp_path: Path) -> None:
    payload = yaml.safe_load(V2.read_text(encoding="utf-8"))
    payload["packs"]["p4_process_templates"]["templates"] = {}
    invalid = tmp_path / "invalid-v2.yaml"
    invalid.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")

    with pytest.raises(SnapshotSemanticError, match="T1_7steps"):
        FileSnapshotService(invalid)


def test_default_app_starts_from_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SNAPSHOT_SEED_PATH", raising=False)

    with TestClient(create_app()) as client:
        health = client.get("/healthz").json()

    assert health["snapshot_version"] == "v2"
