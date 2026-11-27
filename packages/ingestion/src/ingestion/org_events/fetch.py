"""Polite HTTP for organization websites (#1347).

- An honest User-Agent naming open-navigator; no browser disguise, no proxies.
- robots.txt read once per host (RFC 9309: 401/403/5xx or unreachable -> stay out; 404 -> no rules).
- At least ``min_interval`` seconds between requests to one host (or the host's Crawl-delay if longer).
- A 403/429 or a bot-check page marks the host blocked for the rest of the run: nothing retries it.
"""

from __future__ import annotations

import re
import time
import urllib.robotparser
from typing import Callable, Optional
from urllib.parse import urlsplit

import httpx
from loguru import logger

ROBOT_NAME = "open-navigator"
USER_AGENT = (
    "open-navigator/0.1 (nonprofit public events reader; "
    "+https://github.com/getcommunityone/open-navigator)"
)
_CHALLENGE_RE = re.compile(
    r"(cf-browser-verification|challenge-platform|Just a moment\.\.\.|captcha|Attention Required!)", re.I
)


class Blocked(Exception):
    """The host refused us (403/429 or a bot check); stop asking it."""


class Disallowed(Exception):
    """robots.txt does not allow the URL for our user agent."""


class PoliteClient:
    def __init__(
        self,
        *,
        min_interval: float = 2.0,
        timeout: float = 20.0,
        client: Optional[httpx.Client] = None,
        sleep: Callable[[float], None] = time.sleep,
        max_bytes: int = 3_000_000,
    ) -> None:
        self.min_interval = min_interval
        self.client = client or httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        if client is not None:
            self.client.headers["User-Agent"] = USER_AGENT
        self.sleep = sleep
        self.max_bytes = max_bytes
        self._last: dict[str, float] = {}
        self._robots: dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
        self.blocked: set[str] = set()
        self.requests = 0

    def close(self) -> None:
        self.client.close()

    def _wait(self, host: str) -> None:
        gap = self.min_interval
        parser = self._robots.get(host)
        if parser is not None:
            try:
                gap = max(gap, float(parser.crawl_delay(ROBOT_NAME) or 0))
            except Exception:  # noqa: BLE001 - a malformed Crawl-delay is ignored
                pass
        last = self._last.get(host)
        if last is not None:
            delay = gap - (time.monotonic() - last)
            if delay > 0:
                self.sleep(delay)
        self._last[host] = time.monotonic()

    def _raw(self, url: str) -> httpx.Response:
        host = (urlsplit(url).hostname or "").lower()
        self._wait(host)
        self.requests += 1
        return self.client.get(url)

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if host in self.blocked:
            return False
        if host not in self._robots:
            parser: Optional[urllib.robotparser.RobotFileParser] = urllib.robotparser.RobotFileParser()
            try:
                resp = self._raw(f"{parts.scheme}://{parts.netloc}/robots.txt")
                ctype = resp.headers.get("content-type", "")
                if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
                    parser.disallow_all = True  # type: ignore[union-attr]
                elif "html" in ctype and _CHALLENGE_RE.search(resp.text[:5000]):
                    parser.disallow_all = True  # type: ignore[union-attr]
                elif resp.status_code >= 400 or "html" in ctype:
                    parser = None  # no robots.txt: no rules
                else:
                    parser.parse(resp.text.splitlines())  # type: ignore[union-attr]
            except httpx.HTTPError as err:
                logger.info("robots.txt for {} unreadable ({}); not fetching that host", host, type(err).__name__)
                parser = urllib.robotparser.RobotFileParser()
                parser.disallow_all = True
            self._robots[host] = parser
        parser = self._robots[host]
        return True if parser is None else parser.can_fetch(ROBOT_NAME, url)

    def get_text(self, url: str) -> tuple[str, str]:
        """(final URL, body) for a page robots.txt allows. Raises Disallowed, Blocked or httpx errors."""
        if not self.allowed(url):
            raise Disallowed(url)
        host = (urlsplit(url).hostname or "").lower()
        resp = self._raw(url)
        final = str(resp.url)
        if resp.status_code in (403, 429):
            self.blocked.add(host)
            raise Blocked(f"{resp.status_code} from {host}")
        if resp.history and final != url and not self.allowed(final):
            raise Disallowed(final)
        resp.raise_for_status()
        body = resp.text[: self.max_bytes]
        if "html" in resp.headers.get("content-type", "") and _CHALLENGE_RE.search(body[:5000]):
            self.blocked.add(host)
            raise Blocked(f"bot check at {host}")
        return final, body


def get_public_xml(client: httpx.Client, url: str) -> Optional[str]:
    """A public data-lake object (the GivingTuesday 990 XML); None when missing."""
    resp = client.get(url)
    if resp.status_code != 200:
        return None
    return resp.text
