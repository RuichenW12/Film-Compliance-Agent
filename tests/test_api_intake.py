"""API-level checks for the intake and classification routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.deps.services import AppContext
from api.main import create_app
from api.settings import Settings
from core.llm import UnavailableLLM

INTERNAL_TOKEN = "t_test_internal"

CRIME_INTENT = {
    "form_type_claimed": "micro_drama",
    "genre_keywords": ["缉毒", "卧底"],
    "logline": "卧底警察深入毒枭内部，在缉毒行动中面临身份暴露的危机。",
    "episode_count": 24,
    "episode_minutes": 3,
    "budget_band": "band_b",
    "is_ai_generated": True,
    "has_finished_film": False,
}

ROMANCE_INTENT = {
    "form_type_claimed": "micro_drama",
    "genre_keywords": ["甜宠"],
    "logline": "总裁与实习生在职场相遇，逐渐走到一起的爱情故事。",
    "episode_count": 30,
    "episode_minutes": 2,
    "budget_band": "band_c",
    "is_ai_generated": False,
}


@pytest.fixture
def client(stores, snapshots, clock) -> TestClient:
    context = AppContext(
        settings=Settings(internal_token=INTERNAL_TOKEN),
        stores=stores,
        snapshots=snapshots,
        clock=clock,
        llm=UnavailableLLM(),
    )
    return TestClient(create_app(context=context))


def create_project(client: TestClient) -> str:
    response = client.post("/v1/projects", json={"title_working": "迷雾行动"})
    assert response.status_code == 201
    return response.json()["project_id"]


def test_healthz_reports_the_pinned_snapshot(client):
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["snapshot_version"] == "v1"
    assert body["snapshot_verification_status"] == "mock_verified"


def test_full_intake_to_classification(client):
    project_id = create_project(client)

    intent = client.post(f"/v1/projects/{project_id}/intent", json=CRIME_INTENT)
    assert intent.status_code == 200
    assert intent.json() == {"state": "INTAKE_DONE", "missing": []}

    channels = client.post(
        f"/v1/projects/{project_id}/channels",
        json={"domestic_platforms": ["hongguo", "douyin"], "overseas": []},
    )
    assert channels.json()["tracks_enabled"] == {"china": True, "us": False}

    classified = client.post(f"/v1/projects/{project_id}/classify")
    assert classified.status_code == 200
    body = classified.json()
    assert body["classification"]["tier"] == "T1"
    assert body["classification"]["co_review_required"] is True
    assert body["classification"]["policy_snapshot_version"] == "v1"
    assert body["state"] == "CLASSIFIED"

    timeline = client.get(f"/v1/projects/{project_id}/timeline").json()
    events = [event["event"] for event in timeline]
    assert "project.created" in events
    assert "state.CLASSIFIED" in events


def test_partial_intent_reports_what_is_missing(client):
    project_id = create_project(client)
    response = client.post(
        f"/v1/projects/{project_id}/intent", json={"logline": "一个故事"}
    )
    assert response.json()["missing"] == ["episode_count", "episode_minutes"]


def test_intent_accepts_and_persists_exact_investment_amount(client):
    project_id = create_project(client)
    response = client.post(
        f"/v1/projects/{project_id}/intent",
        json={**ROMANCE_INTENT, "investment_amount_rmb": 1_500_000},
    )

    assert response.status_code == 200
    project = client.get(f"/v1/projects/{project_id}").json()["project"]
    assert project["intent_profile"]["investment_amount_rmb"] == 1_500_000


def test_intent_rejects_a_negative_exact_investment_amount(client):
    project_id = create_project(client)
    response = client.post(
        f"/v1/projects/{project_id}/intent",
        json={**ROMANCE_INTENT, "investment_amount_rmb": -1},
    )

    assert response.status_code == 422
    errors = response.json()["error"]["details"]["errors"]
    assert errors[0]["loc"][-1] == "investment_amount_rmb"
    assert errors[0]["type"] == "greater_than_equal"


def test_classification_projects_exact_amount_as_a_user_answer_fact(client):
    project_id = create_project(client)
    client.post(
        f"/v1/projects/{project_id}/intent",
        json={**ROMANCE_INTENT, "investment_amount_rmb": 1_500_000},
    )
    client.post(f"/v1/projects/{project_id}/classify")

    facts = client.get(f"/v1/projects/{project_id}/facts").json()
    amount = next(fact for fact in facts if fact["key"] == "investment_amount_rmb")
    assert amount["value"] == 1_500_000
    assert amount["source_ref"]["answer_id"] == "intent.investment_amount_rmb"


def test_classify_without_enough_answers_returns_state_invalid(client):
    project_id = create_project(client)
    client.post(f"/v1/projects/{project_id}/intent", json={"logline": "一个故事"})

    response = client.post(f"/v1/projects/{project_id}/classify")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "STATE_INVALID"
    assert "episode_count" in error["details"]["missing"]


def test_unknown_project_returns_the_error_envelope(client):
    response = client.get("/v1/projects/proj_missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_another_creator_may_not_read_the_project(client):
    project_id = create_project(client)
    response = client.get(
        f"/v1/projects/{project_id}", headers={"X-User-Id": "u_someone_else"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_institution_role_may_not_create_projects(client):
    response = client.post(
        "/v1/projects", json={}, headers={"X-Mock-Role": "institution"}
    )
    assert response.status_code == 403


def test_tier_choice_reruns_d1c(client):
    project_id = create_project(client)
    client.post(f"/v1/projects/{project_id}/intent", json=ROMANCE_INTENT)
    first = client.post(f"/v1/projects/{project_id}/classify").json()
    assert first["classification"]["tier"] == "T3"

    second = client.post(
        f"/v1/projects/{project_id}/tier-choice", json={"budget_band": "band_a"}
    ).json()
    assert second["classification"]["tier"] == "T1"
    assert second["classification"]["tier_provisional"] is True


def test_gate_reports_machine_readable_gaps(client):
    project_id = create_project(client)
    client.post(f"/v1/projects/{project_id}/intent", json=CRIME_INTENT)
    client.post(f"/v1/projects/{project_id}/classify")

    gate = client.get(f"/v1/projects/{project_id}/gate").json()
    assert gate["passed"] is False
    checks = {gap["check"] for gap in gate["gaps"]}
    assert "facts_missing" in checks


def test_recalc_tier_requires_the_internal_token(client):
    project_id = create_project(client)
    response = client.post(
        f"/v1/internal/projects/{project_id}/recalc-tier",
        json={"snapshot_version": "v1"},
    )
    assert response.status_code == 403


def test_recalc_tier_only_touches_provisional_projects(client, monkeypatch):
    """A settled tier is left alone. Since the seed's subject rules are still
    unconfirmed, a special-subject project is provisional (D-026), so this uses
    a project whose tier really is final."""

    project_id = create_project(client)
    client.post(f"/v1/projects/{project_id}/intent", json=CRIME_INTENT)
    client.post(f"/v1/projects/{project_id}/classify")

    stored = client.app.state.context.stores.projects.get(project_id)
    settled = stored.classification.model_copy(update={"tier_provisional": False})
    client.app.state.context.stores.projects.save(
        stored.model_copy(update={"classification": settled})
    )

    response = client.post(
        f"/v1/internal/projects/{project_id}/recalc-tier",
        json={"snapshot_version": "v1"},
        headers={"X-Internal-Token": INTERNAL_TOKEN},
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {"tier": "T1", "tier_provisional": False, "changed": False}
    assert response.headers["X-Recalc-Reason"] == "not_provisional"


def test_recalc_tier_response_matches_the_shared_contract(client):
    from schemas.policy_snapshot import RecalcTierResponse

    project_id = create_project(client)
    client.post(f"/v1/projects/{project_id}/intent", json=ROMANCE_INTENT)
    client.post(f"/v1/projects/{project_id}/classify")

    response = client.post(
        f"/v1/internal/projects/{project_id}/recalc-tier",
        json={"snapshot_version": "v1"},
        headers={"X-Internal-Token": INTERNAL_TOKEN},
    )
    # The policy loop parses this body with extra="forbid": no stray fields.
    parsed = RecalcTierResponse.model_validate(response.json())
    assert parsed.tier == "T3"
    assert parsed.tier_provisional is True


def test_policy_stale_flag_never_changes_the_classification(client):
    project_id = create_project(client)
    client.post(f"/v1/projects/{project_id}/intent", json=CRIME_INTENT)
    before = client.post(f"/v1/projects/{project_id}/classify").json()

    stale = client.post(
        f"/v1/internal/projects/{project_id}/policy-stale",
        json={"snapshot_version": "v2"},
        headers={"X-Internal-Token": INTERNAL_TOKEN},
    )
    assert stale.json()["policy_stale"] is True

    after = client.get(f"/v1/projects/{project_id}").json()["project"]
    assert after["policy_stale"] is True
    assert after["classification"]["tier"] == before["classification"]["tier"]


def test_unknown_snapshot_version_is_a_clean_404(client):
    """The policy loop may name a version the product cannot read yet."""

    project_id = create_project(client)
    client.post(f"/v1/projects/{project_id}/intent", json=ROMANCE_INTENT)
    client.post(f"/v1/projects/{project_id}/classify")

    response = client.post(
        f"/v1/internal/projects/{project_id}/recalc-tier",
        json={"snapshot_version": "v99"},
        headers={"X-Internal-Token": INTERNAL_TOKEN},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert "v99" in response.json()["error"]["message"]
