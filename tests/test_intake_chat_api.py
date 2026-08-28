"""The intake turn endpoint: what it returns, and what it refuses to become.

The endpoint's safety property is negative — it cannot write. These tests hold
that line, because the tempting next commit is always "and then apply the
patch", which would put a model between a sentence and the stored answers with
nobody in between.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.deps.services import AppContext
from api.main import create_app
from api.settings import Settings
from core.llm import ScriptedLLM, UnavailableLLM


@pytest.fixture
def scripted_llm():
    return ScriptedLLM(
        {
            "intake_chat": {
                "answers": [
                    {"key": "episode_count", "value": 24, "quote": "24 episodes"},
                    {
                        "key": "investment_amount_rmb",
                        "value": 1000000,
                        "quote": "around a million",
                    },
                    {"key": "tier", "value": "T3", "quote": "24 episodes"},
                ],
                "reply": "Filled in what I could read.",
            }
        }
    )


@pytest.fixture
def chat_client(stores, snapshots, clock, scripted_llm) -> TestClient:
    """An app whose backend answers one scripted intake reading."""

    context = AppContext(
        settings=Settings(),
        stores=stores,
        snapshots=snapshots,
        clock=clock,
        llm=scripted_llm,
    )
    return TestClient(create_app(context=context))


HEADERS = {"X-Mock-Role": "creator", "X-User-Id": "u_demo"}


def test_a_turn_returns_proposals_with_the_words_they_came_from(chat_client):
    response = chat_client.post(
        "/v1/intake/turn",
        json={"turn": "24 episodes, budget around a million"},
        headers=HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    by_key = {p["key"]: p for p in body["proposals"]}

    assert by_key["episode_count"]["value"] == 24
    assert by_key["episode_count"]["inferred"] is False
    assert by_key["investment_amount_rmb"]["value"] == 1000000
    assert by_key["investment_amount_rmb"]["inferred"] is True
    assert by_key["investment_amount_rmb"]["quote"] == "around a million"

    # The scripted backend also offered a tier. It is not in the response.
    assert "tier" not in by_key


def test_the_endpoint_stores_nothing(chat_client):
    """The point of the whole design. If this ever fails, the guard is decorative."""

    created = chat_client.post("/v1/projects", json={}, headers=HEADERS)
    project_id = created.json()["project_id"]

    chat_client.post(
        "/v1/intake/turn",
        json={"turn": "24 episodes, budget around a million"},
        headers=HEADERS,
    )

    project = chat_client.get(f"/v1/projects/{project_id}", headers=HEADERS).json()
    intent = project["project"]["intent_profile"]
    assert intent["episode_count"] is None
    assert intent["investment_amount_rmb"] is None


def test_an_empty_turn_is_not_a_model_call(chat_client, scripted_llm):
    response = chat_client.post(
        "/v1/intake/turn", json={"turn": "   "}, headers=HEADERS
    )

    assert response.status_code == 200
    assert response.json()["proposals"] == []
    assert scripted_llm.calls == []


def test_an_oversized_turn_is_refused_rather_than_sent(chat_client, scripted_llm):
    response = chat_client.post(
        "/v1/intake/turn", json={"turn": "x" * 5000}, headers=HEADERS
    )

    # 422 is what ValidationFailedError means across this API; the point of the
    # test is that the refusal happens before the model is called, not the code.
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert scripted_llm.calls == []


def test_an_institution_cannot_read_intake_turns(chat_client):
    response = chat_client.post(
        "/v1/intake/turn",
        json={"turn": "24 episodes"},
        headers={"X-Mock-Role": "institution", "X-User-Id": "u_inst"},
    )

    assert response.status_code == 403


def test_no_backend_reports_pending_rather_than_nothing_found(stores, snapshots, clock):
    """Offline the endpoint still answers, and says why it has no proposals."""

    client = TestClient(
        create_app(
            context=AppContext(
                settings=Settings(),
                stores=stores,
                snapshots=snapshots,
                clock=clock,
                llm=UnavailableLLM(),
            )
        )
    )

    response = client.post(
        "/v1/intake/turn", json={"turn": "24 episodes"}, headers=HEADERS
    )

    assert response.status_code == 200
    body = response.json()
    assert body["proposals"] == []
    assert body["pending_flags"] == ["intake_chat_pending"]
