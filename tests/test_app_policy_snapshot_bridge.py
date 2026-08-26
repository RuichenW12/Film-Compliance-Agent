"""Gate 5-a: admin publication becomes product-readable in one process."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.deps.policy import SOURCE_ID, PolicyApiState, build_local_policy_api_state
from api.deps.services import build_context
from api.main import create_app
from api.settings import Settings


NOW = datetime(2026, 8, 27, 20, 30, tzinfo=timezone(timedelta(hours=8)))
INTERNAL_TOKEN = "t_gate5a_internal"
ADMIN_HEADERS = {"X-Mock-Role": "admin"}
CREATOR_HEADERS = {"X-Mock-Role": "creator", "X-User-Id": "u_gate5a"}
V2_SEED = Path(__file__).parents[1] / "policy" / "seed-snapshot-v2.yaml"
ROMANCE_INTENT = {
    "form_type_claimed": "micro_drama",
    "genre_keywords": ["甜宠"],
    "logline": "总裁与实习生在职场相遇，逐渐走到一起的爱情故事。",
    "episode_count": 30,
    "episode_minutes": 2,
    "budget_band": "band_c",
    "investment_amount_rmb": 1_500_000,
    "is_ai_generated": None,
}


@pytest.fixture
def policy_state(tmp_path: Path) -> PolicyApiState:
    return asyncio.run(
        build_local_policy_api_state(
            tmp_path / "blobs",
            seed_path=V2_SEED,
            clock=lambda: NOW,
        )
    )


def create_provisional_romance(client: TestClient) -> str:
    created = client.post(
        "/v1/projects",
        json={"title_working": "Gate 5-a romance"},
        headers=CREATOR_HEADERS,
    )
    assert created.status_code == 201
    project_id = created.json()["project_id"]

    intent = client.post(
        f"/v1/projects/{project_id}/intent",
        json=ROMANCE_INTENT,
        headers=CREATOR_HEADERS,
    )
    assert intent.status_code == 200

    classified = client.post(
        f"/v1/projects/{project_id}/classify",
        headers=CREATOR_HEADERS,
    )
    assert classified.status_code == 200
    classification = classified.json()["classification"]
    assert classification["tier"] == "T3"
    assert classification["tier_provisional"] is True
    assert classification["policy_snapshot_version"] == "v2"
    return project_id


def publish_v3(client: TestClient) -> str:
    crawl = client.post(
        "/v1/admin/policy/crawl",
        json={"source_id": SOURCE_ID},
        headers=ADMIN_HEADERS,
    )
    assert crawl.status_code == 202

    run = client.get(
        f"/v1/admin/policy/runs/{crawl.json()['run_id']}",
        headers=ADMIN_HEADERS,
    )
    assert run.status_code == 200
    assert run.json()["status"] == "proposal_created"

    published = client.post(
        "/v1/admin/policy/proposals/"
        f"{run.json()['proposal_id']}/publish",
        headers=ADMIN_HEADERS,
    )
    assert published.status_code == 201
    assert published.json() == {"snapshot_version": "v3"}
    return published.json()["snapshot_version"]


def test_publish_v3_then_product_recalc_reads_the_same_repository(
    policy_state: PolicyApiState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTERNAL_TOKEN", INTERNAL_TOKEN)

    with TestClient(create_app(policy_state=policy_state)) as client:
        assert client.get("/healthz").json()["snapshot_version"] == "v2"
        project_id = create_provisional_romance(client)

        version = publish_v3(client)
        assert client.get("/healthz").json()["snapshot_version"] == "v3"

        recalculated = client.post(
            f"/v1/internal/projects/{project_id}/recalc-tier",
            json={"snapshot_version": version},
            headers={"X-Internal-Token": INTERNAL_TOKEN},
        )
        assert recalculated.status_code == 200
        assert recalculated.json() == {
            "tier": "T3",
            "tier_provisional": True,
            "changed": False,
        }

        project = client.get(
            f"/v1/projects/{project_id}",
            headers=CREATOR_HEADERS,
        )
        assert project.status_code == 200
        classification = project.json()["project"]["classification"]
        assert classification["policy_snapshot_version"] == "v3"
        assert classification["tier_provisional"] is True


def test_explicit_context_is_not_replaced_by_policy_composition(
    policy_state: PolicyApiState,
) -> None:
    run_id = policy_state.launcher.launch(SOURCE_ID, NOW)
    result = asyncio.run(policy_state.launcher.execute(run_id, SOURCE_ID, NOW))
    assert result.proposal_id is not None
    policy_state.publisher.publish(result.proposal_id, "admin_richard", NOW)
    assert set(policy_state.repository.list_snapshots()) == {"v2", "v3"}

    explicit = build_context(
        Settings(
            internal_token=INTERNAL_TOKEN,
            snapshot_seed_path="policy/seed-snapshot-v1.yaml",
        )
    )
    with TestClient(
        create_app(context=explicit, policy_state=policy_state)
    ) as client:
        assert client.get("/healthz").json()["snapshot_version"] == "v1"
        assert client.app.state.context is explicit
