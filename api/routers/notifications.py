"""Notification reads (API contract section 4, task and notification reads).

The producer lives in `WorkflowService`; the policy loop triggers it through
`/v1/internal/*` and never writes here directly.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.workflow_service import WorkflowService
from schemas.workflow import Notification

from ..deps.demo_auth import Principal, get_principal
from ..deps.services import get_workflow

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


@router.get("", response_model=list[Notification])
def list_notifications(
    unread_only: bool = Query(default=False),
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> list[Notification]:
    """Every caller reads their own inbox. There is no cross-user read."""

    return workflow.list_notifications(principal.user_id, unread_only)


@router.post("/{notification_id}/read", response_model=Notification)
def mark_read(
    notification_id: str,
    principal: Principal = Depends(get_principal),
    workflow: WorkflowService = Depends(get_workflow),
) -> Notification:
    return workflow.mark_notification_read(notification_id, principal.user_id)
