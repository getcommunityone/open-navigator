"""
HTTP helpers for jurisdiction / meeting scrapers.

When ``HTTP_PROXY`` / ``HTTPS_PROXY`` / ``ALL_PROXY`` / ``SCRAPE_HTTPS_PROXY`` route
traffic through a VPN or SOCKS listener, some ``.gov`` sites fail (403, timeouts, TLS).
Set ``SCRAPE_VPN_BYPASS_RETRY=true`` (default) to automatically retry once on **direct
egress** (``trust_env=False``, no proxy) before callers fall back to Playwright.

Environment:
  SCRAPE_VPN_BYPASS_RETRY — ``true`` / ``false`` (default ``true``)
  SCRAPE_HTTPS_PROXY — optional explicit proxy for the *first* attempt only
  DISCOVERY_HTTPS_PROXY — alias for SCRAPE_HTTPS_PROXY
"""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping, Optional, Union

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
    """
    if not scrape_vpn_bypass_retry_enabled():
        return await client.get(url, **kwargs)

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
        return await _direct_get(client, url, kwargs)

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
            return bypass_resp
        return response

    return response
