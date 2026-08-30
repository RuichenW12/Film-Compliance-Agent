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
from store.memory import InMemoryStores, Stores
from store.sqlite import SqliteStores

from ..settings import Settings


@dataclass
class AppContext:
    settings: Settings
    # The port, not one implementation: two things satisfy it now.
    stores: Stores
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


def build_stores(settings: Settings) -> Stores:
    """Memory by default; SQLite or Firestore when asked for.

    The default stays memory so tests and a throwaway run keep their clean
    slate. `STORE_BACKEND=sqlite` is what makes a local demo survive a restart.
    `STORE_BACKEND=firestore` is the only one that survives Cloud Run, which
    replaces containers freely and runs several at once -- a SQLite file lives
    on a container filesystem and is gone at the next revision.

    An unknown value fails loudly rather than falling back: silently running in
    memory when someone asked for durability is exactly the surprise this is
    meant to remove. Firestore is imported here rather than at module scope so
    a machine without the cloud extra can still run everything else.
    """

    backend = (settings.store_backend or "memory").strip().lower()
    if backend == "memory":
        return InMemoryStores()
    if backend == "sqlite":
        return SqliteStores.at(settings.sqlite_file)
    if backend == "firestore":
        from store.firestore import FirestoreStores

        return FirestoreStores.for_project(
            project=settings.google_cloud_project or None,
            database=settings.firestore_database or None,
        )
    raise ValueError(
        f"unknown STORE_BACKEND {backend!r}; "
        "expected 'memory', 'sqlite' or 'firestore'"
    )


def build_context(
    settings: Settings | None = None,
    *,
    snapshots: SnapshotService | None = None,
) -> AppContext:
    settings = settings or Settings.from_env()
    return AppContext(
        settings=settings,
        stores=build_stores(settings),
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
