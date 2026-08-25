"""C1-a script pre-check (API contract section 4, step 8).

The pre-check reports and stores findings; it does not move project state. The
revision loop that consumes them is T-A5.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.errors import ForbiddenError
from core.workflow_service import WorkflowService
from schemas.enums import Role
from schemas.findings import Finding

from ..deps.demo_auth import Principal, get_principal
from ..deps.services import get_workflow
from ..dto import FindingActionRequest, ReviewResponse

router = APIRouter(prefix="/v1/projects/{project_id}", tags=["review"])


def _assert_owner(principal: Principal, owner_uid: str) -> None:
    if principal.user_id != owner_uid:
        raise ForbiddenError("this project belongs to another creator")


@router.post("/review", response_model=ReviewResponse)
def run_review(
    project_id: str,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> ReviewResponse:
    _assert_owner(principal, workflow.get_project(project_id).owner_uid)
    project, findings, result = workflow.run_script_review(project_id)
    return ReviewResponse(
        findings=findings,
        discarded=result.discarded,
        pending_flags=result.pending_flags,
        backend=result.backend,
        state=project.state,
    )


@router.get("/findings", response_model=list[Finding])
def list_findings(
    project_id: str,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> list[Finding]:
    """Institutions read findings in their console; creators read their own."""

    project = workflow.get_project(project_id)
    if principal.role is not Role.INSTITUTION and principal.role is not Role.ADMIN:
        _assert_owner(principal, project.owner_uid)
    return workflow.list_findings(project_id)


@router.post("/findings/{finding_id}/action", response_model=Finding)
def act_on_finding(
    project_id: str,
    finding_id: str,
    body: FindingActionRequest,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> Finding:
    """Deciding what to do about a finding is the creator's own act."""

    _assert_owner(principal, workflow.get_project(project_id).owner_uid)
    return workflow.act_on_finding(
        project_id, finding_id, body.action, body.reason, body.option_id
    )
