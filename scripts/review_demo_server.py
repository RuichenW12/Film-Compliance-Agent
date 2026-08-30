"""Local entrypoint for the synthetic upload-first browser demo.

This entrypoint is intentionally separate from ``api.main:app``. It uses the
configured Vertex client when available and an explicitly fixture-bounded local
adapter otherwise. Local fallback evidence must never be reported as Vertex or
production-backend validation.
"""

from dataclasses import replace

from api.deps.services import AppContext, build_llm
from api.main import create_app
from api.settings import Settings
from core.clock import SystemClock
from core.demo_intake_llm import DemoIntakeLLM
from core.llm import LLMClient
from schemas.snapshot import FileSnapshotService
from store.memory import InMemoryStores


def select_demo_llm(settings: Settings) -> LLMClient:
    """Prefer configured Vertex; use bounded fixture data only if unavailable."""

    real_llm = build_llm(settings)
    return real_llm if real_llm.available() else DemoIntakeLLM()


settings = replace(
    Settings.from_env(), snapshot_seed_path="policy/seed-snapshot-v2.yaml"
)
context = AppContext(
    settings=settings,
    stores=InMemoryStores(),
    snapshots=FileSnapshotService(settings.snapshot_path),
    clock=SystemClock(),
    llm=select_demo_llm(settings),
)
app = create_app(context=context)
