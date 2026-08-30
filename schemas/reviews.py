"""Contracts for the creator-facing upload-first review orchestration."""

from __future__ import annotations

from enum import StrEnum

from pydantic import AwareDatetime, Field, field_validator, model_validator

from .common import DomainModel
from .enums import AmountBracket


class ReviewState(StrEnum):
    UPLOADING = "UPLOADING"
    EXTRACTING = "EXTRACTING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    ANALYZING = "ANALYZING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class ReviewMode(StrEnum):
    SCRIPT = "script"
    IDEA = "idea"


class CandidateOrigin(StrEnum):
    EXTRACTED = "extracted"
    SUGGESTED = "suggested"


class IntakeStatus(StrEnum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class SemanticStatus(StrEnum):
    COMPLETE = "complete"
    PENDING = "pending"


class ReviewArtifactType(StrEnum):
    FORM = "form"
    SUMMARY = "summary"
    ANNOTATED_SCRIPT = "annotated-script"


class CandidateValue(DomainModel):
    value: str | int | float | list[str]
    origin: CandidateOrigin
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_quote: str | None = None
    explanation: str | None = None

    @model_validator(mode="after")
    def validate_provenance(self) -> CandidateValue:
        if self.origin is CandidateOrigin.SUGGESTED and not (
            self.explanation and self.explanation.strip()
        ):
            raise ValueError("suggested candidates require an explanation")
        return self

class ScriptStructure(DomainModel):
    source_episode_count: int | None = Field(default=None, ge=1)
    source_total_minutes: float | None = Field(default=None, gt=0)
    source_scene_count: int = Field(default=0, ge=0)


class CandidateReviewDetails(DomainModel):
    title: CandidateValue | None = None
    tags: CandidateValue | None = None
    synopsis: CandidateValue | None = None
    episode_count: CandidateValue | None = None
    episode_minutes: CandidateValue | None = None
    amount_bracket: CandidateValue | None = None
    structure: ScriptStructure | None = None


class ConfirmedReviewDetails(DomainModel):
    title: str = Field(min_length=1, max_length=200)
    tags: list[str] = Field(min_length=1, max_length=8)
    synopsis: str = Field(min_length=1, max_length=4000)
    episode_count: int = Field(ge=1, le=500)
    episode_minutes: float = Field(gt=0, le=60)
    amount_bracket: AmountBracket

    @field_validator("title", "synopsis", mode="before")
    @classmethod
    def strip_required_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value):
        if not isinstance(value, list):
            return value
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                normalized.append(item)
                continue
            tag = item.strip()
            if not tag:
                continue
            if len(tag) > 40:
                raise ValueError("tags must be at most 40 characters")
            if tag not in normalized:
                normalized.append(tag)
        return normalized

    @field_validator("amount_bracket")
    @classmethod
    def require_known_amount_bracket(cls, value: AmountBracket) -> AmountBracket:
        if value is AmountBracket.UNKNOWN:
            raise ValueError("amount_bracket must be confirmed")
        return value


class ReviewSession(DomainModel):
    review_id: str
    owner_uid: str
    mode: ReviewMode
    state: ReviewState
    project_id: str
    asset_version: str | None = None
    source_filename: str | None = None
    source_sha256: str | None = None
    normalized_text_uri: str | None = None
    candidates: CandidateReviewDetails | None = None
    confirmed: ConfirmedReviewDetails | None = None
    intake_status: IntakeStatus
    intake_pending_flags: list[str] = Field(default_factory=list)
    semantic_status: SemanticStatus | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def validate_state_payload(self) -> ReviewSession:
        source_fields = (
            "asset_version",
            "source_filename",
            "source_sha256",
            "normalized_text_uri",
        )
        if self.mode is ReviewMode.IDEA:
            if any(getattr(self, field) is not None for field in source_fields):
                raise ValueError("idea sessions cannot carry script source references")
        elif self.state in {
            ReviewState.EXTRACTING,
            ReviewState.AWAITING_CONFIRMATION,
            ReviewState.ANALYZING,
            ReviewState.COMPLETE,
        }:
            for field in source_fields:
                if not getattr(self, field):
                    raise ValueError(
                        f"script sessions in {self.state} require {field}"
                    )

        if self.state is ReviewState.FAILED:
            if not self.error_code:
                raise ValueError("failed sessions require error_code")
            if not self.error_message:
                raise ValueError("failed sessions require error_message")

        if self.state is ReviewState.COMPLETE and self.confirmed is None:
            raise ValueError("complete sessions require confirmed details")
        return self
