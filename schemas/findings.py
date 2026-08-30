"""C1-a review output (TDD section 2.5)."""

from __future__ import annotations

from pydantic import AwareDatetime, Field, model_validator

from .common import DomainModel, EvidenceRef
from .enums import AlertOption, FindingSeverity, FindingStatus


class Locator(DomainModel):
    """Where a finding is, precisely enough to edit it.

    `quote` is the first matching line, kept verbatim so the evidence rule
    holds. `line` is that line's 1-based position in the uploaded document and
    `match_lines` lists every line in the same scene that matched, so a scene
    reported once can still be traced back line by line.
    """

    episode: int | None = None
    scene: int | None = None
    quote: str
    line: int | None = None
    match_lines: list[int] = Field(default_factory=list)


class AlertDept(DomainModel):
    name: str
    practical_contact: str | None = None
    region_note: str | None = None


class AlertChoice(DomainModel):
    id: AlertOption
    action: str
    impact: str


class Alert(DomainModel):
    """The five-field edge-case alert: reason, dept, options, choice."""

    risk_reason: str
    dept: AlertDept
    options: list[AlertChoice] = Field(min_length=2)
    chosen_option: AlertOption | None = None
    chosen_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_choice(self) -> Alert:
        if self.chosen_option is not None:
            allowed = {option.id for option in self.options}
            if self.chosen_option not in allowed:
                raise ValueError("chosen_option must be one of the offered options")
        return self


class Finding(DomainModel):
    """One reviewed scene conclusion. No evidence -> severity needs_human."""

    finding_id: str
    asset_version: str
    locator: Locator
    category: str
    severity: FindingSeverity
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    dual_regime_conflict: bool = False
    suggestion: str | None = None
    alert: Alert | None = None
    status: FindingStatus = FindingStatus.OPEN
    prompt_version: str | None = None
    snapshot_version: str | None = None
    analysis_generation: int | None = Field(default=None, ge=0)
    active: bool = True
    created_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def enforce_evidence_rule(self) -> Finding:
        """Ground rule 2: an unevidenced legal conclusion is downgraded, never asserted."""

        asserts_conclusion = self.severity in (
            FindingSeverity.BLOCK,
            FindingSeverity.CO_REVIEW_REQUIRED,
            FindingSeverity.CAUTION,
        )
        if asserts_conclusion and not self.evidence_refs:
            raise ValueError(
                "findings that assert a compliance conclusion require evidence_refs"
            )
        return self

    @property
    def blocks_gate_d3(self) -> bool:
        """Only current open conclusions and undispatched alerts block D3."""

        if not self.active:
            return False
        if self.status in (
            FindingStatus.RESOLVED,
            FindingStatus.WAIVED,
            FindingStatus.REJECTED,
        ):
            return False
        if self.severity in (FindingSeverity.BLOCK, FindingSeverity.NEEDS_HUMAN):
            return True
        if self.alert is not None and self.alert.chosen_option is None:
            return True
        return False
