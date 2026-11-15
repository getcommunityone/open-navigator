"""Check that job-application links still work (DC-1.3, #248).

Admins keep the links in ``public.job_application_link`` (see the admin screen).
This module answers two questions about one link:

- ``check_link(url)``: does the page still answer? ``live`` for HTTP 2xx/3xx after
  redirects, ``dead`` for 404/410 (the posting is gone), and ``error`` for anything
  else (403 from a bot filter, 5xx, timeouts, DNS). Only ``dead`` hides a link from
  the public page, so a careers site that blocks bots is never hidden by mistake.
- ``is_stale(last_verified_at, now)``: has it gone unverified for more than 30 days?

A page that still answers 200 but says "this position is closed" reads as ``live``:
the 30-day flag and an admin's "Mark verified" cover that case.

The server makes these requests, so every hop (the URL and each redirect) must
resolve to public addresses: loopback, private, link-local (cloud metadata) and
reserved hosts are refused as ``error`` without a request.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urljoin, urlparse

import httpx

STALE_AFTER_DAYS = 30
TIMEOUT_SECONDS = 10.0
USER_AGENT = "OpenNavigatorLinkCheck/1.0 (+https://www.communityone.com)"

LinkStatus = Literal["live", "dead", "error"]

MAX_REDIRECTS = 5

# HEAD isn't always allowed; these answers mean "try GET instead".
_RETRY_WITH_GET = {403, 405, 501}
_GONE = {404, 410}


@dataclass(frozen=True)
class LinkCheck:
    status: LinkStatus
    http_status: int | None
    checked_at: datetime

    @property
    def verified(self) -> bool:
        """True when this check counts as verifying the link."""
        return self.status == "live"


def is_http_url(url: str | None) -> bool:
    """True for an absolute http(s) URL with a host."""
    if not url:
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def host_is_public(host: str | None) -> bool:
    """True when every address ``host`` resolves to is a public one."""
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0].split("%", 1)[0])
        except ValueError:
            return False
        if not ip.is_global or ip.is_multicast:
            return False
    return bool(infos)


class _Refused(Exception):
    """A hop pointed at a non-public address, or redirects never settled."""


def _fetch_status(client: httpx.Client, method: str, url: str) -> int:
    """Request ``url``, following redirects by hand so every hop is checked."""
    for _ in range(MAX_REDIRECTS + 1):
        if not is_http_url(url) or not host_is_public(urlparse(url).hostname):
            raise _Refused(url)
        resp = client.request(method, url, follow_redirects=False)
        location = resp.headers.get("location")
        if resp.is_redirect and location:
            url = urljoin(url, location)
            continue
        return resp.status_code
    raise _Refused(f"more than {MAX_REDIRECTS} redirects")


def classify(http_status: int | None) -> LinkStatus:
    """Map a final HTTP status to live / dead / error."""
    if http_status is None:
        return "error"
    if 200 <= http_status < 400:
        return "live"
    if http_status in _GONE:
        return "dead"
    return "error"


def is_stale(
    last_verified_at: datetime | None,
    now: datetime | None = None,
    days: int = STALE_AFTER_DAYS,
) -> bool:
    """Never verified, or last verified more than ``days`` ago."""
    if last_verified_at is None:
        return True
    now = now or datetime.now(timezone.utc)
    if last_verified_at.tzinfo is None:
        last_verified_at = last_verified_at.replace(tzinfo=timezone.utc)
    return now - last_verified_at > timedelta(days=days)


def check_link(url: str, client: httpx.Client | None = None) -> LinkCheck:
    """Request ``url`` (HEAD, then GET when HEAD is refused) and classify the answer."""
    now = datetime.now(timezone.utc)
    if not is_http_url(url):
        return LinkCheck(status="error", http_status=None, checked_at=now)

    own_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
    try:
        try:
            code = _fetch_status(client, "HEAD", url)
            if code in _RETRY_WITH_GET:
                code = _fetch_status(client, "GET", url)
        except (httpx.HTTPError, _Refused):
            return LinkCheck(status="error", http_status=None, checked_at=now)
        return LinkCheck(status=classify(code), http_status=code, checked_at=now)
    finally:
        if own_client:
            client.close()
