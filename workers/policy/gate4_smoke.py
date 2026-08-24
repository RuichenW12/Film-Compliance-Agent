"""Reusable, metadata-only Gate 4 smoke checks."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from schemas.policy_snapshot import ImpactNode, PolicySnapshot, PolicyUpdatedEvent

from .cloud_runtime import (
    CloudPolicyConfigurationError,
    CloudPolicyRuntime,
    CloudPolicySettings,
    build_cloud_policy_runtime,
)
from .interfaces import PolicyRepository
from .models import FetchedSource, PolicySource, ProposalRequest
from .normalize import create_policy_diff, normalize_html
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


class CloudSmokeReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["cloud"] = "cloud"
    overall: SmokeStatus
    source_status: SmokeStatus
    gcs_status: SmokeStatus
    firestore_status: SmokeStatus
    failure_status: SmokeStatus
    gemini_status: SmokeStatus
    pubsub_status: SmokeStatus
    project: str | None
    database: str | None
    bucket: str | None
    topic: str | None
    model: str | None
    checked_at: datetime
    source_id: str | None
    normalized_sha256: str | None
    message_id: str | None
    last_known_good_preserved: bool
    stage_code: str | None = None


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


async def run_cloud_smoke(
    *,
    settings: CloudPolicySettings | None = None,
    env: dict[str, str] | None = None,
    runtime_builder: Callable[[CloudPolicySettings], CloudPolicyRuntime] = (
        build_cloud_policy_runtime
    ),
    clock: Callable[[], datetime],
) -> CloudSmokeReport:
    checked_at = clock()
    if settings is None:
        try:
            settings = CloudPolicySettings.from_env(env)
        except CloudPolicyConfigurationError:
            return CloudSmokeReport(
                overall="SKIP",
                source_status="SKIP",
                gcs_status="SKIP",
                firestore_status="SKIP",
                failure_status="SKIP",
                gemini_status="SKIP",
                pubsub_status="SKIP",
                project=None,
                database=None,
                bucket=None,
                topic=None,
                model=None,
                checked_at=checked_at,
                source_id=None,
                normalized_sha256=None,
                message_id=None,
                last_known_good_preserved=False,
                stage_code="POLICY_CLOUD_CONFIG_MISSING",
            )

    def report(
        *,
        overall: SmokeStatus,
        source_status: SmokeStatus = "SKIP",
        gcs_status: SmokeStatus = "SKIP",
        firestore_status: SmokeStatus = "SKIP",
        failure_status: SmokeStatus = "SKIP",
        gemini_status: SmokeStatus = "SKIP",
        pubsub_status: SmokeStatus = "SKIP",
        normalized_sha256: str | None = None,
        message_id: str | None = None,
        preserved: bool = False,
        stage_code: str | None = None,
    ) -> CloudSmokeReport:
        return CloudSmokeReport(
            overall=overall,
            source_status=source_status,
            gcs_status=gcs_status,
            firestore_status=firestore_status,
            failure_status=failure_status,
            gemini_status=gemini_status,
            pubsub_status=pubsub_status,
            project=settings.project,
            database=settings.firestore_database,
            bucket=settings.gcs_bucket,
            topic=settings.pubsub_topic,
            model=settings.gemini_model,
            checked_at=checked_at,
            source_id="nrta_micro_drama_management_measures",
            normalized_sha256=normalized_sha256,
            message_id=message_id,
            last_known_good_preserved=preserved,
            stage_code=stage_code,
        )

    if "smoke" not in settings.pubsub_topic.lower():
        return report(
            overall="FAIL",
            pubsub_status="FAIL",
            stage_code="POLICY_CLOUD_SMOKE_TOPIC_INVALID",
        )

    try:
        runtime = runtime_builder(settings)
    except Exception:
        return report(
            overall="FAIL",
            source_status="FAIL",
            gcs_status="FAIL",
            firestore_status="FAIL",
            gemini_status="FAIL",
            pubsub_status="FAIL",
            stage_code="POLICY_CLOUD_RUNTIME_FAILED",
        )

    source_id = "nrta_micro_drama_management_measures"
    try:
        run_id = runtime.launcher.launch(source_id, checked_at)
        await runtime.launcher.execute(run_id, source_id, checked_at)
        source_state = runtime.repository.get_source_state(source_id)
        source_run = runtime.repository.get_run(run_id)
        if source_state is None or source_run.status not in {
            "no_change",
            "proposal_created",
        }:
            raise ValueError("cloud source state was not persisted")
        normalized_sha256 = source_state.normalized_sha256
        snapshot_before = runtime.repository.latest_snapshot()
        if snapshot_before is None:
            raise ValueError("cloud seed snapshot is missing")
        state_before = source_state.model_dump_json()
        snapshot_before_json = snapshot_before.model_dump_json()
    except Exception:
        return report(
            overall="FAIL",
            source_status="FAIL",
            gcs_status="FAIL",
            firestore_status="FAIL",
            stage_code="POLICY_CLOUD_SOURCE_FAILED",
        )

    try:
        failure_run_id = runtime.launcher.launch(source_id, checked_at)
        failure_refresh = PolicyRefreshModule(
            sources={source_id: runtime.sources[source_id]},
            fetcher=_InjectedFailureFetcher(),
            blob_store=runtime.blob_store,
            proposal_model=runtime.proposal_model,
            repository=runtime.repository,
        )
        failure_raised = False
        try:
            await failure_refresh.run(failure_run_id, source_id, checked_at)
        except PolicyRefreshError:
            failure_raised = True
        state_after = runtime.repository.get_source_state(source_id)
        snapshot_after = runtime.repository.latest_snapshot()
        preserved = (
            failure_raised
            and runtime.repository.get_run(failure_run_id).status == "failed"
            and state_after is not None
            and snapshot_after is not None
            and state_after.model_dump_json() == state_before
            and snapshot_after.model_dump_json() == snapshot_before_json
        )
        if not preserved:
            raise ValueError("last-known-good state changed")
    except Exception:
        return report(
            overall="FAIL",
            source_status="PASS",
            gcs_status="PASS",
            firestore_status="PASS",
            failure_status="FAIL",
            normalized_sha256=normalized_sha256,
            stage_code="POLICY_CLOUD_FAILURE_PROBE_FAILED",
        )

    try:
        fixture_root = Path(__file__).parents[2] / "tests" / "fixtures" / "policy"
        previous = normalize_html(
            (fixture_root / "source-v1.html").read_bytes(), "#zoom"
        )
        current = normalize_html(
            (fixture_root / "source-v2.html").read_bytes(), "#zoom"
        )
        diff = create_policy_diff(source_id, previous, current)
        proposals_before = runtime.repository.list_proposals()
        await runtime.proposal_model.draft(
            ProposalRequest(
                source_url=(
                    "https://www.nrta.gov.cn/art/2026/7/31/art_113_73785.html"
                ),
                previous_sha256=diff.previous_sha256,
                current_sha256=diff.current_sha256,
                unified_diff=diff.unified_diff,
            )
        )
        if runtime.repository.list_proposals() != proposals_before:
            raise ValueError("Gemini probe persisted a synthetic proposal")
    except Exception:
        return report(
            overall="FAIL",
            source_status="PASS",
            gcs_status="PASS",
            firestore_status="PASS",
            failure_status="PASS",
            gemini_status="FAIL",
            normalized_sha256=normalized_sha256,
            preserved=True,
            stage_code="POLICY_CLOUD_GEMINI_FAILED",
        )

    try:
        event = PolicyUpdatedEvent(
            snapshot_version="v2",
            impact=[ImpactNode.D1C],
            thresholds_published=False,
            effective_from=checked_at,
            published_at=checked_at,
            idempotency_key="policy.updated:v2",
        )
        message_id = runtime.event_publisher.publish(event)
        if not message_id:
            raise ValueError("Pub/Sub message ID is empty")
    except Exception:
        return report(
            overall="FAIL",
            source_status="PASS",
            gcs_status="PASS",
            firestore_status="PASS",
            failure_status="PASS",
            gemini_status="PASS",
            pubsub_status="FAIL",
            normalized_sha256=normalized_sha256,
            preserved=True,
            stage_code="POLICY_CLOUD_PUBSUB_FAILED",
        )

    return report(
        overall="PASS",
        source_status="PASS",
        gcs_status="PASS",
        firestore_status="PASS",
        failure_status="PASS",
        gemini_status="PASS",
        pubsub_status="PASS",
        normalized_sha256=normalized_sha256,
        message_id=message_id,
        preserved=True,
    )
