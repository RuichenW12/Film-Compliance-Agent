"""C1-c form drafts (TDD section 2.6). Unknown fields render as PENDING, never invented."""

from __future__ import annotations

from pydantic import AwareDatetime, Field, model_validator

from .common import DomainModel, SourceRef
from .enums import FieldStatus

PENDING_DISPLAY = "待补充"


class FormField(DomainModel):
    value: str | int | float | None = None
    source_ref: SourceRef | None = None
    status: FieldStatus = FieldStatus.PENDING
    confirmed_at: AwareDatetime | None = None
    override_reason: str | None = None

    @model_validator(mode="after")
    def enforce_source_rule(self) -> FormField:
        """Ground rule 3: a filled field must be traceable to a fact."""

        if self.status is FieldStatus.FILLED:
            if self.value in (None, ""):
                raise ValueError("filled fields require a value")
            if self.source_ref is None:
                raise ValueError("filled fields require a source_ref")
        return self

    @property
    def display_value(self) -> str:
        if self.status is FieldStatus.FILLED and self.value is not None:
            return str(self.value)
        return PENDING_DISPLAY


class FormConflict(DomainModel):
    check: str
    message_key: str
    items: list[str] = Field(default_factory=list)


class FormDraft(DomainModel):
    """projects/{pid}/form_drafts/{did}."""

    draft_id: str
    form_type: str = "registration_publicity"
    frozen: bool = False
    fields: dict[str, FormField] = Field(default_factory=dict)
    conflicts: list[FormConflict] = Field(default_factory=list)
    hash: str | None = None
    snapshot_version: str
    confirmed_by_user_at: AwareDatetime | None = None
    parent_draft: str | None = None
    created_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_freeze(self) -> FormDraft:
        if self.frozen and not self.hash:
            raise ValueError("frozen drafts require a content hash")
        return self
