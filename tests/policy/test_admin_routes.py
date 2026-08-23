import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.deps.policy import (
    SOURCE_ID,
    PolicyApiState,
    build_local_policy_api_state,
)
from api.main import create_app


NOW = datetime(2026, 8, 23, 20, 30, tzinfo=timezone(timedelta(hours=8)))
ADMIN_HEADERS = {"X-Mock-Role": "admin"}


@pytest.fixture
def policy_state(tmp_path: Path) -> PolicyApiState:
    return asyncio.run(
        build_local_policy_api_state(
            tmp_path / "blobs",
            clock=lambda: NOW,
        )
    )


@pytest.fixture
def api_client(policy_state: PolicyApiState):
    with TestClient(create_app(policy_state)) as client:
        yield client


def admin_get(client: TestClient, path: str):
    return client.get(path, headers=ADMIN_HEADERS)


def seed_proposal(state: PolicyApiState) -> str:
    run_id = state.launcher.launch(SOURCE_ID, NOW)
    result = asyncio.run(state.launcher.execute(run_id, SOURCE_ID, NOW))
    assert result.proposal_id is not None
    return result.proposal_id


def test_admin_routes_require_mock_admin(api_client: TestClient) -> None:
    response = api_client.get("/v1/admin/policy/snapshots")

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "POLICY_ADMIN_FORBIDDEN",
            "message": "admin role required",
            "details": {},
        }
    }


def test_seed_snapshot_is_listed(api_client: TestClient) -> None:
    response = admin_get(api_client, "/v1/admin/policy/snapshots")

    assert response.status_code == 200
    assert response.json() == [
        {
            "version": "v1",
            "published_at": "2026-08-22T00:05:00+08:00",
            "effective_from": "2026-08-22T00:00:00+08:00",
            "published_by": "admin_seed",
            "thresholds_published": False,
        }
    ]


def test_missing_run_and_proposal_use_stable_envelopes(
    api_client: TestClient,
) -> None:
    run = admin_get(api_client, "/v1/admin/policy/runs/missing")
    proposal = admin_get(api_client, "/v1/admin/policy/proposals/missing")

    assert (run.status_code, run.json()["error"]["code"]) == (
        404,
        "POLICY_RUN_NOT_FOUND",
    )
    assert (proposal.status_code, proposal.json()["error"]["code"]) == (
        404,
        "POLICY_PROPOSAL_NOT_FOUND",
    )


def test_run_can_be_read_after_direct_launcher_execution(
    api_client: TestClient,
    policy_state: PolicyApiState,
) -> None:
    proposal_id = seed_proposal(policy_state)

    response = admin_get(api_client, "/v1/admin/policy/runs/run_001")

    assert response.status_code == 200
    assert response.json()["status"] == "proposal_created"
    assert response.json()["proposal_id"] == proposal_id


def test_pending_proposals_are_descending_and_detail_contains_diff(
    api_client: TestClient,
    policy_state: PolicyApiState,
) -> None:
    first_id = seed_proposal(policy_state)
    first = policy_state.repository.get_proposal(first_id)
    second_id = policy_state.repository.create_proposal(
        first.model_copy(
            update={
                "created_at": NOW + timedelta(minutes=1),
                "summary": "Later synthetic proposal",
            }
        )
    )

    listing = admin_get(
        api_client,
        "/v1/admin/policy/proposals?status=pending",
    )
    detail = admin_get(
        api_client,
        f"/v1/admin/policy/proposals/{first_id}",
    )

    assert listing.status_code == 200
    assert [row["proposal_id"] for row in listing.json()] == [
        second_id,
        first_id,
    ]
    assert detail.status_code == 200
    assert detail.json()["proposal_id"] == first_id
    assert detail.json()["impact"] == ["D1c"]
    assert detail.json()["source_diff_uri"].startswith("file://")
    assert "-分类标准尚未公布。" in detail.json()["source_diff_text"]
    assert "+分类标准正式公布。" in detail.json()["source_diff_text"]
    assert detail.json()["draft_pack_updates"] == {
        "p3_tier_thresholds": {"thresholds_published": True}
    }


def test_unreadable_diff_uses_safe_error_without_internal_path(
    api_client: TestClient,
    policy_state: PolicyApiState,
) -> None:
    first_id = seed_proposal(policy_state)
    first = policy_state.repository.get_proposal(first_id)
    bad_id = policy_state.repository.create_proposal(
        first.model_copy(update={"source_diff_uri": "file:///private/secret.json"})
    )

    response = admin_get(
        api_client,
        f"/v1/admin/policy/proposals/{bad_id}",
    )

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "POLICY_BLOB_READ_FAILED",
        "message": "proposal diff could not be read",
        "details": {},
    }
    assert "/private/secret.json" not in response.text
