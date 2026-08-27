import asyncio
from dataclasses import replace
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
from schemas.policy_snapshot import OutboxStatus, ProposalStatus
from workers.policy.adapters.fake_event_publisher import FakeEventPublisher
from workers.policy.outbox import OutboxDispatcher


NOW = datetime(2026, 8, 27, 20, 30, tzinfo=timezone(timedelta(hours=8)))
ADMIN_HEADERS = {"X-Mock-Role": "admin"}
V2_SEED = Path(__file__).parents[2] / "policy" / "seed-snapshot-v2.yaml"


@pytest.fixture
def policy_state(tmp_path: Path) -> PolicyApiState:
    return asyncio.run(
        build_local_policy_api_state(
            tmp_path / "blobs",
            seed_path=V2_SEED,
            clock=lambda: NOW,
        )
    )


@pytest.fixture
def api_client(policy_state: PolicyApiState):
    with TestClient(create_app(policy_state=policy_state)) as client:
        yield client


def admin_get(client: TestClient, path: str):
    return client.get(path, headers=ADMIN_HEADERS)


def admin_post(
    client: TestClient,
    path: str,
    *,
    json: dict[str, object] | None = None,
):
    return client.post(path, headers=ADMIN_HEADERS, json=json)


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
            "version": "v2",
            "published_at": "2026-08-26T23:15:00+08:00",
            "effective_from": "2026-08-26T00:00:00+08:00",
            "published_by": "mock_seed",
            "thresholds_published": True,
            "verification_status": "mock_verified",
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


def test_failed_run_hides_internal_error_details(
    api_client: TestClient,
    policy_state: PolicyApiState,
) -> None:
    policy_state.repository.create_run("run_failed", SOURCE_ID, NOW)
    policy_state.repository.fail_run(
        "run_failed",
        "POLICY_REFRESH_FAILED: could not read /private/secret/policy.html",
        NOW,
    )

    response = admin_get(api_client, "/v1/admin/policy/runs/run_failed")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error"] == "policy refresh failed"
    assert "/private/secret/policy.html" not in response.text


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
    p3_update = detail.json()["draft_pack_updates"]["p3_tier_thresholds"]
    assert p3_update["thresholds_published"] is True
    assert set(p3_update["threshold_sets"]) == {"live_action", "ai_generated"}


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


def test_crawl_returns_202_and_background_task_creates_proposal(
    api_client: TestClient,
) -> None:
    response = admin_post(
        api_client,
        "/v1/admin/policy/crawl",
        json={"source_id": SOURCE_ID},
    )

    assert response.status_code == 202
    run_id = response.json()["run_id"]
    run = admin_get(api_client, f"/v1/admin/policy/runs/{run_id}").json()
    assert run["status"] == "proposal_created"
    assert run["proposal_id"] == "proposal_001"


def test_unknown_source_is_404_without_creating_a_run(
    api_client: TestClient,
    policy_state: PolicyApiState,
) -> None:
    response = admin_post(
        api_client,
        "/v1/admin/policy/crawl",
        json={"source_id": "missing_source"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "POLICY_SOURCE_NOT_FOUND"
    assert set(policy_state.repository.list_runs()) == {"run_baseline"}


def test_publish_creates_v3_and_snapshot_list_is_descending(
    api_client: TestClient,
    policy_state: PolicyApiState,
) -> None:
    proposal_id = seed_proposal(policy_state)

    response = admin_post(
        api_client,
        f"/v1/admin/policy/proposals/{proposal_id}/publish",
    )

    assert response.status_code == 201
    assert response.json() == {"snapshot_version": "v3"}
    snapshots = admin_get(api_client, "/v1/admin/policy/snapshots").json()
    assert [row["version"] for row in snapshots] == ["v3", "v2"]
    assert policy_state.repository.get_outbox(
        "policy.updated:v3"
    ).status is OutboxStatus.SENT


def test_future_effective_publish_is_rejected_by_the_server(
    api_client: TestClient,
    policy_state: PolicyApiState,
) -> None:
    first_id = seed_proposal(policy_state)
    first = policy_state.repository.get_proposal(first_id)
    future_id = policy_state.repository.create_proposal(
        first.model_copy(update={"effective_from": NOW + timedelta(days=1)})
    )

    response = admin_post(
        api_client,
        f"/v1/admin/policy/proposals/{future_id}/publish",
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "POLICY_NOT_EFFECTIVE"
    assert policy_state.repository.get_proposal(
        future_id
    ).status is ProposalStatus.PENDING
    assert set(policy_state.repository.list_snapshots()) == {"v2"}


def test_discard_returns_204_and_repeat_is_a_conflict(
    api_client: TestClient,
    policy_state: PolicyApiState,
) -> None:
    proposal_id = seed_proposal(policy_state)

    discarded = admin_post(
        api_client,
        f"/v1/admin/policy/proposals/{proposal_id}/discard",
    )
    repeated = admin_post(
        api_client,
        f"/v1/admin/policy/proposals/{proposal_id}/discard",
    )

    assert discarded.status_code == 204
    assert discarded.content == b""
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "POLICY_PROPOSAL_CONFLICT"


def test_dispatch_failure_does_not_rollback_successful_publish(
    policy_state: PolicyApiState,
) -> None:
    proposal_id = seed_proposal(policy_state)
    failing_publisher = FakeEventPublisher(fail_on={"policy.updated:v3"})
    state = replace(
        policy_state,
        dispatcher=OutboxDispatcher(
            policy_state.repository,
            failing_publisher,
            clock=lambda: NOW,
        ),
    )

    with TestClient(create_app(policy_state=state)) as client:
        response = admin_post(
            client,
            f"/v1/admin/policy/proposals/{proposal_id}/publish",
        )

    assert response.status_code == 201
    assert response.json() == {"snapshot_version": "v3"}
    assert policy_state.repository.get_outbox(
        "policy.updated:v3"
    ).status is OutboxStatus.PENDING


def test_default_app_builds_the_local_fixture_state() -> None:
    with TestClient(create_app()) as client:
        response = admin_get(client, "/v1/admin/policy/snapshots")

    assert response.status_code == 200
    assert [row["version"] for row in response.json()] == ["v2"]


def test_cors_allows_only_the_local_policy_ui(
    api_client: TestClient,
) -> None:
    allowed = api_client.options(
        "/v1/admin/policy/snapshots",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Mock-Role",
        },
    )
    denied = api_client.options(
        "/v1/admin/policy/snapshots",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Mock-Role",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == (
        "http://127.0.0.1:3000"
    )
    assert "access-control-allow-origin" not in denied.headers
