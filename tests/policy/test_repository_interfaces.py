from datetime import datetime, timezone
from pathlib import Path

import yaml

from schemas.policy_snapshot import PolicySnapshot
from workers.policy.interfaces import PolicyRepository, SnapshotReadRepository
from workers.policy.repository import InMemoryPolicyRepository


NOW = datetime(2026, 8, 24, 0, 0, tzinfo=timezone.utc)
SEED_PATH = Path(__file__).parents[2] / "policy" / "seed-snapshot-v1.yaml"


def test_in_memory_repository_works_through_composed_protocol() -> None:
    repository: PolicyRepository = InMemoryPolicyRepository()

    repository.create_run("run_protocol", "nrta_micro_drama", NOW)

    assert repository.get_run("run_protocol").status == "running"


def test_in_memory_repository_works_through_snapshot_read_protocol() -> None:
    raw = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    seed = PolicySnapshot.model_validate(raw)
    repository = InMemoryPolicyRepository()
    repository.put_snapshot(seed)

    reader: SnapshotReadRepository = repository

    assert reader.get_snapshot("v1").version == "v1"
    assert list(reader.list_snapshots()) == ["v1"]
