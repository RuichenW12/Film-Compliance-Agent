"""Read interface for effective policy snapshots."""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .policy_snapshot import Clause, PackName, PolicySnapshot


class SnapshotNotFoundError(LookupError):
    code = "SNAPSHOT_NOT_FOUND"

    def __init__(self, message: str) -> None:
        super().__init__(f"{self.code}: {message}")


class SnapshotService(ABC):
    """The only policy snapshot read interface exposed to the A-line."""

    @abstractmethod
    def latest_version(self, as_of: datetime | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_pack(self, name: PackName, version: str | None = None) -> dict:
        raise NotImplementedError

    @abstractmethod
    def clause(self, clause_id: str, version: str) -> Clause:
        raise NotImplementedError


class FileSnapshotService(SnapshotService):
    """Read and validate the Gate 1 YAML seed through the shared contract."""

    def __init__(self, snapshot_path: str | Path) -> None:
        raw = yaml.safe_load(Path(snapshot_path).read_text(encoding="utf-8"))
        snapshot = PolicySnapshot.model_validate(raw)
        self._snapshots = {snapshot.version: snapshot}

    def latest_version(self, as_of: datetime | None = None) -> str:
        effective_at = as_of or datetime.now(timezone.utc)
        if effective_at.tzinfo is None or effective_at.utcoffset() is None:
            raise ValueError("as_of must include timezone information")

        candidates = [
            snapshot
            for snapshot in self._snapshots.values()
            if snapshot.effective_from <= effective_at
        ]
        if not candidates:
            raise SnapshotNotFoundError("no snapshot is effective at the requested time")

        latest = max(
            candidates,
            key=lambda snapshot: (snapshot.effective_from, snapshot.published_at),
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

    def _snapshot(self, version: str) -> PolicySnapshot:
        try:
            return self._snapshots[version]
        except KeyError as exc:
            raise SnapshotNotFoundError(f"snapshot not found: {version}") from exc
