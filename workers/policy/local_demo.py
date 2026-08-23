"""Same-process assembly for deterministic Gate 2 acceptance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml

from schemas.policy_snapshot import PolicySnapshot

from .adapters.fake_event_publisher import FakeEventPublisher
from .adapters.fake_proposal import FakeProposalModel
from .adapters.fake_recalc import FakeRecalcClient
from .adapters.file_blob import FileBlobStore
from .adapters.fixture_source import FixtureSourceFetcher
from .adapters.memory_projects import InMemoryProjectRepository
from .consumer import PolicyUpdatedConsumer
from .models import PolicySource, ProposalDraft
from .outbox import OutboxDispatcher
from .publish import PolicyPublisher
from .refresh import PolicyRefreshModule
from .repository import InMemoryPolicyRepository


@dataclass(frozen=True)
class LocalPolicyLoop:
    policy: InMemoryPolicyRepository
    projects: InMemoryProjectRepository
    fetcher: FixtureSourceFetcher
    proposal_model: FakeProposalModel
    refresh: PolicyRefreshModule
    publisher: PolicyPublisher
    event_publisher: FakeEventPublisher
    dispatcher: OutboxDispatcher
    recalc: FakeRecalcClient
    consumer: PolicyUpdatedConsumer


def build_local_policy_loop(
    *,
    source: PolicySource,
    fixture_path: Path,
    blob_root: Path,
    seed_path: Path,
    proposal_draft: ProposalDraft,
    now: datetime,
    recalculated_tier: Literal["T1", "T2", "T3"],
) -> LocalPolicyLoop:
    policy = InMemoryPolicyRepository()
    seed_data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    policy.put_snapshot(PolicySnapshot.model_validate(seed_data))

    projects = InMemoryProjectRepository()
    fetcher = FixtureSourceFetcher({source.source_id: fixture_path})
    proposal_model = FakeProposalModel(proposal_draft)
    refresh = PolicyRefreshModule(
        sources={source.source_id: source},
        fetcher=fetcher,
        blob_store=FileBlobStore(blob_root),
        proposal_model=proposal_model,
        repository=policy,
    )
    publisher = PolicyPublisher(policy)
    event_publisher = FakeEventPublisher()
    dispatcher = OutboxDispatcher(
        policy, event_publisher, clock=lambda: now
    )
    recalc = FakeRecalcClient(projects, new_tier=recalculated_tier)
    consumer = PolicyUpdatedConsumer(projects, recalc)
    return LocalPolicyLoop(
        policy=policy,
        projects=projects,
        fetcher=fetcher,
        proposal_model=proposal_model,
        refresh=refresh,
        publisher=publisher,
        event_publisher=event_publisher,
        dispatcher=dispatcher,
        recalc=recalc,
        consumer=consumer,
    )
