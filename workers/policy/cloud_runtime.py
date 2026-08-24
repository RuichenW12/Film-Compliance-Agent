"""Credential-gated assembly for the production policy adapters."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib.resources import files
import os
from typing import Any
from uuid import uuid4

import yaml

from schemas.policy_snapshot import PolicySnapshot

from .adapters.firestore_policy import FirestorePolicyRepository
from .adapters.gcs_blob import GcsBlobStore
from .adapters.gemini_proposal import GeminiProposalModel
from .adapters.http_source import HttpSourceFetcher
from .adapters.pubsub_event import PubSubEventPublisher
from .interfaces import PolicyRepository
from .launch import PolicyRunLauncher
from .models import PolicySource
from .outbox import EventPublisher, OutboxDispatcher
from .publish import PolicyPublisher
from .refresh import BlobStore, PolicyRefreshModule, ProposalModel, SourceFetcher
from .source_config import load_policy_sources


class CloudPolicyConfigurationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class CloudPolicySettings:
    project: str
    gcs_bucket: str
    pubsub_topic: str
    location: str = "global"
    gemini_model: str = "gemini-3.5-flash"
    firestore_database: str = "(default)"

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
    ) -> "CloudPolicySettings":
        values = os.environ if env is None else env
        required = {
            "project": "GOOGLE_CLOUD_PROJECT",
            "gcs_bucket": "POLICY_GCS_BUCKET",
            "pubsub_topic": "POLICY_PUBSUB_TOPIC",
        }
        resolved: dict[str, str] = {}
        for field, variable in required.items():
            value = values.get(variable, "").strip()
            if not value:
                raise CloudPolicyConfigurationError(
                    "POLICY_CLOUD_CONFIG_INVALID",
                    f"required cloud setting is missing: {variable}",
                )
            resolved[field] = value
        return cls(
            **resolved,
            location=values.get("GOOGLE_CLOUD_LOCATION", "global").strip()
            or "global",
            gemini_model=values.get(
                "POLICY_GEMINI_MODEL", "gemini-3.5-flash"
            ).strip()
            or "gemini-3.5-flash",
            firestore_database=values.get(
                "FIRESTORE_DATABASE", "(default)"
            ).strip()
            or "(default)",
        )


@dataclass(frozen=True)
class CloudAdapterFactories:
    firestore: Callable[[str, str], PolicyRepository]
    gcs: Callable[[str, str], BlobStore]
    http: Callable[[], SourceFetcher]
    gemini: Callable[[str, str, str, str], ProposalModel]
    pubsub: Callable[[str, str], EventPublisher]


@dataclass(frozen=True)
class CloudPolicyRuntime:
    sources: Mapping[str, PolicySource]
    repository: PolicyRepository
    blob_store: BlobStore
    proposal_model: ProposalModel
    refresh: PolicyRefreshModule
    launcher: PolicyRunLauncher
    publisher: PolicyPublisher
    event_publisher: EventPublisher
    dispatcher: OutboxDispatcher


def _default_factories() -> CloudAdapterFactories:
    return CloudAdapterFactories(
        firestore=lambda project, database: FirestorePolicyRepository.from_project(
            project, database
        ),
        gcs=lambda project, bucket: GcsBlobStore.from_project(project, bucket),
        http=HttpSourceFetcher,
        gemini=lambda project, location, model, prompt: (
            GeminiProposalModel.from_vertex_ai(
                project,
                location,
                model,
                prompt,
            )
        ),
        pubsub=lambda project, topic: PubSubEventPublisher.from_project(
            project, topic
        ),
    )


def build_cloud_policy_runtime(
    settings: CloudPolicySettings,
    *,
    factories: CloudAdapterFactories | None = None,
) -> CloudPolicyRuntime:
    sources = load_policy_sources(
        files("policy").joinpath("policy_sources.yaml")  # type: ignore[arg-type]
    )
    seed_data: Any = yaml.safe_load(
        files("policy").joinpath("seed-snapshot-v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    prompt_text = files("prompts.policy").joinpath("proposal-v1.md").read_text(
        encoding="utf-8"
    )
    constructors = factories or _default_factories()
    repository = constructors.firestore(
        settings.project,
        settings.firestore_database,
    )
    blob_store = constructors.gcs(settings.project, settings.gcs_bucket)
    fetcher = constructors.http()
    proposal_model = constructors.gemini(
        settings.project,
        settings.location,
        settings.gemini_model,
        prompt_text,
    )
    event_publisher = constructors.pubsub(
        settings.project,
        settings.pubsub_topic,
    )

    if repository.latest_snapshot() is None:
        repository.put_snapshot(PolicySnapshot.model_validate(seed_data))

    refresh = PolicyRefreshModule(
        sources=sources,
        fetcher=fetcher,
        blob_store=blob_store,
        proposal_model=proposal_model,
        repository=repository,
    )
    launcher = PolicyRunLauncher(
        repository,
        refresh,
        set(sources),
        run_id_factory=lambda: f"run_{uuid4().hex}",
    )
    publisher = PolicyPublisher(repository)
    dispatcher = OutboxDispatcher(repository, event_publisher)
    return CloudPolicyRuntime(
        sources=dict(sources),
        repository=repository,
        blob_store=blob_store,
        proposal_model=proposal_model,
        refresh=refresh,
        launcher=launcher,
        publisher=publisher,
        event_publisher=event_publisher,
        dispatcher=dispatcher,
    )
