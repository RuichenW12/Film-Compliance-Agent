"""Configured local HTML source adapter for tests and the Gate 2 demo."""

from pathlib import Path

from ..models import FetchedSource, PolicySource


class FixtureSourceError(OSError):
    code = "POLICY_FETCH_FAILED"


class FixtureSourceFetcher:
    def __init__(self, paths: dict[str, Path]) -> None:
        self._paths = dict(paths)

    def set_path(self, source_id: str, path: Path) -> None:
        self._paths[source_id] = path

    async def fetch(self, source: PolicySource) -> FetchedSource:
        try:
            path = self._paths[source.source_id]
            content = path.read_bytes()
        except (KeyError, OSError) as exc:
            raise FixtureSourceError(f"fixture unavailable: {source.source_id}") from exc
        if not content:
            raise FixtureSourceError(f"fixture is empty: {source.source_id}")
        return FetchedSource(content=content, source_url=source.url)
