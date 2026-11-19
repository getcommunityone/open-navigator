"""
HTTP helpers for jurisdiction / meeting scrapers.

When ``HTTP_PROXY`` / ``HTTPS_PROXY`` / ``ALL_PROXY`` / ``SCRAPE_HTTPS_PROXY`` route
traffic through a VPN or SOCKS listener, some ``.gov`` sites fail (403, timeouts, TLS).
Set ``SCRAPE_VPN_BYPASS_RETRY=true`` (default) to automatically retry once on **direct
egress** (``trust_env=False``, no proxy) before callers fall back to Playwright.

A full-tunnel VPN (Surfshark, on Windows or in WSL's mirrored networking) is not a
proxy: turning proxies off still leaves through the tunnel. When the route table
has a VPN split-default route (``0.0.0.0/1``), the direct retry binds its socket to
the interface of the ordinary default route instead (the home connection, e.g.
``eth3``), so it really leaves outside the VPN. A host that answered only that way
is remembered for the rest of the process and tried direct first after that.

YouTube hosts (youtube.com, youtu.be, ytimg, googlevideo) are the exception: the
home connection must never reach them (#488). For those URLs
``async_get_with_vpn_bypass`` checks ``scrapers.youtube.vpn_guard.require_vpn`` and
makes one normal request, with no direct-to-home retry. City websites keep the retry.

Environment:
  SCRAPE_VPN_BYPASS_RETRY — ``true`` / ``false`` (default ``true``)
  SCRAPE_HTTPS_PROXY — optional explicit proxy for the *first* attempt only
  DISCOVERY_HTTPS_PROXY — alias for SCRAPE_HTTPS_PROXY
  SCRAPE_DIRECT_INTERFACE — interface for direct egress (default: detected when a
    VPN tunnel is up; ``off`` disables binding)
"""

from __future__ import annotations

import os
import socket
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Union
from urllib.parse import urlsplit

import httpx
from loguru import logger

_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "WIKIDATA_HTTPS_PROXY",
    "SCRAPE_HTTPS_PROXY",
    "DISCOVERY_HTTPS_PROXY",
)


def scrape_vpn_bypass_retry_enabled() -> bool:
    v = (os.getenv("SCRAPE_VPN_BYPASS_RETRY") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def scrape_explicit_proxy_url() -> Optional[str]:
    for key in ("SCRAPE_HTTPS_PROXY", "DISCOVERY_HTTPS_PROXY"):
        v = (os.getenv(key) or "").strip()
        if v:
            return v
    return None


_ROUTE_TABLE = Path("/proc/net/route")
# Hosts that answered only outside the VPN in this process; tried direct first.
_DIRECT_FIRST_HOSTS: set[str] = set()


def parse_direct_interface(route_table: str) -> Optional[str]:
    """The ordinary default route's interface when a VPN split-default route is up.

    A VPN client that captures all traffic usually adds ``0.0.0.0/1`` and
    ``128.0.0.0/1`` routes, which beat the ``0.0.0.0/0`` default without removing
    it. Returns ``None`` when there is no such tunnel (direct already means direct).
    """
    tunnel_ifaces: set[str] = set()
    defaults: list[tuple[int, str]] = []
    for line in route_table.splitlines()[1:]:
        cols = line.split()
        if len(cols) < 8:
            continue
        iface, dest, gateway, metric, mask = cols[0], cols[1], cols[2], cols[6], cols[7]
        if dest == "00000000" and mask == "00000080":  # 0.0.0.0/1 (little-endian hex)
            tunnel_ifaces.add(iface)
        elif dest == "00000000" and mask == "00000000" and gateway != "00000000":
            try:
                defaults.append((int(metric), iface))
            except ValueError:
                continue
    if not tunnel_ifaces:
        return None
    for _metric, iface in sorted(defaults):
        if iface not in tunnel_ifaces:
            return iface
    return None


@lru_cache(maxsize=1)
def direct_egress_interface() -> Optional[str]:
    """Interface the direct retry binds to, or ``None`` to just turn proxies off."""
    configured = (os.getenv("SCRAPE_DIRECT_INTERFACE") or "").strip()
    if configured.lower() in ("off", "none", "0", "false"):
        return None
    if configured:
        return configured
    if not hasattr(socket, "SO_BINDTODEVICE"):
        return None
    try:
        iface = parse_direct_interface(_ROUTE_TABLE.read_text())
    except OSError:
        return None
    if iface:
        logger.info("scrape_direct_interface detected VPN tunnel; direct egress via {}", iface)
    return iface


class _InterfaceBoundBackend:
    """httpcore network backend that binds each socket to ``iface`` *before* connecting.

    httpx's own ``socket_options`` are applied after the connection is made, so the
    connection has already gone through the VPN. This binds first, as
    ``curl --interface`` does.
    """

    def __init__(self, iface: str) -> None:
        import httpcore

        self._iface = iface.encode()
        self._fallback = httpcore.AnyIOBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        import asyncio

        import anyio
        import anyio.abc
        import httpcore
        from httpcore._backends.anyio import AnyIOStream

        loop = asyncio.get_running_loop()
        try:
            with anyio.fail_after(timeout):
                infos = await loop.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_STREAM)
                last: Optional[BaseException] = None
                for family, type_, proto, _canon, addr in infos:
                    sock = socket.socket(family, type_, proto)
                    try:
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, self._iface)
                        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        sock.setblocking(False)
                        await loop.sock_connect(sock, addr)
                    except OSError as exc:
                        sock.close()
                        last = exc
                        continue
                    return AnyIOStream(await anyio.abc.SocketStream.from_socket(sock))
                raise last or OSError(f"no IPv4 address for {host}")
        except TimeoutError as exc:
            raise httpcore.ConnectTimeout(str(exc)) from exc
        except OSError as exc:
            raise httpcore.ConnectError(str(exc)) from exc

    async def connect_unix_socket(self, *args, **kwargs):
        return await self._fallback.connect_unix_socket(*args, **kwargs)

    async def sleep(self, seconds: float) -> None:
        await self._fallback.sleep(seconds)


def interface_bound_transport(iface: str) -> httpx.AsyncHTTPTransport:
    """An httpx transport whose connections leave through ``iface``."""
    transport = httpx.AsyncHTTPTransport()
    # httpx has no public hook for the network backend; the pool's is swapped.
    transport._pool._network_backend = _InterfaceBoundBackend(iface)  # type: ignore[attr-defined]
    return transport


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def remember_direct_host(url: str) -> None:
    host = _host(url)
    if host:
        _DIRECT_FIRST_HOSTS.add(host)


def prefers_direct(url: str) -> bool:
    return _host(url) in _DIRECT_FIRST_HOSTS


def env_proxy_is_configured() -> bool:
    if scrape_explicit_proxy_url():
        return True
    return any((os.getenv(k) or "").strip() for k in _PROXY_ENV_KEYS)


def is_scrape_transport_or_vpn_failure(
    *,
    status_code: Optional[int] = None,
    exc: Optional[BaseException] = None,
) -> bool:
    """True when a one-shot direct-egress retry is worth trying."""
    if status_code is not None:
        if status_code in (407, 502, 503, 504, 403, 429):
            return True
    if exc is None:
        return False
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.RequestError):
        msg = str(exc).lower()
        needles = (
            "proxy",
            "socks",
            "tunnel",
            "connection refused",
            "connection reset",
            "network unreachable",
            "certificate",
            "ssl",
            "eof",
            "aborted",
            "name or service not known",
            "temporary failure",
        )
        return any(n in msg for n in needles)
    return False


def _client_timeout_and_headers(
    client: httpx.AsyncClient,
    kwargs: Mapping[str, Any],
) -> tuple[Any, Optional[Dict[str, str]], bool]:
    timeout = kwargs.get("timeout", client.timeout)
    raw_headers = kwargs.get("headers")
    if raw_headers is not None:
        headers = dict(raw_headers)
    elif client.headers is not None:
        headers = dict(client.headers)
    else:
        headers = None
    follow_redirects = bool(kwargs.get("follow_redirects", client.follow_redirects))
    return timeout, headers, follow_redirects


def _passthrough_get_kwargs(kwargs: Mapping[str, Any]) -> Dict[str, Any]:
    skip = {"timeout", "headers", "follow_redirects"}
    return {k: v for k, v in kwargs.items() if k not in skip}


def make_scrape_async_client(
    *,
    timeout: Union[float, httpx.Timeout] = 20.0,
    headers: Optional[Dict[str, str]] = None,
    follow_redirects: bool = True,
    direct_egress: bool = False,
) -> httpx.AsyncClient:
    """
    Build an ``httpx.AsyncClient`` for scraping.

    ``direct_egress=True`` — ignore proxy env (bypass VPN/local SOCKS).
    Otherwise uses ``SCRAPE_HTTPS_PROXY`` when set, else ``trust_env=True``.
    """
    kw: Dict[str, Any] = {
        "timeout": timeout,
        "follow_redirects": follow_redirects,
    }
    if headers:
        kw["headers"] = headers
    if direct_egress:
        kw["trust_env"] = False
        kw["proxy"] = None
        iface = direct_egress_interface()
        if iface:
            kw["transport"] = interface_bound_transport(iface)
    else:
        explicit = scrape_explicit_proxy_url()
        if explicit:
            kw["proxy"] = explicit
            kw["trust_env"] = False
        else:
            kw["trust_env"] = True
    return httpx.AsyncClient(**kw)


async def _direct_get(
    client: httpx.AsyncClient,
    url: str,
    kwargs: Mapping[str, Any],
) -> httpx.Response:
    timeout, headers, follow_redirects = _client_timeout_and_headers(client, kwargs)
    extra = _passthrough_get_kwargs(kwargs)
    async with make_scrape_async_client(
        timeout=timeout,
        headers=headers,
        follow_redirects=follow_redirects,
        direct_egress=True,
    ) as bypass:
        return await bypass.get(url, **extra)


async def async_get_with_vpn_bypass(
    client: httpx.AsyncClient,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    """
    GET ``url``; on VPN/proxy-ish failure, retry once without proxy env.

    A YouTube URL is never retried on the home connection: it needs the VPN
    (``VpnRequiredError`` otherwise) and gets a single request on the default route.
    """
    from scrapers.youtube.vpn_guard import is_youtube_url, require_vpn

    if is_youtube_url(url):
        require_vpn()
        return await client.get(url, **kwargs)

    if not scrape_vpn_bypass_retry_enabled():
        return await client.get(url, **kwargs)

    if prefers_direct(url):
        try:
            return await _direct_get(client, url, kwargs)
        except Exception as exc:  # noqa: BLE001 - fall back to the normal route
            logger.debug("scrape_direct_first failed url={!r}: {!r}", url, exc)

    try:
        response = await client.get(url, **kwargs)
    except Exception as exc:
        if not is_scrape_transport_or_vpn_failure(exc=exc):
            raise
        logger.info(
            "scrape_vpn_bypass_retry url={url!r} reason=exception detail={detail!r}",
            url=url,
            detail=exc,
        )
        bypass_resp = await _direct_get(client, url, kwargs)
        if bypass_resp.status_code < 400:
            remember_direct_host(url)
        return bypass_resp

    if is_scrape_transport_or_vpn_failure(status_code=response.status_code):
        logger.info(
            "scrape_vpn_bypass_retry url={url!r} reason=http_status status={status}",
            url=url,
            status=response.status_code,
        )
        try:
            bypass_resp = await _direct_get(client, url, kwargs)
        except Exception:
            return response
        if bypass_resp.status_code < response.status_code or (
            bypass_resp.status_code == 200 and response.status_code != 200
        ):
            logger.info(
                "scrape_vpn_bypass_ok url={url!r} before={before} after={after}",
                url=url,
                before=response.status_code,
                after=bypass_resp.status_code,
            )
            if bypass_resp.status_code < 400:
                remember_direct_host(url)
            return bypass_resp
        return response

    return response
