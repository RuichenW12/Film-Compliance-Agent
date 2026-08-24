"""Bounded HTTPS policy source fetcher."""

from __future__ import annotations

import httpx

from ..models import FetchedSource, PolicySource


class PolicySourceFetchError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class HttpSourceFetcher:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        timeout_seconds: float = 20.0,
        max_bytes: int = 5 * 1024 * 1024,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes

    async def fetch(self, source: PolicySource) -> FetchedSource:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=5,
            timeout=self._timeout_seconds,
            headers={"User-Agent": "Film-Compliance-Agent/0.1 policy-monitor"},
        )
        try:
            response = await client.get(source.url)
            response.raise_for_status()
            content = response.content
        except httpx.HTTPError as exc:
            raise PolicySourceFetchError(
                "POLICY_SOURCE_FETCH_FAILED",
                "policy source request failed",
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        if not content or len(content) > self._max_bytes:
            raise PolicySourceFetchError(
                "POLICY_SOURCE_FETCH_FAILED",
                "policy source body is invalid",
            )
        if response.url.scheme != "https":
            raise PolicySourceFetchError(
                "POLICY_SOURCE_FETCH_FAILED",
                "policy source redirect is unsafe",
            )
        return FetchedSource(content=content, source_url=str(response.url))
