import asyncio
from datetime import datetime, timezone
from pathlib import Path

import yaml

from schemas.policy_snapshot import ImpactNode, PackName, PolicySnapshot
from workers.policy.adapters.fake_event_publisher import FakeEventPublisher
from workers.policy.adapters.fake_proposal import FakeProposalModel
from workers.policy.adapters.file_blob import FileBlobStore
from workers.policy.adapters.fixture_source import FixtureSourceFetcher
from workers.policy.cloud_runtime import (
    CloudAdapterFactories,
    CloudPolicySettings,
    build_cloud_policy_runtime,
)
from workers.policy.gate4_smoke import run_cloud_smoke, run_source_smoke
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


class SecretFailEventPublisher:
    def publish(self, event):
        _ = event
        raise RuntimeError("credential secret must not leak")


def build_injected_cloud_runtime(tmp_path: Path, *, fail_pubsub: bool = False):
    settings = CloudPolicySettings(
        project="film-project",
        gcs_bucket="policy-smoke-bucket",
        pubsub_topic="policy-smoke",
    )
    repository = InMemoryPolicyRepository()
    proposal_model = FakeProposalModel(
        ProposalDraft(
            summary="synthetic fixture diff",
            impact=[ImpactNode.D1C],
            effective_from=NOW,
            draft_pack_updates={
                PackName.P3_TIER_THRESHOLDS: {"thresholds_published": False}
            },
        )
    )
    event_publisher = (
        SecretFailEventPublisher() if fail_pubsub else FakeEventPublisher()
    )
    factories = CloudAdapterFactories(
        firestore=lambda project, database: repository,
        gcs=lambda project, bucket: FileBlobStore(tmp_path / "cloud-blobs"),
        http=lambda: FixtureSourceFetcher(
            {
                SOURCE.source_id: (
                    ROOT / "tests" / "fixtures" / "policy" / "source-v1.html"
                )
            }
        ),
        gemini=lambda project, location, model, prompt: proposal_model,
        pubsub=lambda project, topic: event_publisher,
    )
    runtime = build_cloud_policy_runtime(settings, factories=factories)
    return settings, runtime, repository, proposal_model, event_publisher


def test_cloud_smoke_skips_without_required_settings() -> None:
    report = asyncio.run(
        run_cloud_smoke(
            env={},
            runtime_builder=lambda settings: (_ for _ in ()).throw(
                AssertionError("runtime must not be built")
            ),
            clock=lambda: NOW,
        )
    )

    assert report.overall == "SKIP"
    assert report.stage_code == "POLICY_CLOUD_CONFIG_MISSING"
    assert {
        report.source_status,
        report.gcs_status,
        report.firestore_status,
        report.failure_status,
        report.gemini_status,
        report.pubsub_status,
    } == {"SKIP"}


def test_cloud_smoke_runs_all_probes_without_persisting_synthetic_proposal(
    tmp_path: Path,
) -> None:
    settings, runtime, repository, proposal_model, event_publisher = (
        build_injected_cloud_runtime(tmp_path)
    )

    report = asyncio.run(
        run_cloud_smoke(
            settings=settings,
            runtime_builder=lambda selected: runtime,
            clock=lambda: NOW,
        )
    )

    assert report.overall == "PASS"
    assert report.source_status == "PASS"
    assert report.gcs_status == "PASS"
    assert report.firestore_status == "PASS"
    assert report.failure_status == "PASS"
    assert report.gemini_status == "PASS"
    assert report.pubsub_status == "PASS"
    assert report.last_known_good_preserved is True
    assert report.normalized_sha256
    assert repository.get_source_state(SOURCE.source_id) is not None
    assert sorted(run.status for run in repository.list_runs().values()) == [
        "failed",
        "no_change",
    ]
    assert repository.list_proposals() == {}
    assert proposal_model.call_count == 1
    assert len(event_publisher.published) == 1
    assert event_publisher.published[0].idempotency_key == "policy.updated:v2"
    assert report.message_id == "message-v2"


def test_cloud_adapter_failure_reports_stable_stage_without_secret(
    tmp_path: Path,
) -> None:
    settings, runtime, _, _, _ = build_injected_cloud_runtime(
        tmp_path,
        fail_pubsub=True,
    )

    report = asyncio.run(
        run_cloud_smoke(
            settings=settings,
            runtime_builder=lambda selected: runtime,
            clock=lambda: NOW,
        )
    )

    assert report.overall == "FAIL"
    assert report.pubsub_status == "FAIL"
    assert report.stage_code == "POLICY_CLOUD_PUBSUB_FAILED"
    assert report.message_id is None
    assert "secret" not in report.model_dump_json().lower()
