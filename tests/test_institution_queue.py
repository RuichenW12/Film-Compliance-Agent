"""A reviewer has to be able to find work.

`ProjectStore.list_all` existed as a port method that nothing called, so the
institution console could open a project only when somebody handed over its id.
That makes it a lookup tool rather than an inbox, and it is the reason the
reviewer side felt unbuilt when in fact every route behind it worked.

These tests pin what the queue is for: it shows the two states an institution
owns, it shows them newest first, it does not leak a creator's projects to
another creator, and it never invents a title for a project that has none.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.deps.services import AppContext
from api.main import create_app
from api.settings import Settings
from core.llm import UnavailableLLM

CREATOR = {"X-Mock-Role": "creator", "X-User-Id": "u_demo"}
INSTITUTION = {"X-Mock-Role": "institution"}
ADMIN = {"X-Mock-Role": "admin"}

SCRIPT = "第一场 便利店 夜 内\n林小满站在收银台后。\n"

INTENT = {
    "form_type_claimed": "micro_drama",
    "genre_keywords": ["都市"],
    "synopsis": "一个刚毕业的女孩在便利店打工，遇到常来买咖啡的程序员。",
    "episode_count": 24,
    "episode_minutes": 3,
    "amount_bracket": "below_lower",
    "is_ai_generated": True,
    "production_stage": "idea",
    "platform_promoted": False,
    "voluntary_key_declaration": False,
}

INSTITUTIONS = [
    {
        "institution_id": "inst_demo",
        "name": "待补充",
        "license_no": "待补充",
        "valid_until": "2027-12-31",
        "registered_capital_rmb": 5_000_000,
        "has_foreign": False,
    }
]



@pytest.fixture
def client(stores, snapshots, clock) -> TestClient:
    """No LLM: the queue is plumbing, and the pre-check is covered elsewhere.

    `UnavailableLLM` makes the review stage report a pending flag rather than
    findings, which is the documented behaviour for a missing backend and does
    not block the freeze this file needs.
    """

    context = AppContext(
        settings=Settings(),
        stores=stores,
        snapshots=snapshots,
        clock=clock,
        llm=UnavailableLLM(),
    )
    return TestClient(create_app(context=context))


def _frozen_project(client: TestClient, title: str | None = "夏日便利店") -> str:
    """Take one project all the way to a frozen form."""

    created = client.post("/v1/projects", json={"title_working": title}, headers=CREATOR)
    pid = created.json()["project_id"]
    client.post(f"/v1/projects/{pid}/intent", json=INTENT, headers=CREATOR)
    client.post(f"/v1/projects/{pid}/classify", headers=CREATOR)
    client.post(f"/v1/projects/{pid}/roadmap/confirm", headers=CREATOR)

    ticket = client.post(
        f"/v1/projects/{pid}/assets/upload-url",
        json={"kind": "script", "filename": "s.txt"},
        headers=CREATOR,
    ).json()
    asset = client.put(
        ticket["upload_url"], content=SCRIPT.encode("utf-8"), headers=CREATOR
    ).json()
    client.post(
        f"/v1/projects/{pid}/review",
        json={"asset_version": asset["version_id"]},
        headers=CREATOR,
    )

    for card in client.get(f"/v1/projects/{pid}/materials", headers=CREATOR).json():
        if card["required"]:
            client.post(
                f"/v1/projects/{pid}/materials/{card['material_id']}/waive",
                json={"reason": "covered by the queue test"},
                headers=CREATOR,
            )
    # Answer whatever this snapshot's form actually asks for, rather than a
    # hard-coded list. The seed snapshots disagree -- v1 wants
    # `investment_structure`, v2 wants `investment_amount_rmb` -- and a helper
    # that guesses breaks the day the test snapshot changes.
    ANSWERS = {
        "title": "夏日便利店",
        "episode_count": 24,
        "episode_minutes": 3,
        "investment_amount_rmb": 250_000,
        "investment_structure": "自筹",
    }
    DEFERRABLE = {"applicant_entity"}

    draft = client.get(f"/v1/projects/{pid}/form", headers=CREATOR).json()
    for key, field in draft["fields"].items():
        if field["status"] == "filled":
            continue
        if key in DEFERRABLE:
            client.post(
                f"/v1/projects/{pid}/form/fields/{key}/defer",
                json={"reason": "individual creator"},
                headers=CREATOR,
            )
        elif key in ANSWERS:
            client.post(
                f"/v1/projects/{pid}/form/fields/{key}/confirm",
                json={"value": ANSWERS[key]},
                headers=CREATOR,
            )

    client.post(f"/v1/projects/{pid}/gate/pass", headers=CREATOR)
    client.post(f"/v1/projects/{pid}/form/freeze", headers=CREATOR)
    return pid


@pytest.fixture
def submitted(client: TestClient) -> str:
    client.put("/v1/admin/institutions", json=INSTITUTIONS, headers=ADMIN)
    pid = _frozen_project(client)
    client.post(
        f"/v1/projects/{pid}/institution/submit",
        json={"institution_id": "inst_demo"},
        headers=CREATOR,
    )
    return pid


def test_a_submitted_project_appears_in_the_queue(client, submitted) -> None:
    rows = client.get("/v1/institution/queue", headers=INSTITUTION).json()
    assert [row["project_id"] for row in rows] == [submitted]
    assert rows[0]["state"] == "INSTITUTION_REVIEW"
    assert rows[0]["institution_id"] == "inst_demo"


def test_the_queue_is_empty_before_anything_is_submitted(client) -> None:
    assert client.get("/v1/institution/queue", headers=INSTITUTION).json() == []


def test_a_creator_may_not_read_the_queue(client, submitted) -> None:
    """It lists every creator's work, so it is not a creator's route."""

    response = client.get("/v1/institution/queue", headers=CREATOR)
    assert response.status_code == 403


def test_the_queue_can_be_narrowed_to_one_institution(client, submitted) -> None:
    mine = client.get(
        "/v1/institution/queue?institution_id=inst_demo", headers=INSTITUTION
    ).json()
    theirs = client.get(
        "/v1/institution/queue?institution_id=inst_other", headers=INSTITUTION
    ).json()
    assert [row["project_id"] for row in mine] == [submitted]
    assert theirs == []


def test_an_accepted_project_stays_in_the_queue_until_it_is_filed(
    client, submitted
) -> None:
    """Filing is the institution's act too, so accepting is not done with it."""

    client.post(
        f"/v1/projects/{submitted}/institution/decide",
        json={"decision": "accept", "signed_agreement_uri": "blob://a/1"},
        headers=INSTITUTION,
    )
    rows = client.get("/v1/institution/queue", headers=INSTITUTION).json()
    assert [row["state"] for row in rows] == ["READY_FOR_EXTERNAL_FILING"]

    client.post(
        f"/v1/projects/{submitted}/filing",
        json={"registration_number": "REG-2026-0001"},
        headers=INSTITUTION,
    )
    assert client.get("/v1/institution/queue", headers=INSTITUTION).json() == []


def test_a_returned_project_leaves_the_queue(client, submitted) -> None:
    """A returned project is the creator's work again, not the reviewer's."""

    client.post(
        f"/v1/projects/{submitted}/institution/decide",
        json={"decision": "return", "return_comments": "请补充授权文件。"},
        headers=INSTITUTION,
    )
    assert client.get("/v1/institution/queue", headers=INSTITUTION).json() == []


def test_the_queue_carries_the_licence_reasons(client) -> None:
    """A reviewer must see why a licence check failed, not just that it did."""

    client.put(
        "/v1/admin/institutions",
        json=[{**INSTITUTIONS[0], "registered_capital_rmb": 0}],
        headers=ADMIN,
    )
    pid = _frozen_project(client)
    client.post(
        f"/v1/projects/{pid}/institution/submit",
        json={"institution_id": "inst_demo"},
        headers=CREATOR,
    )
    rows = client.get("/v1/institution/queue", headers=INSTITUTION).json()
    assert rows[0]["licence_reasons"] == ["registered_capital_below_threshold"]


def test_a_project_with_no_title_is_not_given_one(client) -> None:
    """待补充 discipline: an absent title stays absent in the queue."""

    client.put("/v1/admin/institutions", json=INSTITUTIONS, headers=ADMIN)
    pid = _frozen_project(client, title=None)
    client.post(
        f"/v1/projects/{pid}/institution/submit",
        json={"institution_id": "inst_demo"},
        headers=CREATOR,
    )
    rows = client.get("/v1/institution/queue", headers=INSTITUTION).json()
    assert rows[0]["title_working"] is None


def test_the_newest_submission_is_first(client) -> None:
    client.put("/v1/admin/institutions", json=INSTITUTIONS, headers=ADMIN)
    first = _frozen_project(client)
    second = _frozen_project(client)
    for pid in (first, second):
        client.post(
            f"/v1/projects/{pid}/institution/submit",
            json={"institution_id": "inst_demo"},
            headers=CREATOR,
        )
    rows = client.get("/v1/institution/queue", headers=INSTITUTION).json()
    assert [row["project_id"] for row in rows][0] == second
