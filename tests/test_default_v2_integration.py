"""Default local policy v2 proves the creator workflow without live services."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import create_app


OWNER = {"X-Mock-Role": "creator", "X-User-Id": "u_owner"}


def upload(client: TestClient, project_id: str, kind: str, content: bytes) -> str:
    ticket_response = client.post(
        f"/v1/projects/{project_id}/assets/upload-url",
        json={"kind": kind},
        headers=OWNER,
    )
    assert ticket_response.status_code == 200, ticket_response.text
    ticket = ticket_response.json()
    response = client.put(ticket["upload_url"], content=content, headers=OWNER)
    assert response.status_code == 201, response.text
    return response.json()["version_id"]


def test_default_mock_v2_reaches_gate_and_frozen_form(monkeypatch) -> None:
    """The repository default is complete enough for deterministic integration."""

    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("VERTEX_MODEL_GEMINI", raising=False)
    monkeypatch.delenv("SNAPSHOT_SEED_PATH", raising=False)

    with TestClient(create_app()) as client:
        health = client.get("/healthz").json()
        assert health["snapshot_version"] == "v2"
        assert health["snapshot_verification_status"] == "mock_verified"

        created = client.post(
            "/v1/projects",
            json={"title_working": "联调项目"},
            headers=OWNER,
        )
        assert created.status_code == 201, created.text
        project_id = created.json()["project_id"]

        intent = client.post(
            f"/v1/projects/{project_id}/intent",
            json={
                "form_type_claimed": "micro_drama",
                "genre_keywords": ["都市"],
                "synopsis": "两位创业者共同完成一部作品。",
                "episode_count": 20,
                "episode_minutes": 3,
                "amount_bracket": "between",
                "investment_amount_rmb": 1_500_000,
                "is_ai_generated": False,
            },
            headers=OWNER,
        )
        assert intent.status_code == 200, intent.text

        classified_response = client.post(
            f"/v1/projects/{project_id}/classify", headers=OWNER
        )
        assert classified_response.status_code == 200, classified_response.text
        classified = classified_response.json()["classification"]
        assert (classified["tier"], classified["tier_provisional"]) == (
            "T2",
            False,
        )
        assert classified["policy_verification_status"] == "mock_verified"

        roadmap = client.post(
            f"/v1/projects/{project_id}/roadmap/confirm", headers=OWNER
        )
        assert roadmap.status_code == 200, roadmap.text

        versions = {
            "mat_synopsis": upload(client, project_id, "synopsis", b"synopsis"),
            "mat_script": upload(
                client,
                project_id,
                "script",
                "第一集 场景一：办公室。两位创业者讨论作品。".encode(),
            ),
        }
        for material_id, version_id in versions.items():
            attached = client.post(
                f"/v1/projects/{project_id}/materials/{material_id}/attach",
                json={"asset_version": version_id},
                headers=OWNER,
            )
            assert attached.status_code == 200, attached.text
            validated = client.post(
                f"/v1/projects/{project_id}/materials/{material_id}/validate",
                headers=OWNER,
            )
            assert validated.status_code == 200, validated.text
            assert validated.json()["status"] == "valid"

        reviewed = client.post(f"/v1/projects/{project_id}/review", headers=OWNER)
        assert reviewed.status_code == 200, reviewed.text

        for key, value in {
            "title": "联调项目",
            "applicant_entity": "联调主体",
        }.items():
            confirmed = client.post(
                f"/v1/projects/{project_id}/form/fields/{key}/confirm",
                json={"value": value},
                headers=OWNER,
            )
            assert confirmed.status_code == 200, confirmed.text

        passed = client.post(f"/v1/projects/{project_id}/gate/pass", headers=OWNER)
        assert passed.status_code == 200, passed.text

        frozen_response = client.post(
            f"/v1/projects/{project_id}/form/freeze", headers=OWNER
        )
        assert frozen_response.status_code == 200, frozen_response.text
        frozen = frozen_response.json()
        assert frozen["frozen"] is True
        assert frozen["snapshot_version"] == "v2"
