"""Internal routes called by the policy loop (API contract section 4.2).

Contract note: the handbook shows a `reason` field on the not-recalculated
branch, but the frozen shared model `RecalcTierResponse` forbids extra fields.
Until both owners agree to add it, the reason is reported in the response header
and the project timeline, and the body stays exactly on contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, Response

from core.workflow_service import WorkflowService
from schemas.enums import Tier
from schemas.policy_snapshot import RecalcTierRequest, RecalcTierResponse

from ..deps.demo_auth import require_internal_token
from ..deps.services import get_context, get_workflow

router = APIRouter(prefix="/v1/internal", tags=["internal"])

RECALC_REASON_HEADER = "X-Recalc-Reason"


@router.post("/projects/{project_id}/recalc-tier", response_model=RecalcTierResponse)
def recalc_tier(
    project_id: str,
    body: RecalcTierRequest,
    request: Request,
    response: Response,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
    workflow: WorkflowService = Depends(get_workflow),
) -> RecalcTierResponse:
    settings = get_context(request).settings
    require_internal_token(settings.internal_token, x_internal_token)

    result = workflow.recalc_tier(project_id, body.snapshot_version)
    if result.reason:
        response.headers[RECALC_REASON_HEADER] = result.reason

    tier = result.tier if result.tier is not Tier.UNDETERMINED else Tier.T3
    return RecalcTierResponse(
        tier=tier.value,
        tier_provisional=result.tier_provisional,
        changed=result.changed,
    )


@router.post("/projects/{project_id}/policy-stale")
def mark_policy_stale(
    project_id: str,
    body: RecalcTierRequest,
    request: Request,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
    workflow: WorkflowService = Depends(get_workflow),
) -> dict:
    """Flag-only path for impacted projects. Never rewrites frozen data."""

    settings = get_context(request).settings
    require_internal_token(settings.internal_token, x_internal_token)
    project = workflow.mark_policy_stale(project_id, body.snapshot_version)
    return {"project_id": project.project_id, "policy_stale": project.policy_stale}
