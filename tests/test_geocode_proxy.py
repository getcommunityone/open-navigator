"""Offline regression tests for the Nominatim geocoding proxy."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

import httpx
import pytest
from fastapi import HTTPException

from api.routes import geocode


class StubAsyncClient:
    """Minimal async httpx client replacement with deterministic responses."""

    def __init__(
        self,
        outcomes: Iterable[httpx.Response | Exception],
        *,
        yield_before_response: bool = False,
    ) -> None:
        self._outcomes = iter(outcomes)
        self.yield_before_response = yield_before_response
        self.calls: list[dict[str, object]] = []

    async def __aenter__(self) -> "StubAsyncClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> httpx.Response:
        self.calls.append({"url": url, "params": params, "headers": headers})
        if self.yield_before_response:
            await asyncio.sleep(0)
        outcome = next(self._outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def response(
    status_code: int,
    *,
    json: object | None = None,
    content: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request("GET", "https://nominatim.openstreetmap.org/search")
    if content is not None:
        return httpx.Response(
            status_code,
            content=content,
            headers=headers,
            request=request,
        )
    return httpx.Response(status_code, json=json, headers=headers, request=request)


@pytest.fixture(autouse=True)
def reset_proxy_state(monkeypatch: pytest.MonkeyPatch) -> None:
    geocode._cache.clear()
    geocode._last_call_ts = 0.0
    monkeypatch.setattr(geocode, "_throttle_lock", asyncio.Lock())
    monkeypatch.setattr(geocode, "_MIN_INTERVAL_S", 0.0)


def install_client(monkeypatch: pytest.MonkeyPatch, client: StubAsyncClient) -> None:
    monkeypatch.setattr(geocode.httpx, "AsyncClient", lambda **_kwargs: client)


def test_identical_concurrent_requests_share_one_upstream_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [{"display_name": "Seattle, Washington"}]
    client = StubAsyncClient([response(200, json=payload)], yield_before_response=True)
    install_client(monkeypatch, client)
    params = {"q": "Seattle", "format": "json"}

    async def run() -> list[object]:
        return await asyncio.gather(
            geocode._throttled_get("/search", params),
            geocode._throttled_get("/search", params),
        )

    results = asyncio.run(run())

    assert results == [payload, payload]
    assert len(client.calls) == 1


def test_successful_response_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"display_name": "King County, Washington"}
    client = StubAsyncClient([response(200, json=payload)])
    install_client(monkeypatch, client)
    params = {"lat": "47.6", "lon": "-122.3"}

    first = asyncio.run(geocode._throttled_get("/reverse", params))
    second = asyncio.run(geocode._throttled_get("/reverse", params))

    assert first == second == payload
    assert len(client.calls) == 1


@pytest.mark.parametrize(
    ("upstream_error", "detail"),
    [
        (httpx.ReadTimeout("slow upstream"), "Geocoder request timed out."),
        (httpx.ConnectError("connection refused"), "Geocoder is unavailable."),
    ],
)
def test_transport_failures_become_safe_gateway_errors(
    monkeypatch: pytest.MonkeyPatch,
    upstream_error: httpx.RequestError,
    detail: str,
) -> None:
    client = StubAsyncClient([upstream_error])
    install_client(monkeypatch, client)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(geocode._throttled_get("/search", {"q": "Seattle"}))

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == detail
    assert geocode._last_call_ts > 0


def test_rate_limit_forwards_integer_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    client = StubAsyncClient(
        [response(429, json={"error": "rate limited"}, headers={"Retry-After": "7"})]
    )
    install_client(monkeypatch, client)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(geocode._throttled_get("/search", {"q": "Seattle"}))

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "7"}


def test_invalid_retry_after_uses_safe_default(monkeypatch: pytest.MonkeyPatch) -> None:
    client = StubAsyncClient(
        [response(429, json={"error": "rate limited"}, headers={"Retry-After": "later"})]
    )
    install_client(monkeypatch, client)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(geocode._throttled_get("/search", {"q": "Seattle"}))

    assert exc_info.value.headers == {"Retry-After": "1"}


def test_non_json_response_becomes_gateway_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = StubAsyncClient([response(200, content=b"not-json")])
    install_client(monkeypatch, client)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(geocode._throttled_get("/search", {"q": "Seattle"}))

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Geocoder returned non-JSON."


def test_search_normalizes_query_and_country_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    client = StubAsyncClient([response(200, json=[])])
    install_client(monkeypatch, client)

    result = asyncio.run(geocode.geocode_search("  Seattle  ", 4, "US,CA"))

    assert result == []
    assert client.calls[0]["params"] == {
        "q": "Seattle",
        "format": "json",
        "addressdetails": "1",
        "countrycodes": "us,ca",
        "limit": "4",
    }


def test_search_rejects_whitespace_only_query() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(geocode.geocode_search("   ", 6, "us"))

    assert exc_info.value.status_code == 422
