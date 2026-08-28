"""Request and response bodies. Domain shapes come from `schemas/`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from schemas.enums import (
    AssetKind,
    AmountBracket,
    ClaimedFormType,
    ExitKind,
    ProductionStage,
    ProjectState,
)
from schemas.common import Fact
from schemas.findings import Finding
from schemas.workflow import InstitutionReview, WorkflowTask
from schemas.project import Classification, Roadmap


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateProjectRequest(ApiModel):
    title_working: str | None = None


class CreateProjectResponse(ApiModel):
    project_id: str
    state: ProjectState


class IntentRequest(ApiModel):
    """S1. Every field is optional: partial submissions are the normal case."""

    form_type_claimed: ClaimedFormType | None = None
    genre_keywords: list[str] | None = None
    synopsis: str | None = None
    synopsis: str | None = None
    episode_count: int | None = Field(default=None, ge=1)
    episode_minutes: float | None = Field(default=None, gt=0)
    amount_bracket: AmountBracket | None = None
    investment_amount_rmb: int | None = Field(default=None, ge=0)
    is_ai_generated: bool | None = None
    production_stage: ProductionStage | None = None
    # 广电办发〔2024〕35号 makes 重点微短剧 any one of four conditions. These are
    # the two that have nothing to do with money, and they must be accepted here
    # or the wizard's whole submission is rejected: ApiModel forbids extras.
    platform_promoted: bool | None = None
    voluntary_key_declaration: bool | None = None


class FieldHelpRequest(ApiModel):
    """A question about one intake field. Not a project, not an answer to it."""

    field: str
    question: str = ""
    # What the form calls this field. Sent by the UI so the answer talks about
    # "AI generated content" rather than `is_ai_generated`.
    label: str = ""


class FieldHelpResponse(ApiModel):
    """Prose, and the clauses it was drawn from.

    There is no value here. The reply cannot fill the field it explains, which
    is why the extraction guard this replaced is no longer needed.
    """

    answer: str = ""
    clause_refs: list[str] = Field(default_factory=list)
    snapshot_version: str = ""
    pending_flags: list[str] = Field(default_factory=list)


class IntentResponse(ApiModel):
    state: ProjectState
    missing: list[str]


class ChannelsRequest(ApiModel):
    domestic_platforms: list[str] | None = None
    overseas: list[str] | None = None
    theatrical_intent: bool | None = None


class TracksEnabledResponse(ApiModel):
    china: bool
    us: bool


class ChannelsResponse(ApiModel):
    tracks_enabled: TracksEnabledResponse


class ExitResponse(ApiModel):
    kind: ExitKind
    obligations: list[str]
    card_key: str


class ClassifyResponse(ApiModel):
    classification: Classification | None = None
    exit: ExitResponse | None = None
    roadmap_preview: dict | None = None
    state: ProjectState
    alert_finding_id: str | None = None


class TierChoiceRequest(ApiModel):
    amount_bracket: AmountBracket


class GateResponse(ApiModel):
    passed: bool
    gaps: list[dict]


class ProjectCounts(ApiModel):
    findings_open_block: int
    materials_pending: int


class ProjectResponse(ApiModel):
    project: dict
    counts: ProjectCounts


class UploadUrlRequest(ApiModel):
    kind: AssetKind
    filename: str | None = None


class UploadTicketResponse(ApiModel):
    """`backend` says where the bytes will land, so a local run is never
    mistaken for a cloud one."""

    ticket_id: str
    upload_url: str
    method: str
    backend: str
    storage_uri: str


class AttachMaterialRequest(ApiModel):
    asset_version: str


class WaiveMaterialRequest(ApiModel):
    reason: str


class ExtractFactsResponse(ApiModel):
    """`pending_flags` carries `fact_extraction_pending` when no backend ran, so
    an empty `facts` list is never mistaken for "the document held nothing"."""

    facts: list[Fact]
    discarded: list[str]
    pending_flags: list[str]
    backend: str


class RoadmapResponse(ApiModel):
    """`pending_flags` carries `roadmap_template_pending` when the process pack
    defines no steps, so an empty plan is never read as a short one."""

    roadmap: Roadmap | None = None
    state: ProjectState | None = None
    pending_flags: list[str]


class ReviewResponse(ApiModel):
    """`pending_flags` carries `script_semantic_check_pending` when no backend
    ran, so "patterns found nothing" is never rendered as "the script is clean"."""

    findings: list[Finding]
    discarded: list[str]
    pending_flags: list[str]
    backend: str
    state: ProjectState


class FindingActionRequest(ApiModel):
    """`accept` acknowledges; `resolve`, `waive`, and `reject` release the gate.
    `waive` and `reject` require a reason, which is recorded with the finding."""

    action: str
    reason: str | None = None
    option_id: str | None = None


class ConfirmFieldRequest(ApiModel):
    """A value the documents did not supply, given by the creator."""

    value: str | int | float
    reason: str | None = None


class GatePassResponse(ApiModel):
    state: ProjectState
    passed: bool


class SubmitToInstitutionRequest(ApiModel):
    institution_id: str


class InstitutionDecisionRequest(ApiModel):
    """`accept` needs a signed agreement; `return` needs comments."""

    decision: str
    return_comments: str | None = None
    signed_agreement_uri: str | None = None


class InstitutionReviewResponse(ApiModel):
    review: InstitutionReview
    state: ProjectState


class FilingRequest(ApiModel):
    """The number a human received. The product never generates one."""

    registration_number: str


class FilingResponse(ApiModel):
    state: ProjectState
    registration_number: str | None = None


class TeaserRequestBody(ApiModel):
    seconds: int = 8


class TeaserResponse(ApiModel):
    """`task.status` is `needs_human` when no video backend is configured, so an
    absent teaser is never mistaken for a generated one."""

    task: WorkflowTask
    promotional_only: bool = True
