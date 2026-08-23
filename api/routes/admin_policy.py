"""Read routes for deterministic policy administration state."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError

from api.deps.policy import PolicyApiState, get_policy_state, require_admin
from api.errors import PolicyApiError
from api.models.policy import (
    PolicyRunResponse,
    ProposalDetail,
    ProposalSummary,
    SnapshotSummary,
)
from schemas.policy_snapshot import PolicyProposal, ProposalStatus
from workers.policy.models import PolicyDiff


router = APIRouter(
    prefix="/v1/admin/policy",
    dependencies=[Depends(require_admin)],
)


def _proposal_summary(
    proposal_id: str,
    proposal: PolicyProposal,
) -> ProposalSummary:
    return ProposalSummary(
        proposal_id=proposal_id,
        summary=proposal.summary,
        impact=proposal.impact,
        effective_from=proposal.effective_from,
        status=proposal.status,
    )


@router.get("/runs/{run_id}", response_model=PolicyRunResponse)
def get_run(
    run_id: str,
    state: Annotated[PolicyApiState, Depends(get_policy_state)],
) -> PolicyRunResponse:
    try:
        run = state.repository.get_run(run_id)
    except KeyError as exc:
        raise PolicyApiError(
            404,
            "POLICY_RUN_NOT_FOUND",
            "policy run not found",
        ) from exc
    return PolicyRunResponse.model_validate(run.model_dump())


@router.get("/proposals", response_model=list[ProposalSummary])
def list_proposals(
    state: Annotated[PolicyApiState, Depends(get_policy_state)],
    status: ProposalStatus = Query(default=ProposalStatus.PENDING),
) -> list[ProposalSummary]:
    proposals = [
        (proposal_id, proposal)
        for proposal_id, proposal in state.repository.list_proposals().items()
        if proposal.status is status
    ]
    proposals.sort(key=lambda item: item[1].created_at, reverse=True)
    return [
        _proposal_summary(proposal_id, proposal)
        for proposal_id, proposal in proposals
    ]


@router.get("/proposals/{proposal_id}", response_model=ProposalDetail)
def get_proposal(
    proposal_id: str,
    state: Annotated[PolicyApiState, Depends(get_policy_state)],
) -> ProposalDetail:
    try:
        proposal = state.repository.get_proposal(proposal_id)
    except KeyError as exc:
        raise PolicyApiError(
            404,
            "POLICY_PROPOSAL_NOT_FOUND",
            "policy proposal not found",
        ) from exc
    try:
        raw = json.loads(state.blob_store.read_text(proposal.source_diff_uri))
        source_diff_text = PolicyDiff.model_validate(raw).unified_diff
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        raise PolicyApiError(
            500,
            "POLICY_BLOB_READ_FAILED",
            "proposal diff could not be read",
        ) from exc
    return ProposalDetail(
        proposal_id=proposal_id,
        summary=proposal.summary,
        impact=proposal.impact,
        effective_from=proposal.effective_from,
        status=proposal.status,
        source_diff_uri=proposal.source_diff_uri,
        source_diff_text=source_diff_text,
        draft_pack_updates=proposal.draft_pack_updates,
        published_version=proposal.published_version,
    )


@router.get("/snapshots", response_model=list[SnapshotSummary])
def list_snapshots(
    state: Annotated[PolicyApiState, Depends(get_policy_state)],
) -> list[SnapshotSummary]:
    snapshots = list(state.repository.list_snapshots().values())
    snapshots.sort(key=lambda snapshot: snapshot.published_at, reverse=True)
    return [
        SnapshotSummary(
            version=snapshot.version,
            published_at=snapshot.published_at,
            effective_from=snapshot.effective_from,
            published_by=snapshot.published_by,
            thresholds_published=snapshot.thresholds_published,
        )
        for snapshot in snapshots
    ]
