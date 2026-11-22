"""scrapers.youtube.vpn_guard: YouTube only through the VPN, never the home IP (#488).

No network: the route table, both public-IP lookups and the clock are replaced.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from loguru import logger

from scrapers.discovery import scrape_http as sh
from scrapers.youtube import vpn_guard as vg

# WSL with Surfshark up: eth2 is the tunnel (0.0.0.0/1 + 128.0.0.0/1), eth3 home.
ROUTES_VPN_UP = """Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT
eth2\t00000000\t00000000\t0001\t0\t0\t5\t00000080\t0\t0\t0
eth2\t00000080\t00000000\t0001\t0\t0\t5\t00000080\t0\t0\t0
eth2\t000E0A00\t00000000\t0001\t0\t0\t261\t0000FFFF\t0\t0\t0
eth3\t00000000\t0156A8C0\t0003\t0\t0\t35\t00000000\t0\t0\t0
"""
# Surfshark disconnected: eth3's default route is all that's left.
ROUTES_VPN_DOWN = """Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT
eth3\t00000000\t0156A8C0\t0003\t0\t0\t35\t00000000\t0\t0\t0
eth3\t0056A8C0\t00000000\t0001\t0\t0\t291\t00FFFFFF\t0\t0\t0
"""

VPN_IP = "185.10.20.30"
HOME_IP = "136.239.40.50"


class _Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class _Net:
    """Fake route table + IP lookups, counting the lookups."""

    def __init__(
        self,
        routes: str = ROUTES_VPN_UP,
        public: str | None = VPN_IP,
        home: str | None = HOME_IP,
    ):
        self.routes = routes
        self.public = public
        self.home = home
        self.public_calls = 0
        self.home_calls: list[str] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> "_Net":
        monkeypatch.setattr(
            vg, "read_routes", lambda path=vg.ROUTE_TABLE: vg.parse_routes(self.routes)
        )
        monkeypatch.setattr(vg, "default_route_public_ip", self._public)
        monkeypatch.setattr(vg, "home_public_ip", self._home)
        return self

    def _public(self, timeout: float = 10.0) -> str | None:
        self.public_calls += 1
        return self.public

    def _home(self, iface: str, timeout: float = 10.0) -> str | None:
        self.home_calls.append(iface)
        return self.home


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("YOUTUBE_REQUIRE_VPN", raising=False)
    clock = _Clock()
    monkeypatch.setattr(vg, "_clock", clock)
    vg.reset_cache()
    yield clock
    vg.reset_cache()


@pytest.fixture
def clock(_reset) -> _Clock:
    return _reset


# --- route parsing -----------------------------------------------------------------


def test_parse_routes_vpn_up_finds_tunnel_and_home():
    routes = vg.parse_routes(ROUTES_VPN_UP)
    assert routes == vg.RouteInfo(tunnel_interface="eth2", home_interface="eth3")
    # Same home interface as scrape_http's direct-egress parser.
    assert routes.home_interface == sh.parse_direct_interface(ROUTES_VPN_UP)


def test_parse_routes_vpn_down_has_no_tunnel():
    routes = vg.parse_routes(ROUTES_VPN_DOWN)
    assert routes.tunnel_interface is None
    assert routes.home_interface == "eth3"
    assert sh.parse_direct_interface(ROUTES_VPN_DOWN) is None


def test_parse_routes_empty_and_garbage():
    assert vg.parse_routes("") == vg.RouteInfo(None, None)
    assert vg.parse_routes("Iface\tDestination\nbad line\n") == vg.RouteInfo(None, None)


def test_parse_routes_picks_lowest_metric_non_tunnel_default():
    table = (
        ROUTES_VPN_UP + "wlan0\t00000000\t0101A8C0\t0003\t0\t0\t10\t00000000\t0\t0\t0\n"
    )
    assert vg.parse_routes(table).home_interface == "wlan0"


def test_read_routes_missing_file_fails_closed(tmp_path):
    assert vg.read_routes(tmp_path / "nope") == vg.RouteInfo(None, None)


# --- IP comparison -----------------------------------------------------------------


def test_vpn_up_passes(monkeypatch):
    net = _Net().install(monkeypatch)
    vg.require_vpn()
    assert net.public_calls == 1 and net.home_calls == ["eth3"]
    status = vg.vpn_status()
    assert status["vpn_up"] is True and status["reason"] == ""
    assert status["tunnel_interface"] == "eth2" and status["home_interface"] == "eth3"
    assert status["public_ip"] == VPN_IP and status["home_ip"] == HOME_IP


def test_vpn_down_raises_without_any_lookup(monkeypatch):
    net = _Net(routes=ROUTES_VPN_DOWN, public=HOME_IP).install(monkeypatch)
    with pytest.raises(
        vg.VpnRequiredError, match="Surfshark is off: connect it, then re-run"
    ):
        vg.require_vpn()
    assert net.public_calls == 0 and net.home_calls == []


def test_tunnel_route_but_same_public_ip_raises(monkeypatch):
    _Net(public=HOME_IP, home=HOME_IP).install(monkeypatch)
    with pytest.raises(vg.VpnRequiredError) as exc:
        vg.require_vpn()
    assert "equals the home IP" in str(exc.value)
    # IPs are masked in the message.
    assert HOME_IP not in str(exc.value) and "136.239.x.x" in str(exc.value)


@pytest.mark.parametrize("public,home", [(None, HOME_IP), (VPN_IP, None), (None, None)])
def test_ip_lookup_failure_fails_closed(monkeypatch, public, home):
    _Net(public=public, home=home).install(monkeypatch)
    with pytest.raises(vg.VpnRequiredError, match="lookup"):
        vg.require_vpn()


def test_vpn_required_error_is_a_runtime_error():
    assert issubclass(vg.VpnRequiredError, RuntimeError)


# --- re-check interval -------------------------------------------------------------


def test_recheck_interval_caches_a_pass(monkeypatch, clock):
    net = _Net().install(monkeypatch)
    vg.require_vpn()
    clock.t += 60
    vg.require_vpn()
    assert net.public_calls == 1  # within 120 s: no new lookup
    clock.t += 61
    vg.require_vpn()
    assert net.public_calls == 2  # past 120 s: looked up again
    vg.require_vpn(recheck_seconds=0)
    assert net.public_calls == 3


def test_tunnel_drop_is_caught_inside_the_interval(monkeypatch, clock):
    net = _Net().install(monkeypatch)
    vg.require_vpn()
    net.routes = ROUTES_VPN_DOWN  # Surfshark disconnects
    clock.t += 5
    with pytest.raises(vg.VpnRequiredError):
        vg.require_vpn()
    net.routes = ROUTES_VPN_UP  # back up: the failure was not cached as a pass
    vg.require_vpn()
    assert net.public_calls == 2


def test_failure_is_never_cached(monkeypatch, clock):
    net = _Net(public=HOME_IP).install(monkeypatch)
    with pytest.raises(vg.VpnRequiredError):
        vg.require_vpn()
    net.public = VPN_IP
    vg.require_vpn()
    assert net.public_calls == 2


# --- opt-out -----------------------------------------------------------------------


@pytest.fixture
def warnings():
    seen: list[str] = []
    sink = logger.add(lambda m: seen.append(m.record["message"]), level="WARNING")
    yield seen
    logger.remove(sink)


@pytest.mark.parametrize("value", ["0", "false", "off", "no"])
def test_opt_out_skips_the_check_and_warns_once(monkeypatch, warnings, value):
    net = _Net(routes=ROUTES_VPN_DOWN).install(monkeypatch)
    monkeypatch.setenv("YOUTUBE_REQUIRE_VPN", value)
    vg.require_vpn()
    vg.require_vpn()
    assert net.public_calls == 0
    opt_out = [w for w in warnings if "YOUTUBE_REQUIRE_VPN=0" in w]
    assert len(opt_out) == 1


def test_default_and_explicit_one_require_the_vpn(monkeypatch):
    _Net(routes=ROUTES_VPN_DOWN).install(monkeypatch)
    for value in (None, "1", "true", ""):
        if value is None:
            monkeypatch.delenv("YOUTUBE_REQUIRE_VPN", raising=False)
        else:
            monkeypatch.setenv("YOUTUBE_REQUIRE_VPN", value)
        with pytest.raises(vg.VpnRequiredError):
            vg.require_vpn()


# --- helpers -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=abc", True),
        ("https://youtube.com/@TuscaloosaCityAL", True),
        ("https://youtu.be/abc", True),
        ("https://i.ytimg.com/vi/abc/hqdefault.jpg", True),
        ("https://rr3---sn-abc.googlevideo.com/videoplayback", True),
        ("https://www.youtube-nocookie.com/embed/abc", True),
        ("https://www.tuscaloosa.com/meetings", False),
        ("https://notyoutube.com/", False),
        ("https://www.googleapis.com/youtube/v3/search", False),
        ("", False),
    ],
)
def test_is_youtube_url(url, expected):
    assert vg.is_youtube_url(url) is expected


def test_mask_ip():
    assert vg.mask_ip("136.239.12.34") == "136.239.x.x"
    assert vg.mask_ip(None) == "unknown"
    assert vg.mask_ip("not-an-ip") == "invalid"
    assert vg.mask_ip("2001:db8::1").startswith("2001:0db8:x")


def test_home_public_ip_works_inside_a_running_loop(monkeypatch):
    async def fake_bound(iface: str, timeout: float) -> str:
        return f"9.9.9.{len(iface)}"

    monkeypatch.setattr(vg, "_bound_public_ip", fake_bound)

    async def inside() -> str | None:
        return vg.home_public_ip("eth3")

    assert asyncio.run(inside()) == "9.9.9.4"


def test_home_public_ip_failure_is_none(monkeypatch):
    async def boom(iface: str, timeout: float) -> str:
        raise OSError("no such device")

    monkeypatch.setenv("VPN_IP_LOOKUP_ATTEMPTS", "1")
    monkeypatch.setattr(vg, "_bound_public_ip", boom)
    assert vg.home_public_ip("eth9") is None


def test_home_public_ip_retries_transient_miss(monkeypatch):
    calls = {"n": 0}

    async def flaky(iface: str, timeout: float) -> str | None:
        calls["n"] += 1
        if calls["n"] < 3:
            return None
        return "1.2.3.4"

    monkeypatch.setenv("VPN_IP_LOOKUP_ATTEMPTS", "3")
    monkeypatch.setenv("VPN_IP_LOOKUP_DELAY_SECONDS", "0")
    monkeypatch.setattr(vg, "_bound_public_ip", flaky)
    monkeypatch.setattr(vg.time, "sleep", lambda _s: None)
    assert vg.home_public_ip("eth3") == "1.2.3.4"
    assert calls["n"] == 3


def test_exit_if_vpn_off_sync_and_async():
    @vg.exit_if_vpn_off
    def sync_main() -> int:
        raise vg.VpnRequiredError("off")

    @vg.exit_if_vpn_off
    async def async_main() -> int:
        raise vg.VpnRequiredError("off")

    with pytest.raises(SystemExit) as exc:
        sync_main()
    assert exc.value.code == vg.VPN_EXIT_CODE == 5
    with pytest.raises(SystemExit) as exc:
        asyncio.run(async_main())
    assert exc.value.code == 5


def test_cli_prints_masked_status_and_exits_5(monkeypatch, capsys):
    _Net(routes=ROUTES_VPN_DOWN, public=HOME_IP, home=HOME_IP).install(monkeypatch)
    assert vg.main([]) == 5
    out = json.loads(capsys.readouterr().out)
    assert out["vpn_up"] is False and out["public_ip"] == "136.239.x.x"


def test_cli_exits_0_when_up(monkeypatch):
    _Net().install(monkeypatch)
    assert vg.main([]) == 0


# --- scrape_http: YouTube never takes the home retry -------------------------------


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_scrape_http_youtube_url_needs_the_vpn(monkeypatch):
    _Net(routes=ROUTES_VPN_DOWN).install(monkeypatch)
    hits: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hits.append(str(request.url))
        return httpx.Response(200)

    async def go() -> None:
        async with _client(handler) as client:
            await sh.async_get_with_vpn_bypass(client, "https://www.youtube.com/@x")

    with pytest.raises(vg.VpnRequiredError):
        asyncio.run(go())
    assert hits == []


def test_scrape_http_youtube_429_is_not_retried_on_home(monkeypatch):
    _Net().install(monkeypatch)

    async def no_direct(*a, **k):
        raise AssertionError("YouTube must not be retried on the home connection")

    monkeypatch.setattr(sh, "_direct_get", no_direct)

    async def go() -> int:
        async with _client(lambda r: httpx.Response(429)) as client:
            resp = await sh.async_get_with_vpn_bypass(
                client, "https://www.youtube.com/@x"
            )
            return resp.status_code

    assert asyncio.run(go()) == 429


def test_scrape_http_city_site_still_retries_on_home(monkeypatch):
    """City websites keep the direct-to-home retry, VPN or not."""
    _Net(routes=ROUTES_VPN_DOWN).install(monkeypatch)
    calls: list[str] = []

    async def direct(client, url, kwargs):
        calls.append(url)
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr(sh, "_direct_get", direct)
    monkeypatch.setenv("SCRAPE_VPN_BYPASS_RETRY", "true")
    sh._DIRECT_FIRST_HOSTS.clear()

    async def go() -> int:
        async with _client(lambda r: httpx.Response(403)) as client:
            resp = await sh.async_get_with_vpn_bypass(
                client, "https://www.tuscaloosa.com/x"
            )
            return resp.status_code

    try:
        assert asyncio.run(go()) == 200
        assert calls == ["https://www.tuscaloosa.com/x"]
    finally:
        sh._DIRECT_FIRST_HOSTS.clear()


def test_wait_until_vpn_up_polls_until_require_vpn_passes(monkeypatch):
    """#700: Discover waits (poll) instead of exiting when Surfshark drops."""
    net = _Net(routes=ROUTES_VPN_DOWN).install(monkeypatch)
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        # Bring the tunnel back after the first wait.
        if len(sleeps) == 1:
            net.routes = ROUTES_VPN_UP

    monkeypatch.setattr(vg.time, "sleep", fake_sleep)
    monkeypatch.setenv("VPN_WAIT_POLL_SECONDS", "7")
    vg.wait_until_vpn_up("discover Henrico, VA")
    assert sleeps == [7.0]
    assert net.public_calls >= 1


def test_async_call_with_vpn_retry_retries_after_wait(monkeypatch):
    _Net(routes=ROUTES_VPN_DOWN).install(monkeypatch)
    attempts = {"n": 0}
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(vg.time, "sleep", fake_sleep)
    monkeypatch.setattr(vg, "vpn_wait_poll_seconds", lambda: 1.0)

    # First require_vpn inside wait fails once more then passes via patched require.
    checks = {"n": 0}

    def fake_require(*, recheck_seconds: float = vg.DEFAULT_RECHECK_SECONDS) -> None:
        checks["n"] += 1
        if checks["n"] == 1:
            raise vg.VpnRequiredError("still down")
        return None

    async def factory() -> str:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise vg.VpnRequiredError("Surfshark is off")
        return "ok"

    monkeypatch.setattr(vg, "require_vpn", fake_require)

    async def go() -> str:
        return await vg.async_call_with_vpn_retry(factory, what="discover test")

    assert asyncio.run(go()) == "ok"
    assert attempts["n"] == 2
    assert sleeps == [1.0]
    assert checks["n"] == 2
