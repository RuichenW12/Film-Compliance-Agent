"""Validated Firestore storage for Richard-owned policy state."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel

from schemas.policy_snapshot import (
    OutboxStatus,
    PolicyOutbox,
    PolicyProposal,
    PolicySnapshot,
    ProposalStatus,
)

from ..models import PolicyRun, SourceState


T = TypeVar("T")
ModelT = TypeVar("ModelT", bound=BaseModel)


class FirestorePolicyRepository:
    SOURCE_STATES = "policy_source_states"
    RUNS = "policy_runs"
    PROPOSALS = "policy_proposals"
    SNAPSHOTS = "policy_snapshots"
    OUTBOX = "policy_outbox"

    def __init__(
        self,
        client: Any,
        transaction_runner: Callable[[Callable[[Any], T]], T],
    ) -> None:
        self._client = client
        self._run_transaction = transaction_runner

    @classmethod
    def from_project(
        cls,
        project: str,
        database: str = "(default)",
    ) -> "FirestorePolicyRepository":
        from google.cloud import firestore

        client = firestore.Client(project=project, database=database)

        def transaction_runner(callback):
            @firestore.transactional
            def execute(transaction):
                return callback(transaction)

            return execute(client.transaction())

        return cls(client, transaction_runner)

    def create_run(self, run_id: str, source_id: str, started_at: datetime) -> None:
        run = PolicyRun(
            run_id=run_id,
            source_id=source_id,
            status="running",
            started_at=started_at,
        )
        self._document(self.RUNS, run_id).create(self._dump(run))

    def get_run(self, run_id: str) -> PolicyRun:
        return self._read(self.RUNS, run_id, PolicyRun)

    def list_runs(self) -> dict[str, PolicyRun]:
        return self._list(self.RUNS, PolicyRun)

    def fail_run(self, run_id: str, error: str, finished_at: datetime) -> None:
        run_ref = self._document(self.RUNS, run_id)

        def commit(transaction) -> None:
            run = self._transaction_run(transaction, run_ref)
            failed = run.model_copy(
                update={
                    "status": "failed",
                    "finished_at": finished_at,
                    "error": error,
                }
            )
            transaction.set(run_ref, self._dump(failed))

        self._run_transaction(commit)

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
        run_ref = self._document(self.RUNS, run_id)
        source_ref = self._document(self.SOURCE_STATES, source_id)
        proposal_ref = self._client.collection(self.PROPOSALS).document()

        def commit(transaction) -> None:
            run = self._transaction_running_run(transaction, run_ref)
            completed = run.model_copy(
                update={
                    "status": "proposal_created",
                    "finished_at": finished_at,
                    "previous_sha256": previous_sha256,
                    "current_sha256": current_sha256,
                    "proposal_id": proposal_ref.id,
                    "error": None,
                }
            )
            transaction.create(proposal_ref, self._dump(proposal))
            transaction.set(source_ref, self._dump(source_state))
            transaction.set(run_ref, self._dump(completed))

        self._run_transaction(commit)
        return proposal_ref.id

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
        run_ref = self._document(self.RUNS, run_id)
        source_ref = self._document(self.SOURCE_STATES, source_id)

        def commit(transaction) -> None:
            run = self._transaction_running_run(transaction, run_ref)
            completed = run.model_copy(
                update={
                    "status": "no_change",
                    "finished_at": finished_at,
                    "previous_sha256": previous_sha256,
                    "current_sha256": current_sha256,
                    "proposal_id": None,
                    "error": None,
                }
            )
            transaction.set(source_ref, self._dump(source_state))
            transaction.set(run_ref, self._dump(completed))

        self._run_transaction(commit)

    def get_source_state(self, source_id: str) -> SourceState | None:
        snapshot = self._document(self.SOURCE_STATES, source_id).get()
        if not snapshot.exists:
            return None
        return SourceState.model_validate(snapshot.to_dict())

    def put_source_state(self, source_id: str, state: SourceState) -> None:
        self._document(self.SOURCE_STATES, source_id).set(self._dump(state))

    def get_proposal(self, proposal_id: str | None) -> PolicyProposal:
        if proposal_id is None:
            raise KeyError("proposal id is required")
        return self._read(self.PROPOSALS, proposal_id, PolicyProposal)

    def list_proposals(self) -> dict[str, PolicyProposal]:
        return self._list(self.PROPOSALS, PolicyProposal)

    def put_snapshot(self, snapshot: PolicySnapshot) -> None:
        self._document(self.SNAPSHOTS, snapshot.version).create(self._dump(snapshot))

    def get_snapshot(self, version: str) -> PolicySnapshot:
        return self._read(self.SNAPSHOTS, version, PolicySnapshot)

    def list_snapshots(self) -> dict[str, PolicySnapshot]:
        return self._list(self.SNAPSHOTS, PolicySnapshot)

    def latest_snapshot(self) -> PolicySnapshot | None:
        snapshots = self.list_snapshots()
        if not snapshots:
            return None
        version = max(snapshots, key=lambda item: int(item[1:]))
        return snapshots[version]

    def get_outbox(self, outbox_id: str) -> PolicyOutbox:
        return self._read(self.OUTBOX, outbox_id, PolicyOutbox)

    def list_outbox(self) -> dict[str, PolicyOutbox]:
        return self._list(self.OUTBOX, PolicyOutbox)

    def put_outbox(self, outbox_id: str, outbox: PolicyOutbox) -> None:
        self._document(self.OUTBOX, outbox_id).create(self._dump(outbox))

    def commit_publication(
        self,
        proposal_id: str,
        snapshot: PolicySnapshot,
        outbox_id: str,
        outbox: PolicyOutbox,
    ) -> None:
        proposal_ref = self._document(self.PROPOSALS, proposal_id)
        snapshot_ref = self._document(self.SNAPSHOTS, snapshot.version)
        outbox_ref = self._document(self.OUTBOX, outbox_id)

        def commit(transaction) -> None:
            proposal_snapshot = self._transaction_snapshot(
                transaction, proposal_ref
            )
            if proposal_snapshot is None or not proposal_snapshot.exists:
                raise KeyError(f"missing proposal document: {proposal_id}")
            proposal = PolicyProposal.model_validate(proposal_snapshot.to_dict())
            if proposal.status is not ProposalStatus.PENDING:
                raise ValueError("proposal is not pending")
            existing_snapshot = self._transaction_snapshot(
                transaction, snapshot_ref
            )
            if existing_snapshot is not None and existing_snapshot.exists:
                raise ValueError("snapshot already exists")
            existing_outbox = self._transaction_snapshot(
                transaction, outbox_ref
            )
            if existing_outbox is not None and existing_outbox.exists:
                raise ValueError("outbox already exists")

            proposal_data = proposal.model_dump(mode="python")
            proposal_data.update(
                status=ProposalStatus.PUBLISHED,
                published_version=snapshot.version,
            )
            published = PolicyProposal.model_validate(proposal_data)
            transaction.create(snapshot_ref, self._dump(snapshot))
            transaction.create(outbox_ref, self._dump(outbox))
            transaction.set(proposal_ref, self._dump(published))

        self._run_transaction(commit)

    def discard_proposal(self, proposal_id: str) -> None:
        proposal_ref = self._document(self.PROPOSALS, proposal_id)

        def commit(transaction) -> None:
            proposal_snapshot = self._transaction_snapshot(
                transaction, proposal_ref
            )
            if proposal_snapshot is None or not proposal_snapshot.exists:
                raise KeyError(f"missing proposal document: {proposal_id}")
            proposal = PolicyProposal.model_validate(proposal_snapshot.to_dict())
            if proposal.status is not ProposalStatus.PENDING:
                raise ValueError("proposal is not pending")
            proposal_data = proposal.model_dump(mode="python")
            proposal_data.update(
                status=ProposalStatus.DISCARDED,
                published_version=None,
            )
            transaction.set(
                proposal_ref,
                self._dump(PolicyProposal.model_validate(proposal_data)),
            )

        self._run_transaction(commit)

    def list_pending_outbox(self, limit: int) -> list[tuple[str, PolicyOutbox]]:
        pending = [
            (outbox_id, row)
            for outbox_id, row in self.list_outbox().items()
            if row.status is OutboxStatus.PENDING
        ]
        pending.sort(key=lambda item: (item[1].created_at, item[0]))
        return pending[: max(0, limit)]

    def mark_outbox_sent(
        self,
        outbox_id: str,
        sent_at: datetime,
        pubsub_message_id: str,
    ) -> None:
        if not pubsub_message_id:
            raise ValueError("pubsub message id is required")
        outbox_ref = self._document(self.OUTBOX, outbox_id)

        def commit(transaction) -> None:
            outbox_snapshot = self._transaction_snapshot(
                transaction, outbox_ref
            )
            if outbox_snapshot is None or not outbox_snapshot.exists:
                raise KeyError(f"missing outbox document: {outbox_id}")
            outbox = PolicyOutbox.model_validate(outbox_snapshot.to_dict())
            if outbox.status is not OutboxStatus.PENDING:
                raise ValueError("outbox is not pending")
            outbox_data = outbox.model_dump(mode="python")
            outbox_data.update(
                status=OutboxStatus.SENT,
                sent_at=sent_at,
                pubsub_message_id=pubsub_message_id,
            )
            transaction.set(
                outbox_ref,
                self._dump(PolicyOutbox.model_validate(outbox_data)),
            )

        self._run_transaction(commit)

    def _document(self, collection: str, document_id: str):
        return self._client.collection(collection).document(document_id)

    @staticmethod
    def _transaction_run(transaction, run_ref) -> PolicyRun:
        snapshot = FirestorePolicyRepository._transaction_snapshot(
            transaction, run_ref
        )
        if snapshot is None or not snapshot.exists:
            raise KeyError(f"missing run document: {run_ref.id}")
        return PolicyRun.model_validate(snapshot.to_dict())

    @staticmethod
    def _transaction_snapshot(transaction, reference):
        result = transaction.get(reference)
        if hasattr(result, "exists"):
            return result
        snapshots = list(result)
        if not snapshots:
            return None
        if len(snapshots) != 1:
            raise ValueError("document transaction read returned multiple snapshots")
        return snapshots[0]

    @classmethod
    def _transaction_running_run(cls, transaction, run_ref) -> PolicyRun:
        run = cls._transaction_run(transaction, run_ref)
        if run.status != "running":
            raise ValueError("run is not running")
        return run

    def _read(self, collection: str, document_id: str, model: type[ModelT]) -> ModelT:
        snapshot = self._document(collection, document_id).get()
        if not snapshot.exists:
            raise KeyError(f"missing {collection} document: {document_id}")
        return model.model_validate(snapshot.to_dict())

    def _list(self, collection: str, model: type[ModelT]) -> dict[str, ModelT]:
        return {
            snapshot.id: model.model_validate(snapshot.to_dict())
            for snapshot in self._client.collection(collection).stream()
        }

    @staticmethod
    def _dump(model: BaseModel) -> dict[str, object]:
        return model.model_dump(mode="python")
