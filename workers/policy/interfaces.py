"""Storage protocols for policy orchestration."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from schemas.policy_snapshot import PolicyOutbox, PolicyProposal, PolicySnapshot

from .models import PolicyRun, SourceState


class RefreshRepository(Protocol):
    def create_run(self, run_id: str, source_id: str, started_at: datetime) -> None: ...
    def get_run(self, run_id: str) -> PolicyRun: ...
    def fail_run(self, run_id: str, error: str, finished_at: datetime) -> None: ...
    def get_source_state(self, source_id: str) -> SourceState | None: ...

    def commit_refresh_proposal(
        self, *, run_id: str, source_id: str, proposal: PolicyProposal,
        source_state: SourceState, finished_at: datetime,
        previous_sha256: str, current_sha256: str,
    ) -> str: ...

    def commit_refresh_no_change(
        self, *, run_id: str, source_id: str, source_state: SourceState,
        finished_at: datetime, previous_sha256: str | None,
        current_sha256: str,
    ) -> None: ...


class PublicationRepository(Protocol):
    def get_proposal(self, proposal_id: str | None) -> PolicyProposal: ...
    def latest_snapshot(self) -> PolicySnapshot | None: ...
    def commit_publication(
        self, proposal_id: str, snapshot: PolicySnapshot,
        outbox_id: str, outbox: PolicyOutbox,
    ) -> None: ...
    def discard_proposal(self, proposal_id: str) -> None: ...


class OutboxRepository(Protocol):
    def list_pending_outbox(self, limit: int) -> list[tuple[str, PolicyOutbox]]: ...
    def mark_outbox_sent(
        self, outbox_id: str, sent_at: datetime, pubsub_message_id: str,
    ) -> None: ...


class SnapshotReadRepository(Protocol):
    def get_snapshot(self, version: str) -> PolicySnapshot: ...
    def list_snapshots(self) -> dict[str, PolicySnapshot]: ...


class PolicyReadRepository(Protocol):
    def list_runs(self) -> dict[str, PolicyRun]: ...
    def list_proposals(self) -> dict[str, PolicyProposal]: ...
    def list_snapshots(self) -> dict[str, PolicySnapshot]: ...
    def get_run(self, run_id: str) -> PolicyRun: ...
    def get_proposal(self, proposal_id: str | None) -> PolicyProposal: ...


class PolicyRepository(
    RefreshRepository,
    PublicationRepository,
    OutboxRepository,
    PolicyReadRepository,
    SnapshotReadRepository,
    Protocol,
):
    def put_snapshot(self, snapshot: PolicySnapshot) -> None: ...
