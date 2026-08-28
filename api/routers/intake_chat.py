"""Conversational intake: read one turn, return proposals (design: Step 1-2).

Deliberately stateless and project-free. It reads a sentence and says what
intake answers it supports; it does not store, does not classify, and does not
need a project to exist. Storing is `POST /v1/projects/{id}/intent`, unchanged,
after a person has looked at the proposals and accepted them.

Keeping the two apart is the safety property, not an accident of layering: as
long as this endpoint cannot write, no prompt reaching it can make the product
believe anything.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from core.intake_chat import IntakeTurnResult, read_turn

from ..deps.demo_auth import Principal, get_principal
from ..deps.services import get_context
from ..dto import IntakeTurnRequest, IntakeTurnResponse, ProposedAnswerResponse
from core.errors import ValidationFailedError
from schemas.enums import Role

router = APIRouter(prefix="/v1/intake", tags=["intake"])

MAX_TURN_CHARS = 4000


def _to_response(result: IntakeTurnResult) -> IntakeTurnResponse:
    return IntakeTurnResponse(
        proposals=[
            ProposedAnswerResponse(
                key=proposal.key,
                value=proposal.value,
                quote=proposal.quote,
                inferred=proposal.inferred,
            )
            for proposal in result.proposals
        ],
        reply=result.reply,
        pending_flags=result.pending_flags,
        backend=result.backend,
    )


@router.post("/turn", response_model=IntakeTurnResponse)
def read_intake_turn(
    body: IntakeTurnRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> IntakeTurnResponse:
    principal.require(Role.CREATOR, Role.ADMIN)

    turn = body.turn.strip()
    if not turn:
        # An empty turn is not a model call.
        return IntakeTurnResponse(proposals=[], reply="", pending_flags=[], backend="")
    if len(turn) > MAX_TURN_CHARS:
        raise ValidationFailedError(
            f"a turn may be at most {MAX_TURN_CHARS} characters",
            {"length": len(turn), "limit": MAX_TURN_CHARS},
        )

    return _to_response(read_turn(turn, get_context(request).llm))
