"""Roadmap preview and confirmation (contract step 5).

The step list is policy content from `p4_process_templates`. Which template a
project gets is already decided by the classification chain (tier → template
name). This covers the product half: build, preview, confirm, transition.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from api.deps.services import AppContext
from api.main import create_app
from api.settings import Settings
from core.llm import UnavailableLLM
from schemas.policy_snapshot import Clause, PackName
from schemas.snapshot import SnapshotNotFoundError, SnapshotService

OWNER = {"X-Mock-Role": "creator", "X-User-Id": "u_owner"}
OTHER = {"X-Mock-Role": "creator", "X-User-Id": "u_other"}

ROMANCE_INTENT = {
    "form_type_claimed": "micro_drama",
    "genre_keywords": ["甜宠"],
    "logline": "总裁与实习生在职场相遇，逐渐走到一起的爱情故事。",
    "episode_count": 30,
    "episode_minutes": 2,
    "budget_band": "band_c",
    "is_ai_generated": False,
}

PROCESS_PACK = {
    "templates": {
        "T3_4steps": {
            "steps": [
                {
                    "name": "roadmap.step.materials",
                    "owner": "creator",
                    "material_refs": ["mat_synopsis"],
                    "est_weeks": 2,
                },
                {"name": "roadmap.step.self_check", "owner": "creator"},
            ]
        }
    }
}

# A p3 pack that leaves thresholds unpublished, matching the seed.
BASE_PACKS = {
    PackName.P1_FORM_DEFINITION.value: {
        "episode_max_minutes_exclusive": 20,
        "continuous_plot_required": True,
    },
    PackName.P2_SUBJECT_RULES.value: {
        "special_subject": {
            "subjects": ["public_security"],
            "clear_hit_outcome": {"tier": "T1", "co_review_required": True},
        }
    },
    PackName.P3_TIER_THRESHOLDS.value: {"thresholds_published": False, "thresholds": None},
    PackName.P6_LEGAL_CLAUSES.value: {},
}


class StubSnapshots(SnapshotService):
    def __init__(self, packs: dict) -> None:
        self._packs = packs

    def latest_version(self, as_of: datetime | None = None) -> str:
        return "v1"

    def get_pack(self, name: PackName, version: str | None = None) -> dict:
        return dict(self._packs.get(PackName(name).value, {}))

    def clause(self, clause_id: str, version: str) -> Clause:
        raise SnapshotNotFoundError(f"no such clause: {clause_id}")


def make_client(extra_packs: dict, stores, clock) -> TestClient:
    context = AppContext(
        settings=Settings(),
        stores=stores,
        snapshots=StubSnapshots({**BASE_PACKS, **extra_packs}),
        clock=clock,
        llm=UnavailableLLM(),
    )
    return TestClient(create_app(context=context))


@pytest.fixture
def client(stores, clock) -> TestClient:
    return make_client(
        {PackName.P4_PROCESS_TEMPLATES.value: PROCESS_PACK}, stores, clock
    )


@pytest.fixture
def empty_pack_client(stores, clock) -> TestClient:
    return make_client({PackName.P4_PROCESS_TEMPLATES.value: {}}, stores, clock)


def classified_project(client: TestClient) -> str:
    created = client.post(
        "/v1/projects", json={"title_working": "Sweet Office"}, headers=OWNER
    )
    project_id = created.json()["project_id"]
    client.post(
        f"/v1/projects/{project_id}/intent", json=ROMANCE_INTENT, headers=OWNER
    )
    classified = client.post(f"/v1/projects/{project_id}/classify", headers=OWNER)
    assert classified.json()["classification"]["tier"] == "T3"
    return project_id


def roadmap_of(client: TestClient, project_id: str) -> dict:
    response = client.get(f"/v1/projects/{project_id}/roadmap", headers=OWNER)
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client: TestClient, project_id: str, headers: dict = OWNER):
    return client.post(f"/v1/projects/{project_id}/roadmap/confirm", headers=headers)


# ------------------------------------------------------- the steps come from p4


def test_the_template_follows_the_tier(client):
    body = roadmap_of(client, classified_project(client))
    assert body["roadmap"]["template"] == "T3_4steps"


def test_steps_are_built_from_the_pack_in_order(client):
    body = roadmap_of(client, classified_project(client))
    steps = body["roadmap"]["steps"]
    assert [step["idx"] for step in steps] == [1, 2]
    assert steps[0]["name"] == "roadmap.step.materials"
    assert steps[0]["material_refs"] == ["mat_synopsis"]
    assert steps[0]["est_weeks"] == 2
    assert body["pending_flags"] == []


def test_an_empty_pack_yields_no_steps_and_says_so(empty_pack_client):
    """No invented plan. The gap is reported, not filled."""

    body = roadmap_of(empty_pack_client, classified_project(empty_pack_client))
    assert body["roadmap"]["steps"] == []
    assert body["pending_flags"] == ["roadmap_template_pending"]


def test_an_unclassified_project_has_no_roadmap_yet(client):
    created = client.post(
        "/v1/projects", json={"title_working": "Draft"}, headers=OWNER
    )
    project_id = created.json()["project_id"]
    body = roadmap_of(client, project_id)
    assert body["roadmap"] is None
    assert body["pending_flags"] == ["classification_pending"]


# ------------------------------------------------------------------- confirm


def test_confirming_moves_the_project_to_roadmap_confirmed(client):
    project_id = classified_project(client)
    response = confirm(client, project_id)

    assert response.status_code == 200
    assert response.json()["roadmap"]["confirmed"] is True
    assert response.json()["state"] == "ROADMAP_CONFIRMED"

    project = client.get(f"/v1/projects/{project_id}", headers=OWNER).json()
    assert project["project"]["state"] == "ROADMAP_CONFIRMED"
    assert project["project"]["roadmap"]["confirmed"] is True


def test_confirming_an_unclassified_project_is_refused(client):
    created = client.post(
        "/v1/projects", json={"title_working": "Draft"}, headers=OWNER
    )
    refused = confirm(client, created.json()["project_id"])
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] in ("STATE_INVALID", "CONFLICT")


def test_confirming_an_empty_roadmap_still_reports_the_gap(empty_pack_client):
    """The path must not be blocked on unpublished policy, only flagged."""

    project_id = classified_project(empty_pack_client)
    response = confirm(empty_pack_client, project_id)

    assert response.status_code == 200
    assert response.json()["roadmap"]["confirmed"] is True
    assert response.json()["pending_flags"] == ["roadmap_template_pending"]


def test_confirming_twice_is_idempotent(client):
    project_id = classified_project(client)
    assert confirm(client, project_id).status_code == 200
    second = confirm(client, project_id)

    assert second.status_code == 200
    assert second.json()["state"] == "ROADMAP_CONFIRMED"

    timeline = client.get(f"/v1/projects/{project_id}/timeline", headers=OWNER).json()
    confirmed = [e for e in timeline if e["event"] == "roadmap.confirmed"]
    assert len(confirmed) == 1


def test_another_creator_cannot_confirm(client):
    project_id = classified_project(client)
    assert confirm(client, project_id, OTHER).status_code == 403


def test_the_confirmation_is_on_the_timeline(client):
    project_id = classified_project(client)
    confirm(client, project_id)

    timeline = client.get(f"/v1/projects/{project_id}/timeline", headers=OWNER).json()
    confirmed = [e for e in timeline if e["event"] == "roadmap.confirmed"]
    assert confirmed[0]["detail"]["template"] == "T3_4steps"
    assert confirmed[0]["detail"]["step_count"] == 2
