"""Content-addressed Google Cloud Storage policy blobs."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Any
from urllib.parse import unquote, urlparse

from schemas.policy_snapshot import PackName

from ..models import BlobRef, PolicyDiff


class PolicyBlobIntegrityError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class GcsBlobStore:
    def __init__(
        self,
        client: Any,
        bucket: str,
        precondition_failed_type: type[Exception],
    ) -> None:
        self._client = client
        self._bucket_name = bucket
        self._bucket = client.bucket(bucket)
        self._precondition_failed_type = precondition_failed_type

    @classmethod
    def from_project(cls, project: str, bucket: str) -> "GcsBlobStore":
        from google.api_core.exceptions import PreconditionFailed
        from google.cloud import storage

        return cls(storage.Client(project=project), bucket, PreconditionFailed)

    def put_raw(
        self, source_id: str, content: bytes, fetched_at: datetime
    ) -> BlobRef:
        digest = sha256(content).hexdigest()
        object_name = (
            f"policy/raw/{source_id}/{fetched_at:%Y}/{fetched_at:%m}/"
            f"{fetched_at:%d}/{digest}.html"
        )
        return self._put(object_name, content, digest)

    def put_normalized(
        self, source_id: str, text: str, fetched_at: datetime
    ) -> BlobRef:
        _ = fetched_at
        content = text.encode("utf-8")
        digest = sha256(content).hexdigest()
        return self._put(
            f"policy/normalized/{source_id}/{digest}.txt",
            content,
            digest,
        )

    def put_diff(
        self, source_id: str, diff: PolicyDiff, created_at: datetime
    ) -> BlobRef:
        _ = created_at
        content = json.dumps(
            diff.model_dump(), ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        digest = sha256(content).hexdigest()
        object_name = (
            f"policy/diffs/{source_id}/"
            f"{diff.previous_sha256}..{diff.current_sha256}.json"
        )
        return self._put(object_name, content, digest)

    def put_pack(
        self,
        snapshot_version: str,
        pack_name: PackName,
        content: dict[str, object],
    ) -> BlobRef:
        encoded = json.dumps(
            content, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        digest = sha256(encoded).hexdigest()
        return self._put(
            f"policy/packs/{snapshot_version}/{pack_name.value}.json",
            encoded,
            digest,
        )

    def read_text(self, uri: str) -> str:
        parsed = urlparse(uri)
        object_name = unquote(parsed.path.lstrip("/"))
        if (
            parsed.scheme != "gs"
            or parsed.netloc != self._bucket_name
            or not object_name
        ):
            raise ValueError("blob URI is outside the configured GCS bucket")
        return self._bucket.blob(object_name).download_as_bytes().decode("utf-8")

    def _put(self, object_name: str, content: bytes, digest: str) -> BlobRef:
        blob = self._bucket.blob(object_name)
        try:
            blob.upload_from_string(content, if_generation_match=0)
        except self._precondition_failed_type:
            if blob.download_as_bytes() != content:
                raise PolicyBlobIntegrityError(
                    "POLICY_BLOB_INTEGRITY_FAILED",
                    "existing policy blob does not match expected content",
                ) from None
        return BlobRef(
            uri=f"gs://{self._bucket_name}/{object_name}",
            sha256=digest,
        )
