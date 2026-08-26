"""Composition root: builds the store, snapshot service, clock, and LLM backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from fastapi import Request

from core.clock import Clock, SystemClock
from core.llm import LLMClient, UnavailableLLM
from core.jobs import InlineRunner, JobRunner
from core.teaser import UnavailableVideo, VideoBackend
from core.workflow_service import WorkflowService
from schemas.snapshot import FileSnapshotService, SnapshotService
from store.memory import InMemoryStores

from ..settings import Settings


@dataclass
class AppContext:
    settings: Settings
    stores: InMemoryStores
    snapshots: SnapshotService
    clock: Clock
    llm: LLMClient
    video: VideoBackend = field(default_factory=UnavailableVideo)
    jobs: JobRunner = field(default_factory=InlineRunner)

    @property
    def workflow(self) -> WorkflowService:
        return WorkflowService(
            self.stores, self.snapshots, self.clock, self.llm, self.video, self.jobs
        )


def build_llm(settings: Settings) -> LLMClient:
    """Vertex when configured, otherwise a backend that refuses to guess."""

    if not settings.llm_configured:
        return UnavailableLLM()
    from core.llm_vertex import VertexGeminiLLM

    return VertexGeminiLLM(
        project=settings.google_cloud_project,
        location=settings.region,
        model=settings.vertex_model_gemini,
    )


def build_context(
    settings: Settings | None = None,
    *,
    snapshots: SnapshotService | None = None,
) -> AppContext:
    settings = settings or Settings.from_env()
    return AppContext(
        settings=settings,
        stores=InMemoryStores(),
        snapshots=snapshots or FileSnapshotService(settings.snapshot_path),
        clock=SystemClock(),
        llm=build_llm(settings),
        video=UnavailableVideo(),
        jobs=InlineRunner(),
    )


@lru_cache(maxsize=1)
def default_context() -> AppContext:
    return build_context()


def get_context(request: Request) -> AppContext:
    return request.app.state.context


def get_workflow(request: Request) -> WorkflowService:
    return get_context(request).workflow
