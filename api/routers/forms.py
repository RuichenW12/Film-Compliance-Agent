"""Gate passage and the C1-c form draft (API contract section 4, step 11).

A form is prepared from facts, never from prose: a field is filled only where a
confirmed fact backs it, and everything else renders as 待补充. Freezing hashes
the result so a submitted form is verifiable against the policy it was prepared
under.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.errors import ForbiddenError
from core.workflow_service import WorkflowService
from schemas.forms import FormDraft

from ..deps.demo_auth import Principal, get_principal
from ..deps.services import get_workflow
from ..dto import ConfirmFieldRequest, GatePassResponse

router = APIRouter(prefix="/v1/projects/{project_id}", tags=["forms"])


def _assert_owner(principal: Principal, owner_uid: str) -> None:
    if principal.user_id != owner_uid:
        raise ForbiddenError("this project belongs to another creator")


@router.post("/gate/pass", response_model=GatePassResponse)
def pass_gate(
    project_id: str,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> GatePassResponse:
    """Refuses with the machine-readable gaps rather than a bare no."""

    _assert_owner(principal, workflow.get_project(project_id).owner_uid)
    project = workflow.pass_gate(project_id)
    return GatePassResponse(state=project.state, passed=True)


@router.get("/form", response_model=FormDraft)
def read_form(
    project_id: str,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> FormDraft:
    _assert_owner(principal, workflow.get_project(project_id).owner_uid)
    return workflow.form_draft(project_id)


@router.post("/form/fields/{key}/confirm", response_model=FormDraft)
def confirm_field(
    project_id: str,
    key: str,
    body: ConfirmFieldRequest,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> FormDraft:
    """The creator supplies what the documents did not, recorded as their answer."""

    _assert_owner(principal, workflow.get_project(project_id).owner_uid)
    return workflow.confirm_form_field(project_id, key, body.value, body.reason)


@router.post("/form/freeze", response_model=FormDraft)
def freeze_form(
    project_id: str,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> FormDraft:
    _assert_owner(principal, workflow.get_project(project_id).owner_uid)
    return workflow.freeze_form(project_id)
