"""Finding actions and incremental review (contract step 9).

What a creator can do with a finding, and what happens to findings when the
script changes underneath them. The rule that shapes both: acknowledging a
problem is not the same as fixing it, so `accept` keeps blocking the gate while
`resolve`, `waive`, and `reject` release it — each for a different, recorded
reason.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from api.deps.services import AppContext
from api.main import create_app
from api.settings import Settings
from core.llm import UnavailableLLM
from schemas.policy_snapshot import PackName
from schemas.snapshot import SnapshotService

OWNER = {"X-Mock-Role": "creator", "X-User-Id": "u_owner"}
OTHER = {"X-Mock-Role": "creator", "X-User-Id": "u_other"}

FLAGGED = (
    "第一集 场景一：码头。卧底警察与线人接头。\n"
    "第一集 场景二：派出所。民警连夜审讯嫌疑人。\n"
)
REWRITTEN = (
    "第一集 场景一：码头。两个老友深夜叙旧。\n"
    "第一集 场景二：派出所。民警连夜审讯嫌疑人。\n"
)


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


def upload(client: TestClient, project_id: str, script: str) -> str:
    ticket = client.post(
        f"/v1/projects/{project_id}/assets/upload-url",
        json={"kind": "script"},
        headers=OWNER,
    ).json()
    created = client.put(
        ticket["upload_url"], content=script.encode("utf-8"), headers=OWNER
    )
    assert created.status_code == 201
    return created.json()["version_id"]


def reviewed_project(client: TestClient, script: str = FLAGGED) -> tuple[str, list[dict]]:
    created = client.post(
        "/v1/projects", json={"title_working": "Operation Fog"}, headers=OWNER
    )
    project_id = created.json()["project_id"]
    upload(client, project_id, script)
    findings = client.post(f"/v1/projects/{project_id}/review", headers=OWNER).json()[
        "findings"
    ]
    assert findings
    return project_id, findings


def act(client: TestClient, project_id: str, finding_id: str, body: dict, headers=OWNER):
    return client.post(
        f"/v1/projects/{project_id}/findings/{finding_id}/action",
        json=body,
        headers=headers,
    )


def gate_items(client: TestClient, project_id: str, check: str) -> list[str]:
    gate = client.get(f"/v1/projects/{project_id}/gate", headers=OWNER).json()
    for gap in gate["gaps"]:
        if gap["check"] == check:
            return gap["items"]
    return []


# ------------------------------------------------------------------- actions


def test_accepting_acknowledges_without_releasing_the_gate(client):
    """Agreeing that a scene is a problem does not make it stop being one."""

    project_id, findings = reviewed_project(client)
    finding_id = findings[0]["finding_id"]

    response = act(client, project_id, finding_id, {"action": "accept"})
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert finding_id in gate_items(client, project_id, "findings_needs_human")


def test_resolving_releases_the_gate(client):
    project_id, findings = reviewed_project(client)
    finding_id = findings[0]["finding_id"]

    response = act(client, project_id, finding_id, {"action": "resolve"})
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    assert finding_id not in gate_items(client, project_id, "findings_needs_human")


def test_waiving_requires_a_reason_and_records_it(client):
    project_id, findings = reviewed_project(client)
    finding_id = findings[0]["finding_id"]

    refused = act(client, project_id, finding_id, {"action": "waive"})
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "VALIDATION_ERROR"

    waived = act(
        client,
        project_id,
        finding_id,
        {"action": "waive", "reason": "已与属地主管部门沟通确认"},
    )
    assert waived.status_code == 200
    assert waived.json()["status"] == "waived"
    assert finding_id not in gate_items(client, project_id, "findings_needs_human")


def test_rejecting_requires_a_reason(client):
    project_id, findings = reviewed_project(client)
    finding_id = findings[0]["finding_id"]

    refused = act(client, project_id, finding_id, {"action": "reject"})
    assert refused.status_code == 422

    rejected = act(
        client,
        project_id,
        finding_id,
        {"action": "reject", "reason": "该场景并非公安题材"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_an_unknown_action_is_refused(client):
    project_id, findings = reviewed_project(client)
    refused = act(
        client, project_id, findings[0]["finding_id"], {"action": "obliterate"}
    )
    assert refused.status_code == 422


def test_another_creator_cannot_act(client):
    project_id, findings = reviewed_project(client)
    refused = act(
        client, project_id, findings[0]["finding_id"], {"action": "resolve"}, OTHER
    )
    assert refused.status_code == 403


def test_an_unknown_finding_is_a_404(client):
    project_id, _ = reviewed_project(client)
    missing = act(client, project_id, "fnd_nope", {"action": "resolve"})
    assert missing.status_code == 404


def test_every_action_lands_on_the_timeline(client):
    project_id, findings = reviewed_project(client)
    finding_id = findings[0]["finding_id"]
    act(client, project_id, finding_id, {"action": "accept"})
    act(client, project_id, finding_id, {"action": "resolve"})

    timeline = client.get(f"/v1/projects/{project_id}/timeline", headers=OWNER).json()
    actions = [e for e in timeline if e["event"] == "finding.action"]
    assert [e["detail"]["action"] for e in actions] == ["accept", "resolve"]
    assert all(e["detail"]["finding_id"] == finding_id for e in actions)


# ----------------------------------------------------------- alert dispatch
#
# The seed's synthesized rules never set `is_edge_case`, so the edge-case alert
# is unreachable with the placeholder pack. These tests publish an explicit rule
# pack — the shape the policy loop will publish — to exercise the path.

EDGE_PACK = {
    "subject_rules": [
        {
            "rule_id": "SR-EDGE-1",
            "category": "public_security",
            "trigger_patterns": ["缉毒"],
            "is_edge_case": True,
            "clause_ref": "nrta-order-16-article-5",
        }
    ]
}

EDGE_INTENT = {
    "form_type_claimed": "micro_drama",
    "genre_keywords": ["缉毒"],
    "logline": "一名缉毒警察在边境执行卧底任务。",
    "episode_count": 24,
    "episode_minutes": 3,
    "budget_band": "band_b",
    "is_ai_generated": True,
}


class EdgeSnapshots(SnapshotService):
    """The seed, with p2 replaced by an explicit edge-case rule."""

    def __init__(self, base: SnapshotService) -> None:
        self._base = base

    def latest_version(self, as_of: datetime | None = None) -> str:
        return self._base.latest_version(as_of)

    def get_pack(self, name: PackName, version: str | None = None) -> dict:
        if PackName(name) is PackName.P2_SUBJECT_RULES:
            return dict(EDGE_PACK)
        return self._base.get_pack(name, version)

    def clause(self, clause_id: str, version: str):
        return self._base.clause(clause_id, version)


@pytest.fixture
def edge_client(stores, snapshots, clock) -> TestClient:
    context = AppContext(
        settings=Settings(),
        stores=stores,
        snapshots=EdgeSnapshots(snapshots),
        clock=clock,
        llm=UnavailableLLM(),
    )
    return TestClient(create_app(context=context))


def alert_finding(client: TestClient) -> tuple[str, dict]:
    created = client.post(
        "/v1/projects", json={"title_working": "Edge case"}, headers=OWNER
    )
    project_id = created.json()["project_id"]
    client.post(f"/v1/projects/{project_id}/intent", json=EDGE_INTENT, headers=OWNER)
    client.post(f"/v1/projects/{project_id}/classify", headers=OWNER)

    alerts = [
        finding
        for finding in client.get(
            f"/v1/projects/{project_id}/findings", headers=OWNER
        ).json()
        if finding["alert"] is not None
    ]
    assert alerts, "an edge-case rule should raise an alert finding"
    return project_id, alerts[0]


def test_an_undispatched_alert_blocks_the_gate(edge_client):
    project_id, finding = alert_finding(edge_client)
    assert finding["finding_id"] in gate_items(
        edge_client, project_id, "alerts_undispatched"
    )


def test_choosing_an_offered_option_dispatches_the_alert(edge_client):
    project_id, finding = alert_finding(edge_client)
    option_id = finding["alert"]["options"][0]["id"]

    chosen = act(
        edge_client,
        project_id,
        finding["finding_id"],
        {"action": "choose_option", "option_id": option_id},
    )
    assert chosen.status_code == 200
    assert chosen.json()["alert"]["chosen_option"] == option_id
    assert chosen.json()["alert"]["chosen_at"] is not None
    assert finding["finding_id"] not in gate_items(
        edge_client, project_id, "alerts_undispatched"
    )


def test_an_option_that_was_not_offered_is_refused(edge_client):
    project_id, finding = alert_finding(edge_client)
    refused = act(
        edge_client,
        project_id,
        finding["finding_id"],
        {"action": "choose_option", "option_id": "Z_not_offered"},
    )
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "VALIDATION_ERROR"


def test_choosing_an_option_on_a_plain_finding_is_refused(client):
    project_id, findings = reviewed_project(client)
    refused = act(
        client,
        project_id,
        findings[0]["finding_id"],
        {"action": "choose_option", "option_id": "B_modify"},
    )
    assert refused.status_code == 422


# ------------------------------------------------------- incremental review


def test_a_rewritten_scene_resolves_its_finding(client):
    """The creator fixed it: the quote is gone from the new version."""

    project_id, first = reviewed_project(client)
    assert len(first) == 2

    upload(client, project_id, REWRITTEN)
    client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    findings = client.get(
        f"/v1/projects/{project_id}/findings", headers=OWNER
    ).json()
    resolved = [f for f in findings if f["status"] == "self_fixed"]
    assert len(resolved) == 1
    assert "卧底警察" in resolved[0]["locator"]["quote"]


def test_a_scene_that_survived_the_rewrite_is_not_reported_twice(client):
    project_id, _ = reviewed_project(client)
    upload(client, project_id, REWRITTEN)
    client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    findings = client.get(
        f"/v1/projects/{project_id}/findings", headers=OWNER
    ).json()
    surviving = [f for f in findings if "派出所" in f["locator"]["quote"]]
    assert len(surviving) == 1
    assert surviving[0]["status"] == "open"


def test_a_decision_survives_the_next_version(client):
    """A waiver the creator already justified is not re-litigated on re-review."""

    project_id, findings = reviewed_project(client)
    surviving = [f for f in findings if "派出所" in f["locator"]["quote"]][0]
    act(
        client,
        project_id,
        surviving["finding_id"],
        {"action": "waive", "reason": "已与属地主管部门沟通确认"},
    )

    upload(client, project_id, REWRITTEN)
    client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    after = [
        f
        for f in client.get(
            f"/v1/projects/{project_id}/findings", headers=OWNER
        ).json()
        if "派出所" in f["locator"]["quote"]
    ]
    assert len(after) == 1
    assert after[0]["status"] == "waived"


def test_the_incremental_pass_is_on_the_timeline(client):
    project_id, _ = reviewed_project(client)
    upload(client, project_id, REWRITTEN)
    client.post(f"/v1/projects/{project_id}/review", headers=OWNER)

    timeline = client.get(f"/v1/projects/{project_id}/timeline", headers=OWNER).json()
    completed = [e for e in timeline if e["event"] == "review.completed"]
    assert len(completed) == 2
    assert completed[-1]["detail"]["self_fixed"] == 1
