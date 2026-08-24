from datetime import datetime, timedelta, timezone
from copy import deepcopy

from pydantic import ValidationError
import pytest

from schemas.policy_snapshot import (
    OutboxStatus,
    PackName,
    PolicyOutbox,
    PolicyPacks,
    PolicyProposal,
    PolicySnapshot,
    PolicyUpdatedEvent,
    ProposalStatus,
    SnapshotDiff,
)
from fakes.firestore import FakeFirestoreClient, FakeTransaction
from workers.policy.adapters.firestore_policy import FirestorePolicyRepository
from workers.policy.models import SourceState


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def build_repository():
    client = FakeFirestoreClient()
    return FirestorePolicyRepository(client, client.run_transaction), client


class SdkLikeFakeTransaction(FakeTransaction):
    def get(self, reference):
        return iter([super().get(reference)])


class SdkLikeFakeFirestoreClient(FakeFirestoreClient):
    def transaction(self):
        return SdkLikeFakeTransaction(self)


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


def make_source_state(digest: str = "b" * 64) -> SourceState:
    return SourceState(
        last_success_at=NOW,
        raw_uri="gs://policy-bucket/policy/raw/source/body.html",
        normalized_uri="gs://policy-bucket/policy/normalized/source/body.txt",
        normalized_sha256=digest,
    )


def make_outbox(version: str = "v2", *, created_at: datetime = NOW) -> PolicyOutbox:
    outbox_id = f"policy.updated:{version}"
    return PolicyOutbox(
        topic="policy.updated",
        payload=PolicyUpdatedEvent(
            snapshot_version=version,
            impact=["D1c"],
            thresholds_published=False,
            effective_from=NOW,
            published_at=NOW,
            idempotency_key=outbox_id,
        ),
        status=OutboxStatus.PENDING,
        created_at=created_at,
        sent_at=None,
        pubsub_message_id=None,
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


def test_refresh_no_change_updates_run_and_source_state_together() -> None:
    repository, _ = build_repository()
    repository.create_run("run_001", "source", NOW)
    state = make_source_state()

    repository.commit_refresh_no_change(
        run_id="run_001",
        source_id="source",
        source_state=state,
        finished_at=NOW + timedelta(seconds=1),
        previous_sha256="a" * 64,
        current_sha256="b" * 64,
    )

    run = repository.get_run("run_001")
    assert run.status == "no_change"
    assert run.previous_sha256 == "a" * 64
    assert run.current_sha256 == "b" * 64
    assert repository.get_source_state("source") == state


def test_refresh_proposal_creates_auto_id_and_updates_all_state() -> None:
    repository, _ = build_repository()
    repository.create_run("run_001", "source", NOW)
    state = make_source_state()

    proposal_id = repository.commit_refresh_proposal(
        run_id="run_001",
        source_id="source",
        proposal=make_proposal(),
        source_state=state,
        finished_at=NOW + timedelta(seconds=1),
        previous_sha256="a" * 64,
        current_sha256="b" * 64,
    )

    assert proposal_id == "auto_001"
    assert repository.get_proposal(proposal_id) == make_proposal()
    assert repository.get_source_state("source") == state
    run = repository.get_run("run_001")
    assert run.status == "proposal_created"
    assert run.proposal_id == proposal_id


@pytest.mark.parametrize("method", ["no_change", "proposal"])
def test_missing_run_rolls_back_refresh(method: str) -> None:
    repository, client = build_repository()
    before = deepcopy(client.documents)

    with pytest.raises(KeyError):
        if method == "no_change":
            repository.commit_refresh_no_change(
                run_id="missing",
                source_id="source",
                source_state=make_source_state(),
                finished_at=NOW,
                previous_sha256=None,
                current_sha256="b" * 64,
            )
        else:
            repository.commit_refresh_proposal(
                run_id="missing",
                source_id="source",
                proposal=make_proposal(),
                source_state=make_source_state(),
                finished_at=NOW,
                previous_sha256="a" * 64,
                current_sha256="b" * 64,
            )

    assert client.documents == before


def test_non_running_run_rolls_back_refresh_proposal() -> None:
    repository, client = build_repository()
    repository.create_run("run_001", "source", NOW)
    repository.commit_refresh_no_change(
        run_id="run_001",
        source_id="source",
        source_state=make_source_state(),
        finished_at=NOW,
        previous_sha256=None,
        current_sha256="b" * 64,
    )
    before = deepcopy(client.documents)

    with pytest.raises(ValueError, match="run is not running"):
        repository.commit_refresh_proposal(
            run_id="run_001",
            source_id="source",
            proposal=make_proposal(),
            source_state=make_source_state("c" * 64),
            finished_at=NOW,
            previous_sha256="b" * 64,
            current_sha256="c" * 64,
        )

    assert client.documents == before


def test_fail_run_preserves_hashes_and_source_state() -> None:
    repository, client = build_repository()
    repository.create_run("run_001", "source", NOW)
    state = make_source_state("a" * 64)
    repository.put_source_state("source", state)
    client.documents["policy_runs/run_001"].update(
        previous_sha256="0" * 64,
        current_sha256="a" * 64,
    )

    repository.fail_run("run_001", "POLICY_REFRESH_FAILED", NOW)

    run = repository.get_run("run_001")
    assert run.status == "failed"
    assert run.error == "POLICY_REFRESH_FAILED"
    assert run.previous_sha256 == "0" * 64
    assert run.current_sha256 == "a" * 64
    assert repository.get_source_state("source") == state


def test_firestore_transactions_accept_sdk_streamed_document_get() -> None:
    client = SdkLikeFakeFirestoreClient()
    repository = FirestorePolicyRepository(client, client.run_transaction)
    repository.create_run("run_sdk", "source", NOW)

    repository.commit_refresh_no_change(
        run_id="run_sdk",
        source_id="source",
        source_state=make_source_state(),
        finished_at=NOW,
        previous_sha256=None,
        current_sha256="b" * 64,
    )

    assert repository.get_run("run_sdk").status == "no_change"


def test_publication_updates_proposal_and_creates_snapshot_and_outbox() -> None:
    repository, client = build_repository()
    client.documents["policy_proposals/proposal_001"] = make_proposal().model_dump(
        mode="python"
    )
    snapshot = make_snapshot("v2")
    outbox = make_outbox()

    repository.commit_publication(
        "proposal_001",
        snapshot,
        "policy.updated:v2",
        outbox,
    )

    proposal = repository.get_proposal("proposal_001")
    assert proposal.status is ProposalStatus.PUBLISHED
    assert proposal.published_version == "v2"
    assert repository.get_snapshot("v2") == snapshot
    assert repository.get_outbox("policy.updated:v2") == outbox


@pytest.mark.parametrize("collision", ["snapshot", "outbox"])
def test_publication_collision_rolls_back_every_change(collision: str) -> None:
    repository, client = build_repository()
    client.documents["policy_proposals/proposal_001"] = make_proposal().model_dump(
        mode="python"
    )
    if collision == "snapshot":
        client.documents["policy_snapshots/v2"] = make_snapshot("v2").model_dump(
            mode="python"
        )
    else:
        client.documents["policy_outbox/policy.updated:v2"] = make_outbox().model_dump(
            mode="python"
        )
    before = deepcopy(client.documents)

    with pytest.raises(ValueError):
        repository.commit_publication(
            "proposal_001",
            make_snapshot("v2"),
            "policy.updated:v2",
            make_outbox(),
        )

    assert client.documents == before


@pytest.mark.parametrize("status", [ProposalStatus.DISCARDED, ProposalStatus.PUBLISHED])
def test_publication_rejects_non_pending_proposal(status: ProposalStatus) -> None:
    repository, client = build_repository()
    proposal = make_proposal().model_copy(
        update={
            "status": status,
            "published_version": "v1" if status is ProposalStatus.PUBLISHED else None,
        }
    )
    client.documents["policy_proposals/proposal_001"] = proposal.model_dump(
        mode="python"
    )
    before = deepcopy(client.documents)

    with pytest.raises(ValueError, match="proposal is not pending"):
        repository.commit_publication(
            "proposal_001",
            make_snapshot("v2"),
            "policy.updated:v2",
            make_outbox(),
        )

    assert client.documents == before


def test_discard_only_accepts_pending_proposal() -> None:
    repository, client = build_repository()
    client.documents["policy_proposals/proposal_001"] = make_proposal().model_dump(
        mode="python"
    )

    repository.discard_proposal("proposal_001")

    assert repository.get_proposal("proposal_001").status is ProposalStatus.DISCARDED
    with pytest.raises(ValueError, match="proposal is not pending"):
        repository.discard_proposal("proposal_001")


def test_pending_outbox_is_sorted_and_limited() -> None:
    repository, client = build_repository()
    rows = [
        ("policy.updated:v4", make_outbox("v4", created_at=NOW + timedelta(seconds=2))),
        ("policy.updated:v3", make_outbox("v3", created_at=NOW + timedelta(seconds=1))),
        ("policy.updated:v2", make_outbox("v2", created_at=NOW + timedelta(seconds=1))),
    ]
    for outbox_id, row in rows:
        client.documents[f"policy_outbox/{outbox_id}"] = row.model_dump(mode="python")

    selected = repository.list_pending_outbox(2)

    assert [outbox_id for outbox_id, _ in selected] == [
        "policy.updated:v2",
        "policy.updated:v3",
    ]


def test_mark_outbox_sent_requires_pending_and_non_empty_message_id() -> None:
    repository, client = build_repository()
    outbox_id = "policy.updated:v2"
    client.documents[f"policy_outbox/{outbox_id}"] = make_outbox().model_dump(
        mode="python"
    )

    with pytest.raises(ValueError, match="message id"):
        repository.mark_outbox_sent(outbox_id, NOW, "")
    assert repository.get_outbox(outbox_id).status is OutboxStatus.PENDING

    repository.mark_outbox_sent(outbox_id, NOW, "message-123")
    sent = repository.get_outbox(outbox_id)
    assert sent.status is OutboxStatus.SENT
    assert sent.pubsub_message_id == "message-123"
    with pytest.raises(ValueError, match="outbox is not pending"):
        repository.mark_outbox_sent(outbox_id, NOW, "message-456")
