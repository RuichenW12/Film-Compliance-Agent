"""Upload tickets and immutable asset versions (contract step 6, mechanism half).

Nothing here depends on policy content: an asset is an asset whatever the
snapshot says. The material-card list and fact extraction come later.
"""

from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from api.deps.services import AppContext
from api.main import create_app
from api.settings import Settings
from core.llm import UnavailableLLM

OWNER = {"X-Mock-Role": "creator", "X-User-Id": "u_owner"}
OTHER = {"X-Mock-Role": "creator", "X-User-Id": "u_other"}
SCRIPT = "第一集：卧底警察在码头与线人接头。".encode("utf-8")
REVISED = "第一集：卧底警察在码头与线人接头，随后暴露。".encode("utf-8")


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


def new_project(client: TestClient, headers: dict = OWNER) -> str:
    created = client.post(
        "/v1/projects", json={"title_working": "迷雾行动"}, headers=headers
    )
    assert created.status_code == 201
    return created.json()["project_id"]


def ticket_for(client: TestClient, project_id: str, kind: str = "script") -> dict:
    response = client.post(
        f"/v1/projects/{project_id}/assets/upload-url",
        json={"kind": kind, "filename": "ep01.txt"},
        headers=OWNER,
    )
    assert response.status_code == 200, response.text
    return response.json()


def upload(client: TestClient, ticket: dict, data: bytes):
    return client.put(ticket["upload_url"], content=data, headers=OWNER)


# ------------------------------------------------------------------- tickets


def test_the_ticket_names_the_backend_it_will_use(client):
    """No bucket configured means a local upload, said out loud, never faked."""

    ticket = ticket_for(client, new_project(client))
    assert ticket["backend"] == "local"
    assert ticket["method"] == "PUT"
    assert ticket["upload_url"].startswith("/v1/uploads/")


def test_another_creator_cannot_request_a_ticket(client):
    project_id = new_project(client)
    refused = client.post(
        f"/v1/projects/{project_id}/assets/upload-url",
        json={"kind": "script"},
        headers=OTHER,
    )
    assert refused.status_code == 403


def test_an_unknown_ticket_is_a_contract_404(client):
    missing = client.put("/v1/uploads/tkt_nope", content=b"x", headers=OWNER)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"


# ------------------------------------------------------------ asset versions


def test_an_upload_records_its_own_sha256(client):
    project_id = new_project(client)
    response = upload(client, ticket_for(client, project_id), SCRIPT)

    assert response.status_code == 201
    body = response.json()
    assert body["sha256"] == hashlib.sha256(SCRIPT).hexdigest()
    assert body["kind"] == "script"
    assert body["uploaded_by"] == "u_owner"
    assert body["parent_version"] is None
    assert body["version_id"].startswith("av_")


def test_a_ticket_is_single_use(client):
    """A replayed upload must not silently write a second version."""

    project_id = new_project(client)
    ticket = ticket_for(client, project_id)
    assert upload(client, ticket, SCRIPT).status_code == 201

    replayed = upload(client, ticket, SCRIPT)
    assert replayed.status_code == 409
    assert replayed.json()["error"]["code"] == "CONFLICT"

    listed = client.get(f"/v1/projects/{project_id}/assets", headers=OWNER)
    assert len(listed.json()) == 1


def test_a_second_upload_chains_onto_the_first(client):
    project_id = new_project(client)
    first = upload(client, ticket_for(client, project_id), SCRIPT).json()
    second = upload(client, ticket_for(client, project_id), REVISED).json()

    assert second["parent_version"] == first["version_id"]
    assert second["sha256"] != first["sha256"]

    listed = client.get(f"/v1/projects/{project_id}/assets", headers=OWNER).json()
    assert [item["version_id"] for item in listed] == [
        first["version_id"],
        second["version_id"],
    ]


def test_versions_of_different_kinds_do_not_chain_together(client):
    """A synopsis is not a revision of a script."""

    project_id = new_project(client)
    script = upload(client, ticket_for(client, project_id, "script"), SCRIPT).json()
    synopsis = upload(
        client, ticket_for(client, project_id, "synopsis"), b"logline"
    ).json()

    assert script["parent_version"] is None
    assert synopsis["parent_version"] is None


def test_an_empty_upload_is_refused(client):
    project_id = new_project(client)
    refused = upload(client, ticket_for(client, project_id), b"")
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "VALIDATION_ERROR"


def test_the_stored_bytes_come_back_unchanged(client):
    project_id = new_project(client)
    version = upload(client, ticket_for(client, project_id), SCRIPT).json()

    fetched = client.get(
        f"/v1/projects/{project_id}/assets/{version['version_id']}/content",
        headers=OWNER,
    )
    assert fetched.status_code == 200
    assert fetched.content == SCRIPT


def test_another_creator_cannot_read_the_bytes(client):
    project_id = new_project(client)
    version = upload(client, ticket_for(client, project_id), SCRIPT).json()

    refused = client.get(
        f"/v1/projects/{project_id}/assets/{version['version_id']}/content",
        headers=OTHER,
    )
    assert refused.status_code == 403


def test_the_upload_is_on_the_timeline(client):
    project_id = new_project(client)
    version = upload(client, ticket_for(client, project_id), SCRIPT).json()

    timeline = client.get(f"/v1/projects/{project_id}/timeline", headers=OWNER).json()
    uploaded = [event for event in timeline if event["event"] == "asset.uploaded"]
    assert len(uploaded) == 1
    assert uploaded[0]["detail"]["version_id"] == version["version_id"]
    assert uploaded[0]["detail"]["kind"] == "script"


# ------------------------------------------------------------ browser access


def test_the_browser_may_preflight_an_upload(client):
    """Found by driving the real UI: without PUT allowed, every test still
    passes and the upload fails only in a browser."""

    response = client.options(
        "/v1/uploads/tkt_any",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "x-mock-role,x-user-id",
        },
    )
    assert response.status_code == 200
    allowed = response.headers["access-control-allow-methods"]
    assert "PUT" in allowed
