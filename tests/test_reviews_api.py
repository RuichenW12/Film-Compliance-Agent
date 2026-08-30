from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from api.deps.services import AppContext
from api.main import create_app
from api.settings import Settings
from core.llm import ScriptedLLM, UnavailableLLM
from core.script_intake import SCRIPT_INTAKE_PROMPT_ID


SCRIPT = """# 《先挂电话》

### 第一集 场景一：派出所
社区民警帮助居民核实一通可疑来电。
"""

INTAKE_REPLY = {
    "tags": {
        "value": ["public security", "family drama"],
        "origin": "suggested",
        "explanation": "The script combines public safety and family drama.",
    },
    "synopsis": {
        "value": "A family and an officer confront a suspicious call.",
        "origin": "suggested",
        "explanation": "This captures the story conflict.",
    },
    "episode_count": {
        "value": 10,
        "origin": "suggested",
        "explanation": "Ten short episodes preserve the source length.",
    },
    "episode_minutes": {
        "value": 3,
        "origin": "suggested",
        "explanation": "Three minutes is suitable for the demo format.",
    },
    "amount_bracket": {
        "value": "at_or_above_upper",
        "origin": "suggested",
        "explanation": "This is an editable planning estimate.",
    },
}

CONFIRMED = {
    "title": "先挂电话（确认版）",
    "tags": ["公安", "现实题材"],
    "synopsis": "社区民警帮助居民识别可疑来电。",
    "episode_count": 10,
    "episode_minutes": 3,
    "amount_bracket": "at_or_above_upper",
}


@pytest.fixture
def client(stores, review_snapshots, clock) -> TestClient:
    context = AppContext(
        settings=Settings(),
        stores=stores,
        snapshots=review_snapshots,
        clock=clock,
        llm=ScriptedLLM({SCRIPT_INTAKE_PROMPT_ID: INTAKE_REPLY}),
    )
    return TestClient(create_app(context=context))


def upload_review(
    client: TestClient,
    *,
    filename: str = "demo-script.md",
    content: bytes | None = None,
):
    return client.post(
        "/v1/reviews",
        data={"mode": "script"},
        files={
            "script": (
                filename,
                content if content is not None else SCRIPT.encode(),
                "text/markdown",
            )
        },
    )


def complete_review(client: TestClient) -> tuple[str, dict]:
    review_id = upload_review(client).json()["review_id"]
    response = client.post(
        f"/v1/reviews/{review_id}/confirm", json=CONFIRMED
    )
    assert response.status_code == 200
    return review_id, response.json()


def test_multipart_upload_returns_confirmation_view_without_internal_ids(client) -> None:
    response = upload_review(client)

    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "AWAITING_CONFIRMATION"
    assert body["mode"] == "script"
    assert body["candidates"]["title"]["value"] == "先挂电话"
    assert body["source_sha256"] == hashlib.sha256(SCRIPT.encode()).hexdigest()
    serialized = response.text
    assert "project_id" not in serialized
    assert "asset_version" not in serialized
    assert "intake_pending_flags" not in serialized


def test_idea_creation_is_manual_and_rejects_a_script_attachment(client) -> None:
    response = client.post("/v1/reviews", data={"mode": "idea"})
    assert response.status_code == 201
    assert response.json()["state"] == "AWAITING_CONFIRMATION"
    assert response.json()["source_download_url"] is None

    mismatch = client.post(
        "/v1/reviews",
        data={"mode": "idea"},
        files={"script": ("unexpected.md", b"# unexpected", "text/markdown")},
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["code"] == "VALIDATION_ERROR"


def test_script_mode_requires_an_upload_and_creator_role(client) -> None:
    missing = client.post("/v1/reviews", data={"mode": "script"})
    assert missing.status_code == 422

    forbidden = client.post(
        "/v1/reviews",
        data={"mode": "script"},
        files={"script": ("demo.md", SCRIPT.encode(), "text/markdown")},
        headers={"X-Mock-Role": "institution"},
    )
    assert forbidden.status_code == 403


def test_get_confirm_validation_state_and_owner_errors(client) -> None:
    started = upload_review(client).json()
    review_id = started["review_id"]

    assert client.get(f"/v1/reviews/{review_id}").json() == started
    other = client.get(
        f"/v1/reviews/{review_id}", headers={"X-User-Id": "u_other"}
    )
    assert other.status_code == 403
    assert client.get("/v1/reviews/review_missing").status_code == 404

    invalid = client.post(
        f"/v1/reviews/{review_id}/confirm",
        json={**CONFIRMED, "amount_bracket": "unknown"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"

    completed = client.post(
        f"/v1/reviews/{review_id}/confirm", json=CONFIRMED
    )
    assert completed.status_code == 200
    assert completed.json()["state"] == "COMPLETE"
    conflict = client.post(
        f"/v1/reviews/{review_id}/confirm",
        json={**CONFIRMED, "title": "Different title"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "STATE_INVALID"


def test_retry_intake_route_preserves_confirmation_step(
    stores, review_snapshots, clock
) -> None:
    context = AppContext(
        settings=Settings(),
        stores=stores,
        snapshots=review_snapshots,
        clock=clock,
        llm=UnavailableLLM(),
    )
    client = TestClient(create_app(context=context))
    started = upload_review(client).json()
    assert started["intake_status"] == "unavailable"

    retried = client.post(
        f"/v1/reviews/{started['review_id']}/retry-intake"
    )
    assert retried.status_code == 200
    assert retried.json()["state"] == "AWAITING_CONFIRMATION"
    assert retried.json()["intake_status"] == "unavailable"


def test_source_download_returns_exact_bytes_checksum_and_safe_filename(client) -> None:
    response = upload_review(client, filename="../demo-script.md")
    review_id = response.json()["review_id"]

    source = client.get(f"/v1/reviews/{review_id}/source")

    assert source.status_code == 200
    assert source.content == SCRIPT.encode()
    assert source.headers["content-type"].startswith("text/markdown")
    assert source.headers["x-source-sha256"] == hashlib.sha256(
        SCRIPT.encode()
    ).hexdigest()
    disposition = source.headers["content-disposition"]
    assert "demo-script.md" in disposition
    assert "../" not in disposition
    assert "\r" not in disposition and "\n" not in disposition


def test_completed_review_downloads_all_artifacts_with_safe_headers(client) -> None:
    review_id, body = complete_review(client)
    assert {item["artifact_type"] for item in body["artifacts"]} == {
        "form",
        "summary",
        "annotated-script",
    }

    for artifact_type, filename, media_prefix in (
        ("form", "project-review-form.pdf", "application/pdf"),
        ("summary", "risk-summary.pdf", "application/pdf"),
        ("annotated-script", "annotated-script.md", "text/markdown"),
    ):
        response = client.get(
            f"/v1/reviews/{review_id}/artifacts/{artifact_type}"
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(media_prefix)
        assert filename in response.headers["content-disposition"]
        if artifact_type != "annotated-script":
            assert response.content.startswith(b"%PDF-")
        else:
            assert "<!-- RISK-001" in response.text


def test_idea_review_exposes_only_form_artifact(client) -> None:
    started = client.post("/v1/reviews", data={"mode": "idea"}).json()
    review_id = started["review_id"]
    completed = client.post(
        f"/v1/reviews/{review_id}/confirm", json=CONFIRMED
    ).json()
    assert [item["artifact_type"] for item in completed["artifacts"]] == [
        "form"
    ]
    summary = client.get(f"/v1/reviews/{review_id}/artifacts/summary")
    assert summary.status_code == 409
