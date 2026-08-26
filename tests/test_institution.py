"""Institution review and filing (contract steps 12-14).

Two rules run through every test here:

- **the licence check is mock and says so.** TDD section 11 forbids real licence
  verification, so an institution the registry does not know reports "cannot
  verify", never "verified". `LicenseCheck.mock` is always true.
- **a registration number comes from a human.** It is the one value a filing
  cannot proceed without and the one value this system may never generate.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.deps.services import AppContext
from api.main import create_app
from api.settings import Settings
from core.llm import UnavailableLLM
from schemas.workflow import MockInstitution

OWNER = {"X-Mock-Role": "creator", "X-User-Id": "u_owner"}
OTHER = {"X-Mock-Role": "creator", "X-User-Id": "u_other"}
INSTITUTION = {"X-Mock-Role": "institution", "X-User-Id": "u_inst"}
ADMIN = {"X-Mock-Role": "admin", "X-User-Id": "u_admin"}

# Placeholder entries: obviously not real names or licence numbers, and marked
# mock end to end. Nothing here asserts that any real entity exists.
DEMO_INSTITUTIONS = [
    {
        "institution_id": "inst_demo_ok",
        "name": "示例持证机构甲 (demo licensed institution A)",
        "license_no": "DEMO-LICENSE-0001",
        "valid_until": "2030-12-31",
        "registered_capital_rmb": 10_000_000,
        "has_foreign": False,
    },
    {
        "institution_id": "inst_demo_foreign",
        "name": "示例外资机构乙 (demo foreign-invested institution B)",
        "license_no": "DEMO-LICENSE-0002",
        "valid_until": "2030-12-31",
        "registered_capital_rmb": 10_000_000,
        "has_foreign": True,
    },
]

ROMANCE_INTENT = {
    "form_type_claimed": "micro_drama",
    "genre_keywords": ["甜宠"],
    "logline": "总裁与实习生在职场相遇，逐渐走到一起的爱情故事。",
    "episode_count": 30,
    "episode_minutes": 2,
    "budget_band": "band_c",
    "is_ai_generated": False,
}
CLEAN_SCRIPT = "第一集 场景一：咖啡厅。实习生林悦第一次见到总裁。\n"


@pytest.fixture
def client(stores, snapshots, clock) -> TestClient:
    context = AppContext(
        settings=Settings(),
        stores=stores,
        snapshots=snapshots,
        clock=clock,
        llm=UnavailableLLM(),
    )
    return TestClient(create_app(context=context))


@pytest.fixture
def loaded_client(client: TestClient) -> TestClient:
    response = client.put(
        "/v1/admin/institutions", json=DEMO_INSTITUTIONS, headers=ADMIN
    )
    assert response.status_code == 200, response.text
    return client


def frozen_project(client: TestClient) -> str:
    """Walk the golden path to a frozen form."""

    created = client.post(
        "/v1/projects", json={"title_working": "Sweet Office"}, headers=OWNER
    )
    project_id = created.json()["project_id"]
    client.post(f"/v1/projects/{project_id}/intent", json=ROMANCE_INTENT, headers=OWNER)
    client.post(f"/v1/projects/{project_id}/classify", headers=OWNER)
    client.post(f"/v1/projects/{project_id}/roadmap/confirm", headers=OWNER)

    ticket = client.post(
        f"/v1/projects/{project_id}/assets/upload-url",
        json={"kind": "script"},
        headers=OWNER,
    ).json()
    client.put(
        ticket["upload_url"], content=CLEAN_SCRIPT.encode("utf-8"), headers=OWNER
    )
    client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    for key, value in [
        ("title", "迷雾行动"),
        ("episode_count", 30),
        ("episode_minutes", 2),
        ("applicant_entity", "示例申报主体"),
        ("investment_structure", "示例出资结构"),
    ]:
        client.post(
            f"/v1/projects/{project_id}/form/fields/{key}/confirm",
            json={"value": value},
            headers=OWNER,
        )
    client.post(f"/v1/projects/{project_id}/gate/pass", headers=OWNER)
    frozen = client.post(f"/v1/projects/{project_id}/form/freeze", headers=OWNER)
    assert frozen.status_code == 200, frozen.text
    return project_id


def submit(client: TestClient, project_id: str, institution_id: str, headers=OWNER):
    return client.post(
        f"/v1/projects/{project_id}/institution/submit",
        json={"institution_id": institution_id},
        headers=headers,
    )


def decide(client: TestClient, project_id: str, body: dict, headers=INSTITUTION):
    return client.post(
        f"/v1/projects/{project_id}/institution/decide", json=body, headers=headers
    )


# ------------------------------------------------------------- the registry


def test_the_registry_is_empty_until_someone_loads_it(client):
    """No invented institutions ship in the product."""

    listed = client.get("/v1/institutions", headers=OWNER)
    assert listed.status_code == 200
    assert listed.json() == []


def test_only_an_admin_may_load_the_registry(client):
    refused = client.put("/v1/admin/institutions", json=DEMO_INSTITUTIONS, headers=OWNER)
    assert refused.status_code == 403


def test_a_loaded_institution_is_listed(loaded_client):
    listed = loaded_client.get("/v1/institutions", headers=OWNER).json()
    assert {item["institution_id"] for item in listed} == {
        "inst_demo_ok",
        "inst_demo_foreign",
    }


def test_the_registry_model_marks_demo_data(loaded_client):
    """`MockInstitution` is the type; nothing pretends to be a real registry."""

    entry = MockInstitution.model_validate(DEMO_INSTITUTIONS[0])
    assert entry.license_no.startswith("DEMO-")


# ---------------------------------------------------------------- submission


def test_submitting_moves_the_project_into_review(loaded_client):
    project_id = frozen_project(loaded_client)
    response = submit(loaded_client, project_id, "inst_demo_ok")

    assert response.status_code == 200
    body = response.json()
    assert body["review"]["institution_id"] == "inst_demo_ok"
    assert body["review"]["decision"] == "pending"
    assert body["state"] == "INSTITUTION_REVIEW"


def test_the_licence_check_is_always_marked_mock(loaded_client):
    project_id = frozen_project(loaded_client)
    check = submit(loaded_client, project_id, "inst_demo_ok").json()["review"][
        "license_check"
    ]
    assert check["mock"] is True


def test_an_unknown_institution_cannot_be_verified(loaded_client):
    """Not knowing an institution is reported, never treated as a pass."""

    project_id = frozen_project(loaded_client)
    check = submit(loaded_client, project_id, "inst_not_in_registry").json()["review"][
        "license_check"
    ]
    assert check["reasons"] == ["institution_not_in_registry"]
    assert check["capital_ok"] is None
    assert check["no_foreign_ok"] is None


def test_a_foreign_invested_institution_fails_the_mock_check(loaded_client):
    project_id = frozen_project(loaded_client)
    check = submit(loaded_client, project_id, "inst_demo_foreign").json()["review"][
        "license_check"
    ]
    assert check["no_foreign_ok"] is False
    assert "foreign_investment" in check["reasons"]


def test_submitting_before_the_form_is_frozen_is_refused(loaded_client):
    created = loaded_client.post(
        "/v1/projects", json={"title_working": "Draft"}, headers=OWNER
    )
    refused = submit(loaded_client, created.json()["project_id"], "inst_demo_ok")
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "STATE_INVALID"


def test_resubmitting_switches_institution_without_touching_the_form(loaded_client):
    """The state table allows staying in review; the frozen form is untouched."""

    project_id = frozen_project(loaded_client)
    before = loaded_client.get(f"/v1/projects/{project_id}/form", headers=OWNER).json()

    submit(loaded_client, project_id, "inst_not_in_registry")
    again = submit(loaded_client, project_id, "inst_demo_ok")

    assert again.status_code == 200
    assert again.json()["review"]["institution_id"] == "inst_demo_ok"
    after = loaded_client.get(f"/v1/projects/{project_id}/form", headers=OWNER).json()
    assert after["hash"] == before["hash"]


def test_another_creator_cannot_submit(loaded_client):
    project_id = frozen_project(loaded_client)
    assert submit(loaded_client, project_id, "inst_demo_ok", OTHER).status_code == 403


# ----------------------------------------------------------------- decisions


def test_accepting_requires_a_signed_agreement(loaded_client):
    project_id = frozen_project(loaded_client)
    submit(loaded_client, project_id, "inst_demo_ok")

    refused = decide(loaded_client, project_id, {"decision": "accept"})
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "VALIDATION_ERROR"


def test_accepting_requires_a_licence_check_that_passed(loaded_client):
    """An institution the mock check rejected cannot accept the project."""

    project_id = frozen_project(loaded_client)
    submit(loaded_client, project_id, "inst_demo_foreign")

    refused = decide(
        loaded_client,
        project_id,
        {"decision": "accept", "signed_agreement_uri": "blob://agreement"},
    )
    assert refused.status_code == 422
    assert "license" in refused.json()["error"]["message"].lower()


def test_accepting_readies_the_project_for_filing(loaded_client):
    project_id = frozen_project(loaded_client)
    submit(loaded_client, project_id, "inst_demo_ok")

    accepted = decide(
        loaded_client,
        project_id,
        {"decision": "accept", "signed_agreement_uri": "blob://agreement"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["state"] == "READY_FOR_EXTERNAL_FILING"
    assert accepted.json()["review"]["decided_at"]


def test_returning_requires_comments_and_sends_it_back(loaded_client):
    project_id = frozen_project(loaded_client)
    submit(loaded_client, project_id, "inst_demo_ok")

    refused = decide(loaded_client, project_id, {"decision": "return"})
    assert refused.status_code == 422

    returned = decide(
        loaded_client,
        project_id,
        {"decision": "return", "return_comments": "请补充出资结构说明"},
    )
    assert returned.status_code == 200
    assert returned.json()["state"] == "INSTITUTION_RETURNED"


def test_a_creator_cannot_decide(loaded_client):
    project_id = frozen_project(loaded_client)
    submit(loaded_client, project_id, "inst_demo_ok")

    refused = decide(
        loaded_client,
        project_id,
        {"decision": "accept", "signed_agreement_uri": "blob://agreement"},
        OWNER,
    )
    assert refused.status_code == 403


# -------------------------------------------------------------------- filing


def test_filing_needs_a_registration_number_from_a_human(loaded_client):
    """The one value the system may never generate."""

    project_id = frozen_project(loaded_client)
    submit(loaded_client, project_id, "inst_demo_ok")
    decide(
        loaded_client,
        project_id,
        {"decision": "accept", "signed_agreement_uri": "blob://agreement"},
    )

    refused = loaded_client.post(
        f"/v1/projects/{project_id}/filing",
        json={"registration_number": "  "},
        headers=INSTITUTION,
    )
    assert refused.status_code == 422


def test_recording_a_filing_moves_the_project_to_filed(loaded_client):
    project_id = frozen_project(loaded_client)
    submit(loaded_client, project_id, "inst_demo_ok")
    decide(
        loaded_client,
        project_id,
        {"decision": "accept", "signed_agreement_uri": "blob://agreement"},
    )

    filed = loaded_client.post(
        f"/v1/projects/{project_id}/filing",
        json={"registration_number": "DEMO-REG-2026-0001"},
        headers=INSTITUTION,
    )
    assert filed.status_code == 200
    assert filed.json()["state"] == "FILED"

    project = loaded_client.get(
        f"/v1/projects/{project_id}", headers=OWNER
    ).json()["project"]
    assert project["registration_number"] == "DEMO-REG-2026-0001"


def test_filing_before_acceptance_is_refused(loaded_client):
    project_id = frozen_project(loaded_client)
    submit(loaded_client, project_id, "inst_demo_ok")

    refused = loaded_client.post(
        f"/v1/projects/{project_id}/filing",
        json={"registration_number": "DEMO-REG-2026-0002"},
        headers=INSTITUTION,
    )
    assert refused.status_code == 409


def test_a_filed_project_keeps_its_frozen_form(loaded_client):
    """Filing must never rewrite what was submitted."""

    project_id = frozen_project(loaded_client)
    before = loaded_client.get(f"/v1/projects/{project_id}/form", headers=OWNER).json()

    submit(loaded_client, project_id, "inst_demo_ok")
    decide(
        loaded_client,
        project_id,
        {"decision": "accept", "signed_agreement_uri": "blob://agreement"},
    )
    loaded_client.post(
        f"/v1/projects/{project_id}/filing",
        json={"registration_number": "DEMO-REG-2026-0003"},
        headers=INSTITUTION,
    )

    after = loaded_client.get(f"/v1/projects/{project_id}/form", headers=OWNER).json()
    assert after["hash"] == before["hash"]
    assert after["frozen"] is True


def test_the_whole_institution_path_is_on_the_timeline(loaded_client):
    project_id = frozen_project(loaded_client)
    submit(loaded_client, project_id, "inst_demo_ok")
    decide(
        loaded_client,
        project_id,
        {"decision": "accept", "signed_agreement_uri": "blob://agreement"},
    )
    loaded_client.post(
        f"/v1/projects/{project_id}/filing",
        json={"registration_number": "DEMO-REG-2026-0004"},
        headers=INSTITUTION,
    )

    timeline = loaded_client.get(
        f"/v1/projects/{project_id}/timeline", headers=OWNER
    ).json()
    events = [event["event"] for event in timeline]
    assert "institution.submitted" in events
    assert "institution.decided" in events
    assert "filing.recorded" in events


# ------------------------------------------------- the way back from a return


def test_a_returned_project_can_resume_the_revision_loop(loaded_client):
    """Without this, INSTITUTION_RETURNED is a dead end and the project is stuck."""

    project_id = frozen_project(loaded_client)
    submit(loaded_client, project_id, "inst_demo_ok")
    decide(
        loaded_client,
        project_id,
        {"decision": "return", "return_comments": "请补充出资结构说明"},
    )

    resumed = loaded_client.post(
        f"/v1/projects/{project_id}/institution/resume", headers=OWNER
    )
    assert resumed.status_code == 200
    assert resumed.json()["state"] == "REVISION_LOOP"


def test_resuming_a_project_that_was_not_returned_is_refused(loaded_client):
    project_id = frozen_project(loaded_client)
    refused = loaded_client.post(
        f"/v1/projects/{project_id}/institution/resume", headers=OWNER
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "STATE_INVALID"


def test_the_return_comments_are_readable_by_the_creator(loaded_client):
    project_id = frozen_project(loaded_client)
    submit(loaded_client, project_id, "inst_demo_ok")
    decide(
        loaded_client,
        project_id,
        {"decision": "return", "return_comments": "请补充出资结构说明"},
    )

    review = loaded_client.get(
        f"/v1/projects/{project_id}/institution", headers=OWNER
    ).json()
    assert review["decision"] == "return"
    assert review["return_comments"] == "请补充出资结构说明"


def test_another_creator_cannot_read_the_review(loaded_client):
    project_id = frozen_project(loaded_client)
    submit(loaded_client, project_id, "inst_demo_ok")
    refused = loaded_client.get(
        f"/v1/projects/{project_id}/institution", headers=OTHER
    )
    assert refused.status_code == 403


def test_an_unsubmitted_project_has_no_review(loaded_client):
    project_id = frozen_project(loaded_client)
    assert (
        loaded_client.get(
            f"/v1/projects/{project_id}/institution", headers=OWNER
        ).json()
        is None
    )


def test_the_task_list_records_the_work_a_project_has_had_done(loaded_client):
    """Every long-running job is a task first, whether or not it ran inline."""

    project_id = frozen_project(loaded_client)
    tasks = loaded_client.get(f"/v1/projects/{project_id}/tasks", headers=OWNER)

    assert tasks.status_code == 200
    types = {task["type"] for task in tasks.json()}
    assert "review_full" in types
    assert all(task["idempotency_key"].startswith(project_id) for task in tasks.json())
