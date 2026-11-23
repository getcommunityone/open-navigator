"""Block pages and partial loads are retried outside the VPN; such hosts are remembered across runs (#767)."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from scrapers.discovery import scrape_http as sh

NORMAL = (
    "<html><head><title>Coffee County, AL | Official Website</title></head><body>"
    + "".join(f'<p>Commission meeting notice number {i} for residents.</p><a href="/p{i}">page {i}</a>' for i in range(60))
    + "</body></html>"
)
BLOCK = "<html><head><title>Access Denied</title></head><body>You don't have permission. Reference #18.abc</body></html>"
SHELL = "<html><head></head><body><div id=root></div></body></html>"


def _resp(body: str, status: int = 200, ctype: str = "text/html; charset=utf-8") -> httpx.Response:
    return httpx.Response(status, headers={"content-type": ctype}, text=body,
                          request=httpx.Request("GET", "https://coffeecounty.us/"))


@pytest.fixture(autouse=True)
def _reset(monkeypatch, tmp_path):
    sh._DIRECT_FIRST_HOSTS.clear()
    sh._reset_saved_hosts_state()
    monkeypatch.setenv("SCRAPE_DIRECT_HOSTS_FILE", str(tmp_path / "hosts.json"))
    monkeypatch.delenv("SCRAPE_DIRECT_PROXY", raising=False)
    yield
    sh._DIRECT_FIRST_HOSTS.clear()
    sh._reset_saved_hosts_state()


def test_a_normal_page_is_not_blocked():
    assert not sh.looks_blocked_or_partial(_resp(NORMAL))


@pytest.mark.parametrize("body", [BLOCK, SHELL, "<html><title>x</title><body>Just a moment...</body></html>"])
def test_block_pages_and_empty_shells_look_blocked(body):
    assert sh.looks_blocked_or_partial(_resp(body))


def test_non_html_is_never_blocked():
    assert not sh.looks_blocked_or_partial(_resp("%PDF-1.4 tiny", ctype="application/pdf"))


class _BareResponse:
    """An httpx-like response with no headers, as the site-search tests use."""

    def __init__(self, text: str):
        self.url = "https://www.cobbcounty.org/"
        self.text = text
        self.content = text.encode()
        self.status_code = 200


def test_a_response_without_headers_is_not_judged():
    assert not sh.looks_blocked_or_partial(_BareResponse("<html><body>Access Denied</body></html>"))


def test_a_response_without_headers_passes_through_the_bypass(monkeypatch):
    bare = _BareResponse('<html><body><a href="https://www.youtube.com/user/CobbCountyGovt">YouTube</a></body></html>')

    async def fake_direct(client, url, kwargs):
        raise AssertionError("no direct retry for an unjudged response")

    monkeypatch.setattr(sh, "_direct_get", fake_direct)

    class Client:
        async def get(self, url, **kw):
            return bare

    assert asyncio.run(sh.async_get_with_vpn_bypass(Client(), "https://www.cobbcounty.org/")) is bare


def test_a_blocked_200_is_retried_outside_the_vpn_and_the_host_saved(monkeypatch, tmp_path):
    async def fake_direct(client, url, kwargs):
        return _resp(NORMAL)

    monkeypatch.setattr(sh, "_direct_get", fake_direct)
    transport = httpx.MockTransport(lambda request: _resp(BLOCK))

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await sh.async_get_with_vpn_bypass(client, "https://coffeecounty.us/")

    resp = asyncio.run(run())
    assert "Official Website" in resp.text
    assert sh.prefers_direct("https://coffeecounty.us/about")
    assert json.loads((tmp_path / "hosts.json").read_text()) == ["coffeecounty.us"]


def test_saved_hosts_are_tried_direct_first_in_a_later_run(tmp_path):
    (tmp_path / "hosts.json").write_text(json.dumps(["coffeecounty.us"]))
    sh._DIRECT_FIRST_HOSTS.clear()
    sh._reset_saved_hosts_state()
    assert sh.prefers_direct("https://coffeecounty.us/")
    assert not sh.prefers_direct("https://example.org/")


def test_a_saved_host_that_fails_direct_falls_back_to_the_vpn(monkeypatch, tmp_path):
    """A host saved in an earlier run is not stuck outside the VPN once the direct route fails."""
    (tmp_path / "hosts.json").write_text(json.dumps(["coffeecounty.us"]))
    direct_calls = []

    async def fake_direct(client, url, kwargs):
        direct_calls.append(url)
        return _resp(BLOCK, status=403)

    monkeypatch.setattr(sh, "_direct_get", fake_direct)
    transport = httpx.MockTransport(lambda request: _resp(NORMAL))

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await sh.async_get_with_vpn_bypass(client, "https://coffeecounty.us/")

    resp = asyncio.run(run())
    assert resp.status_code == 200 and "Official Website" in resp.text
    assert direct_calls == ["https://coffeecounty.us/"]


def test_saving_can_be_turned_off(monkeypatch, tmp_path):
    monkeypatch.setenv("SCRAPE_DIRECT_HOSTS_FILE", "off")
    sh.remember_direct_host("https://coffeecounty.us/")
    assert sh.prefers_direct("https://coffeecounty.us/")
    assert not (tmp_path / "hosts.json").exists()


def test_a_direct_proxy_replaces_interface_binding(monkeypatch):
    monkeypatch.setenv("SCRAPE_DIRECT_PROXY", "http://127.0.0.1:8899")
    calls = {}
    real = httpx.AsyncClient

    def spy(**kw):
        calls.update(kw)
        return real(**{k: v for k, v in kw.items() if k != "transport"})

    monkeypatch.setattr(sh.httpx, "AsyncClient", spy)
    client = sh.make_scrape_async_client(direct_egress=True)
    asyncio.run(client.aclose())
    assert calls.get("proxy") == "http://127.0.0.1:8899" and "transport" not in calls and calls["trust_env"] is False
