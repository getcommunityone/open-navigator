"""Polite HTTP for the meeting-platform readers (#536).

Every request the Granicus and Legistar readers make goes through :class:`PoliteClient`:

- **A descriptive User-Agent** naming the project, with no personal details.
- **robots.txt is honoured.** Each host's robots.txt is read once (RFC 9309: a 4xx
  means no rules, a 5xx or an unreachable host means "assume everything is
  disallowed"). A disallowed URL raises :class:`RobotsDisallowed` before any request.
- **A per-host rate limit:** at least ``min_interval_s`` between requests to the same
  host, or the host's ``Crawl-delay`` when it asks for more.
- **Bot protection is respected, never worked around** (#443). A 403/429 or a
  challenge page raises :class:`Blocked`; nothing retries it with another identity.
- The only retry is the city-site direct-egress one in
  :func:`scrapers.discovery.scrape_http.async_get_with_vpn_bypass` (these are not
  YouTube hosts, so the VPN guard does not apply).

Tests pass their own ``httpx.AsyncClient`` (``httpx.MockTransport``) so nothing
touches the network.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from loguru import logger

from scrapers.discovery.meeting_source_fingerprints import challenge_reason
from scrapers.discovery.scrape_http import async_get_with_vpn_bypass, make_scrape_async_client

# The robots.txt product token is the part before the slash.
ROBOT_NAME = "OpenNavigatorMeetingReader"
USER_AGENT = (
    f"{ROBOT_NAME}/1.0 (+https://github.com/getcommunityone/open-navigator; "
    "public meeting index for civic research)"
)
DEFAULT_MIN_INTERVAL_S = 1.0


class PlatformFetchError(Exception):
    """A request that did not return a usable page."""

    status = "error"


class RobotsDisallowed(PlatformFetchError):
    """The host's robots.txt does not allow this URL for our user agent."""

    status = "robots_disallowed"


class Blocked(PlatformFetchError):
    """The host answered with bot protection (403/429 or a challenge page)."""

    status = "blocked"


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme or 'https'}://{(parts.netloc or '').lower()}"


class PoliteClient:
    """GETs that check robots.txt, keep a per-host pace and report blocks honestly."""

    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        *,
        min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
        timeout_s: float = 30.0,
        user_agent: str = USER_AGENT,
        use_vpn_bypass: bool = True,
    ) -> None:
        self._owns_client = client is None
        self._client = client or make_scrape_async_client(
            timeout=timeout_s, headers={"User-Agent": user_agent}
        )
        if client is not None:
            self._client.headers["User-Agent"] = user_agent
        self.user_agent = user_agent
        self.min_interval_s = min_interval_s
        self.use_vpn_bypass = use_vpn_bypass
        self._robots: dict[str, Optional[RobotFileParser]] = {}
        self._robots_locks: dict[str, asyncio.Lock] = {}
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._last_request: dict[str, float] = {}
        self.requests = 0

    async def __aenter__(self) -> "PoliteClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # ------------------------------------------------------------------ robots

    async def _raw_get(self, url: str) -> httpx.Response:
        """One paced GET (no robots check); the direct-egress retry applies to city hosts."""
        host = (urlsplit(url).hostname or "").lower()
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            wait = self._interval(host) - (time.monotonic() - self._last_request.get(host, 0.0))
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                if self.use_vpn_bypass:
                    return await async_get_with_vpn_bypass(self._client, url)
                return await self._client.get(url)
            finally:
                self._last_request[host] = time.monotonic()
                self.requests += 1

    def _interval(self, host: str) -> float:
        parser = self._robots.get(f"https://{host}") or self._robots.get(f"http://{host}")
        delay = None
        if parser is not None:
            try:
                delay = parser.crawl_delay(ROBOT_NAME)
            except Exception:  # noqa: BLE001 - a malformed Crawl-delay is just ignored
                delay = None
        return max(self.min_interval_s, float(delay or 0))

    async def robots(self, url: str) -> RobotFileParser:
        origin = _origin(url)
        lock = self._robots_locks.setdefault(origin, asyncio.Lock())
        async with lock:
            if origin not in self._robots:
                self._robots[origin] = await self._load_robots(origin)
        parser = self._robots[origin]
        assert parser is not None
        return parser

    async def _load_robots(self, origin: str) -> RobotFileParser:
        parser = RobotFileParser()
        robots_url = f"{origin}/robots.txt"
        parser.set_url(robots_url)
        try:
            resp = await self._raw_get(robots_url)
        except httpx.HTTPError as exc:
            logger.info("robots.txt unreachable at {} ({!r}); treating the host as disallowed", origin, exc)
            parser.disallow_all = True
            return parser
        if resp.status_code >= 500:
            parser.disallow_all = True
        elif resp.status_code >= 400:
            parser.allow_all = True
        else:
            text = resp.text
            # A host that serves an HTML page at /robots.txt has no robots rules.
            if "<html" in text[:500].lower():
                parser.allow_all = True
            else:
                parser.parse(text.splitlines())
        return parser

    async def allowed(self, url: str) -> bool:
        parser = await self.robots(url)
        return parser.can_fetch(ROBOT_NAME, url)

    # ------------------------------------------------------------------ GET

    async def get(self, url: str, *, allow_status: tuple[int, ...] = ()) -> httpx.Response:
        """GET ``url`` after the robots check. Raises on robots, bot protection and errors.

        ``allow_status`` lists non-2xx codes the caller wants back instead of an error
        (Legistar answers an unconfigured client with a 500 and a JSON message).
        """
        if not await self.allowed(url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")
        try:
            resp = await self._raw_get(url)
        except httpx.HTTPError as exc:
            raise PlatformFetchError(f"{url}: {exc!r}") from exc
        if resp.status_code in allow_status:
            return resp
        ctype = resp.headers.get("content-type", "")
        body = resp.text if "html" in ctype else ""
        reason = challenge_reason(body, resp.status_code)
        if reason:
            raise Blocked(f"{url}: {reason}")
        if resp.status_code >= 400:
            raise PlatformFetchError(f"{url}: HTTP {resp.status_code}")
        return resp
