from __future__ import annotations

import importlib
from copy import deepcopy
from pathlib import Path

import pytest

from api.settings import Settings
from core.classify.subject_rules import load_subject_rules
from core.demo_intake_llm import DemoIntakeLLM
from core.errors import UpstreamLLMError
from core.llm import LLMRequest
from core.review import (
    RESPONSE_SCHEMA as REVIEW_RESPONSE_SCHEMA,
    SCRIPT_REVIEW_PROMPT_ID,
    SCRIPT_REVIEW_PROMPT_VERSION,
    review_script,
    split_scenes,
)
from core.script_intake import (
    SCRIPT_INTAKE_PROMPT_ID,
    SCRIPT_INTAKE_PROMPT_VERSION,
    ScriptIntakeAnalyzer,
    _response_schema as intake_response_schema,
)
from core.script_text import parse_script
from schemas.enums import FindingSeverity
from schemas.policy_snapshot import PackName
from schemas.reviews import IntakeStatus
from schemas.snapshot import FileSnapshotService


FIXTURES = Path(__file__).parent / "fixtures" / "scripts"
CURRENT_SEED = Path(__file__).resolve().parents[1] / "policy" / "seed-snapshot-v2.yaml"
THRESHOLD_OPTIONS = [
    {"value": "below_lower", "label": "Under CNY 300,000"},
    {"value": "between", "label": "CNY 300,000-800,000"},
    {"value": "at_or_above_upper", "label": "CNY 800,000 or above"},
]


def fixture_document(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def intake_request(
    document: str,
    *,
    version: str = SCRIPT_INTAKE_PROMPT_VERSION,
    schema: dict | None = None,
) -> LLMRequest:
    response_schema = (
        intake_response_schema(
            [option["value"] for option in THRESHOLD_OPTIONS]
        )
        if schema is None
        else schema
    )
    return LLMRequest(
        prompt_id=SCRIPT_INTAKE_PROMPT_ID,
        prompt_version=version,
        instruction="test intake",
        document=document,
        response_schema=response_schema,
    )


def review_request(
    document: str,
    *,
    version: str = SCRIPT_REVIEW_PROMPT_VERSION,
    schema: dict | None = None,
) -> LLMRequest:
    reviewable = "\n".join(scene.quote for scene in split_scenes(document))
    return LLMRequest(
        prompt_id=SCRIPT_REVIEW_PROMPT_ID,
        prompt_version=version,
        instruction="test review",
        document=reviewable,
        response_schema=(
            deepcopy(REVIEW_RESPONSE_SCHEMA) if schema is None else schema
        ),
    )


def test_english_intake_is_coupled_to_the_exact_current_document() -> None:
    llm = DemoIntakeLLM()
    thirty = llm.structured(
        intake_request(fixture_document("e2e-30min-public-security-en.md"))
    )
    seventy = llm.structured(
        intake_request(fixture_document("e2e-70min-judicial-long-context-en.md"))
    )

    assert thirty["tags"]["value"] != seventy["tags"]["value"]
    assert thirty["synopsis"]["value"] != seventy["synopsis"]["value"]
    assert {"public security", "anti-fraud"} <= set(thirty["tags"]["value"])
    assert {"judicial", "authorship dispute"} <= set(
        seventy["tags"]["value"]
    )


@pytest.mark.parametrize(
    "name,expected_minutes,expected_bracket",
    [
        ("e2e-30min-public-security-en.md", 30, "between"),
        ("e2e-70min-judicial-long-context-en.md", 70, "at_or_above_upper"),
        ("e2e-30min-public-security.md", 30, "between"),
        ("e2e-70min-judicial-long-context.md", 70, "at_or_above_upper"),
    ],
)
def test_known_fixture_intake_is_complete_and_preserves_duration(
    name: str, expected_minutes: int, expected_bracket: str
) -> None:
    raw = (FIXTURES / name).read_bytes()
    parsed = parse_script(name, raw)

    result = ScriptIntakeAnalyzer(DemoIntakeLLM()).analyze(
        parsed, THRESHOLD_OPTIONS
    )

    assert result.status is IntakeStatus.COMPLETE
    assert result.backend == "local-content-aware-demo"
    assert (
        result.candidates.episode_count.value
        * result.candidates.episode_minutes.value
        == expected_minutes
    )
    amount = result.candidates.amount_bracket
    assert amount.value == expected_bracket
    assert amount.origin.value == "suggested"
    assert amount.explanation
    if name.endswith("-en.md"):
        assert "synthetic" in amount.explanation.lower()
        assert "editable" in amount.explanation.lower()
        assert "not extracted from the script" in amount.explanation.lower()
        assert "production complexity" in amount.explanation.lower()
        assert "not a compliance conclusion" in amount.explanation.lower()
    else:
        assert "合成" in amount.explanation
        assert "可编辑" in amount.explanation
        assert "并非从剧本提取" in amount.explanation
        assert "制作复杂度" in amount.explanation
        assert "不是合规结论" in amount.explanation


def test_chinese_and_english_versions_use_the_same_story_estimate() -> None:
    llm = DemoIntakeLLM()
    thirty_zh = llm.structured(
        intake_request(fixture_document("e2e-30min-public-security.md"))
    )
    thirty_en = llm.structured(
        intake_request(fixture_document("e2e-30min-public-security-en.md"))
    )
    seventy_zh = llm.structured(
        intake_request(fixture_document("e2e-70min-judicial-long-context.md"))
    )
    seventy_en = llm.structured(
        intake_request(fixture_document("e2e-70min-judicial-long-context-en.md"))
    )

    assert thirty_zh["amount_bracket"]["value"] == "between"
    assert thirty_en["amount_bracket"]["value"] == "between"
    assert seventy_zh["amount_bracket"]["value"] == "at_or_above_upper"
    assert seventy_en["amount_bracket"]["value"] == "at_or_above_upper"


def test_unknown_document_fails_closed() -> None:
    with pytest.raises(UpstreamLLMError, match="unknown demo document"):
        DemoIntakeLLM().structured(intake_request("# A different screenplay"))


def test_unknown_prompt_id_fails_closed() -> None:
    request = intake_request(
        fixture_document("e2e-30min-public-security-en.md")
    )
    request = LLMRequest(
        prompt_id="not-a-demo-prompt",
        prompt_version=request.prompt_version,
        instruction=request.instruction,
        document=request.document,
        response_schema=request.response_schema,
    )

    with pytest.raises(UpstreamLLMError, match="unsupported demo prompt"):
        DemoIntakeLLM().structured(request)


@pytest.mark.parametrize(
    "llm_request",
    [
        intake_request(
            fixture_document("e2e-30min-public-security-en.md"), version="v999"
        ),
        review_request(
            fixture_document("e2e-70min-judicial-long-context-en.md"),
            version="v999",
        ),
    ],
)
def test_wrong_prompt_version_fails_closed(llm_request: LLMRequest) -> None:
    with pytest.raises(UpstreamLLMError, match="unsupported demo prompt version"):
        DemoIntakeLLM().structured(llm_request)


@pytest.mark.parametrize(
    "change", ["missing-schema", "missing-property", "changed-type"]
)
def test_changed_intake_response_schema_fails_closed(change: str) -> None:
    schema = intake_response_schema(
        [option["value"] for option in THRESHOLD_OPTIONS]
    )
    if change == "missing-schema":
        schema = {}
    elif change == "missing-property":
        del schema["properties"]["tags"]
    else:
        schema["properties"]["episode_count"]["properties"]["value"] = {
            "type": "string"
        }

    request = intake_request(
        fixture_document("e2e-30min-public-security-en.md"), schema=schema
    )

    with pytest.raises(UpstreamLLMError, match="intake response schema"):
        DemoIntakeLLM().structured(request)


def test_intake_schema_must_allow_the_fixture_estimate() -> None:
    schema = intake_response_schema(["below_lower", "at_or_above_upper"])
    request = intake_request(
        fixture_document("e2e-30min-public-security-en.md"), schema=schema
    )

    with pytest.raises(UpstreamLLMError, match="amount bracket"):
        DemoIntakeLLM().structured(request)


def test_changed_review_response_schema_fails_closed() -> None:
    schema = deepcopy(REVIEW_RESPONSE_SCHEMA)
    schema["properties"]["hits"]["items"]["required"].remove("reason")
    request = review_request(
        fixture_document("e2e-70min-judicial-long-context-en.md"), schema=schema
    )

    with pytest.raises(UpstreamLLMError, match="review response schema"):
        DemoIntakeLLM().structured(request)


def test_canned_replies_are_defensively_copied() -> None:
    request = intake_request(
        fixture_document("e2e-30min-public-security-en.md")
    )
    first = DemoIntakeLLM().structured(request)
    first["tags"]["value"].append("mutated")
    first["synopsis"]["value"] = "mutated"

    second = DemoIntakeLLM().structured(request)

    assert "mutated" not in second["tags"]["value"]
    assert second["synopsis"]["value"] != "mutated"


@pytest.mark.parametrize(
    "name,category,quote,episode,scene",
    [
        (
            "e2e-30min-public-security-en.md",
            "public_security",
            "The police station is right at the end of the street. You don't "
            "have to argue with them, and you don't have to make a decision "
            "right now. Just change locations, sit down, and confirm.",
            1,
            9,
        ),
        (
            "e2e-70min-judicial-long-context-en.md",
            "judicial",
            "Let's separate the performance authorization from the promotional "
            "credits first. Do both sides acknowledge the authenticity of the "
            "main text of the authorization?",
            4,
            2,
        ),
    ],
)
def test_english_semantic_review_is_exact_locatable_and_needs_human(
    name: str, category: str, quote: str, episode: int, scene: int
) -> None:
    document = fixture_document(name)
    snapshots = FileSnapshotService(CURRENT_SEED)
    rules = load_subject_rules(
        snapshots.get_pack(PackName.P2_SUBJECT_RULES, snapshots.latest_version())
    )

    result = review_script(document, rules, DemoIntakeLLM())

    assert result.pending_flags == []
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.category == category
    assert finding.scene.quote == quote
    assert finding.scene.episode == episode
    assert finding.scene.scene == scene
    assert finding.severity is FindingSeverity.NEEDS_HUMAN
    assert finding.expert_pending is True
    assert quote in document


def test_demo_llm_is_explicitly_available() -> None:
    assert DemoIntakeLLM().available() is True


def test_demo_server_auto_prefers_available_vertex(monkeypatch) -> None:
    from scripts import review_demo_server

    class AvailableClient:
        name = "vertex-test"

        def available(self) -> bool:
            return True

        def structured(self, request: LLMRequest) -> dict:
            raise UpstreamLLMError("configured Vertex failure")

    real_llm = AvailableClient()
    monkeypatch.setattr(review_demo_server, "build_llm", lambda settings: real_llm)

    selected = review_demo_server.select_demo_llm(Settings(), backend="auto")

    assert selected is real_llm
    with pytest.raises(UpstreamLLMError, match="configured Vertex failure"):
        selected.structured(
            intake_request(fixture_document("e2e-30min-public-security-en.md"))
        )


def test_demo_server_defaults_to_auto(monkeypatch) -> None:
    from scripts import review_demo_server

    class AvailableClient:
        name = "vertex-test"

        def available(self) -> bool:
            return True

    real_llm = AvailableClient()
    monkeypatch.delenv("DEMO_LLM_BACKEND", raising=False)
    monkeypatch.setattr(review_demo_server, "build_llm", lambda settings: real_llm)

    selected = review_demo_server.select_demo_llm(Settings())

    assert selected is real_llm


def test_demo_server_auto_uses_local_only_when_vertex_is_unavailable(
    monkeypatch,
) -> None:
    from scripts import review_demo_server

    class UnavailableClient:
        name = "unavailable-test"

        def available(self) -> bool:
            return False

        def structured(self, request: LLMRequest) -> dict:
            raise AssertionError("unavailable client must not be called")

    unavailable = UnavailableClient()
    monkeypatch.setattr(
        review_demo_server, "build_llm", lambda settings: unavailable
    )

    selected = review_demo_server.select_demo_llm(Settings(), backend="auto")

    assert isinstance(selected, DemoIntakeLLM)
    assert selected.name == "local-content-aware-demo"


def test_demo_server_local_never_builds_vertex(monkeypatch) -> None:
    from scripts import review_demo_server

    def unexpected_build(settings: Settings):
        raise AssertionError("local mode must not construct a Vertex client")

    monkeypatch.setattr(review_demo_server, "build_llm", unexpected_build)

    selected = review_demo_server.select_demo_llm(Settings(), backend="local")

    assert isinstance(selected, DemoIntakeLLM)


def test_demo_server_vertex_requires_available_client(monkeypatch) -> None:
    from scripts import review_demo_server

    class UnavailableClient:
        name = "unavailable-test"

        def available(self) -> bool:
            return False

    monkeypatch.setattr(
        review_demo_server, "build_llm", lambda settings: UnavailableClient()
    )

    with pytest.raises(RuntimeError, match="Vertex.*not configured"):
        review_demo_server.select_demo_llm(Settings(), backend="vertex")


def test_demo_server_vertex_returns_available_client(monkeypatch) -> None:
    from scripts import review_demo_server

    class AvailableClient:
        name = "vertex-test"

        def available(self) -> bool:
            return True

    real_llm = AvailableClient()
    monkeypatch.setattr(review_demo_server, "build_llm", lambda settings: real_llm)

    selected = review_demo_server.select_demo_llm(Settings(), backend="vertex")

    assert selected is real_llm


def test_demo_server_rejects_invalid_backend() -> None:
    from scripts import review_demo_server

    with pytest.raises(ValueError, match="DEMO_LLM_BACKEND"):
        review_demo_server.select_demo_llm(Settings(), backend="scripted")


def test_demo_server_module_context_honors_local_environment(monkeypatch) -> None:
    from scripts import review_demo_server

    monkeypatch.setenv("DEMO_LLM_BACKEND", "local")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "must-not-be-used")
    monkeypatch.setenv("VERTEX_MODEL_GEMINI", "must-not-be-used")

    reloaded = importlib.reload(review_demo_server)

    assert reloaded.settings.llm_configured is True
    assert isinstance(reloaded.context.llm, DemoIntakeLLM)
