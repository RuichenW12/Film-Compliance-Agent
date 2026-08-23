import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from schemas.policy_snapshot import ImpactNode, PackName, ProposalStatus
from workers.policy.refresh import PolicyRefreshError, PolicyRefreshModule
from workers.policy.models import PolicySource, ProposalDraft
from workers.policy.repository import InMemoryPolicyRepository
from workers.policy.adapters.fake_proposal import FakeProposalModel
from workers.policy.adapters.file_blob import FileBlobStore
from workers.policy.adapters.fixture_source import FixtureSourceFetcher


FIXTURES = Path(__file__).parents[1] / "fixtures" / "policy"
NOW = datetime(2026, 8, 23, 14, 0, tzinfo=timezone(timedelta(hours=8)))
SOURCE = PolicySource(
    source_id="nrta_micro_drama",
    url="https://www.nrta.gov.cn/example",
    content_selector="#zoom",
    enabled=True,
)


def build_refresh(tmp_path: Path) -> tuple[
    PolicyRefreshModule,
    InMemoryPolicyRepository,
    FixtureSourceFetcher,
    FakeProposalModel,
]:
    repository = InMemoryPolicyRepository()
    fetcher = FixtureSourceFetcher({SOURCE.source_id: FIXTURES / "source-v1.html"})
    proposal_model = FakeProposalModel(
        ProposalDraft(
            summary="分类标准由未公布变为正式公布",
            impact=[ImpactNode.D1C],
            effective_from=NOW,
            draft_pack_updates={
                PackName.P3_TIER_THRESHOLDS: {"thresholds_published": True}
            },
        )
    )
    module = PolicyRefreshModule(
        sources={SOURCE.source_id: SOURCE},
        fetcher=fetcher,
        blob_store=FileBlobStore(tmp_path / "blobs"),
        proposal_model=proposal_model,
        repository=repository,
    )
    return module, repository, fetcher, proposal_model


def run_refresh(
    module: PolicyRefreshModule,
    repository: InMemoryPolicyRepository,
    run_id: str,
):
    repository.create_run(run_id, SOURCE.source_id, NOW)
    return asyncio.run(module.run(run_id, SOURCE.source_id, NOW))


def test_first_refresh_establishes_baseline_without_proposal(tmp_path: Path) -> None:
    module, repository, _, proposal_model = build_refresh(tmp_path)

    result = run_refresh(module, repository, "run_001")

    assert result.status == "no_change"
    assert result.proposal_id is None
    assert result.previous_sha256 is None
    assert repository.get_source_state(SOURCE.source_id).normalized_sha256
    assert repository.get_run("run_001").status == "no_change"
    assert proposal_model.call_count == 0


def test_repeated_fixture_is_no_change_and_skips_model(tmp_path: Path) -> None:
    module, repository, _, proposal_model = build_refresh(tmp_path)
    first = run_refresh(module, repository, "run_001")

    second = run_refresh(module, repository, "run_002")

    assert second.status == "no_change"
    assert second.previous_sha256 == first.current_sha256
    assert second.current_sha256 == first.current_sha256
    assert proposal_model.call_count == 0


def test_changed_fixture_creates_pending_proposal_and_diff(tmp_path: Path) -> None:
    module, repository, fetcher, proposal_model = build_refresh(tmp_path)
    first = run_refresh(module, repository, "run_001")
    fetcher.set_path(SOURCE.source_id, FIXTURES / "source-v2.html")

    result = run_refresh(module, repository, "run_002")

    proposal = repository.get_proposal(result.proposal_id)
    assert result.status == "proposal_created"
    assert result.previous_sha256 == first.current_sha256
    assert result.current_sha256 != first.current_sha256
    assert proposal.status is ProposalStatus.PENDING
    assert proposal.source_diff_uri.startswith("file://")
    assert proposal_model.call_count == 1
    assert repository.get_source_state(SOURCE.source_id).normalized_sha256 == (
        result.current_sha256
    )


def test_refresh_failure_preserves_last_known_good_source_state(tmp_path: Path) -> None:
    module, repository, fetcher, _ = build_refresh(tmp_path)
    run_refresh(module, repository, "run_001")
    previous_state = repository.get_source_state(SOURCE.source_id)
    fetcher.set_path(SOURCE.source_id, tmp_path / "missing.html")
    repository.create_run("run_002", SOURCE.source_id, NOW)

    with pytest.raises(PolicyRefreshError):
        asyncio.run(module.run("run_002", SOURCE.source_id, NOW))

    assert repository.get_run("run_002").status == "failed"
    assert repository.get_source_state(SOURCE.source_id) == previous_state
