from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
import pytest

from schemas.policy_snapshot import (
    PackName,
    PolicyPacks,
    PolicyProposal,
    PolicySnapshot,
    ProposalStatus,
    SnapshotDiff,
)
from fakes.firestore import FakeFirestoreClient
from workers.policy.adapters.firestore_policy import FirestorePolicyRepository
from workers.policy.models import SourceState


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def build_repository():
    client = FakeFirestoreClient()
    return FirestorePolicyRepository(client, client.run_transaction), client


def make_snapshot(version: str) -> PolicySnapshot:
    return PolicySnapshot(
        version=version,
        published_at=NOW,
        effective_from=NOW,
        published_by="admin_richard",
        packs=PolicyPacks(
            p1_form_definition={"scope": "micro_drama"},
            p2_subject_rules={"platform": "all"},
            p3_tier_thresholds={"thresholds_published": False},
            p4_process_templates={},
            p5_form_templates={},
            p6_legal_clauses={},
        ),
        diff_from_prev=SnapshotDiff(summary="seed", impact=["D1c"]),
        thresholds_published=False,
    )


def make_proposal() -> PolicyProposal:
    return PolicyProposal(
        created_at=NOW,
        source_diff_uri="gs://policy-bucket/policy/diffs/source/a..b.json",
        summary="source changed",
        impact=["D1c"],
        effective_from=NOW,
        draft_pack_updates={
            PackName.P3_TIER_THRESHOLDS: {"thresholds_published": False}
        },
        status=ProposalStatus.PENDING,
        published_version=None,
    )


def test_create_get_and_list_runs() -> None:
    repository, _ = build_repository()
    repository.create_run("run_002", "source", NOW)
    repository.create_run("run_001", "source", NOW - timedelta(seconds=1))

    assert repository.get_run("run_001").status == "running"
    assert list(repository.list_runs()) == ["run_001", "run_002"]


def test_get_and_put_source_state() -> None:
    repository, _ = build_repository()
    state = SourceState(
        last_success_at=NOW,
        raw_uri="gs://policy-bucket/policy/raw/source/body.html",
        normalized_uri="gs://policy-bucket/policy/normalized/source/body.txt",
        normalized_sha256="a" * 64,
    )

    assert repository.get_source_state("source") is None
    repository.put_source_state("source", state)
    assert repository.get_source_state("source") == state


def test_lists_validated_proposals_and_snapshots() -> None:
    repository, client = build_repository()
    client.documents["policy_proposals/proposal_001"] = make_proposal().model_dump(
        mode="python"
    )
    repository.put_snapshot(make_snapshot("v1"))

    assert list(repository.list_proposals()) == ["proposal_001"]
    assert list(repository.list_snapshots()) == ["v1"]
    assert repository.get_proposal("proposal_001").status is ProposalStatus.PENDING
    assert repository.get_snapshot("v1").version == "v1"


def test_latest_snapshot_uses_numeric_version_order() -> None:
    repository, _ = build_repository()
    repository.put_snapshot(make_snapshot("v9"))
    repository.put_snapshot(make_snapshot("v10"))

    assert repository.latest_snapshot().version == "v10"


@pytest.mark.parametrize(
    "path,read",
    [
        ("policy_runs/bad", lambda repository: repository.get_run("bad")),
        (
            "policy_proposals/bad",
            lambda repository: repository.get_proposal("bad"),
        ),
        (
            "policy_snapshots/bad",
            lambda repository: repository.get_snapshot("bad"),
        ),
        (
            "policy_source_states/bad",
            lambda repository: repository.get_source_state("bad"),
        ),
    ],
)
def test_invalid_stored_documents_fail_validation(path, read) -> None:
    repository, client = build_repository()
    client.documents[path] = {"unexpected": True}

    with pytest.raises(ValidationError):
        read(repository)


@pytest.mark.parametrize(
    "read",
    [
        lambda repository: repository.get_run("missing"),
        lambda repository: repository.get_proposal("missing"),
        lambda repository: repository.get_snapshot("missing"),
    ],
)
def test_missing_documents_raise_key_error(read) -> None:
    repository, _ = build_repository()

    with pytest.raises(KeyError):
        read(repository)
