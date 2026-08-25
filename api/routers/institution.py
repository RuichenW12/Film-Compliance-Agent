"""Institution review and filing (API contract section 4, steps 12-14).

Two boundaries this file enforces:

- the creator submits, the institution decides. Neither may do the other's act.
- the registry is demo data and ships empty. Nothing here verifies a real
  licence, and `LicenseCheck.mock` says so on every response.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.errors import ForbiddenError
from core.workflow_service import WorkflowService
from schemas.enums import Role
from schemas.workflow import InstitutionReview, MockInstitution, WorkflowTask

from ..deps.demo_auth import Principal, get_principal
from ..deps.services import get_workflow
from ..dto import (
    FilingRequest,
    FilingResponse,
    InstitutionDecisionRequest,
    InstitutionReviewResponse,
    SubmitToInstitutionRequest,
)

router = APIRouter(tags=["institution"])


def _assert_owner(principal: Principal, owner_uid: str) -> None:
    if principal.user_id != owner_uid:
        raise ForbiddenError("this project belongs to another creator")


def _assert_institution(principal: Principal) -> None:
    if principal.role is not Role.INSTITUTION:
        raise ForbiddenError("only the reviewing institution may decide")


@router.get("/v1/institutions", response_model=list[MockInstitution])
def list_institutions(
    workflow: WorkflowService = Depends(get_workflow),
) -> list[MockInstitution]:
    """Empty until an administrator loads demo data."""

    return workflow.list_institutions()


@router.put("/v1/admin/institutions", response_model=list[MockInstitution])
def load_institutions(
    body: list[MockInstitution],
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> list[MockInstitution]:
    principal.require(Role.ADMIN)
    return workflow.load_institutions(body)


@router.post(
    "/v1/projects/{project_id}/institution/submit",
    response_model=InstitutionReviewResponse,
)
def submit_to_institution(
    project_id: str,
    body: SubmitToInstitutionRequest,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> InstitutionReviewResponse:
    _assert_owner(principal, workflow.get_project(project_id).owner_uid)
    project, review = workflow.submit_to_institution(project_id, body.institution_id)
    return InstitutionReviewResponse(review=review, state=project.state)


@router.post(
    "/v1/projects/{project_id}/institution/decide",
    response_model=InstitutionReviewResponse,
)
def decide_review(
    project_id: str,
    body: InstitutionDecisionRequest,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> InstitutionReviewResponse:
    _assert_institution(principal)
    project, review = workflow.decide_institution_review(
        project_id, body.decision, body.return_comments, body.signed_agreement_uri
    )
    return InstitutionReviewResponse(review=review, state=project.state)


@router.post("/v1/projects/{project_id}/filing", response_model=FilingResponse)
def record_filing(
    project_id: str,
    body: FilingRequest,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> FilingResponse:
    """The registration number comes from a human reading a government system."""

    _assert_institution(principal)
    project = workflow.record_filing(project_id, body.registration_number)
    return FilingResponse(
        state=project.state, registration_number=project.registration_number
    )


@router.get(
    "/v1/projects/{project_id}/institution",
    response_model=InstitutionReview | None,
)
def read_review(
    project_id: str,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> InstitutionReview | None:
    """The creator watches their own submission; the institution reads its queue."""

    project = workflow.get_project(project_id)
    if principal.role is Role.CREATOR:
        _assert_owner(principal, project.owner_uid)
    return workflow.latest_institution_review(project_id)


@router.post(
    "/v1/projects/{project_id}/institution/resume",
    response_model=FilingResponse,
)
def resume_after_return(
    project_id: str,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> FilingResponse:
    """Take a returned project back into the revision loop to be corrected."""

    _assert_owner(principal, workflow.get_project(project_id).owner_uid)
    project = workflow.resume_after_return(project_id)
    return FilingResponse(
        state=project.state, registration_number=project.registration_number
    )


@router.get("/v1/projects/{project_id}/tasks", response_model=list[WorkflowTask])
def list_tasks(
    project_id: str,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> list[WorkflowTask]:
    project = workflow.get_project(project_id)
    if principal.role is Role.CREATOR:
        _assert_owner(principal, project.owner_uid)
    return workflow.list_tasks(project_id)
