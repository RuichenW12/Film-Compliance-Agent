"""Content-addressed file blob adapter for Gate 2."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

from ..models import BlobRef, PolicyDiff


class FileBlobStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def put_raw(
        self, source_id: str, content: bytes, fetched_at: datetime
    ) -> BlobRef:
        digest = sha256(content).hexdigest()
        relative = Path(
            "policy",
            "raw",
            source_id,
            f"{fetched_at:%Y}",
            f"{fetched_at:%m}",
            f"{fetched_at:%d}",
            f"{digest}.html",
        )
        return self._put(relative, content, digest)

    def put_normalized(
        self, source_id: str, text: str, fetched_at: datetime
    ) -> BlobRef:
        content = text.encode("utf-8")
        digest = sha256(content).hexdigest()
        relative = Path("policy", "normalized", source_id, f"{digest}.txt")
        return self._put(relative, content, digest)

    def put_diff(
        self, source_id: str, diff: PolicyDiff, created_at: datetime
    ) -> BlobRef:
        content = json.dumps(
            diff.model_dump(), ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        digest = sha256(content).hexdigest()
        relative = Path(
            "policy",
            "diffs",
            source_id,
            f"{diff.previous_sha256}..{diff.current_sha256}.json",
        )
        return self._put(relative, content, digest)

    def read_text(self, uri: str) -> str:
        path = self._path_from_uri(uri)
        return path.read_text(encoding="utf-8")

    def _put(self, relative: Path, content: bytes, digest: str) -> BlobRef:
        path = (self._root / relative).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != content:
                raise ValueError(f"content-addressed path collision: {path}")
        else:
            path.write_bytes(content)
        return BlobRef(uri=path.as_uri(), sha256=digest)

    def _path_from_uri(self, uri: str) -> Path:
        if not uri.startswith("file://"):
            raise ValueError("FileBlobStore only accepts file:// URIs")
        path = Path(uri.removeprefix("file://")).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("blob URI is outside the configured root")
        return path
