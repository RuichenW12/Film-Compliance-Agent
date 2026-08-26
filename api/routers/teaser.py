"""Veo teaser (API contract section 4, step 18), behind `FLAG_VEO_TEASER`.

A teaser is promotional material and says nothing about compliance. The flag is
off by default, so the route reports itself unavailable rather than 404-ing —
a disabled feature is a fact worth telling the caller.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from core.errors import ForbiddenError
from core.workflow_service import WorkflowService

from ..deps.demo_auth import Principal, get_principal
from ..deps.services import get_context, get_workflow
from ..dto import TeaserRequestBody, TeaserResponse

router = APIRouter(prefix="/v1/projects/{project_id}", tags=["teaser"])


@router.post("/teaser", response_model=TeaserResponse)
def request_teaser(
    project_id: str,
    request: Request,
    body: TeaserRequestBody | None = None,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> TeaserResponse:
    settings = get_context(request).settings
    if not settings.flag_veo_teaser:
        raise ForbiddenError(
            "the teaser feature is switched off", {"flag": "FLAG_VEO_TEASER"}
        )

    owner_uid = workflow.get_project(project_id).owner_uid
    if principal.user_id != owner_uid:
        raise ForbiddenError("this project belongs to another creator")

    task = workflow.request_teaser(project_id, (body or TeaserRequestBody()).seconds)
    return TeaserResponse(task=task)
