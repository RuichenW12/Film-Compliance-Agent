"""Reusable, metadata-only Gate 4 smoke checks."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from schemas.policy_snapshot import PolicySnapshot

from .interfaces import PolicyRepository
from .models import FetchedSource, PolicySource
from .refresh import (
    BlobStore,
    PolicyRefreshError,
    PolicyRefreshModule,
    ProposalModel,
    SourceFetcher,
)


SmokeStatus = Literal["PASS", "FAIL", "SKIP"]


class SourceSmokeReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["source"] = "source"
    overall: SmokeStatus
    source_status: SmokeStatus
    failure_status: SmokeStatus
    source_id: str
    final_url: str | None
    checked_at: datetime
    normalized_sha256: str | None
    first_run_status: str
    failure_run_status: str
    last_known_good_preserved: bool
    reason_code: str | None = None


class _RecordingFetcher:
    def __init__(self, delegate: SourceFetcher) -> None:
        self._delegate = delegate
        self.final_url: str | None = None

    async def fetch(self, source: PolicySource) -> FetchedSource:
        result = await self._delegate.fetch(source)
        self.final_url = result.source_url
        return result


class _InjectedSourceFailure(RuntimeError):
    code = "POLICY_SOURCE_FETCH_FAILED"


class _InjectedFailureFetcher:
    async def fetch(self, source: PolicySource) -> FetchedSource:
        _ = source
        raise _InjectedSourceFailure("injected policy source smoke failure")


async def run_source_smoke(
    *,
    source: PolicySource,
    fetcher: SourceFetcher,
    blob_store: BlobStore,
    repository: PolicyRepository,
    seed: PolicySnapshot,
    proposal_model: ProposalModel,
    clock: Callable[[], datetime],
) -> SourceSmokeReport:
    checked_at = clock()
    if repository.latest_snapshot() is None:
        repository.put_snapshot(seed)

    recording_fetcher = _RecordingFetcher(fetcher)
    refresh = PolicyRefreshModule(
        sources={source.source_id: source},
        fetcher=recording_fetcher,
        blob_store=blob_store,
        proposal_model=proposal_model,
        repository=repository,
    )
    repository.create_run("run_source_baseline", source.source_id, checked_at)
    try:
        first_result = await refresh.run(
            "run_source_baseline",
            source.source_id,
            checked_at,
        )
    except PolicyRefreshError:
        return SourceSmokeReport(
            overall="FAIL",
            source_status="FAIL",
            failure_status="SKIP",
            source_id=source.source_id,
            final_url=recording_fetcher.final_url,
            checked_at=checked_at,
            normalized_sha256=None,
            first_run_status=repository.get_run("run_source_baseline").status,
            failure_run_status="not_run",
            last_known_good_preserved=False,
            reason_code="POLICY_SOURCE_SMOKE_FAILED",
        )

    baseline_state = repository.get_source_state(source.source_id)
    baseline_snapshot = repository.latest_snapshot()
    if baseline_state is None or baseline_snapshot is None:
        return SourceSmokeReport(
            overall="FAIL",
            source_status="FAIL",
            failure_status="SKIP",
            source_id=source.source_id,
            final_url=recording_fetcher.final_url,
            checked_at=checked_at,
            normalized_sha256=None,
            first_run_status=first_result.status,
            failure_run_status="not_run",
            last_known_good_preserved=False,
            reason_code="POLICY_SOURCE_SMOKE_STATE_MISSING",
        )

    state_before = baseline_state.model_dump_json()
    snapshot_before = baseline_snapshot.model_dump_json()
    failure_refresh = PolicyRefreshModule(
        sources={source.source_id: source},
        fetcher=_InjectedFailureFetcher(),
        blob_store=blob_store,
        proposal_model=proposal_model,
        repository=repository,
    )
    repository.create_run("run_source_failure", source.source_id, checked_at)
    failure_raised = False
    try:
        await failure_refresh.run(
            "run_source_failure",
            source.source_id,
            checked_at,
        )
    except PolicyRefreshError:
        failure_raised = True

    failure_run = repository.get_run("run_source_failure")
    state_after = repository.get_source_state(source.source_id)
    snapshot_after = repository.latest_snapshot()
    preserved = (
        state_after is not None
        and snapshot_after is not None
        and state_after.model_dump_json() == state_before
        and snapshot_after.model_dump_json() == snapshot_before
    )
    source_passed = first_result.status == "no_change"
    failure_passed = failure_raised and failure_run.status == "failed"
    overall_passed = source_passed and failure_passed and preserved
    return SourceSmokeReport(
        overall="PASS" if overall_passed else "FAIL",
        source_status="PASS" if source_passed else "FAIL",
        failure_status="PASS" if failure_passed else "FAIL",
        source_id=source.source_id,
        final_url=recording_fetcher.final_url,
        checked_at=checked_at,
        normalized_sha256=baseline_state.normalized_sha256,
        first_run_status=first_result.status,
        failure_run_status=failure_run.status,
        last_known_good_preserved=preserved,
        reason_code=None if overall_passed else "POLICY_SOURCE_SMOKE_FAILED",
    )
