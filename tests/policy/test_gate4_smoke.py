import asyncio
from datetime import datetime, timezone
from pathlib import Path

import yaml

from schemas.policy_snapshot import ImpactNode, PackName, PolicySnapshot
from workers.policy.adapters.fake_proposal import FakeProposalModel
from workers.policy.adapters.file_blob import FileBlobStore
from workers.policy.adapters.fixture_source import FixtureSourceFetcher
from workers.policy.gate4_smoke import run_source_smoke
from workers.policy.models import PolicySource, ProposalDraft
from workers.policy.repository import InMemoryPolicyRepository


ROOT = Path(__file__).parents[2]
NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
SOURCE = PolicySource(
    source_id="nrta_micro_drama_management_measures",
    url="https://www.nrta.gov.cn/art/2026/7/31/art_113_73785.html",
    content_selector="#zoom",
    enabled=True,
)


def test_source_smoke_proves_baseline_and_last_known_good(tmp_path: Path) -> None:
    repository = InMemoryPolicyRepository()
    seed = PolicySnapshot.model_validate(
        yaml.safe_load(
            (ROOT / "policy" / "seed-snapshot-v1.yaml").read_text(encoding="utf-8")
        )
    )
    seed_json = seed.model_dump_json()
    proposal_model = FakeProposalModel(
        ProposalDraft(
            summary="unused",
            impact=[ImpactNode.D1C],
            effective_from=NOW,
            draft_pack_updates={
                PackName.P3_TIER_THRESHOLDS: {"thresholds_published": False}
            },
        )
    )

    report = asyncio.run(
        run_source_smoke(
            source=SOURCE,
            fetcher=FixtureSourceFetcher(
                {
                    SOURCE.source_id: (
                        ROOT / "tests" / "fixtures" / "policy" / "source-v1.html"
                    )
                }
            ),
            blob_store=FileBlobStore(tmp_path / "blobs"),
            repository=repository,
            seed=seed,
            proposal_model=proposal_model,
            clock=lambda: NOW,
        )
    )

    assert report.mode == "source"
    assert report.overall == "PASS"
    assert report.source_status == "PASS"
    assert report.failure_status == "PASS"
    assert report.last_known_good_preserved is True
    assert report.normalized_sha256
    assert report.first_run_status == "no_change"
    assert report.failure_run_status == "failed"
    assert repository.get_run("run_source_baseline").status == "no_change"
    assert repository.get_run("run_source_failure").status == "failed"
    assert repository.latest_snapshot().model_dump_json() == seed_json
    assert (
        repository.get_source_state(SOURCE.source_id).normalized_sha256
        == report.normalized_sha256
    )
    assert "policy text" not in report.model_dump_json().lower()
