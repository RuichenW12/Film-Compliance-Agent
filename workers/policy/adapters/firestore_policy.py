"""Validated Firestore storage for Richard-owned policy state."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel

from schemas.policy_snapshot import PolicyProposal, PolicySnapshot

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

    def _document(self, collection: str, document_id: str):
        return self._client.collection(collection).document(document_id)

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
