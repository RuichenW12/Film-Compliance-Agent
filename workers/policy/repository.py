"""Local policy state used by the deterministic Gate 2 loop."""

from __future__ import annotations

from datetime import datetime

from schemas.policy_snapshot import (
    OutboxStatus,
    PolicyOutbox,
    PolicyProposal,
    PolicySnapshot,
    ProposalStatus,
)

from .models import PolicyRun, SourceState


class InMemoryPolicyRepository:
    def __init__(self) -> None:
        self._runs: dict[str, PolicyRun] = {}
        self._source_states: dict[str, SourceState] = {}
        self._proposals: dict[str, PolicyProposal] = {}
        self._snapshots: dict[str, PolicySnapshot] = {}
        self._outbox: dict[str, PolicyOutbox] = {}
        self._proposal_counter = 0

    def create_run(self, run_id: str, source_id: str, started_at: datetime) -> None:
        if run_id in self._runs:
            raise ValueError(f"run already exists: {run_id}")
        self._runs[run_id] = PolicyRun(
            run_id=run_id,
            source_id=source_id,
            status="running",
            started_at=started_at,
        )

    def get_run(self, run_id: str) -> PolicyRun:
        return self._runs[run_id].model_copy(deep=True)

    def complete_run(
        self,
        run_id: str,
        *,
        status: str,
        finished_at: datetime,
        previous_sha256: str | None,
        current_sha256: str,
        proposal_id: str | None,
    ) -> None:
        run = self._runs[run_id]
        self._runs[run_id] = run.model_copy(
            update={
                "status": status,
                "finished_at": finished_at,
                "previous_sha256": previous_sha256,
                "current_sha256": current_sha256,
                "proposal_id": proposal_id,
                "error": None,
            }
        )

    def fail_run(self, run_id: str, error: str, finished_at: datetime) -> None:
        run = self._runs[run_id]
        self._runs[run_id] = run.model_copy(
            update={"status": "failed", "finished_at": finished_at, "error": error}
        )

    def get_source_state(self, source_id: str) -> SourceState | None:
        state = self._source_states.get(source_id)
        return state.model_copy(deep=True) if state is not None else None

    def put_source_state(self, source_id: str, state: SourceState) -> None:
        self._source_states[source_id] = state.model_copy(deep=True)

    def create_proposal(self, proposal: PolicyProposal) -> str:
        self._proposal_counter += 1
        proposal_id = f"proposal_{self._proposal_counter:03d}"
        self._proposals[proposal_id] = proposal.model_copy(deep=True)
        return proposal_id

    def commit_refresh_proposal(
        self,
        *,
        run_id: str,
        source_id: str,
        proposal: PolicyProposal,
        source_state: SourceState,
        finished_at: datetime,
        previous_sha256: str,
        current_sha256: str,
    ) -> str:
        run = self._runs[run_id]
        if run.status != "running":
            raise ValueError("run is not running")

        proposal_id = f"proposal_{self._proposal_counter + 1:03d}"
        run_data = run.model_dump()
        run_data.update(
            status="proposal_created",
            finished_at=finished_at,
            previous_sha256=previous_sha256,
            current_sha256=current_sha256,
            proposal_id=proposal_id,
            error=None,
        )
        completed_run = PolicyRun.model_validate(run_data)

        new_runs = dict(self._runs)
        new_source_states = dict(self._source_states)
        new_proposals = dict(self._proposals)
        new_runs[run_id] = completed_run.model_copy(deep=True)
        new_source_states[source_id] = source_state.model_copy(deep=True)
        new_proposals[proposal_id] = proposal.model_copy(deep=True)
        self._runs = new_runs
        self._source_states = new_source_states
        self._proposals = new_proposals
        self._proposal_counter += 1
        return proposal_id

    def commit_refresh_no_change(
        self,
        *,
        run_id: str,
        source_id: str,
        source_state: SourceState,
        finished_at: datetime,
        previous_sha256: str | None,
        current_sha256: str,
    ) -> None:
        run = self._runs[run_id]
        if run.status != "running":
            raise ValueError("run is not running")

        run_data = run.model_dump()
        run_data.update(
            status="no_change",
            finished_at=finished_at,
            previous_sha256=previous_sha256,
            current_sha256=current_sha256,
            proposal_id=None,
            error=None,
        )
        completed_run = PolicyRun.model_validate(run_data)

        new_runs = dict(self._runs)
        new_source_states = dict(self._source_states)
        new_runs[run_id] = completed_run.model_copy(deep=True)
        new_source_states[source_id] = source_state.model_copy(deep=True)
        self._runs = new_runs
        self._source_states = new_source_states

    def get_proposal(self, proposal_id: str | None) -> PolicyProposal:
        if proposal_id is None:
            raise KeyError("proposal id is required")
        return self._proposals[proposal_id].model_copy(deep=True)

    def list_proposals(self) -> dict[str, PolicyProposal]:
        return {
            proposal_id: proposal.model_copy(deep=True)
            for proposal_id, proposal in self._proposals.items()
        }

    def put_snapshot(self, snapshot: PolicySnapshot) -> None:
        if snapshot.version in self._snapshots:
            raise ValueError(f"snapshot already exists: {snapshot.version}")
        self._snapshots[snapshot.version] = snapshot.model_copy(deep=True)

    def get_snapshot(self, version: str) -> PolicySnapshot:
        return self._snapshots[version].model_copy(deep=True)

    def latest_snapshot(self) -> PolicySnapshot | None:
        if not self._snapshots:
            return None
        version = max(self._snapshots, key=lambda item: int(item[1:]))
        return self.get_snapshot(version)

    def list_snapshots(self) -> dict[str, PolicySnapshot]:
        return {
            version: snapshot.model_copy(deep=True)
            for version, snapshot in self._snapshots.items()
        }

    def get_outbox(self, outbox_id: str) -> PolicyOutbox:
        return self._outbox[outbox_id].model_copy(deep=True)

    def list_outbox(self) -> dict[str, PolicyOutbox]:
        return {
            outbox_id: row.model_copy(deep=True)
            for outbox_id, row in self._outbox.items()
        }

    def put_outbox(self, outbox_id: str, outbox: PolicyOutbox) -> None:
        if outbox_id in self._outbox:
            raise ValueError(f"outbox already exists: {outbox_id}")
        self._outbox[outbox_id] = outbox.model_copy(deep=True)

    def list_pending_outbox(self, limit: int) -> list[tuple[str, PolicyOutbox]]:
        pending = [
            (outbox_id, row)
            for outbox_id, row in self._outbox.items()
            if row.status is OutboxStatus.PENDING
        ]
        pending.sort(key=lambda item: (item[1].created_at, item[0]))
        return [
            (outbox_id, row.model_copy(deep=True))
            for outbox_id, row in pending[:limit]
        ]

    def mark_outbox_sent(
        self,
        outbox_id: str,
        sent_at: datetime,
        pubsub_message_id: str,
    ) -> None:
        row = self._outbox[outbox_id]
        if row.status is not OutboxStatus.PENDING:
            raise ValueError("outbox is not pending")
        row_data = row.model_dump()
        row_data.update(
            status=OutboxStatus.SENT,
            sent_at=sent_at,
            pubsub_message_id=pubsub_message_id,
        )
        self._outbox[outbox_id] = PolicyOutbox.model_validate(row_data)

    def commit_publication(
        self,
        proposal_id: str,
        snapshot: PolicySnapshot,
        outbox_id: str,
        outbox: PolicyOutbox,
    ) -> None:
        proposal = self._proposals[proposal_id]
        if proposal.status is not ProposalStatus.PENDING:
            raise ValueError("proposal is not pending")
        if snapshot.version in self._snapshots:
            raise ValueError("snapshot already exists")
        if outbox_id in self._outbox:
            raise ValueError("outbox already exists")

        proposal_data = proposal.model_dump()
        proposal_data.update(
            status=ProposalStatus.PUBLISHED,
            published_version=snapshot.version,
        )
        published_proposal = PolicyProposal.model_validate(proposal_data)

        new_proposals = dict(self._proposals)
        new_snapshots = dict(self._snapshots)
        new_outbox = dict(self._outbox)
        new_proposals[proposal_id] = published_proposal.model_copy(deep=True)
        new_snapshots[snapshot.version] = snapshot.model_copy(deep=True)
        new_outbox[outbox_id] = outbox.model_copy(deep=True)
        self._proposals = new_proposals
        self._snapshots = new_snapshots
        self._outbox = new_outbox

    def discard_proposal(self, proposal_id: str) -> None:
        proposal = self._proposals[proposal_id]
        if proposal.status is not ProposalStatus.PENDING:
            raise ValueError("proposal is not pending")
        proposal_data = proposal.model_dump()
        proposal_data.update(status=ProposalStatus.DISCARDED, published_version=None)
        self._proposals[proposal_id] = PolicyProposal.model_validate(proposal_data)
