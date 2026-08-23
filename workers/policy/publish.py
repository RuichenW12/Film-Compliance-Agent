"""Atomic proposal publication and discard orchestration."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from schemas.policy_snapshot import (
    OutboxStatus,
    PackName,
    PolicyOutbox,
    PolicyPacks,
    PolicySnapshot,
    PolicyUpdatedEvent,
    ProposalStatus,
    SnapshotDiff,
)

from .repository import InMemoryPolicyRepository


class PolicyPublishError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class PublishResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_version: str
    outbox_id: str


class PolicyPublisher:
    def __init__(self, repository: InMemoryPolicyRepository) -> None:
        self._repository = repository

    def publish(
        self, proposal_id: str, actor_uid: str, now: datetime
    ) -> PublishResult:
        try:
            proposal = self._repository.get_proposal(proposal_id)
        except KeyError as exc:
            raise PolicyPublishError(
                "POLICY_PROPOSAL_CONFLICT", "proposal not found"
            ) from exc
        if proposal.status is not ProposalStatus.PENDING:
            raise PolicyPublishError(
                "POLICY_PROPOSAL_CONFLICT", "proposal is not pending"
            )
        if proposal.effective_from > now:
            raise PolicyPublishError(
                "POLICY_NOT_EFFECTIVE", "proposal is not effective yet"
            )

        previous = self._repository.latest_snapshot()
        if previous is None:
            raise PolicyPublishError("SNAPSHOT_NOT_FOUND", "seed snapshot is missing")

        packs_data = previous.packs.model_dump()
        for name, update in proposal.draft_pack_updates.items():
            packs_data[name.value] = deepcopy(update)
        packs = PolicyPacks.model_validate(packs_data)
        thresholds_value = packs.p3_tier_thresholds.get("thresholds_published")
        if not isinstance(thresholds_value, bool):
            raise PolicyPublishError(
                "POLICY_PROPOSAL_INVALID",
                "p3_tier_thresholds.thresholds_published must be boolean",
            )

        version = f"v{int(previous.version[1:]) + 1}"
        snapshot = PolicySnapshot(
            version=version,
            published_at=now,
            effective_from=proposal.effective_from,
            published_by=actor_uid,
            packs=packs,
            diff_from_prev=SnapshotDiff(
                summary=proposal.summary, impact=proposal.impact
            ),
            thresholds_published=thresholds_value,
        )
        event = PolicyUpdatedEvent(
            snapshot_version=version,
            impact=proposal.impact,
            thresholds_published=thresholds_value,
            effective_from=proposal.effective_from,
            published_at=now,
            idempotency_key=f"policy.updated:{version}",
        )
        outbox_id = event.idempotency_key
        outbox = PolicyOutbox(
            topic="policy.updated",
            payload=event,
            status=OutboxStatus.PENDING,
            created_at=now,
            sent_at=None,
            pubsub_message_id=None,
        )
        try:
            self._repository.commit_publication(
                proposal_id, snapshot, outbox_id, outbox
            )
        except (KeyError, ValueError) as exc:
            raise PolicyPublishError(
                "POLICY_PROPOSAL_CONFLICT", "publication conflict"
            ) from exc
        return PublishResult(snapshot_version=version, outbox_id=outbox_id)

    def discard(self, proposal_id: str, actor_uid: str, now: datetime) -> None:
        _ = actor_uid, now
        try:
            self._repository.discard_proposal(proposal_id)
        except (KeyError, ValueError) as exc:
            raise PolicyPublishError(
                "POLICY_PROPOSAL_CONFLICT", "proposal is not pending"
            ) from exc
