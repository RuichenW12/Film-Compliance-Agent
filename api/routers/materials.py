"""Material collection cards (API contract section 4, step 6).

Which cards exist is policy content from `p5_form_templates`. What a card can do
— attach, validate, waive — is product logic and lives here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.errors import ForbiddenError
from core.workflow_service import WorkflowService
from schemas.assets import MaterialCard
from schemas.enums import Role

from ..deps.demo_auth import Principal, get_principal
from ..deps.services import get_workflow
from ..dto import AttachMaterialRequest, WaiveMaterialRequest

router = APIRouter(prefix="/v1/projects/{project_id}/materials", tags=["materials"])


def _assert_can_read(principal: Principal, owner_uid: str) -> None:
    if principal.role is Role.ADMIN or principal.role is Role.INSTITUTION:
        return
    if principal.user_id != owner_uid:
        raise ForbiddenError("this project belongs to another creator")


def _assert_can_write(principal: Principal, owner_uid: str) -> None:
    """Collecting materials is the creator's own act."""

    if principal.user_id != owner_uid:
        raise ForbiddenError("this project belongs to another creator")


@router.get("", response_model=list[MaterialCard])
def list_materials(
    project_id: str,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> list[MaterialCard]:
    _assert_can_read(principal, workflow.get_project(project_id).owner_uid)
    return workflow.material_cards(project_id)


@router.post("/{material_id}/attach", response_model=MaterialCard)
def attach_material(
    project_id: str,
    material_id: str,
    body: AttachMaterialRequest,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> MaterialCard:
    _assert_can_write(principal, workflow.get_project(project_id).owner_uid)
    return workflow.attach_material(project_id, material_id, body.asset_version)


@router.post("/{material_id}/validate", response_model=MaterialCard)
def validate_material(
    project_id: str,
    material_id: str,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> MaterialCard:
    _assert_can_write(principal, workflow.get_project(project_id).owner_uid)
    return workflow.validate_material(project_id, material_id)


@router.post("/{material_id}/waive", response_model=MaterialCard)
def waive_material(
    project_id: str,
    material_id: str,
    body: WaiveMaterialRequest,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> MaterialCard:
    _assert_can_write(principal, workflow.get_project(project_id).owner_uid)
    return workflow.waive_material(project_id, material_id, body.reason)
