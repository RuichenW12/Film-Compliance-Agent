"""Base model settings and shared value objects for A-line domain documents."""

from __future__ import annotations

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .enums import Actor, FactStatus, Regime, SourceRefType

SCHEMA_VERSION = 1


class DomainModel(BaseModel):
    """Domain documents forbid unknown fields so contract drift fails loudly."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class SourceRef(DomainModel):
    """Provenance of a fact or a form field value.

    Ground rule 3: a value without a SourceRef is never rendered as fact.
    """

    type: SourceRefType
    asset_version: str | None = None
    locator: str | None = None
    answer_id: str | None = None
    institution_id: str | None = None

    @model_validator(mode="after")
    def validate_reference_target(self) -> SourceRef:
        if self.type is SourceRefType.ASSET and not self.asset_version:
            raise ValueError("asset source refs require asset_version")
        if self.type is SourceRefType.USER_ANSWER and not self.answer_id:
            raise ValueError("user_answer source refs require answer_id")
        return self


class EvidenceRef(DomainModel):
    """Pointer into the pinned policy snapshot. Ground rule 2."""

    snapshot_version: str
    clause_id: str
    regime: Regime = Regime.CURRENT


class DocMeta(DomainModel):
    """Timestamps every Firestore document carries (TDD section 2)."""

    created_at: AwareDatetime
    updated_at: AwareDatetime
    schema_version: int = SCHEMA_VERSION


class AuditEntry(DomainModel):
    """One state-machine transition. Written on every transition, no exceptions."""

    at: AwareDatetime
    actor: Actor
    from_state: str
    to_state: str
    reason: str
    detail: dict = Field(default_factory=dict)


class TimelineEvent(DomainModel):
    """projects/{pid}/timeline/{eid} - the judge-facing 'agent is working' feed."""

    event_id: str
    at: AwareDatetime
    actor: Actor
    event: str
    detail: dict = Field(default_factory=dict)


class Fact(DomainModel):
    """projects/{pid}/facts/{fid} - the only legal source for form fields."""

    fact_id: str
    key: str
    value: str | int | float | None
    source_ref: SourceRef
    status: FactStatus = FactStatus.CONFIRMED
    conflicts_with: str | None = None
    created_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_unknown_value(self) -> Fact:
        if self.value is None and self.status is FactStatus.CONFIRMED:
            raise ValueError("a confirmed fact cannot have a null value")
        return self


def as_utc(value: datetime) -> datetime:
    """Guard against naive datetimes leaking into stored documents."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetimes must be timezone aware")
    return value
