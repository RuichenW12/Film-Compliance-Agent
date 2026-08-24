#!/usr/bin/env python3
"""Run the Gate 4 source or credential-gated cloud smoke."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from schemas.policy_snapshot import ImpactNode, PackName, PolicySnapshot
from workers.policy.adapters.fake_proposal import FakeProposalModel
from workers.policy.adapters.file_blob import FileBlobStore
from workers.policy.adapters.http_source import HttpSourceFetcher
from workers.policy.gate4_smoke import run_cloud_smoke, run_source_smoke
from workers.policy.models import ProposalDraft
from workers.policy.repository import InMemoryPolicyRepository
from workers.policy.source_config import load_policy_sources


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--source", action="store_true")
    mode.add_argument("--cloud", action="store_true")
    return parser.parse_args()


async def run_source() -> int:
    sources = load_policy_sources(
        files("policy").joinpath("policy_sources.yaml")  # type: ignore[arg-type]
    )
    source = sources["nrta_micro_drama_management_measures"]
    seed = PolicySnapshot.model_validate(
        yaml.safe_load(
            files("policy").joinpath("seed-snapshot-v1.yaml").read_text(
                encoding="utf-8"
            )
        )
    )
    now = datetime.now(timezone.utc)
    proposal_model = FakeProposalModel(
        ProposalDraft(
            summary="unused source baseline proposal",
            impact=[ImpactNode.D1C],
            effective_from=now,
            draft_pack_updates={
                PackName.P3_TIER_THRESHOLDS: {"thresholds_published": False}
            },
        )
    )
    with TemporaryDirectory(prefix="policy-gate4-source-") as temp_dir:
        report = await run_source_smoke(
            source=source,
            fetcher=HttpSourceFetcher(),
            blob_store=FileBlobStore(Path(temp_dir)),
            repository=InMemoryPolicyRepository(),
            seed=seed,
            proposal_model=proposal_model,
            clock=lambda: now,
        )
    print(report.model_dump_json())
    return 0 if report.overall == "PASS" else 1


async def run_cloud() -> int:
    report = await run_cloud_smoke(
        clock=lambda: datetime.now(timezone.utc),
    )
    print(report.model_dump_json())
    return 0 if report.overall in {"PASS", "SKIP"} else 1


def main() -> int:
    args = parse_args()
    if args.source:
        return asyncio.run(run_source())
    return asyncio.run(run_cloud())


if __name__ == "__main__":
    raise SystemExit(main())
