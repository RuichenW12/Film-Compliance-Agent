from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.materialize_policy_snapshot_v2 import (
    MaterializationError,
    check_materialization,
    collect_snapshot_source_ids,
    verify_manifest_files,
)


ROOT = Path(__file__).parents[2]
SEED = ROOT / "policy" / "seed-snapshot-v2.yaml"
ARCHIVE = ROOT / "docs" / "partner-review" / "sources-v2"
MANIFEST = ARCHIVE / "manifest.json"
FROZEN = ARCHIVE / "snapshot" / "seed-snapshot-v2.yaml"


def test_snapshot_source_ids_exist_in_manifest() -> None:
    snapshot = yaml.safe_load(SEED.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    catalogued = {source["source_id"] for source in manifest["sources"]}

    assert collect_snapshot_source_ids(snapshot) <= catalogued
    assert {"SRC-001", "SRC-005", "SRC-006", "SRC-007"} <= catalogued


def test_all_manifest_files_have_matching_hashes() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert verify_manifest_files(ARCHIVE, manifest) > 12


def test_unknown_snapshot_source_fails_closed() -> None:
    snapshot = yaml.safe_load(SEED.read_text(encoding="utf-8"))
    snapshot["packs"]["p4_process_templates"]["source_refs"].append("SRC-999")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    with pytest.raises(MaterializationError, match="SRC-999"):
        check_materialization(snapshot, manifest, ARCHIVE, FROZEN)


def test_checked_in_frozen_snapshot_matches_seed() -> None:
    snapshot = yaml.safe_load(SEED.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    check_materialization(snapshot, manifest, ARCHIVE, FROZEN)
