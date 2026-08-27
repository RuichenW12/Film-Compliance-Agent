"""Validate and freeze the evidence-backed policy snapshot v2 archive."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import yaml

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schemas import PolicySnapshot
from policy.validation import validate_snapshot


DEFAULT_SEED = ROOT / "policy" / "seed-snapshot-v2.yaml"
DEFAULT_ARCHIVE = ROOT / "docs" / "partner-review" / "sources-v2"
DEFAULT_MANIFEST = DEFAULT_ARCHIVE / "manifest.json"
DEFAULT_FROZEN = DEFAULT_ARCHIVE / "snapshot" / "seed-snapshot-v2.yaml"


class MaterializationError(ValueError):
    """The seed and evidence archive cannot produce a trustworthy snapshot."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_snapshot_source_ids(value: Any) -> set[str]:
    """Collect explicit source references without treating URLs as catalog IDs."""

    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "source_id" and isinstance(item, str):
                found.add(item)
            elif key == "source_refs" and isinstance(item, list):
                found.update(str(source_id) for source_id in item)
            else:
                found.update(collect_snapshot_source_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(collect_snapshot_source_ids(item))
    return found


def _safe_archive_path(archive: Path, relative: str) -> Path:
    candidate = (archive / relative).resolve()
    archive_root = archive.resolve()
    if candidate != archive_root and archive_root not in candidate.parents:
        raise MaterializationError(f"manifest path escapes archive: {relative}")
    return candidate


def verify_manifest_files(archive: Path, manifest: dict[str, Any]) -> int:
    """Verify every downloaded evidence file declared by the source catalog."""

    checked = 0
    for source in manifest.get("sources", []):
        source_id = source.get("source_id", "unknown")
        for archived in source.get("files", []):
            relative = str(archived["path"])
            path = _safe_archive_path(archive, relative)
            if not path.is_file():
                raise MaterializationError(f"{source_id} missing file: {relative}")
            actual = _sha256(path)
            expected = str(archived["sha256"])
            if actual != expected:
                raise MaterializationError(
                    f"{source_id} hash mismatch for {relative}: {actual}"
                )
            checked += 1
    return checked


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    try:
        validate_snapshot(PolicySnapshot.model_validate(snapshot))
    except Exception as exc:
        raise MaterializationError(f"invalid policy snapshot: {exc}") from exc


def _catalogued_source_ids(manifest: dict[str, Any]) -> set[str]:
    ids = [str(source["source_id"]) for source in manifest.get("sources", [])]
    if len(ids) != len(set(ids)):
        raise MaterializationError("manifest contains duplicate source_id")
    return set(ids)


def check_materialization(
    snapshot: dict[str, Any],
    manifest: dict[str, Any],
    archive: Path,
    frozen: Path,
) -> None:
    """Fail closed if evidence, references, or the frozen copy has drifted."""

    _validate_snapshot(snapshot)
    referenced = collect_snapshot_source_ids(snapshot)
    unknown = sorted(referenced - _catalogued_source_ids(manifest))
    if unknown:
        raise MaterializationError(f"snapshot cites unknown source IDs: {unknown}")
    verify_manifest_files(archive, manifest)
    if not frozen.is_file():
        raise MaterializationError(f"frozen snapshot missing: {frozen}")
    frozen_snapshot = yaml.safe_load(frozen.read_text(encoding="utf-8"))
    if frozen_snapshot != snapshot:
        raise MaterializationError("frozen snapshot differs from canonical v2 seed")
    recorded = manifest.get("snapshot_file", {})
    if recorded.get("path") != "snapshot/seed-snapshot-v2.yaml":
        raise MaterializationError("manifest snapshot_file path is missing or invalid")
    actual = _sha256(frozen)
    if recorded.get("sha256") != actual:
        raise MaterializationError("manifest snapshot_file hash is stale")


def materialize(
    seed: Path = DEFAULT_SEED,
    manifest_path: Path = DEFAULT_MANIFEST,
    archive: Path = DEFAULT_ARCHIVE,
    frozen: Path = DEFAULT_FROZEN,
    *,
    check: bool = False,
) -> None:
    seed_bytes = seed.read_bytes()
    snapshot = yaml.safe_load(seed_bytes)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if check:
        check_materialization(snapshot, manifest, archive, frozen)
        return

    _validate_snapshot(snapshot)
    unknown = sorted(
        collect_snapshot_source_ids(snapshot) - _catalogued_source_ids(manifest)
    )
    if unknown:
        raise MaterializationError(f"snapshot cites unknown source IDs: {unknown}")
    verify_manifest_files(archive, manifest)
    frozen.write_bytes(seed_bytes)
    manifest["snapshot_materialized_at"] = snapshot["published_at"]
    manifest["snapshot_file"] = {
        "path": "snapshot/seed-snapshot-v2.yaml",
        "sha256": _sha256(frozen),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    check_materialization(snapshot, manifest, archive, frozen)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the archive without updating generated files",
    )
    args = parser.parse_args()
    materialize(check=args.check)
    print("policy snapshot v2 archive: OK")


if __name__ == "__main__":
    main()
