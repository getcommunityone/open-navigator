"""USAspending.gov API client (public domain, no key).

Docs: https://api.usaspending.gov/docs/endpoints . We identify as ``open-navigator``,
keep requests slow, and STOP on 403/429 (AGENTS.md scraping rules).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import httpx
from loguru import logger

API_BASE = "https://api.usaspending.gov/api/v2"
USER_AGENT = "open-navigator"
ASSISTANCE_TYPES = ["02", "03", "04", "05"]  # block, formula, project, cooperative agreement
PAGE_SIZE = 100
MAX_ROWS_PER_WINDOW = 4000  # split a window rather than page very deep
MIN_DELAY_S = 0.4

FIELDS = [
    "Award ID", "Recipient Name", "Recipient UEI", "Award Amount", "Total Outlays",
    "Description", "Start Date", "End Date", "Awarding Agency", "Funding Agency",
    "Assistance Listings", "Primary Place of Performance", "Recipient Location",
    "Award Type", "Last Modified Date",
]


class RateLimited(RuntimeError):
    """Raised on HTTP 403/429: we stop rather than retry harder."""


class UsaSpendingClient:
    def __init__(self, delay_s: float = MIN_DELAY_S) -> None:
        self._http = httpx.Client(
            base_url=API_BASE, timeout=90, headers={"User-Agent": USER_AGENT}
        )
        self._delay = delay_s

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(8):
            time.sleep(self._delay)
            try:
                resp = self._http.post(path, json=body)
            except httpx.TransportError as exc:
                logger.warning("transport error {} (attempt {})", exc, attempt + 1)
                time.sleep(min(3 * 2**attempt, 90))
                continue
            if resp.status_code in (403, 429):
                raise RateLimited(f"HTTP {resp.status_code} from USAspending; stopping")
            if resp.status_code >= 500:
                logger.warning("HTTP {} (attempt {})", resp.status_code, attempt + 1)
                time.sleep(min(3 * 2**attempt, 90))
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"USAspending {path} failed after retries")

    @staticmethod
    def filters(start: date, end: date, recipient_type: str, aln: str | None) -> dict[str, Any]:
        f: dict[str, Any] = {
            "award_type_codes": ASSISTANCE_TYPES,
            "recipient_type_names": [recipient_type],
            "time_period": [
                {"start_date": start.isoformat(), "end_date": end.isoformat(), "date_type": "action_date"}
            ],
        }
        if aln:
            f["program_numbers"] = [aln]
        return f

    def count(self, filters: dict[str, Any]) -> int:
        data = self._post("/search/spending_by_award_count/", {"filters": filters})
        return int(data.get("results", {}).get("grants", 0))

    def iter_window(self, filters: dict[str, Any]) -> Iterator[dict[str, Any]]:
        page = 1
        while True:
            data = self._post(
                "/search/spending_by_award/",
                {
                    "filters": filters, "fields": FIELDS, "page": page, "limit": PAGE_SIZE,
                    "sort": "Award ID", "order": "asc",
                },
            )
            yield from data.get("results", [])
            if not data.get("page_metadata", {}).get("hasNext"):
                return
            page += 1

    def iter_awards(
        self,
        start: date,
        end: date,
        recipient_type: str = "local_government",
        aln: str | None = None,
        max_rows: int = MAX_ROWS_PER_WINDOW,
    ) -> Iterator[dict[str, Any]]:
        """Yield awards in [start, end], splitting windows larger than ``max_rows`` to page."""
        flt = self.filters(start, end, recipient_type, aln)
        n = self.count(flt)
        if n == 0:
            return
        if n > max_rows and (end - start).days >= 1:
            mid = start + (end - start) // 2
            yield from self.iter_awards(start, mid, recipient_type, aln, max_rows)
            yield from self.iter_awards(mid + timedelta(days=1), end, recipient_type, aln, max_rows)
            return
        logger.info("{} to {}: {:,} awards", start, end, n)
        yield from self.iter_window(flt)
