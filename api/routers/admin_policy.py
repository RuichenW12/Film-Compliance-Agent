"""Read routes for deterministic policy administration state."""

from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from pydantic import ValidationError

from api.deps.policy import PolicyApiState, get_policy_state, require_admin
from api.errors import PolicyApiError
from api.models.policy import (
    CrawlRequest,
    CrawlResponse,
    PolicyRunResponse,
    ProposalDetail,
    ProposalSummary,
    PublishResponse,
    SnapshotSummary,
)
from schemas.policy_snapshot import PolicyProposal, ProposalStatus
from workers.policy.launch import PolicyLaunchError
from workers.policy.models import PolicyDiff
from workers.policy.publish import PolicyPublishError


_LOGGER = logging.getLogger(__name__)


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


def _publish_error(exc: PolicyPublishError) -> PolicyApiError:
    status_by_code = {
        "POLICY_PROPOSAL_CONFLICT": 409,
        "POLICY_NOT_EFFECTIVE": 409,
        "SNAPSHOT_NOT_FOUND": 503,
        "POLICY_PROPOSAL_INVALID": 502,
    }
    return PolicyApiError(
        status_by_code.get(exc.code, 500),
        exc.code,
        str(exc).partition(": ")[2] or str(exc),
    )


@router.post("/crawl", status_code=202, response_model=CrawlResponse)
async def crawl(
    body: CrawlRequest,
    background_tasks: BackgroundTasks,
    state: Annotated[PolicyApiState, Depends(get_policy_state)],
) -> CrawlResponse:
    now = state.clock()
    try:
        run_id = state.launcher.launch(body.source_id, now)
    except PolicyLaunchError as exc:
        raise PolicyApiError(404, exc.code, str(exc)) from exc
    background_tasks.add_task(
        state.launcher.execute,
        run_id,
        body.source_id,
        now,
    )
    return CrawlResponse(run_id=run_id)


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
    response = run.model_dump()
    response["error"] = (
        "policy refresh failed" if run.status == "failed" else None
    )
    return PolicyRunResponse.model_validate(response)


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


@router.post(
    "/proposals/{proposal_id}/publish",
    status_code=201,
    response_model=PublishResponse,
)
async def publish_proposal(
    proposal_id: str,
    state: Annotated[PolicyApiState, Depends(get_policy_state)],
) -> PublishResponse:
    try:
        result = state.publisher.publish(
            proposal_id,
            "admin_richard",
            state.clock(),
        )
    except PolicyPublishError as exc:
        raise _publish_error(exc) from exc
    # Delivering marks the outbox row sent only after the consumer has handled
    # it, so a failure here leaves the row PENDING and the next publish retries
    # it. The older order -- dispatch, mark sent, then hand to the consumer --
    # lost events outright: a row marked sent is never selected again.
    #
    # Best-effort either way: a publication that succeeded must not be reported
    # as failed because the fan-out stumbled, and the snapshot is durable
    # regardless. The failure is logged, not swallowed.
    try:
        if state.delivery is not None:
            await state.delivery.deliver()
        else:
            state.dispatcher.dispatch()
    except Exception:
        _LOGGER.exception(
            "policy fan-out failed after publishing %s", result.snapshot_version
        )
    return PublishResponse(snapshot_version=result.snapshot_version)


@router.post(
    "/proposals/{proposal_id}/discard",
    status_code=204,
    response_class=Response,
)
def discard_proposal(
    proposal_id: str,
    state: Annotated[PolicyApiState, Depends(get_policy_state)],
) -> Response:
    try:
        state.publisher.discard(
            proposal_id,
            "admin_richard",
            state.clock(),
        )
    except PolicyPublishError as exc:
        raise _publish_error(exc) from exc
    return Response(status_code=204)


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
            verification_status=snapshot.verification_status,
        )
        for snapshot in snapshots
    ]
