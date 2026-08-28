"""Gate passage, form preview, field confirmation, and freeze (contract step 11).

The rule the whole file exists to protect: a form field is filled only where a
confirmed fact backs it. Everything else renders as 待补充, and freezing hashes
what is actually there — so a submitted form is verifiable against the policy it
was prepared under, and can never contain a value nobody sourced.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from api.deps.services import AppContext
from api.main import create_app
from api.settings import Settings
from core.llm import UnavailableLLM
from schemas.forms import PENDING_DISPLAY
from schemas.policy_snapshot import Clause, PackName
from schemas.snapshot import SnapshotNotFoundError, SnapshotService

OWNER = {"X-Mock-Role": "creator", "X-User-Id": "u_owner"}
OTHER = {"X-Mock-Role": "creator", "X-User-Id": "u_other"}

# Two fields keeps the fixtures readable; the mechanism does not care how many.
FORM_PACK = {"required_facts": ["title", "applicant_entity"]}

ROMANCE_INTENT = {
    "form_type_claimed": "micro_drama",
    "genre_keywords": ["甜宠"],
    "synopsis": "总裁与实习生在职场相遇，逐渐走到一起的爱情故事。",
    "episode_count": 30,
    "episode_minutes": 2,
    "amount_bracket": "below_lower",
    "is_ai_generated": False,
}


class StubSnapshots(SnapshotService):
    """The seed, with p5 carrying a two-field form definition."""

    def __init__(self, base: SnapshotService) -> None:
        self._base = base

    def latest_version(self, as_of: datetime | None = None) -> str:
        return self._base.latest_version(as_of)

    def get_pack(self, name: PackName, version: str | None = None) -> dict:
        if PackName(name) is PackName.P5_FORM_TEMPLATES:
            return dict(FORM_PACK)
        return self._base.get_pack(name, version)

    def clause(self, clause_id: str, version: str) -> Clause:
        return self._base.clause(clause_id, version)


@pytest.fixture
def client(stores, snapshots, clock) -> TestClient:
    context = AppContext(
        settings=Settings(),
        stores=stores,
        snapshots=StubSnapshots(snapshots),
        clock=clock,
        llm=UnavailableLLM(),
    )
    return TestClient(create_app(context=context))


def new_project(client: TestClient) -> str:
    created = client.post(
        "/v1/projects", json={"title_working": "Sweet Office"}, headers=OWNER
    )
    project_id = created.json()["project_id"]
    client.post(
        f"/v1/projects/{project_id}/intent", json=ROMANCE_INTENT, headers=OWNER
    )
    client.post(f"/v1/projects/{project_id}/classify", headers=OWNER)
    return project_id


def form_of(client: TestClient, project_id: str) -> dict:
    response = client.get(f"/v1/projects/{project_id}/form", headers=OWNER)
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client: TestClient, project_id: str, key: str, value):
    return client.post(
        f"/v1/projects/{project_id}/form/fields/{key}/confirm",
        json={"value": value},
        headers=OWNER,
    )


CLEAN_SCRIPT = "第一集 场景一：咖啡厅。实习生林悦第一次见到总裁。\n"


def run_precheck(client: TestClient, project_id: str) -> None:
    """The gate is only reachable after a pre-check: collect, review, gate."""

    ticket = client.post(
        f"/v1/projects/{project_id}/assets/upload-url",
        json={"kind": "script"},
        headers=OWNER,
    ).json()
    client.put(
        ticket["upload_url"], content=CLEAN_SCRIPT.encode("utf-8"), headers=OWNER
    )
    reviewed = client.post(f"/v1/projects/{project_id}/review", headers=OWNER)
    assert reviewed.status_code == 200, reviewed.text


def ready_to_freeze(client: TestClient) -> str:
    """Walk the whole path: confirm the roadmap, pre-check, fill, pass."""

    project_id = new_project(client)
    started = client.post(f"/v1/projects/{project_id}/roadmap/confirm", headers=OWNER)
    assert started.status_code == 200, started.text
    run_precheck(client, project_id)
    confirm(client, project_id, "title", "迷雾行动")
    confirm(client, project_id, "applicant_entity", "星河影视文化有限公司")
    passed = client.post(f"/v1/projects/{project_id}/gate/pass", headers=OWNER)
    assert passed.status_code == 200, passed.text
    return project_id


# --------------------------------------------------------------- the preview


def test_an_unsourced_field_renders_as_pending(client):
    fields = form_of(client, new_project(client))["fields"]
    assert set(fields) == {"title", "applicant_entity"}
    assert all(field["status"] == "pending" for field in fields.values())
    assert all(field["value"] is None for field in fields.values())


def test_the_pending_marker_is_the_chinese_placeholder():
    assert PENDING_DISPLAY == "待补充"


def test_the_field_list_comes_from_the_pack(client):
    """Gate and form read the same `required_facts`, so they cannot disagree."""

    project_id = new_project(client)
    gate = client.get(f"/v1/projects/{project_id}/gate", headers=OWNER).json()
    missing = [g for g in gate["gaps"] if g["check"] == "facts_missing"][0]["items"]
    assert set(missing) == set(form_of(client, project_id)["fields"])


def test_the_draft_pins_the_snapshot_it_was_built_under(client):
    assert form_of(client, new_project(client))["snapshot_version"] == "v1"


# ------------------------------------------------------------- confirmation


def test_a_confirmed_field_carries_its_provenance(client):
    project_id = new_project(client)
    response = confirm(client, project_id, "title", "迷雾行动")

    assert response.status_code == 200
    field = response.json()["fields"]["title"]
    assert field["status"] == "filled"
    assert field["value"] == "迷雾行动"
    assert field["source_ref"]["type"] == "user_answer"
    assert field["source_ref"]["answer_id"]


def test_an_empty_confirmation_is_refused(client):
    project_id = new_project(client)
    refused = confirm(client, project_id, "title", "")
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "VALIDATION_ERROR"


def test_confirming_a_field_the_form_does_not_have_is_a_404(client):
    project_id = new_project(client)
    missing = confirm(client, project_id, "not_a_field", "x")
    assert missing.status_code == 404


def test_another_creator_cannot_confirm(client):
    project_id = new_project(client)
    refused = client.post(
        f"/v1/projects/{project_id}/form/fields/title/confirm",
        json={"value": "x"},
        headers=OTHER,
    )
    assert refused.status_code == 403


def test_confirmation_is_on_the_timeline(client):
    project_id = new_project(client)
    confirm(client, project_id, "title", "迷雾行动")

    timeline = client.get(f"/v1/projects/{project_id}/timeline", headers=OWNER).json()
    confirmed = [e for e in timeline if e["event"] == "form.field_confirmed"]
    assert confirmed and confirmed[0]["detail"]["key"] == "title"


# ---------------------------------------------------------------- the gate


def test_the_gate_refuses_with_the_gaps_it_found(client):
    project_id = new_project(client)
    refused = client.post(f"/v1/projects/{project_id}/gate/pass", headers=OWNER)

    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "GATE_BLOCKED"
    checks = {gap["check"] for gap in refused.json()["error"]["details"]["gaps"]}
    assert "facts_missing" in checks


def test_the_gate_says_a_pre_check_is_missing_rather_than_leaking_the_table(client):
    """A creator needs to know what to do next, not the transition names."""

    project_id = new_project(client)
    client.post(f"/v1/projects/{project_id}/roadmap/confirm", headers=OWNER)
    confirm(client, project_id, "title", "迷雾行动")
    confirm(client, project_id, "applicant_entity", "星河影视文化有限公司")

    refused = client.post(f"/v1/projects/{project_id}/gate/pass", headers=OWNER)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "STATE_INVALID"
    assert "pre-check" in refused.json()["error"]["message"]


def test_passing_the_gate_moves_the_state(client):
    project_id = ready_to_freeze(client)
    project = client.get(f"/v1/projects/{project_id}", headers=OWNER).json()
    assert project["project"]["state"] == "GATE_D3_PASSED"


def test_passing_twice_is_idempotent(client):
    project_id = ready_to_freeze(client)
    again = client.post(f"/v1/projects/{project_id}/gate/pass", headers=OWNER)
    assert again.status_code == 200
    assert again.json()["state"] == "GATE_D3_PASSED"


# -------------------------------------------------------------------- freeze


def test_freezing_before_the_gate_is_refused(client):
    project_id = new_project(client)
    refused = client.post(f"/v1/projects/{project_id}/form/freeze", headers=OWNER)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "STATE_INVALID"


def test_a_frozen_form_carries_a_hash_and_moves_the_state(client):
    project_id = ready_to_freeze(client)
    frozen = client.post(f"/v1/projects/{project_id}/form/freeze", headers=OWNER)

    assert frozen.status_code == 200
    body = frozen.json()
    assert body["frozen"] is True
    assert len(body["hash"]) == 64
    assert body["confirmed_by_user_at"]

    project = client.get(f"/v1/projects/{project_id}", headers=OWNER).json()
    assert project["project"]["state"] == "FORM_FROZEN"


def test_the_hash_covers_the_values(client):
    """Two projects with different answers must not hash alike."""

    first = ready_to_freeze(client)
    hash_one = client.post(
        f"/v1/projects/{first}/form/freeze", headers=OWNER
    ).json()["hash"]

    second = new_project(client)
    client.post(f"/v1/projects/{second}/roadmap/confirm", headers=OWNER)
    run_precheck(client, second)
    confirm(client, second, "title", "另一个片名")
    confirm(client, second, "applicant_entity", "星河影视文化有限公司")
    client.post(f"/v1/projects/{second}/gate/pass", headers=OWNER)
    hash_two = client.post(
        f"/v1/projects/{second}/form/freeze", headers=OWNER
    ).json()["hash"]

    assert hash_one != hash_two


def test_freezing_twice_returns_the_same_frozen_draft(client):
    project_id = ready_to_freeze(client)
    first = client.post(f"/v1/projects/{project_id}/form/freeze", headers=OWNER).json()
    second = client.post(f"/v1/projects/{project_id}/form/freeze", headers=OWNER).json()

    assert first["hash"] == second["hash"]
    assert first["draft_id"] == second["draft_id"]


def test_a_frozen_form_cannot_be_edited(client):
    project_id = ready_to_freeze(client)
    client.post(f"/v1/projects/{project_id}/form/freeze", headers=OWNER)

    refused = confirm(client, project_id, "title", "改个名字")
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "CONFLICT"


def test_reading_a_frozen_form_returns_the_frozen_one(client):
    project_id = ready_to_freeze(client)
    frozen = client.post(
        f"/v1/projects/{project_id}/form/freeze", headers=OWNER
    ).json()

    assert form_of(client, project_id)["hash"] == frozen["hash"]


def test_the_freeze_is_on_the_timeline(client):
    project_id = ready_to_freeze(client)
    frozen = client.post(
        f"/v1/projects/{project_id}/form/freeze", headers=OWNER
    ).json()

    timeline = client.get(f"/v1/projects/{project_id}/timeline", headers=OWNER).json()
    events = [e for e in timeline if e["event"] == "form.frozen"]
    assert events and events[0]["detail"]["hash"] == frozen["hash"]
