from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from schemas.policy_snapshot import PackName, PolicyPacks, PolicySnapshot
from schemas.snapshot import SnapshotNotFoundError
from workers.policy.adapters.repository_snapshot import RepositorySnapshotService
from workers.policy.repository import InMemoryPolicyRepository


ROOT = Path(__file__).parents[2]
SEED_PATH = ROOT / "policy" / "seed-snapshot-v1.yaml"
NOW = datetime(2026, 8, 24, 0, 0, tzinfo=timezone.utc)


def seed_repository() -> tuple[InMemoryPolicyRepository, PolicySnapshot]:
    raw = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    seed = PolicySnapshot.model_validate(raw)
    repository = InMemoryPolicyRepository()
    repository.put_snapshot(seed)
    return repository, seed


def make_v2(
    seed: PolicySnapshot,
    *,
    effective_from: datetime = NOW,
) -> PolicySnapshot:
    packs = seed.packs.model_dump(mode="python")
    packs[PackName.P3_TIER_THRESHOLDS.value] = {
        **packs[PackName.P3_TIER_THRESHOLDS.value],
        "thresholds_published": True,
    }
    data = seed.model_dump(mode="python")
    data.update(
        version="v2",
        published_at=NOW,
        effective_from=effective_from,
        published_by="admin_richard",
        packs=PolicyPacks.model_validate(packs),
        thresholds_published=True,
    )
    return PolicySnapshot.model_validate(data)


def test_explicit_versions_are_readable_and_packs_are_copies() -> None:
    repository, seed = seed_repository()
    repository.put_snapshot(make_v2(seed))
    service = RepositorySnapshotService(repository)

    v1 = service.get_pack(PackName.P3_TIER_THRESHOLDS, "v1")
    v2 = service.get_pack(PackName.P3_TIER_THRESHOLDS, "v2")

    assert v1["thresholds_published"] is False
    assert v2["thresholds_published"] is True
    v2["thresholds_published"] = False
    assert service.get_pack(
        PackName.P3_TIER_THRESHOLDS, "v2"
    )["thresholds_published"] is True


def test_latest_version_respects_effective_from_and_timezone() -> None:
    repository, seed = seed_repository()
    future = NOW + timedelta(days=1)
    repository.put_snapshot(make_v2(seed, effective_from=future))
    service = RepositorySnapshotService(repository)

    assert service.latest_version(as_of=NOW) == "v1"
    assert service.latest_version(as_of=future) == "v2"
    with pytest.raises(ValueError, match="timezone"):
        service.latest_version(as_of=NOW.replace(tzinfo=None))


def test_unknown_version_and_no_effective_snapshot_fail_closed() -> None:
    repository, seed = seed_repository()
    service = RepositorySnapshotService(repository)

    with pytest.raises(SnapshotNotFoundError, match="v99"):
        service.get_pack(PackName.P3_TIER_THRESHOLDS, "v99")
    with pytest.raises(SnapshotNotFoundError, match="no snapshot is effective"):
        service.latest_version(as_of=seed.effective_from - timedelta(seconds=1))


def test_clause_lookup_matches_the_file_adapter_contract() -> None:
    repository, _ = seed_repository()
    service = RepositorySnapshotService(repository)

    clause = service.clause("nrta-order-16-article-2", "v1")

    assert clause.clause_id == "nrta-order-16-article-2"
    with pytest.raises(KeyError, match="clause not found"):
        service.clause("missing_clause", "v1")
