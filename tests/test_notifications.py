"""Policy-driven notifications: the producer, the read routes, and idempotency.

B P0 item 9 lists `policy_stale` and `tier_recalculated` notifications, but the
policy loop may not edit product code — it reaches the product only through
`/v1/internal/*`. So the trigger is B's and the producer is A's, and these are
the A-side checks.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.deps.policy import SOURCE_ID, PolicyApiState, build_local_policy_api_state
from api.deps.services import AppContext
from api.main import create_app
from api.settings import Settings
from core.llm import UnavailableLLM
from schemas.enums import NotificationKind

INTERNAL_TOKEN = "t_test_internal"
INTERNAL_HEADERS = {"X-Internal-Token": INTERNAL_TOKEN}
OWNER = {"X-Mock-Role": "creator", "X-User-Id": "u_owner"}
OTHER_CREATOR = {"X-Mock-Role": "creator", "X-User-Id": "u_other"}
NOW = datetime(2026, 8, 27, 20, 30, tzinfo=timezone(timedelta(hours=8)))

ROMANCE_INTENT = {
    "form_type_claimed": "micro_drama",
    "genre_keywords": ["甜宠"],
    "logline": "总裁与实习生在职场相遇，逐渐走到一起的爱情故事。",
    "episode_count": 30,
    "episode_minutes": 2,
    "budget_band": "band_c",
    "investment_amount_rmb": 1_500_000,
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


def classified_project(client: TestClient, headers: dict = OWNER) -> str:
    created = client.post(
        "/v1/projects", json={"title_working": "甜宠项目"}, headers=headers
    )
    assert created.status_code == 201
    project_id = created.json()["project_id"]

    assert (
        client.post(
            f"/v1/projects/{project_id}/intent", json=ROMANCE_INTENT, headers=headers
        ).status_code
        == 200
    )
    classified = client.post(f"/v1/projects/{project_id}/classify", headers=headers)
    assert classified.status_code == 200
    assert classified.json()["classification"]["tier_provisional"] is True
    return project_id


def notifications(client: TestClient, headers: dict = OWNER, **params) -> list[dict]:
    response = client.get("/v1/notifications", params=params, headers=headers)
    assert response.status_code == 200
    return response.json()


# --------------------------------------------------------------- the producer


def test_policy_stale_notifies_the_owner(client):
    project_id = classified_project(client)

    marked = client.post(
        f"/v1/internal/projects/{project_id}/policy-stale",
        json={"snapshot_version": "v1"},
        headers=INTERNAL_HEADERS,
    )
    assert marked.status_code == 200

    items = notifications(client)
    assert len(items) == 1
    assert items[0]["kind"] == NotificationKind.POLICY_STALE.value
    assert items[0]["project_id"] == project_id
    assert items[0]["user_id"] == "u_owner"
    assert items[0]["read"] is False
    assert items[0]["params"]["snapshot_version"] == "v1"


def test_a_repeated_stale_flag_does_not_notify_twice(client):
    """The consumer is idempotent on redelivery; the inbox must be too."""

    project_id = classified_project(client)
    for _ in range(3):
        assert (
            client.post(
                f"/v1/internal/projects/{project_id}/policy-stale",
                json={"snapshot_version": "v1"},
                headers=INTERNAL_HEADERS,
            ).status_code
            == 200
        )

    assert len(notifications(client)) == 1


def test_recalculation_without_a_change_stays_silent(client):
    """Re-running the same snapshot is not news. Only a real change notifies."""

    project_id = classified_project(client)

    recalculated = client.post(
        f"/v1/internal/projects/{project_id}/recalc-tier",
        json={"snapshot_version": "v1"},
        headers=INTERNAL_HEADERS,
    )
    assert recalculated.status_code == 200
    assert recalculated.json()["changed"] is False
    assert notifications(client) == []


def test_a_refused_recalculation_never_notifies(client):
    """A project with no classification is left entirely alone, inbox included."""

    created = client.post(
        "/v1/projects", json={"title_working": "未分类项目"}, headers=OWNER
    )
    assert created.status_code == 201
    project_id = created.json()["project_id"]

    refused = client.post(
        f"/v1/internal/projects/{project_id}/recalc-tier",
        json={"snapshot_version": "v1"},
        headers=INTERNAL_HEADERS,
    )
    assert refused.status_code == 200
    assert refused.json()["changed"] is False
    assert refused.headers["X-Recalc-Reason"] == "not_classified"
    assert notifications(client) == []


# ------------------------------------------------------------- the read routes


def test_notifications_are_scoped_to_their_owner(client):
    project_id = classified_project(client)
    assert (
        client.post(
            f"/v1/internal/projects/{project_id}/policy-stale",
            json={"snapshot_version": "v1"},
            headers=INTERNAL_HEADERS,
        ).status_code
        == 200
    )

    assert len(notifications(client, OWNER)) == 1
    assert notifications(client, OTHER_CREATOR) == []


def test_unread_only_filters_what_the_owner_has_seen(client):
    project_id = classified_project(client)
    assert (
        client.post(
            f"/v1/internal/projects/{project_id}/policy-stale",
            json={"snapshot_version": "v1"},
            headers=INTERNAL_HEADERS,
        ).status_code
        == 200
    )

    notification_id = notifications(client)[0]["notification_id"]
    marked = client.post(
        f"/v1/notifications/{notification_id}/read", headers=OWNER
    )
    assert marked.status_code == 200
    assert marked.json()["read"] is True

    assert len(notifications(client, OWNER)) == 1
    assert notifications(client, OWNER, unread_only=True) == []


def test_another_creator_cannot_mark_a_notification_read(client):
    project_id = classified_project(client)
    assert (
        client.post(
            f"/v1/internal/projects/{project_id}/policy-stale",
            json={"snapshot_version": "v1"},
            headers=INTERNAL_HEADERS,
        ).status_code
        == 200
    )

    notification_id = notifications(client)[0]["notification_id"]
    refused = client.post(
        f"/v1/notifications/{notification_id}/read", headers=OTHER_CREATOR
    )
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "FORBIDDEN"


def test_an_unknown_notification_is_a_contract_404(client):
    missing = client.post("/v1/notifications/ntf_nope/read", headers=OWNER)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"


# ------------------------------------------------- the closed loop, end to end


@pytest.fixture
def policy_state(tmp_path: Path) -> PolicyApiState:
    return asyncio.run(
        build_local_policy_api_state(
            tmp_path / "blobs",
            seed_path=Path(__file__).parents[1]
            / "policy"
            / "seed-snapshot-v1.yaml",
            clock=lambda: NOW,
        )
    )


def test_incomplete_snapshot_is_rejected_without_notifications(
    policy_state: PolicyApiState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A flag-only v2 never reaches the product notification boundary."""

    monkeypatch.setenv("INTERNAL_TOKEN", INTERNAL_TOKEN)

    with TestClient(create_app(policy_state=policy_state)) as client:
        project_id = classified_project(client)

        crawl = client.post(
            "/v1/admin/policy/crawl",
            json={"source_id": SOURCE_ID},
            headers={"X-Mock-Role": "admin"},
        )
        assert crawl.status_code == 202
        run = client.get(
            f"/v1/admin/policy/runs/{crawl.json()['run_id']}",
            headers={"X-Mock-Role": "admin"},
        )
        published = client.post(
            f"/v1/admin/policy/proposals/{run.json()['proposal_id']}/publish",
            headers={"X-Mock-Role": "admin"},
        )
        assert published.status_code == 502
        assert published.json()["error"]["code"] == "POLICY_PROPOSAL_INVALID"
        assert set(policy_state.repository.list_snapshots()) == {"v1"}
        assert policy_state.repository.list_outbox() == {}
        assert client.get(
            f"/v1/projects/{project_id}", headers=OWNER
        ).json()["project"]["classification"]["policy_snapshot_version"] == "v1"
        assert notifications(client) == []
