from datetime import datetime, timezone
from hashlib import sha256
import json

import pytest

from schemas.policy_snapshot import PackName
from workers.policy.adapters.gcs_blob import GcsBlobStore, PolicyBlobIntegrityError
from workers.policy.models import PolicyDiff


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


class FakePreconditionFailed(Exception):
    pass


class FakeBlob:
    def __init__(self, name: str, objects: dict[str, bytes], uploads: list[tuple]):
        self.name = name
        self._objects = objects
        self._uploads = uploads

    def upload_from_string(self, content: bytes, **kwargs) -> None:
        self._uploads.append((self.name, content, kwargs))
        if self.name in self._objects:
            raise FakePreconditionFailed
        self._objects[self.name] = content

    def download_as_bytes(self) -> bytes:
        return self._objects[self.name]


class FakeBucket:
    def __init__(self, objects: dict[str, bytes], uploads: list[tuple]):
        self._objects = objects
        self._uploads = uploads

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(name, self._objects, self._uploads)


class FakeStorageClient:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.uploads: list[tuple] = []
        self.requested_buckets: list[str] = []

    def bucket(self, name: str) -> FakeBucket:
        self.requested_buckets.append(name)
        return FakeBucket(self.objects, self.uploads)


def build_store() -> tuple[GcsBlobStore, FakeStorageClient]:
    client = FakeStorageClient()
    return (
        GcsBlobStore(client, "policy-bucket", FakePreconditionFailed),
        client,
    )


def test_puts_raw_normalized_diff_and_pack_at_deterministic_paths() -> None:
    store, client = build_store()
    raw = b"<html>policy</html>"
    raw_digest = sha256(raw).hexdigest()
    normalized = "政策正文"
    normalized_digest = sha256(normalized.encode()).hexdigest()
    diff = PolicyDiff(
        source_id="nrta_source",
        previous_sha256="a" * 64,
        current_sha256="b" * 64,
        unified_diff="-old\n+new",
    )

    raw_ref = store.put_raw("nrta_source", raw, NOW)
    normalized_ref = store.put_normalized("nrta_source", normalized, NOW)
    diff_ref = store.put_diff("nrta_source", diff, NOW)
    pack_ref = store.put_pack(
        "v2",
        PackName.P3_TIER_THRESHOLDS,
        {"thresholds_published": False, "中文": "保留"},
    )

    assert raw_ref.uri == (
        f"gs://policy-bucket/policy/raw/nrta_source/2026/08/24/{raw_digest}.html"
    )
    assert normalized_ref.uri == (
        f"gs://policy-bucket/policy/normalized/nrta_source/{normalized_digest}.txt"
    )
    assert diff_ref.uri == (
        "gs://policy-bucket/policy/diffs/nrta_source/"
        f"{'a' * 64}..{'b' * 64}.json"
    )
    assert pack_ref.uri == (
        "gs://policy-bucket/policy/packs/v2/p3_tier_thresholds.json"
    )
    assert client.objects["policy/packs/v2/p3_tier_thresholds.json"] == json.dumps(
        {"thresholds_published": False, "中文": "保留"},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    assert all(upload[2] == {"if_generation_match": 0} for upload in client.uploads)


def test_identical_retry_is_accepted() -> None:
    store, client = build_store()

    first = store.put_normalized("source", "same", NOW)
    second = store.put_normalized("source", "same", NOW)

    assert second == first
    assert len(client.objects) == 1


def test_mismatched_existing_object_raises_integrity_error() -> None:
    store, client = build_store()
    expected = "same".encode()
    digest = sha256(expected).hexdigest()
    client.objects[f"policy/normalized/source/{digest}.txt"] = b"tampered"

    with pytest.raises(PolicyBlobIntegrityError) as exc_info:
        store.put_normalized("source", "same", NOW)

    assert exc_info.value.code == "POLICY_BLOB_INTEGRITY_FAILED"


@pytest.mark.parametrize(
    "uri",
    [
        "https://policy-bucket/policy/normalized/a.txt",
        "gs://another-bucket/policy/normalized/a.txt",
        "gs://policy-bucket/",
    ],
)
def test_read_text_rejects_invalid_uri(uri: str) -> None:
    store, _ = build_store()

    with pytest.raises(ValueError):
        store.read_text(uri)


def test_read_text_decodes_utf8_and_rejects_invalid_utf8() -> None:
    store, client = build_store()
    client.objects["policy/normalized/source/valid.txt"] = "政策".encode()
    client.objects["policy/normalized/source/invalid.txt"] = b"\xff"

    assert (
        store.read_text("gs://policy-bucket/policy/normalized/source/valid.txt")
        == "政策"
    )
    with pytest.raises(UnicodeDecodeError):
        store.read_text("gs://policy-bucket/policy/normalized/source/invalid.txt")
