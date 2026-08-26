"""Expose published repository snapshots through the product read contract."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from schemas.policy_snapshot import (
    Clause,
    PackName,
    PolicySnapshot,
    VerificationStatus,
)
from schemas.snapshot import SnapshotNotFoundError, SnapshotService
from workers.policy.interfaces import SnapshotReadRepository


class RepositorySnapshotService(SnapshotService):
    """Read inline policy packs from the policy repository."""

    def __init__(self, repository: SnapshotReadRepository) -> None:
        self._repository = repository

    def latest_version(self, as_of: datetime | None = None) -> str:
        effective_at = as_of or datetime.now(timezone.utc)
        if effective_at.tzinfo is None or effective_at.utcoffset() is None:
            raise ValueError("as_of must include timezone information")

        candidates = [
            snapshot
            for snapshot in self._repository.list_snapshots().values()
            if snapshot.effective_from <= effective_at
        ]
        if not candidates:
            raise SnapshotNotFoundError(
                "no snapshot is effective at the requested time"
            )

        latest = max(
            candidates,
            key=lambda snapshot: (
                snapshot.effective_from,
                snapshot.published_at,
            ),
        )
        return latest.version

    def get_pack(self, name: PackName, version: str | None = None) -> dict:
        selected_version = version or self.latest_version()
        snapshot = self._snapshot(selected_version)
        return deepcopy(getattr(snapshot.packs, name.value))

    def clause(self, clause_id: str, version: str) -> Clause:
        legal_pack = self.get_pack(PackName.P6_LEGAL_CLAUSES, version)
        for raw_clause in legal_pack.get("clauses", []):
            clause = Clause.model_validate(raw_clause)
            if clause.clause_id == clause_id:
                return clause
        raise KeyError(f"clause not found: {clause_id}")

    def verification_status(self, version: str) -> VerificationStatus:
        return self._snapshot(version).verification_status

    def _snapshot(self, version: str) -> PolicySnapshot:
        try:
            return self._repository.get_snapshot(version)
        except KeyError as exc:
            raise SnapshotNotFoundError(
                f"snapshot not found: {version}"
            ) from exc
