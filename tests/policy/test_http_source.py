import asyncio

import httpx
import pytest

from workers.policy.adapters.http_source import (
    HttpSourceFetcher,
    PolicySourceFetchError,
)
from workers.policy.models import PolicySource


SOURCE = PolicySource(
    source_id="nrta_micro_drama_management_measures",
    url="https://example.com/policy",
    content_selector="#zoom",
    enabled=True,
)


def run_fetch(
    handler,
    *,
    max_bytes: int = 5 * 1024 * 1024,
    timeout_seconds: float = 20.0,
):
    async def execute():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
        ) as client:
            return await HttpSourceFetcher(
                client,
                max_bytes=max_bytes,
                timeout_seconds=timeout_seconds,
            ).fetch(SOURCE)

    return asyncio.run(execute())


def test_fetch_returns_raw_bytes_and_final_https_url() -> None:
    result = run_fetch(
        lambda request: httpx.Response(
            200,
            content=b"<div id='zoom'>policy</div>",
            request=request,
        )
    )

    assert result.content == b"<div id='zoom'>policy</div>"
    assert result.source_url == "https://example.com/policy"


@pytest.mark.parametrize("status", [404, 503])
def test_fetch_maps_non_success_status_to_stable_error(status: int) -> None:
    with pytest.raises(PolicySourceFetchError) as exc_info:
        run_fetch(lambda request: httpx.Response(status, request=request))

    assert exc_info.value.code == "POLICY_SOURCE_FETCH_FAILED"
    assert "response" not in str(exc_info.value).lower()


@pytest.mark.parametrize("body,max_bytes", [(b"", 1024), (b"too large", 3)])
def test_fetch_rejects_invalid_body(body: bytes, max_bytes: int) -> None:
    with pytest.raises(PolicySourceFetchError) as exc_info:
        run_fetch(
            lambda request: httpx.Response(200, content=body, request=request),
            max_bytes=max_bytes,
        )

    assert exc_info.value.code == "POLICY_SOURCE_FETCH_FAILED"


def test_fetch_maps_timeout_to_stable_error() -> None:
    def timeout(request):
        raise httpx.ReadTimeout("secret upstream detail", request=request)

    with pytest.raises(PolicySourceFetchError) as exc_info:
        run_fetch(timeout)

    assert exc_info.value.code == "POLICY_SOURCE_FETCH_FAILED"
    assert "secret" not in str(exc_info.value)


def test_fetch_enforces_total_timeout_across_stream() -> None:
    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for chunk in (b"a", b"b", b"c"):
                await asyncio.sleep(0.02)
                yield chunk

    with pytest.raises(PolicySourceFetchError) as exc_info:
        run_fetch(
            lambda request: httpx.Response(
                200,
                stream=SlowStream(),
                request=request,
            ),
            timeout_seconds=0.03,
        )

    assert exc_info.value.code == "POLICY_SOURCE_FETCH_FAILED"


def test_fetch_stops_streaming_as_soon_as_body_exceeds_limit() -> None:
    class CountingStream(httpx.AsyncByteStream):
        def __init__(self) -> None:
            self.yielded = 0

        async def __aiter__(self):
            for chunk in (b"aa", b"bb", b"must-not-be-read"):
                self.yielded += 1
                yield chunk

    stream = CountingStream()

    with pytest.raises(PolicySourceFetchError):
        run_fetch(
            lambda request: httpx.Response(
                200,
                stream=stream,
                request=request,
            ),
            max_bytes=3,
        )

    assert stream.yielded == 2


def test_fetch_rejects_final_non_https_url() -> None:
    def redirect_to_http(request):
        if request.url.scheme == "https":
            return httpx.Response(
                302,
                headers={"Location": "http://example.com/policy"},
                request=request,
            )
        return httpx.Response(200, content=b"policy", request=request)

    with pytest.raises(PolicySourceFetchError) as exc_info:
        run_fetch(redirect_to_http)

    assert exc_info.value.code == "POLICY_SOURCE_FETCH_FAILED"
