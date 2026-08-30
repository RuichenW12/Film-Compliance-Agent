"""Local scripted adapter for the synthetic upload-first browser demo.

This entrypoint is intentionally separate from ``api.main:app``. It provides
repeatable intake suggestions for the checked-in fixture and must never be
reported as a Vertex or production-backend validation.
"""

from api.deps.services import AppContext
from api.main import create_app
from api.settings import Settings
from core.clock import SystemClock
from core.llm import ScriptedLLM
from core.script_intake import SCRIPT_INTAKE_PROMPT_ID
from schemas.snapshot import FileSnapshotService
from store.memory import InMemoryStores


INTAKE_REPLY = {
    "tags": {
        "value": ["公安", "家庭现实"],
        "origin": "suggested",
        "explanation": "The source-language tags preserve the public-security subject signal.",
    },
    "synopsis": {
        "value": "社区民警在派出所帮助居民识别可疑来电，修复父女关系。",
        "origin": "suggested",
        "explanation": "This condenses the uploaded story in its source language without rewriting it.",
    },
    "episode_count": {
        "value": 10,
        "origin": "suggested",
        "explanation": "Ten episodes preserve the thirty-minute source duration.",
    },
    "episode_minutes": {
        "value": 3,
        "origin": "suggested",
        "explanation": "Three minutes per episode preserves the total duration.",
    },
    "amount_bracket": {
        "value": "at_or_above_upper",
        "origin": "suggested",
        "explanation": "A user-editable planning estimate from the current snapshot ranges.",
    },
}


settings = Settings(snapshot_seed_path="policy/seed-snapshot-v2.yaml")
context = AppContext(
    settings=settings,
    stores=InMemoryStores(),
    snapshots=FileSnapshotService(settings.snapshot_path),
    clock=SystemClock(),
    llm=ScriptedLLM({SCRIPT_INTAKE_PROMPT_ID: INTAKE_REPLY}),
)
app = create_app(context=context)
