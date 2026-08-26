"""Material collection card lifecycle (contract step 6, mechanism half).

The card *list* is policy content: it comes from the `p5_form_templates` pack.
The seed pack is empty, so these tests supply their own pack and exercise the
lifecycle — attach, validate, waive — which is what the D3 gate consumes.
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

# The shape this loader accepts. Two cards: one with a clause behind it, one
# without — the second must not claim to be required by law.
CARD_PACK = {
    "required_facts": ["title", "applicant_entity"],
    "material_cards": [
        {
            "material_id": "mat_synopsis",
            "name_key": "material.synopsis",
            "asset_kind": "synopsis",
            "required": True,
            "why_clause_id": "nrta-order-16-article-19",
            "common_rejects_key": "material.synopsis.rejects",
        },
        {
            "material_id": "mat_id_scan",
            "name_key": "material.id_scan",
            "asset_kind": "supporting_document",
            "required": False,
        },
    ],
}


class StubSnapshots(SnapshotService):
    """A one-version snapshot carrying the card pack the seed does not have."""

    def __init__(self, packs: dict) -> None:
        self._packs = packs

    def latest_version(self, as_of: datetime | None = None) -> str:
        return "v1"

    def get_pack(self, name: PackName, version: str | None = None) -> dict:
        return dict(self._packs.get(PackName(name).value, {}))

    def clause(self, clause_id: str, version: str) -> Clause:
        if clause_id != "nrta-order-16-article-19":
            raise SnapshotNotFoundError(f"no such clause: {clause_id}")
        return Clause(
            clause_id=clause_id,
            title="第十九条",
            text="省级主管部门认为确有必要的，应当征求有关主管部门意见。",
            source_url="https://www.nrta.gov.cn/art/2026/7/31/art_113_73785.html",
        )


def make_client(packs: dict, stores, clock) -> TestClient:
    context = AppContext(
        settings=Settings(),
        stores=stores,
        snapshots=StubSnapshots(packs),
        clock=clock,
        llm=UnavailableLLM(),
    )
    return TestClient(create_app(context=context))


@pytest.fixture
def client(stores, clock) -> TestClient:
    return make_client({PackName.P5_FORM_TEMPLATES.value: CARD_PACK}, stores, clock)


@pytest.fixture
def empty_pack_client(stores, clock) -> TestClient:
    return make_client({}, stores, clock)


def new_project(client: TestClient) -> str:
    created = client.post(
        "/v1/projects", json={"title_working": "Operation Fog"}, headers=OWNER
    )
    assert created.status_code == 201
    return created.json()["project_id"]


def materials(client: TestClient, project_id: str) -> list[dict]:
    response = client.get(f"/v1/projects/{project_id}/materials", headers=OWNER)
    assert response.status_code == 200, response.text
    return response.json()


def upload_asset(client: TestClient, project_id: str, kind: str = "synopsis") -> str:
    ticket = client.post(
        f"/v1/projects/{project_id}/assets/upload-url",
        json={"kind": kind},
        headers=OWNER,
    ).json()
    created = client.put(
        ticket["upload_url"], content="a synopsis".encode("utf-8"), headers=OWNER
    )
    assert created.status_code == 201
    return created.json()["version_id"]


# ------------------------------------------------------- the list comes from p5


def test_cards_are_built_from_the_pack(client):
    cards = materials(client, new_project(client))
    assert [card["material_id"] for card in cards] == ["mat_synopsis", "mat_id_scan"]
    assert all(card["status"] == "pending" for card in cards)


def test_cards_expose_the_pack_asset_kind(client):
    cards = materials(client, new_project(client))

    assert {card["material_id"]: card["asset_kind"] for card in cards} == {
        "mat_synopsis": "synopsis",
        "mat_id_scan": "supporting_document",
    }


def test_a_card_with_a_clause_carries_real_evidence(client):
    cards = materials(client, new_project(client))
    synopsis = cards[0]
    assert synopsis["why_clause"]["clause_id"] == "nrta-order-16-article-19"
    assert synopsis["why_clause"]["snapshot_version"] == "v1"


def test_a_card_without_a_clause_does_not_claim_one(client):
    """Ground rule 2: no evidence, no compliance assertion."""

    cards = materials(client, new_project(client))
    assert cards[1]["why_clause"] is None
    assert cards[1]["required"] is False


def test_an_empty_pack_yields_no_cards_rather_than_invented_ones(empty_pack_client):
    project_id = new_project(empty_pack_client)
    assert materials(empty_pack_client, project_id) == []


def test_the_card_list_is_stable_across_reads(client):
    """Re-reading must not mint a second copy of every card."""

    project_id = new_project(client)
    first = materials(client, project_id)
    second = materials(client, project_id)
    assert [card["material_id"] for card in first] == [
        card["material_id"] for card in second
    ]
    assert len(second) == 2


# ----------------------------------------------------------------- attach


def test_attaching_an_asset_moves_the_card_to_uploaded(client):
    project_id = new_project(client)
    version_id = upload_asset(client, project_id)

    attached = client.post(
        f"/v1/projects/{project_id}/materials/mat_synopsis/attach",
        json={"asset_version": version_id},
        headers=OWNER,
    )
    assert attached.status_code == 200
    assert attached.json()["status"] == "uploaded"
    assert attached.json()["asset_version"] == version_id


def test_wrong_asset_kind_is_422_and_does_not_mutate_card(client):
    project_id = new_project(client)
    script_version = upload_asset(client, project_id, "script")

    response = client.post(
        f"/v1/projects/{project_id}/materials/mat_synopsis/attach",
        json={"asset_version": script_version},
        headers=OWNER,
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"] == {
        "expected_kind": "synopsis",
        "actual_kind": "script",
    }
    card = materials(client, project_id)[0]
    assert card["status"] == "pending"
    assert card["asset_version"] is None


def test_attaching_an_unknown_asset_is_a_404(client):
    project_id = new_project(client)
    missing = client.post(
        f"/v1/projects/{project_id}/materials/mat_synopsis/attach",
        json={"asset_version": "av_nope"},
        headers=OWNER,
    )
    assert missing.status_code == 404


def test_another_creator_cannot_attach(client):
    project_id = new_project(client)
    version_id = upload_asset(client, project_id)
    refused = client.post(
        f"/v1/projects/{project_id}/materials/mat_synopsis/attach",
        json={"asset_version": version_id},
        headers=OTHER,
    )
    assert refused.status_code == 403


# ----------------------------------------------------------------- validate


def test_validation_accepts_an_attached_asset_with_bytes(client):
    project_id = new_project(client)
    version_id = upload_asset(client, project_id)
    client.post(
        f"/v1/projects/{project_id}/materials/mat_synopsis/attach",
        json={"asset_version": version_id},
        headers=OWNER,
    )

    validated = client.post(
        f"/v1/projects/{project_id}/materials/mat_synopsis/validate", headers=OWNER
    )
    assert validated.status_code == 200
    assert validated.json()["status"] == "valid"
    assert validated.json()["invalid_reasons"] == []


def test_validating_an_empty_card_reports_why(client):
    project_id = new_project(client)
    validated = client.post(
        f"/v1/projects/{project_id}/materials/mat_synopsis/validate", headers=OWNER
    )
    assert validated.status_code == 200
    assert validated.json()["status"] == "invalid"
    assert validated.json()["invalid_reasons"] == ["no_asset_attached"]


# -------------------------------------------------------------------- waive


def test_waiving_requires_a_reason(client):
    project_id = new_project(client)
    refused = client.post(
        f"/v1/projects/{project_id}/materials/mat_synopsis/waive",
        json={"reason": "   "},
        headers=OWNER,
    )
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a_waived_card_records_who_said_why(client):
    project_id = new_project(client)
    waived = client.post(
        f"/v1/projects/{project_id}/materials/mat_synopsis/waive",
        json={"reason": "供片方已在其他项目提交同一梗概"},
        headers=OWNER,
    )
    assert waived.status_code == 200
    assert waived.json()["status"] == "waived"
    assert waived.json()["waive_reason"].startswith("供片方")


# --------------------------------------------------------------- the D3 gate


def test_the_gate_names_the_unvalidated_required_card(client):
    """No prior visit to the collection page: the gate materialises cards too."""

    project_id = new_project(client)

    gate = client.get(f"/v1/projects/{project_id}/gate", headers=OWNER).json()
    unvalidated = [gap for gap in gate["gaps"] if gap["check"] == "materials_unvalidated"]
    assert unvalidated and unvalidated[0]["items"] == ["mat_synopsis"]


def test_a_waived_card_stops_blocking_the_gate(client):
    project_id = new_project(client)
    client.post(
        f"/v1/projects/{project_id}/materials/mat_synopsis/waive",
        json={"reason": "已在其他项目提交"},
        headers=OWNER,
    )

    gate = client.get(f"/v1/projects/{project_id}/gate", headers=OWNER).json()
    assert not [
        gap for gap in gate["gaps"] if gap["check"] == "materials_unvalidated"
    ]


def test_every_card_change_is_on_the_timeline(client):
    project_id = new_project(client)
    version_id = upload_asset(client, project_id)
    client.post(
        f"/v1/projects/{project_id}/materials/mat_synopsis/attach",
        json={"asset_version": version_id},
        headers=OWNER,
    )
    client.post(
        f"/v1/projects/{project_id}/materials/mat_synopsis/validate", headers=OWNER
    )

    timeline = client.get(f"/v1/projects/{project_id}/timeline", headers=OWNER).json()
    events = [event["event"] for event in timeline]
    assert "material.attached" in events
    assert "material.validated" in events
