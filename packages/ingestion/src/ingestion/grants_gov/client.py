"""Grants.gov client for federal grant *opportunities*.

Fetches open / forecasted federal funding opportunities from the Grants.gov
Search2 REST API. These are PROSPECTIVE opportunities to apply for ("what's
available now"), distinct from the historical IRS 990 Schedule I grants in the
``public.grant`` mart ("who got funded"). The two are separate entities and must
not be conflated — this port lands its own ``bronze_grants_gov_opportunity``.

Ported from scripts/datasources/grants_gov/grants_gov_integration.py to the
ingestion workspace package. The original used ``requests`` + ``pandas`` and dumped
parquet files keyed to an oral-health demo; the transport here is reimplemented
against ``httpx`` (matching the data_gov / google_data_commons ports), the public
method surface is trimmed to the generic API (search + paginate + fetch detail),
and the demo/parquet/oral-health matching is dropped — bronze fidelity comes from
the raw JSON, and any matching belongs downstream in dbt.

API base: https://api.grants.gov/v1/api
Docs:     https://www.grants.gov/api/api-guide
Endpoints used:
  - search2          search opportunities (no API key required)
  - fetchOpportunity opportunity detail by id (no API key required)

The Search2 ``oppHits`` shape (the fields this client reads):
    {
      "id": "351234",            # opportunity id (stable PK)
      "number": "HRSA-24-019",   # opportunity / funding-opportunity number
      "title": "Oral Health ...",
      "agencyCode": "HHS-HRSA",
      "agency": "Health Resources and Services Administration",
      "openDate": "10/15/2024",  # MM/DD/YYYY
      "closeDate": "12/31/2024",
      "oppStatus": "posted",     # forecasted | posted | closed | archived
      "docType": "synopsis",
      "cfdaList": ["93.110"]     # Assistance Listing Numbers (formerly CFDA)
    }
"""

from __future__ import annotations

import time
from typing import Any, Iterator

import httpx
from loguru import logger

API_BASE = "https://api.grants.gov/v1/api"
STAGING_BASE = "https://api.staging.grants.gov/v1/api"
DATA_SOURCE = "Grants.gov"

# Default statuses: open opportunities someone could still act on.
DEFAULT_STATUSES = "forecasted|posted"

# Page size for search2. The API caps a single response; 100 is the documented
# safe maximum and what the legacy script used.
PAGE_SIZE = 100


class GrantsGovClient:
    """Client for the Grants.gov Search2 REST API (no API key required)."""

    def __init__(self, use_staging: bool = False, timeout: float = 60.0):
        """Initialize the client.

        Args:
            use_staging: Hit the staging environment instead of production.
            timeout: HTTP timeout in seconds.
        """
        self.base_url = STAGING_BASE if use_staging else API_BASE
        self.timeout = timeout
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "open-navigator/1.0 (civic data platform)",
        }

    def search_opportunities(
        self,
        keyword: str | None = None,
        funding_categories: str | None = None,
        agencies: str | None = None,
        opp_statuses: str = DEFAULT_STATUSES,
        eligibilities: str | None = None,
        aln: str | None = None,
        rows: int = PAGE_SIZE,
        start_record: int = 0,
    ) -> dict[str, Any]:
        """Run a single Search2 query and return the parsed JSON response.

        Args:
            keyword: Free-text keyword (e.g. "oral health", "broadband").
            funding_categories: Pipe-separated category codes (e.g. "HL" Health).
            agencies: Pipe-separated agency codes (e.g. "HHS|HHS-NIH").
            opp_statuses: Pipe-separated statuses (forecasted|posted|closed|archived).
            eligibilities: Pipe-separated eligibility codes.
            aln: Assistance Listing Number (formerly CFDA).
            rows: Results per page (<= PAGE_SIZE).
            start_record: Zero-based pagination offset.

        Returns:
            The full decoded response dict. ``errorcode == 0`` indicates success;
            results live under ``data.oppHits`` with a total in ``data.hitCount``.
        """
        payload: dict[str, Any] = {
            "rows": rows,
            "startRecordNum": start_record,
            "oppStatuses": opp_statuses,
        }
        if keyword:
            payload["keyword"] = keyword
        if funding_categories:
            payload["fundingCategories"] = funding_categories
        if agencies:
            payload["agencies"] = agencies
        if eligibilities:
            payload["eligibilities"] = eligibilities
        if aln:
            payload["aln"] = aln

        url = f"{self.base_url}/search2"
        logger.info("POST {} {}", url, payload)
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            resp = client.post(url, json=payload, headers=self._headers)

        if resp.status_code >= 400:
            preview = resp.text[:400].replace("\n", " ")
            logger.error("HTTP {} from {} — {}", resp.status_code, url, preview)
            resp.raise_for_status()

        data = resp.json()
        if data.get("errorcode") != 0:
            logger.error("Grants.gov API error: {}", data.get("msg"))
            return data

        hit_count = (data.get("data") or {}).get("hitCount", 0)
        logger.info("Found {:,} opportunities", hit_count)
        return data

    def iter_opportunities(
        self,
        keyword: str | None = None,
        funding_categories: str | None = None,
        agencies: str | None = None,
        opp_statuses: str = DEFAULT_STATUSES,
        max_results: int | None = None,
        sleep: float = 0.5,
    ) -> Iterator[dict[str, Any]]:
        """Yield opportunity hits across all Search2 pages.

        Stops at ``max_results`` (if given), when a page returns no hits, or once
        all ``hitCount`` results have been seen. A small ``sleep`` between pages
        keeps within the API's informal rate limits.

        Yields:
            One ``oppHits`` dict per opportunity (the raw Search2 record).
        """
        fetched = 0
        start = 0
        while True:
            rows = PAGE_SIZE
            if max_results is not None:
                remaining = max_results - fetched
                if remaining <= 0:
                    return
                rows = min(PAGE_SIZE, remaining)

            response = self.search_opportunities(
                keyword=keyword,
                funding_categories=funding_categories,
                agencies=agencies,
                opp_statuses=opp_statuses,
                rows=rows,
                start_record=start,
            )
            if response.get("errorcode") != 0:
                return

            data = response.get("data") or {}
            hits = data.get("oppHits") or []
            if not hits:
                return

            for hit in hits:
                yield hit
                fetched += 1
                if max_results is not None and fetched >= max_results:
                    return

            hit_count = data.get("hitCount", 0)
            start += len(hits)
            if start >= hit_count:
                return
            if sleep:
                time.sleep(sleep)

    def fetch_opportunity(self, opportunity_id: str | int) -> dict[str, Any]:
        """Fetch detail for one opportunity via ``fetchOpportunity``.

        Args:
            opportunity_id: The ``id`` from a Search2 ``oppHits`` record.

        Returns:
            The decoded detail response (``data`` holds the synopsis/forecast).
        """
        url = f"{self.base_url}/fetchOpportunity"
        payload = {"opportunityId": int(opportunity_id)}
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            resp = client.post(url, json=payload, headers=self._headers)

        if resp.status_code >= 400:
            preview = resp.text[:400].replace("\n", " ")
            logger.error("HTTP {} from {} — {}", resp.status_code, url, preview)
            resp.raise_for_status()

        data = resp.json()
        if data.get("errorcode") != 0:
            logger.error("Grants.gov API error: {}", data.get("msg"))
        return data
