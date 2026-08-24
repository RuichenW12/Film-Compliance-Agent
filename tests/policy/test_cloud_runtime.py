from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from schemas.policy_snapshot import ImpactNode, PackName
from workers.policy.adapters.fake_event_publisher import FakeEventPublisher
from workers.policy.adapters.fake_proposal import FakeProposalModel
from workers.policy.adapters.file_blob import FileBlobStore
from workers.policy.adapters.fixture_source import FixtureSourceFetcher
from workers.policy.cloud_runtime import (
    CloudAdapterFactories,
    CloudPolicyConfigurationError,
    CloudPolicySettings,
    build_cloud_policy_runtime,
)
from workers.policy.models import ProposalDraft
from workers.policy.repository import InMemoryPolicyRepository


ROOT = Path(__file__).parents[2]
NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
REQUIRED_ENV = {
    "GOOGLE_CLOUD_PROJECT": "film-project",
    "POLICY_GCS_BUCKET": "film-policy-bucket",
    "POLICY_PUBSUB_TOPIC": "policy-updated",
}


@pytest.mark.parametrize(
    "missing",
    ["GOOGLE_CLOUD_PROJECT", "POLICY_GCS_BUCKET", "POLICY_PUBSUB_TOPIC"],
)
def test_missing_required_cloud_setting_is_stable_error(missing: str) -> None:
    env = dict(REQUIRED_ENV)
    env.pop(missing)

    with pytest.raises(CloudPolicyConfigurationError) as exc_info:
        CloudPolicySettings.from_env(env)

    assert exc_info.value.code == "POLICY_CLOUD_CONFIG_INVALID"


def test_cloud_settings_defaults_and_explicit_values() -> None:
    defaults = CloudPolicySettings.from_env(REQUIRED_ENV)
    explicit = CloudPolicySettings.from_env(
        {
            **REQUIRED_ENV,
            "GOOGLE_CLOUD_LOCATION": "asia-east1",
            "POLICY_GEMINI_MODEL": "gemini-explicit",
            "FIRESTORE_DATABASE": "policy-db",
        }
    )

    assert defaults.location == "global"
    assert defaults.gemini_model == "gemini-3.5-flash"
    assert defaults.firestore_database == "(default)"
    assert explicit.location == "asia-east1"
    assert explicit.gemini_model == "gemini-explicit"
    assert explicit.firestore_database == "policy-db"


def test_local_modules_import_when_google_modules_are_blocked() -> None:
    code = """
import importlib
import importlib.abc
import pkgutil
import sys

class BlockGoogle(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'google' or fullname.startswith('google.'):
            raise ImportError('google modules intentionally hidden')
        return None

sys.meta_path.insert(0, BlockGoogle())
import workers.policy.local_demo
import api.main
for module in pkgutil.iter_modules(['workers/policy/adapters']):
    importlib.import_module(f'workers.policy.adapters.{module.name}')
"""

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_runtime_assets_are_packaged_resources() -> None:
    source_text = files("policy").joinpath("policy_sources.yaml").read_text(
        encoding="utf-8"
    )
    seed_text = files("policy").joinpath("seed-snapshot-v1.yaml").read_text(
        encoding="utf-8"
    )
    prompt_text = (
        files("prompts.policy").joinpath("proposal-v1.md").read_text(encoding="utf-8")
    )

    assert yaml.safe_load(source_text)["sources"][0]["source_id"] == (
        "nrta_micro_drama_management_measures"
    )
    assert yaml.safe_load(seed_text)["version"] == "v1"
    assert "BEGIN_UNTRUSTED_POLICY_DIFF" not in prompt_text
    assert "untrusted evidence" in prompt_text


def test_injected_factories_build_runtime_without_credentials(tmp_path: Path) -> None:
    settings = CloudPolicySettings.from_env(REQUIRED_ENV)
    repository = InMemoryPolicyRepository()
    blob_store = FileBlobStore(tmp_path / "blobs")
    fetcher = FixtureSourceFetcher(
        {
            "nrta_micro_drama_management_measures": (
                ROOT / "tests" / "fixtures" / "policy" / "source-v1.html"
            )
        }
    )
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
    event_publisher = FakeEventPublisher()
    calls: dict[str, tuple] = {}

    factories = CloudAdapterFactories(
        firestore=lambda project, database: (
            calls.setdefault("firestore", (project, database)) and repository
        ),
        gcs=lambda project, bucket: (
            calls.setdefault("gcs", (project, bucket)) and blob_store
        ),
        http=lambda: (calls.setdefault("http", ()) or fetcher),
        gemini=lambda project, location, model, prompt: (
            calls.setdefault("gemini", (project, location, model, prompt))
            and proposal_model
        ),
        pubsub=lambda project, topic: (
            calls.setdefault("pubsub", (project, topic)) and event_publisher
        ),
    )

    runtime = build_cloud_policy_runtime(settings, factories=factories)

    assert runtime.repository is repository
    assert runtime.blob_store is blob_store
    assert set(repository.list_snapshots()) == {"v1"}
    assert calls["firestore"] == ("film-project", "(default)")
    assert calls["gcs"] == ("film-project", "film-policy-bucket")
    assert calls["http"] == ()
    assert calls["gemini"][:3] == (
        "film-project",
        "global",
        "gemini-3.5-flash",
    )
    assert calls["pubsub"] == ("film-project", "policy-updated")
    run_id = runtime.launcher.launch(
        "nrta_micro_drama_management_measures",
        NOW,
    )
    assert run_id.startswith("run_")
    assert len(run_id) == 36
