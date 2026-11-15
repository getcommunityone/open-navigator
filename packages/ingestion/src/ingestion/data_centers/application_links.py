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
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlparse

import httpx

STALE_AFTER_DAYS = 30
TIMEOUT_SECONDS = 10.0
USER_AGENT = "OpenNavigatorLinkCheck/1.0 (+https://www.communityone.com)"

LinkStatus = Literal["live", "dead", "error"]

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
    client = client or httpx.Client(
        follow_redirects=True,
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        try:
            resp = client.head(url)
            code = resp.status_code
            if code in _RETRY_WITH_GET:
                code = client.get(url).status_code
        except httpx.HTTPError:
            return LinkCheck(status="error", http_status=None, checked_at=now)
        return LinkCheck(status=classify(code), http_status=code, checked_at=now)
    finally:
        if own_client:
            client.close()
