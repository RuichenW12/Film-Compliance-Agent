from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from schemas.policy_snapshot import (
    OutboxStatus,
    PackName,
    PolicyProposal,
    PolicySnapshot,
    ProposalStatus,
)
from workers.policy.publish import PolicyPublishError, PolicyPublisher
from workers.policy.repository import InMemoryPolicyRepository


ROOT = Path(__file__).parents[2]
NOW = datetime(2026, 8, 23, 16, 0, tzinfo=timezone(timedelta(hours=8)))


def seed_snapshot() -> PolicySnapshot:
    raw = yaml.safe_load(
        (ROOT / "policy" / "seed-snapshot-v1.yaml").read_text(encoding="utf-8")
    )
    return PolicySnapshot.model_validate(raw)


def proposal(effective_from: datetime) -> PolicyProposal:
    return PolicyProposal(
        created_at=NOW,
        source_diff_uri="file:///tmp/policy-diff.json",
        summary="分类标准正式公布",
        impact=["D1c"],
        effective_from=effective_from,
        draft_pack_updates={
            PackName.P3_TIER_THRESHOLDS: {"thresholds_published": True}
        },
        status=ProposalStatus.PENDING,
        published_version=None,
    )


def build_publisher(effective_from: datetime = NOW):
    repository = InMemoryPolicyRepository()
    repository.put_snapshot(seed_snapshot())
    proposal_id = repository.create_proposal(proposal(effective_from))
    return PolicyPublisher(repository), repository, proposal_id


def test_future_proposal_cannot_publish() -> None:
    publisher, repository, proposal_id = build_publisher(NOW + timedelta(days=1))

    with pytest.raises(PolicyPublishError) as exc_info:
        publisher.publish(proposal_id, "admin_richard", NOW)

    assert exc_info.value.code == "POLICY_NOT_EFFECTIVE"
    assert set(repository.list_snapshots()) == {"v1"}
    assert repository.list_outbox() == {}
    assert repository.get_proposal(proposal_id).status is ProposalStatus.PENDING


def test_publish_creates_v2_updates_proposal_and_writes_pending_outbox() -> None:
    publisher, repository, proposal_id = build_publisher()
    assert seed_snapshot().packs.p3_tier_thresholds["thresholds_published"] is False

    result = publisher.publish(proposal_id, "admin_richard", NOW)

    snapshot = repository.get_snapshot("v2")
    published_proposal = repository.get_proposal(proposal_id)
    outbox = repository.get_outbox(result.outbox_id)
    assert result.snapshot_version == "v2"
    assert result.outbox_id == "policy.updated:v2"
    assert snapshot.thresholds_published is True
    assert snapshot.packs.p3_tier_thresholds["thresholds_published"] is True
    assert snapshot.published_by == "admin_richard"
    assert published_proposal.status is ProposalStatus.PUBLISHED
    assert published_proposal.published_version == "v2"
    assert outbox.status is OutboxStatus.PENDING
    assert outbox.payload.snapshot_version == "v2"
    assert outbox.payload.thresholds_published is True


def test_repeat_publish_is_a_conflict_without_v3() -> None:
    publisher, repository, proposal_id = build_publisher()
    publisher.publish(proposal_id, "admin_richard", NOW)

    with pytest.raises(PolicyPublishError) as exc_info:
        publisher.publish(proposal_id, "admin_richard", NOW)

    assert exc_info.value.code == "POLICY_PROPOSAL_CONFLICT"
    assert set(repository.list_snapshots()) == {"v1", "v2"}
    assert set(repository.list_outbox()) == {"policy.updated:v2"}


def test_discard_only_transitions_a_pending_proposal() -> None:
    publisher, repository, proposal_id = build_publisher()

    publisher.discard(proposal_id, "admin_richard", NOW)

    assert repository.get_proposal(proposal_id).status is ProposalStatus.DISCARDED
    assert set(repository.list_snapshots()) == {"v1"}
    assert repository.list_outbox() == {}
    with pytest.raises(PolicyPublishError) as exc_info:
        publisher.discard(proposal_id, "admin_richard", NOW)
    assert exc_info.value.code == "POLICY_PROPOSAL_CONFLICT"
