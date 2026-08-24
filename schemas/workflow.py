"""Tasks, notifications, and institution review documents."""

from __future__ import annotations

from pydantic import AwareDatetime, Field, model_validator

from .common import DomainModel
from .enums import InstitutionDecision, NotificationKind, TaskStatus, TaskType


class WorkflowTask(DomainModel):
    """projects/{pid}/tasks/{tid}. idempotency_key is the replay guard."""

    task_id: str
    project_id: str
    type: TaskType
    status: TaskStatus = TaskStatus.QUEUED
    idempotency_key: str
    payload: dict = Field(default_factory=dict)
    result: dict | None = None
    error: str | None = None
    retries: int = 0
    created_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None


class Notification(DomainModel):
    """notifications/{nid}. Text is rendered from keys by the UI locale."""

    notification_id: str
    user_id: str
    project_id: str | None = None
    kind: NotificationKind
    title_key: str
    body_key: str
    params: dict = Field(default_factory=dict)
    link: str | None = None
    read: bool = False
    created_at: AwareDatetime | None = None


class LicenseCheck(DomainModel):
    institution_id: str | None = None
    valid_until: str | None = None
    capital_ok: bool | None = None
    no_foreign_ok: bool | None = None
    mock: bool = True
    reasons: list[str] = Field(default_factory=list)

    @property
    def valid(self) -> bool:
        return bool(self.capital_ok) and bool(self.no_foreign_ok) and not self.reasons


class InstitutionReview(DomainModel):
    """projects/{pid}/institution_reviews/{rid}."""

    review_id: str
    institution_id: str | None = None
    agreement_draft_uri: str | None = None
    license_check: LicenseCheck | None = None
    decision: InstitutionDecision = InstitutionDecision.PENDING
    return_comments: str | None = None
    signed_agreement_uri: str | None = None
    decided_at: AwareDatetime | None = None
    created_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_decision(self) -> InstitutionReview:
        if self.decision is InstitutionDecision.ACCEPT and not self.signed_agreement_uri:
            raise ValueError("accepting an institution review requires signed_agreement_uri")
        if self.decision is InstitutionDecision.RETURN and not self.return_comments:
            raise ValueError("returning a project requires return_comments")
        return self


class MockInstitution(DomainModel):
    """mock_institutions/{iid} - demo licensed-entity registry."""

    institution_id: str
    name: str
    license_no: str
    valid_until: str
    registered_capital_rmb: int
    has_foreign: bool = False
