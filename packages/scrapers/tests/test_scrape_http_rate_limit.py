"""A 429 means slow down: back off on the same route, never retry from another address (#1081)."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from scrapers.discovery import scrape_http as sh

URL = "https://www.example-county.gov/meetings"


def _resp(status: int, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, headers={"content-type": "text/html", **(headers or {})},
                          text="<html><body>" + "<p>ok</p>" * 80 + "</body></html>", request=httpx.Request("GET", URL))


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    sh._DIRECT_FIRST_HOSTS.clear()
    sh._reset_saved_hosts_state()
    monkeypatch.setenv("SCRAPE_DIRECT_HOSTS_FILE", str(tmp_path / "hosts.json"))
    monkeypatch.setenv("SCRAPE_VPN_BYPASS_RETRY", "true")
    waits: list[float] = []

    async def fake_sleep(s: float) -> None:
        waits.append(s)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    yield waits
    sh._DIRECT_FIRST_HOSTS.clear()
    sh._reset_saved_hosts_state()


def test_429_is_not_a_reason_to_switch_route():
    assert not sh.is_scrape_transport_or_vpn_failure(status_code=429)
    assert sh.is_scrape_transport_or_vpn_failure(status_code=403)


def test_retry_after_seconds_and_backoff(monkeypatch):
    monkeypatch.setenv("SCRAPE_429_MAX_WAIT_SECONDS", "30")
    monkeypatch.setenv("SCRAPE_429_BASE_SECONDS", "5")
    assert sh.retry_after_seconds(_resp(429, {"Retry-After": "7"}), 0) == 7
    assert sh.retry_after_seconds(_resp(429, {"Retry-After": "999"}), 0) == 30  # capped
    assert sh.retry_after_seconds(_resp(429), 0) == 5
    assert sh.retry_after_seconds(_resp(429), 1) == 10
    assert sh.retry_after_seconds(_resp(429, {"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}), 0) == 0  # in the past


def test_429_moves_on_by_default_without_going_direct(monkeypatch, _env):
    async def fake_direct(client, url, kwargs):
        raise AssertionError("must not retry from another address")

    monkeypatch.setattr(sh, "_direct_get", fake_direct)
    monkeypatch.delenv("SCRAPE_429_MAX_RETRIES", raising=False)
    gets = []

    def handler(request):
        gets.append(str(request.url))
        return _resp(429)

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await sh.async_get_with_vpn_bypass(client, URL)

    assert asyncio.run(go()).status_code == 429
    assert gets == [URL] and _env == []


def test_429_backs_off_then_succeeds_without_going_direct(monkeypatch, _env):
    monkeypatch.setenv("SCRAPE_429_MAX_RETRIES", "2")
    calls = {"normal": 0, "direct": 0}

    async def fake_direct(client, url, kwargs):
        calls["direct"] += 1
        return _resp(200)

    monkeypatch.setattr(sh, "_direct_get", fake_direct)
    seq = iter([_resp(429, {"Retry-After": "3"}), _resp(200)])

    def handler(request):
        calls["normal"] += 1
        return next(seq)

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await sh.async_get_with_vpn_bypass(client, URL)

    r = asyncio.run(go())
    assert r.status_code == 200
    assert calls == {"normal": 2, "direct": 0}
    assert _env == [3.0]


def test_429_gives_up_after_the_limit(monkeypatch, _env):
    monkeypatch.setenv("SCRAPE_429_MAX_RETRIES", "2")

    async def fake_direct(client, url, kwargs):
        raise AssertionError("must not retry from another address")

    monkeypatch.setattr(sh, "_direct_get", fake_direct)

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: _resp(429))) as client:
            return await sh.async_get_with_vpn_bypass(client, URL)

    assert asyncio.run(go()).status_code == 429
    assert len(_env) == 2
