"""Request and response bodies. Domain shapes come from `schemas/`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from schemas.enums import AssetKind, BudgetBand, ClaimedFormType, ExitKind, ProjectState
from schemas.common import Fact
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
    logline: str | None = None
    episode_count: int | None = Field(default=None, ge=1)
    episode_minutes: float | None = Field(default=None, gt=0)
    budget_band: BudgetBand | None = None
    is_ai_generated: bool | None = None
    has_finished_film: bool | None = None


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
    budget_band: BudgetBand


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
