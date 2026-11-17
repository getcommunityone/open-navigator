"""Refuse to contact YouTube unless the full-tunnel VPN is up (issue #488).

The owner's home IP must never reach youtube.com, youtu.be, ytimg or googlevideo:
YouTube bans IPs that fetch captions in bulk. Surfshark runs on the Windows host
as a full-tunnel VPN; WSL sees it as an extra interface carrying the split-default
routes ``0.0.0.0/1`` and ``128.0.0.0/1``. When Surfshark disconnects, those routes
go away and traffic silently leaves through the home connection.

:func:`require_vpn` passes only when

1. ``/proc/net/route`` has a ``0.0.0.0/1`` route on a tunnel interface (parsed the
   same way as :func:`scrapers.discovery.scrape_http.parse_direct_interface`), and
2. the public IP seen on the default route differs from the public IP seen from a
   socket bound (``SO_BINDTODEVICE``) to the home interface.

Anything else, including an IP lookup that fails, raises :class:`VpnRequiredError`:
the check fails closed. The route table is read on every call (it's a local file);
the two IP lookups run at most every ``recheck_seconds`` while the check keeps
passing.

Entry points that stop for the VPN exit with :data:`VPN_EXIT_CODE` (5); wrap a CLI
``main`` with :func:`exit_if_vpn_off` to get that.

Environment:
  YOUTUBE_REQUIRE_VPN — ``1`` (default). ``0`` turns the check off and logs a
    warning on every run; YouTube is then reached on whatever route is up.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import ipaddress
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar
from urllib.parse import urlsplit

from loguru import logger

VPN_EXIT_CODE = 5
DEFAULT_RECHECK_SECONDS = 120.0
ROUTE_TABLE = Path("/proc/net/route")
OFF_MESSAGE = "Surfshark is off: connect it, then re-run"

# Hosts that are YouTube for the purpose of this guard (suffix match).
YOUTUBE_HOST_SUFFIXES = (
    "youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "ytimg.com",
    "googlevideo.com",
)

F = TypeVar("F", bound=Callable[..., Any])


class VpnRequiredError(RuntimeError):
    """Raised when YouTube would be contacted without the VPN tunnel."""


@dataclass(frozen=True)
class RouteInfo:
    """Interfaces found in the kernel route table."""

    tunnel_interface: Optional[str]
    home_interface: Optional[str]


def is_youtube_url(url: str) -> bool:
    """True when ``url``'s host is a YouTube host (youtube.com, youtu.be, ytimg, googlevideo)."""
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return any(host == s or host.endswith("." + s) for s in YOUTUBE_HOST_SUFFIXES)


def parse_routes(route_table: str) -> RouteInfo:
    """Tunnel and home interfaces from ``/proc/net/route`` text.

    The tunnel is the interface carrying ``0.0.0.0/1``. The home interface is the
    lowest-metric ``0.0.0.0/0`` default route with a gateway that isn't the tunnel;
    with a tunnel up this equals ``scrape_http.parse_direct_interface``.
    """
    tunnel: Optional[str] = None
    defaults: list[tuple[int, str]] = []
    for line in route_table.splitlines()[1:]:
        cols = line.split()
        if len(cols) < 8:
            continue
        iface, dest, gateway, metric, mask = cols[0], cols[1], cols[2], cols[6], cols[7]
        if dest == "00000000" and mask == "00000080":  # 0.0.0.0/1 (little-endian hex)
            tunnel = tunnel or iface
        elif dest == "00000000" and mask == "00000000" and gateway != "00000000":
            try:
                defaults.append((int(metric), iface))
            except ValueError:
                continue
    home = next((iface for _m, iface in sorted(defaults) if iface != tunnel), None)
    return RouteInfo(tunnel_interface=tunnel, home_interface=home)


def read_routes(path: Path = ROUTE_TABLE) -> RouteInfo:
    """Parse the live route table; no table means no tunnel (fail closed)."""
    try:
        return parse_routes(path.read_text())
    except OSError:
        return RouteInfo(tunnel_interface=None, home_interface=None)


def mask_ip(ip: Optional[str]) -> str:
    """``136.239.12.34`` -> ``136.239.x.x`` (IPv6: first two groups) for logs."""
    if not ip:
        return "unknown"
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return "invalid"
    if addr.version == 4:
        a, b, *_ = ip.split(".")
        return f"{a}.{b}.x.x"
    groups = addr.exploded.split(":")
    return f"{groups[0]}:{groups[1]}:x:x:x:x:x:x"


def default_route_public_ip(timeout: float = 10.0) -> Optional[str]:
    """Public IP over the default route (the VPN when it's up)."""
    from scrapers.youtube.vpn_refresh import public_ip

    ip = public_ip(timeout=timeout)
    return _valid_ip(ip) if ip else None


def _valid_ip(text: str) -> Optional[str]:
    try:
        return str(ipaddress.ip_address(text.strip()))
    except ValueError:
        return None


async def _bound_public_ip(iface: str, timeout: float) -> Optional[str]:
    import httpx

    from scrapers.discovery.scrape_http import interface_bound_transport
    from scrapers.youtube.vpn_refresh import IP_ECHO_URLS

    async with httpx.AsyncClient(
        transport=interface_bound_transport(iface), timeout=timeout, trust_env=False
    ) as client:
        for url in IP_ECHO_URLS:
            try:
                resp = await client.get(url)
            except httpx.HTTPError:
                continue
            if resp.status_code == 200:
                ip = _valid_ip(resp.text)
                if ip:
                    return ip
    return None


def home_public_ip(iface: str, timeout: float = 10.0) -> Optional[str]:
    """Public IP seen from a socket bound to ``iface`` (the home connection).

    Runs scrape_http's interface-bound transport on a private event loop in a worker
    thread, so it works whether or not the caller is inside an event loop.
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            return pool.submit(asyncio.run, _bound_public_ip(iface, timeout)).result()
        except Exception as exc:  # noqa: BLE001 - any failure means "unknown", fail closed
            logger.debug("vpn_guard: home IP lookup on {} failed: {!r}", iface, exc)
            return None


def vpn_status(*, routes: Optional[RouteInfo] = None) -> dict[str, Any]:
    """Tunnel interface, home interface, public IP and home IP, plus a verdict.

    Keys: ``tunnel_interface``, ``home_interface``, ``public_ip``, ``home_ip``,
    ``vpn_up`` (bool) and ``reason`` (why it's down, ``""`` when up). Contains no
    credentials; mask the IPs with :func:`mask_ip` before writing them anywhere shared.
    """
    routes = routes if routes is not None else read_routes()
    public = default_route_public_ip()
    home = home_public_ip(routes.home_interface) if routes.home_interface else None
    if not routes.tunnel_interface:
        reason = "no VPN tunnel route (0.0.0.0/1) in the route table"
    elif not routes.home_interface:
        reason = "no home default route found to compare against"
    elif not public:
        reason = "public IP lookup on the default route failed"
    elif not home:
        reason = f"public IP lookup bound to the home interface {routes.home_interface} failed"
    elif public == home:
        reason = "default-route public IP equals the home IP: traffic is not leaving through the VPN"
    else:
        reason = ""
    return {
        "tunnel_interface": routes.tunnel_interface,
        "home_interface": routes.home_interface,
        "public_ip": public,
        "home_ip": home,
        "vpn_up": not reason,
        "reason": reason,
    }


def vpn_required() -> bool:
    """False only for an explicit ``YOUTUBE_REQUIRE_VPN=0`` (or false/no/off)."""
    v = (os.getenv("YOUTUBE_REQUIRE_VPN") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


_lock = threading.Lock()
_last_pass: Optional[float] = None
_last_routes: Optional[RouteInfo] = None
_opt_out_warned = False
_clock: Callable[[], float] = time.monotonic


def reset_cache() -> None:
    """Forget the last passing check and the opt-out warning (tests, new runs)."""
    global _last_pass, _last_routes, _opt_out_warned
    with _lock:
        _last_pass = None
        _last_routes = None
        _opt_out_warned = False


def _error(status: dict[str, Any]) -> VpnRequiredError:
    return VpnRequiredError(
        f"{OFF_MESSAGE}. YouTube is only reached through the VPN ({status['reason']}; "
        f"tunnel={status['tunnel_interface'] or 'none'}, home={status['home_interface'] or 'none'}, "
        f"public_ip={mask_ip(status['public_ip'])}, home_ip={mask_ip(status['home_ip'])}). "
        "Set YOUTUBE_REQUIRE_VPN=0 only to override on purpose."
    )


def require_vpn(*, recheck_seconds: float = DEFAULT_RECHECK_SECONDS) -> None:
    """Raise :class:`VpnRequiredError` unless YouTube traffic would leave through the VPN.

    Call it at the start of every run that contacts YouTube and before each YouTube
    request in long runs: the route table is checked every call, the public-IP
    comparison at most every ``recheck_seconds`` while it keeps passing.
    """
    global _last_pass, _last_routes, _opt_out_warned
    if not vpn_required():
        with _lock:
            if not _opt_out_warned:
                _opt_out_warned = True
                logger.warning(
                    "YOUTUBE_REQUIRE_VPN=0: the VPN check is OFF; YouTube may be reached "
                    "on the home IP this run"
                )
        return

    routes = read_routes()
    with _lock:
        if not routes.tunnel_interface:
            _last_pass = None
            raise _error(
                {
                    "reason": "no VPN tunnel route (0.0.0.0/1) in the route table",
                    "tunnel_interface": None,
                    "home_interface": routes.home_interface,
                    "public_ip": None,
                    "home_ip": None,
                }
            )
        now = _clock()
        if (
            _last_pass is not None
            and routes == _last_routes
            and now - _last_pass < recheck_seconds
        ):
            return
        status = vpn_status(routes=routes)
        if not status["vpn_up"]:
            _last_pass = None
            raise _error(status)
        if _last_pass is None:
            logger.info(
                "vpn_guard: VPN up via {} (public {} vs home {} on {})",
                status["tunnel_interface"],
                mask_ip(status["public_ip"]),
                mask_ip(status["home_ip"]),
                status["home_interface"],
            )
        _last_pass = _clock()
        _last_routes = routes


def require_vpn_for_url(
    url: str, *, recheck_seconds: float = DEFAULT_RECHECK_SECONDS
) -> None:
    """:func:`require_vpn` when ``url`` is a YouTube URL; no-op for any other host."""
    if is_youtube_url(url):
        require_vpn(recheck_seconds=recheck_seconds)


def exit_if_vpn_off(func: F) -> F:
    """Decorate a CLI ``main``: a :class:`VpnRequiredError` exits with code 5.

    Works for plain and ``async`` functions.
    """
    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def _async(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except VpnRequiredError as exc:
                logger.error("{}", exc)
                raise SystemExit(VPN_EXIT_CODE) from exc

        return _async  # type: ignore[return-value]

    @functools.wraps(func)
    def _sync(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except VpnRequiredError as exc:
            logger.error("{}", exc)
            raise SystemExit(VPN_EXIT_CODE) from exc

    return _sync  # type: ignore[return-value]


def main(argv: Optional[list[str]] = None) -> int:
    """``python -m scrapers.youtube.vpn_guard``: print the masked status; exit 0 or 5.

    Makes no YouTube request: only the route table and two public-IP echo lookups.
    """
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Check that YouTube would go through the VPN."
    )
    parser.parse_args(argv)
    if not vpn_required():
        logger.warning("YOUTUBE_REQUIRE_VPN=0: the VPN check is OFF")
        return 0
    status = vpn_status()
    shown = {
        **status,
        "public_ip": mask_ip(status["public_ip"]),
        "home_ip": mask_ip(status["home_ip"]),
    }
    print(json.dumps(shown))
    if not status["vpn_up"]:
        logger.error("{}", _error(status))
        return VPN_EXIT_CODE
    logger.success("VPN up via {}", status["tunnel_interface"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
