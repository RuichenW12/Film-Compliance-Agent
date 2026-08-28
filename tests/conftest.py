"""Shared fixtures. No emulator, no credentials, no network."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.clock import FixedClock
from core.llm import ScriptedLLM, UnavailableLLM
from core.workflow_service import WorkflowService
from schemas.enums import AmountBracket, ClaimedFormType, ProductionStage
from schemas.project import ChannelProfile, IntentProfile
from schemas.snapshot import FileSnapshotService
from store.memory import InMemoryStores

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "policy" / "seed-snapshot-v1.yaml"
NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def snapshots() -> FileSnapshotService:
    return FileSnapshotService(SEED_PATH)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW, step_seconds=1)


@pytest.fixture
def stores() -> InMemoryStores:
    return InMemoryStores()


@pytest.fixture
def workflow(stores, snapshots, clock) -> WorkflowService:
    return WorkflowService(stores, snapshots, clock, UnavailableLLM())


@pytest.fixture
def scripted_llm() -> ScriptedLLM:
    return ScriptedLLM({})


@pytest.fixture
def channels() -> ChannelProfile:
    return ChannelProfile(domestic_platforms=["hongguo", "douyin"])


# The three fixed intent profiles the T-A2 acceptance criteria name.

CRIME_LOGLINE = "卧底警察深入毒枭内部，在缉毒行动中面临身份暴露的危机。"


@pytest.fixture
def intent_crime() -> IntentProfile:
    """Xiao Li's project: undercover narcotics police, 24 x 3min, AI generated."""

    return IntentProfile(
        form_type_claimed=ClaimedFormType.MICRO_DRAMA,
        genre_keywords=["缉毒", "卧底"],
        logline=CRIME_LOGLINE,
        episode_count=24,
        episode_minutes=3.0,
        amount_bracket=AmountBracket.BETWEEN,
        is_ai_generated=True,
        production_stage=ProductionStage.SCRIPT_READY,
    )


@pytest.fixture
def intent_romance() -> IntentProfile:
    """An ordinary sweet-romance series: no special subject, tier by amount."""

    return IntentProfile(
        form_type_claimed=ClaimedFormType.MICRO_DRAMA,
        genre_keywords=["甜宠", "都市"],
        logline="总裁与实习生在职场相遇，逐渐走到一起的爱情故事。",
        episode_count=30,
        episode_minutes=2.0,
        amount_bracket=AmountBracket.BELOW_LOWER,
        is_ai_generated=False,
        production_stage=ProductionStage.SCRIPT_READY,
    )


@pytest.fixture
def intent_single_video() -> IntentProfile:
    """A single vlog: not a drama at all."""

    return IntentProfile(
        form_type_claimed=ClaimedFormType.SINGLE_VIDEO,
        genre_keywords=["生活"],
        logline="一支记录城市清晨的短片。",
        episode_count=1,
        episode_minutes=8.0,
        amount_bracket=AmountBracket.BELOW_LOWER,
        is_ai_generated=True,
        production_stage=ProductionStage.FINISHED,
    )
