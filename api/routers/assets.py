"""Upload tickets and immutable asset versions (API contract section 4, step 6).

The product hands out a ticket rather than a bare route so the same client flow
works for a local upload today and a signed object-storage URL later: only
`upload_url` and `backend` change. With no bucket configured the ticket says
`backend: "local"` — a missing cloud backend is reported, never disguised.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from core.errors import ForbiddenError
from core.workflow_service import WorkflowService
from schemas.assets import AssetVersion
from schemas.enums import Role

from ..deps.demo_auth import Principal, get_principal
from ..deps.services import get_context, get_workflow
from ..dto import UploadTicketResponse, UploadUrlRequest

router = APIRouter(tags=["assets"])


def _assert_owner(principal: Principal, owner_uid: str) -> None:
    """Uploads are the creator's own act; an admin observing does not upload."""

    if principal.role is Role.ADMIN and principal.user_id != owner_uid:
        raise ForbiddenError("an administrator observes, and does not upload")
    if principal.user_id != owner_uid:
        raise ForbiddenError("this project belongs to another creator")


@router.post(
    "/v1/projects/{project_id}/assets/upload-url",
    response_model=UploadTicketResponse,
)
def request_upload_url(
    project_id: str,
    body: UploadUrlRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> UploadTicketResponse:
    _assert_owner(principal, workflow.get_project(project_id).owner_uid)
    ticket = workflow.issue_upload_ticket(
        project_id, body.kind, principal.user_id, body.filename
    )
    settings = get_context(request).settings
    return UploadTicketResponse(
        ticket_id=ticket.ticket_id,
        upload_url=f"/v1/uploads/{ticket.ticket_id}",
        method="PUT",
        backend="gcs" if settings.gcs_bucket else "local",
        storage_uri=ticket.storage_uri,
    )


@router.put(
    "/v1/uploads/{ticket_id}",
    response_model=AssetVersion,
    status_code=status.HTTP_201_CREATED,
)
async def upload(
    ticket_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> AssetVersion:
    """Raw bytes in, one immutable version record out. The ticket is spent."""

    return workflow.complete_upload(ticket_id, await request.body())


@router.get(
    "/v1/projects/{project_id}/assets", response_model=list[AssetVersion]
)
def list_assets(
    project_id: str,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> list[AssetVersion]:
    _assert_owner(principal, workflow.get_project(project_id).owner_uid)
    return workflow.list_assets(project_id)


@router.get("/v1/projects/{project_id}/assets/{version_id}/content")
def read_asset(
    project_id: str,
    version_id: str,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> Response:
    """Uploaded text is data, never instructions — it is served, not executed."""

    _assert_owner(principal, workflow.get_project(project_id).owner_uid)
    asset, data = workflow.read_asset(project_id, version_id)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"X-Asset-Sha256": asset.sha256},
    )
