"""projects/{project_id} document and its embedded profiles (TDD section 2.1)."""

from __future__ import annotations

from pydantic import AwareDatetime, Field, model_validator

from .common import DomainModel, EvidenceRef
from .enums import (
    BudgetBand,
    ClaimedFormType,
    FormType,
    Phase,
    ProjectState,
    Tier,
)
from .policy_snapshot import VerificationStatus


class IntentProfile(DomainModel):
    """S1 wizard answers. Every field may stay unknown; unknown is never invented."""

    form_type_claimed: ClaimedFormType = ClaimedFormType.UNKNOWN
    genre_keywords: list[str] = Field(default_factory=list)
    logline: str | None = None
    episode_count: int | None = Field(default=None, ge=1)
    episode_minutes: float | None = Field(default=None, gt=0)
    budget_band: BudgetBand = BudgetBand.UNKNOWN
    investment_amount_rmb: int | None = Field(default=None, ge=0)
    is_ai_generated: bool | None = None
    has_finished_film: bool | None = None
    source: str = "user_stated"

    def missing_fields(self) -> list[str]:
        """Fields D1a needs before it can decide anything."""

        missing: list[str] = []
        if self.episode_count is None:
            missing.append("episode_count")
        if self.episode_minutes is None:
            missing.append("episode_minutes")
        if not self.logline:
            missing.append("logline")
        return missing


class TracksEnabled(DomainModel):
    china: bool = True
    us: bool = False


class ChannelProfile(DomainModel):
    """S2 distribution answers."""

    domestic_platforms: list[str] = Field(default_factory=list)
    overseas: list[str] = Field(default_factory=list)
    theatrical_intent: bool = False
    tracks_enabled: TracksEnabled = Field(default_factory=TracksEnabled)


class MatchedRule(DomainModel):
    """A subject rule hit, always carrying the verbatim trigger text."""

    rule_id: str
    quote: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    stage: str = "pattern"


class Classification(DomainModel):
    """Output of the D1a -> D1b -> D1c chain, pinned to one snapshot version."""

    form_type: FormType = FormType.UNDETERMINED
    tier: Tier = Tier.UNDETERMINED
    tier_provisional: bool = False
    special_subject_hit: bool = False
    co_review_required: bool = False
    matched_rules: list[MatchedRule] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    policy_snapshot_version: str
    policy_verification_status: VerificationStatus = VerificationStatus.MOCK_VERIFIED
    pending_flags: list[str] = Field(default_factory=list)
    # Ground rule 2: a classification that asserts a tier or a special subject
    # must point at the clauses it read, in the snapshot it was pinned to.
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    dept: dict | None = None
    decided_at: AwareDatetime | None = None


class RoadmapStep(DomainModel):
    idx: int = Field(ge=1)
    name: str
    owner: str
    material_refs: list[str] = Field(default_factory=list)
    status: str = "pending"
    est_weeks: int | None = None


class Roadmap(DomainModel):
    template: str
    steps: list[RoadmapStep]
    current_step_idx: int = 1
    confirmed: bool = False


class Project(DomainModel):
    """The workflow aggregate. State is only ever changed by WorkflowService."""

    project_id: str
    owner_uid: str
    title_working: str | None = None
    phase: Phase = Phase.PRE_SHOOT
    state: ProjectState = ProjectState.DRAFT
    intent_profile: IntentProfile = Field(default_factory=IntentProfile)
    channel_profile: ChannelProfile = Field(default_factory=ChannelProfile)
    classification: Classification | None = None
    roadmap: Roadmap | None = None
    registration_number: str | None = None
    policy_stale: bool = False
    created_at: AwareDatetime
    updated_at: AwareDatetime
    schema_version: int = 1

    @model_validator(mode="after")
    def validate_filing(self) -> Project:
        if self.state is ProjectState.FILED and not self.registration_number:
            raise ValueError("FILED projects require a registration_number")
        return self
