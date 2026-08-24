import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from schemas.policy_snapshot import ImpactNode, PackName
from workers.policy.adapters.fake_proposal import FakeProposalModel
from workers.policy.adapters.file_blob import FileBlobStore
from workers.policy.adapters.fixture_source import FixtureSourceFetcher
from workers.policy.launch import PolicyLaunchError, PolicyRunLauncher
from workers.policy.models import PolicySource, ProposalDraft
from workers.policy.refresh import PolicyRefreshModule
from workers.policy.repository import InMemoryPolicyRepository


NOW = datetime(2026, 8, 23, 20, 0, tzinfo=timezone(timedelta(hours=8)))
SOURCE = PolicySource(
    source_id="nrta_micro_drama",
    url="https://www.nrta.gov.cn/example",
    content_selector="#zoom",
    enabled=True,
)
FIXTURES = Path(__file__).parents[1] / "fixtures" / "policy"


def build_launcher(
    tmp_path: Path,
    *,
    run_id_factory: Callable[[], str] | None = None,
) -> tuple[PolicyRunLauncher, InMemoryPolicyRepository]:
    repository = InMemoryPolicyRepository()
    refresh = PolicyRefreshModule(
        sources={SOURCE.source_id: SOURCE},
        fetcher=FixtureSourceFetcher(
            {SOURCE.source_id: FIXTURES / "source-v1.html"}
        ),
        blob_store=FileBlobStore(tmp_path / "blobs"),
        proposal_model=FakeProposalModel(
            ProposalDraft(
                summary="unused baseline draft",
                impact=[ImpactNode.D1C],
                effective_from=NOW,
                draft_pack_updates={
                    PackName.P3_TIER_THRESHOLDS: {
                        "thresholds_published": True
                    }
                },
            )
        ),
        repository=repository,
    )
    return (
        PolicyRunLauncher(
            repository,
            refresh,
            {SOURCE.source_id},
            run_id_factory=run_id_factory,
        ),
        repository,
    )


def test_launch_creates_running_record_before_execution(tmp_path: Path) -> None:
    launcher, repository = build_launcher(tmp_path)

    run_id = launcher.launch(SOURCE.source_id, NOW)

    assert run_id == "run_001"
    assert repository.get_run(run_id).status == "running"


def test_launch_ids_are_monotonic(tmp_path: Path) -> None:
    launcher, repository = build_launcher(tmp_path)

    first = launcher.launch(SOURCE.source_id, NOW)
    second = launcher.launch(SOURCE.source_id, NOW)

    assert (first, second) == ("run_001", "run_002")
    assert set(repository.list_runs()) == {"run_001", "run_002"}


def test_launcher_uses_injected_run_id_factory(tmp_path: Path) -> None:
    launcher, repository = build_launcher(
        tmp_path,
        run_id_factory=lambda: "run_cloud_abc123",
    )

    run_id = launcher.launch(SOURCE.source_id, NOW)

    assert run_id == "run_cloud_abc123"
    assert repository.get_run(run_id).status == "running"


def test_execute_completes_the_created_run(tmp_path: Path) -> None:
    launcher, repository = build_launcher(tmp_path)
    run_id = launcher.launch(SOURCE.source_id, NOW)

    result = asyncio.run(launcher.execute(run_id, SOURCE.source_id, NOW))

    assert result.run_id == run_id
    assert repository.get_run(run_id).status == "no_change"


def test_unknown_source_is_rejected_without_a_run(tmp_path: Path) -> None:
    launcher, repository = build_launcher(tmp_path)

    with pytest.raises(PolicyLaunchError) as exc_info:
        launcher.launch("missing_source", NOW)

    assert exc_info.value.code == "POLICY_SOURCE_NOT_FOUND"
    assert repository.list_runs() == {}
