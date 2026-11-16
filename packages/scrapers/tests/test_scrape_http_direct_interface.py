"""Direct egress escapes a full-tunnel VPN by binding to the home interface."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from scrapers.discovery import scrape_http as sh

# WSL mirrored networking with Surfshark up: eth2 is the tunnel (0.0.0.0/1),
# eth3 the home connection with the ordinary default route.
ROUTES_WITH_VPN = """Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT
eth2\t00000000\t00000000\t0001\t0\t0\t5\t00000080\t0\t0\t0
eth2\t000E0A00\t00000000\t0001\t0\t0\t261\t0000FFFF\t0\t0\t0
eth3\t00000000\t0156A8C0\t0003\t0\t0\t35\t00000000\t0\t0\t0
"""
ROUTES_NO_VPN = """Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT
eth0\t00000000\t0101A8C0\t0003\t0\t0\t100\t00000000\t0\t0\t0
"""


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    sh.direct_egress_interface.cache_clear()
    sh._DIRECT_FIRST_HOSTS.clear()
    monkeypatch.delenv("SCRAPE_DIRECT_INTERFACE", raising=False)
    yield
    sh.direct_egress_interface.cache_clear()
    sh._DIRECT_FIRST_HOSTS.clear()


def test_detects_home_interface_when_vpn_tunnel_is_up():
    assert sh.parse_direct_interface(ROUTES_WITH_VPN) == "eth3"


def test_no_binding_without_a_tunnel():
    assert sh.parse_direct_interface(ROUTES_NO_VPN) is None
    assert sh.parse_direct_interface("") is None


def test_env_overrides_and_can_disable(monkeypatch, tmp_path):
    table = tmp_path / "route"
    table.write_text(ROUTES_WITH_VPN)
    monkeypatch.setattr(sh, "_ROUTE_TABLE", table)
    assert sh.direct_egress_interface() == "eth3"

    sh.direct_egress_interface.cache_clear()
    monkeypatch.setenv("SCRAPE_DIRECT_INTERFACE", "wlan0")
    assert sh.direct_egress_interface() == "wlan0"

    sh.direct_egress_interface.cache_clear()
    monkeypatch.setenv("SCRAPE_DIRECT_INTERFACE", "off")
    assert sh.direct_egress_interface() is None


def test_direct_client_binds_to_the_interface(monkeypatch):
    monkeypatch.setenv("SCRAPE_DIRECT_INTERFACE", "eth3")
    client = sh.make_scrape_async_client(direct_egress=True)
    backend = client._transport._pool._network_backend
    asyncio.run(client.aclose())
    assert isinstance(backend, sh._InterfaceBoundBackend) and backend._iface == b"eth3"


def test_vpn_client_does_not_bind(monkeypatch):
    monkeypatch.setenv("SCRAPE_DIRECT_INTERFACE", "eth3")
    client = sh.make_scrape_async_client()
    backend = client._transport._pool._network_backend
    asyncio.run(client.aclose())
    assert not isinstance(backend, sh._InterfaceBoundBackend)


def test_host_blocked_on_vpn_is_remembered_and_tried_direct_first(monkeypatch):
    calls: list[str] = []

    def vpn_handler(request: httpx.Request) -> httpx.Response:
        calls.append("vpn")
        return httpx.Response(403)

    async def fake_direct(client, url, kwargs):
        calls.append("direct")
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr(sh, "_direct_get", fake_direct)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(vpn_handler)) as client:
            first = await sh.async_get_with_vpn_bypass(client, "https://city.gov/a")
            second = await sh.async_get_with_vpn_bypass(client, "https://city.gov/b")
            other = await sh.async_get_with_vpn_bypass(client, "https://other.gov/")
            return first, second, other

    first, second, other = asyncio.run(run())
    assert first.status_code == 200 and second.status_code == 200
    # city.gov: VPN refused, direct worked; next request went straight to direct.
    # other.gov: not remembered, so VPN first again.
    assert calls == ["vpn", "direct", "direct", "vpn", "direct"]
    assert sh.prefers_direct("https://CITY.gov/x") and other.status_code == 200
