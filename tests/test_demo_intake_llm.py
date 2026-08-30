from __future__ import annotations

from pathlib import Path

import pytest

from api.settings import Settings
from core.classify.subject_rules import load_subject_rules
from core.demo_intake_llm import DemoIntakeLLM
from core.errors import UpstreamLLMError
from core.llm import LLMRequest
from core.review import review_script
from core.script_intake import (
    SCRIPT_INTAKE_PROMPT_ID,
    ScriptIntakeAnalyzer,
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


def intake_request(document: str) -> LLMRequest:
    return LLMRequest(
        prompt_id=SCRIPT_INTAKE_PROMPT_ID,
        prompt_version="v1",
        instruction="test intake",
        document=document,
        response_schema={},
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
    "name,expected_minutes",
    [
        ("e2e-30min-public-security-en.md", 30),
        ("e2e-70min-judicial-long-context-en.md", 70),
        ("e2e-30min-public-security.md", 30),
        ("e2e-70min-judicial-long-context.md", 70),
    ],
)
def test_known_fixture_intake_is_complete_and_preserves_duration(
    name: str, expected_minutes: int
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
    assert result.candidates.amount_bracket.value == "at_or_above_upper"


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


def test_demo_server_prefers_available_vertex(monkeypatch) -> None:
    from scripts import review_demo_server

    class AvailableClient:
        name = "vertex-test"

        def available(self) -> bool:
            return True

        def structured(self, request: LLMRequest) -> dict:
            raise UpstreamLLMError("configured Vertex failure")

    real_llm = AvailableClient()
    monkeypatch.setattr(review_demo_server, "build_llm", lambda settings: real_llm)

    selected = review_demo_server.select_demo_llm(Settings())

    assert selected is real_llm
    with pytest.raises(UpstreamLLMError, match="configured Vertex failure"):
        selected.structured(
            intake_request(fixture_document("e2e-30min-public-security-en.md"))
        )


def test_demo_server_uses_local_adapter_only_when_vertex_is_unavailable(
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

    selected = review_demo_server.select_demo_llm(Settings())

    assert isinstance(selected, DemoIntakeLLM)
    assert selected.name == "local-content-aware-demo"
