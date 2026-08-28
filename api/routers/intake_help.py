"""Intake help: explain a field, answer a question about it (design: revised).

The endpoint that used to live here read a creator's sentence and proposed form
values. It is gone, and so is the guard it needed: this one's reply has no value
field, so nothing a question says can reach the form.

Still stateless and project-free. It reads a question and returns prose plus the
clauses that prose was drawn from.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from core.errors import ValidationFailedError
from core.intake_help import explain_field
from schemas.enums import Role

from ..deps.demo_auth import Principal, get_principal
from ..deps.services import get_context
from ..dto import FieldHelpRequest, FieldHelpResponse

router = APIRouter(prefix="/v1/intake", tags=["intake"])

MAX_QUESTION_CHARS = 500


@router.post("/explain", response_model=FieldHelpResponse)
def explain_intake_field(
    body: FieldHelpRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> FieldHelpResponse:
    principal.require(Role.CREATOR, Role.ADMIN)

    question = body.question.strip()
    if len(question) > MAX_QUESTION_CHARS:
        raise ValidationFailedError(
            f"a question may be at most {MAX_QUESTION_CHARS} characters",
            {"length": len(question), "limit": MAX_QUESTION_CHARS},
        )

    context = get_context(request)
    version = context.snapshots.latest_version()
    result = explain_field(
        body.field,
        question,
        context.snapshots,
        context.llm,
        version,
        label=body.label,
    )
    return FieldHelpResponse(
        answer=result.answer,
        clause_refs=result.clause_refs,
        snapshot_version=version,
        pending_flags=result.pending_flags,
    )
