"""Versioned policy contracts shared by the A and B workstreams."""

from __future__ import annotations

from datetime import datetime

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


Version = Annotated[str, StringConstraints(pattern=r"^v[1-9][0-9]*$")]


class ContractModel(BaseModel):
    """Base settings for boundary contracts."""

    model_config = ConfigDict(extra="forbid")


class PackName(StrEnum):
    P1_FORM_DEFINITION = "p1_form_definition"
    P2_SUBJECT_RULES = "p2_subject_rules"
    P3_TIER_THRESHOLDS = "p3_tier_thresholds"
    P4_PROCESS_TEMPLATES = "p4_process_templates"
    P5_FORM_TEMPLATES = "p5_form_templates"
    P6_LEGAL_CLAUSES = "p6_legal_clauses"


class ImpactNode(StrEnum):
    # D1b is the subject match: the trigger vocabulary a snapshot carries.
    # It had no node, so a change to that vocabulary could be published and
    # no project was ever marked stale by it -- the one impact the loop could
    # not express. See D-050.
    D1B = "D1b"
    D1C = "D1c"
    C1A = "C1-a"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    DISCARDED = "discarded"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"


class VerificationStatus(StrEnum):
    MOCK_VERIFIED = "mock_verified"
    HUMAN_VERIFIED = "human_verified"


def _validate_pack(value: dict[str, Any]) -> dict[str, Any]:
    """A pack is inline data or exactly one GCS blob reference."""

    if "blob_uri" not in value:
        return value
    if set(value) != {"blob_uri"}:
        raise ValueError("a pack cannot mix blob_uri with inline fields")
    blob_uri = value["blob_uri"]
    if not isinstance(blob_uri, str) or not blob_uri.startswith("gs://"):
        raise ValueError("blob_uri must be a gs:// URI")
    return value


class PolicyPacks(ContractModel):
    p1_form_definition: dict[str, Any]
    p2_subject_rules: dict[str, Any]
    p3_tier_thresholds: dict[str, Any]
    p4_process_templates: dict[str, Any]
    p5_form_templates: dict[str, Any]
    p6_legal_clauses: dict[str, Any]

    @field_validator("*")
    @classmethod
    def validate_inline_or_blob(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_pack(value)


class SnapshotDiff(ContractModel):
    summary: str = Field(min_length=1, max_length=1000)
    impact: list[ImpactNode]

    @field_validator("impact")
    @classmethod
    def deduplicate_impact(cls, value: list[ImpactNode]) -> list[ImpactNode]:
        return list(dict.fromkeys(value))


class PolicySnapshot(ContractModel):
    version: Version
    published_at: AwareDatetime
    effective_from: AwareDatetime
    published_by: str = Field(min_length=1)
    packs: PolicyPacks
    diff_from_prev: SnapshotDiff
    thresholds_published: bool
    verification_status: VerificationStatus = VerificationStatus.MOCK_VERIFIED


class PolicyProposal(ContractModel):
    created_at: AwareDatetime
    source_diff_uri: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=1000)
    impact: list[ImpactNode] = Field(min_length=1)
    effective_from: AwareDatetime
    draft_pack_updates: dict[PackName, dict[str, Any]] = Field(min_length=1)
    status: ProposalStatus
    published_version: Version | None

    @field_validator("impact")
    @classmethod
    def deduplicate_impact(cls, value: list[ImpactNode]) -> list[ImpactNode]:
        return list(dict.fromkeys(value))

    @field_validator("draft_pack_updates")
    @classmethod
    def validate_draft_packs(
        cls, value: dict[PackName, dict[str, Any]]
    ) -> dict[PackName, dict[str, Any]]:
        return {name: _validate_pack(pack) for name, pack in value.items()}

    @model_validator(mode="after")
    def validate_publication_state(self) -> PolicyProposal:
        if self.status is ProposalStatus.PUBLISHED and self.published_version is None:
            raise ValueError("published proposals require published_version")
        if self.status is not ProposalStatus.PUBLISHED and self.published_version is not None:
            raise ValueError("only published proposals may have published_version")
        return self


class PolicyUpdatedEvent(ContractModel):
    snapshot_version: Version
    impact: list[ImpactNode] = Field(min_length=1)
    thresholds_published: bool
    effective_from: AwareDatetime
    published_at: AwareDatetime
    idempotency_key: str

    @field_validator("impact")
    @classmethod
    def deduplicate_impact(cls, value: list[ImpactNode]) -> list[ImpactNode]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_idempotency_key(self) -> PolicyUpdatedEvent:
        expected = f"policy.updated:{self.snapshot_version}"
        if self.idempotency_key != expected:
            raise ValueError(f"idempotency_key must be {expected}")
        return self


class PolicyOutbox(ContractModel):
    topic: Literal["policy.updated"]
    payload: PolicyUpdatedEvent
    status: OutboxStatus
    created_at: AwareDatetime
    sent_at: AwareDatetime | None
    pubsub_message_id: str | None

    @model_validator(mode="after")
    def validate_delivery_state(self) -> PolicyOutbox:
        if self.status is OutboxStatus.PENDING:
            if self.sent_at is not None or self.pubsub_message_id is not None:
                raise ValueError("pending outbox rows cannot contain delivery fields")
        elif self.sent_at is None or not self.pubsub_message_id:
            raise ValueError("sent outbox rows require delivery fields")
        return self


class Clause(ContractModel):
    """One cited provision, and the date its own document takes effect.

    `effective_from` is a property of the source, not of the snapshot. A single
    snapshot can carry clauses from documents that come into force on different
    dates — 微短剧发展管理办法 applies from 2026-09-01 while the tier thresholds
    have applied since 2026-01-01 — and the snapshot's own `effective_from`
    answers a different question: from when may this snapshot be used at all.

    Optional, because most clauses in the seed predate the distinction and a
    missing date means "not recorded", never "already in force".
    """

    clause_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    effective_from: AwareDatetime | None = None

    def in_force(self, as_of: datetime) -> bool | None:
        """None when the date is unknown: unknown is not the same as in force."""

        if self.effective_from is None:
            return None
        return self.effective_from <= as_of


class RecalcTierRequest(ContractModel):
    snapshot_version: Version


class RecalcTierResponse(ContractModel):
    tier: Literal["T1", "T2", "T3"]
    tier_provisional: bool
    changed: bool
