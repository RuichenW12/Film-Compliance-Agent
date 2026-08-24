"""Project, intake, and classification routes (API contract sections 4.1-4.2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from core.errors import ForbiddenError
from core.workflow_service import WorkflowService
from schemas.enums import FindingSeverity, MaterialStatus, Role

from ..deps.demo_auth import Principal, get_principal
from ..deps.services import get_context, get_workflow
from ..dto import (
    ChannelsRequest,
    ChannelsResponse,
    ClassifyResponse,
    CreateProjectRequest,
    CreateProjectResponse,
    ExitResponse,
    GateResponse,
    IntentRequest,
    IntentResponse,
    ProjectCounts,
    ProjectResponse,
    TierChoiceRequest,
    TracksEnabledResponse,
)

router = APIRouter(prefix="/v1/projects", tags=["projects"])


def _assert_owner(principal: Principal, owner_uid: str) -> None:
    """Admins observe, institutions use their own console, creators own projects."""

    if principal.role is Role.ADMIN:
        return
    if principal.role is Role.INSTITUTION:
        return
    if principal.user_id != owner_uid:
        raise ForbiddenError("this project belongs to another creator")


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateProjectResponse)
def create_project(
    body: CreateProjectRequest | None = None,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> CreateProjectResponse:
    principal.require(Role.CREATOR, Role.ADMIN)
    project = workflow.create_project(
        principal.user_id, body.title_working if body else None
    )
    return CreateProjectResponse(project_id=project.project_id, state=project.state)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> ProjectResponse:
    project = workflow.get_project(project_id)
    _assert_owner(principal, project.owner_uid)

    stores = get_context(request).stores
    findings = stores.findings.list(project_id)
    materials = stores.materials.list(project_id)
    counts = ProjectCounts(
        findings_open_block=sum(
            1
            for finding in findings
            if finding.severity is FindingSeverity.BLOCK and finding.blocks_gate_d3
        ),
        materials_pending=sum(
            1
            for material in materials
            if material.status
            not in (MaterialStatus.VALID, MaterialStatus.WAIVED)
        ),
    )
    return ProjectResponse(project=project.model_dump(mode="json"), counts=counts)


@router.post("/{project_id}/intent", response_model=IntentResponse)
def submit_intent(
    project_id: str,
    body: IntentRequest,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> IntentResponse:
    principal.require(Role.CREATOR, Role.ADMIN)
    project = workflow.get_project(project_id)
    _assert_owner(principal, project.owner_uid)

    patch = body.model_dump(exclude_none=True)
    project, missing = workflow.submit_intent(project_id, patch)
    return IntentResponse(state=project.state, missing=missing)


@router.post("/{project_id}/channels", response_model=ChannelsResponse)
def submit_channels(
    project_id: str,
    body: ChannelsRequest,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> ChannelsResponse:
    principal.require(Role.CREATOR, Role.ADMIN)
    project = workflow.get_project(project_id)
    _assert_owner(principal, project.owner_uid)

    project = workflow.submit_channels(project_id, body.model_dump(exclude_none=True))
    tracks = project.channel_profile.tracks_enabled
    return ChannelsResponse(
        tracks_enabled=TracksEnabledResponse(china=tracks.china, us=tracks.us)
    )


def _classify_response(
    request: Request, project_id: str, project, outcome
) -> ClassifyResponse:
    stores = get_context(request).stores
    alert_finding_id = None
    if outcome.alert is not None:
        alerts = [
            finding.finding_id
            for finding in stores.findings.list(project_id)
            if finding.alert is not None
        ]
        alert_finding_id = alerts[-1] if alerts else None

    exit_response = None
    if outcome.exit is not None:
        exit_response = ExitResponse(
            kind=outcome.exit.kind,
            obligations=outcome.exit.obligations,
            card_key=outcome.exit.card_key,
        )
    return ClassifyResponse(
        classification=outcome.classification,
        exit=exit_response,
        roadmap_preview=outcome.roadmap_preview,
        state=project.state,
        alert_finding_id=alert_finding_id,
    )


@router.post("/{project_id}/classify", response_model=ClassifyResponse)
def classify_project(
    project_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> ClassifyResponse:
    principal.require(Role.CREATOR, Role.ADMIN)
    project = workflow.get_project(project_id)
    _assert_owner(principal, project.owner_uid)

    project, outcome = workflow.run_classification(project_id)
    return _classify_response(request, project_id, project, outcome)


@router.post("/{project_id}/tier-choice", response_model=ClassifyResponse)
def choose_tier(
    project_id: str,
    body: TierChoiceRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> ClassifyResponse:
    principal.require(Role.CREATOR, Role.ADMIN)
    project = workflow.get_project(project_id)
    _assert_owner(principal, project.owner_uid)

    project, outcome = workflow.choose_tier(project_id, body.budget_band)
    return _classify_response(request, project_id, project, outcome)


@router.get("/{project_id}/gate", response_model=GateResponse)
def read_gate(
    project_id: str,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> GateResponse:
    project = workflow.get_project(project_id)
    _assert_owner(principal, project.owner_uid)
    result = workflow.gate_report(project_id)
    return GateResponse(**result.as_dict())


@router.get("/{project_id}/timeline")
def read_timeline(
    project_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> list[dict]:
    project = workflow.get_project(project_id)
    _assert_owner(principal, project.owner_uid)
    events = get_context(request).stores.timeline.list(project_id)
    return [event.model_dump(mode="json") for event in events]
