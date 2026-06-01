"""Async client for the CivicSearch public JSON API.

Base URL: ``https://schools.civicsearch.org/api/`` (GET-only, no auth/token).

Endpoints (reverse-engineered from the site bundle — the app only uses GET):

  * ``search``           — the meeting list. Params:
        ``keywords``      free-text query (the real param; the site route uses
                          ``k=`` but the API wants ``keywords=``),
        ``topics``        comma-joined NUMERIC topic ids,
        ``lonlat``        ``"<lon>,<lat>"`` location point,
        ``search_radius`` ``0`` for a named place, else miles (the site uses 30),
        ``start_date`` / ``end_date`` ``YYYY-MM-DD``.
        Returns ``results`` (full match set — no pagination), plus aggregates
        ``meeting_counts`` / ``topic_counts`` / ``related_keywords`` / ``places``.
        IMPORTANT: a location alone returns NO meetings (just nearby ``places``);
        meetings require a ``keywords`` (or ``topics``) axis.
  * ``get_place``        — resolve a place to lon/lat. One of ``display_name`` /
        ``zip_code`` / ``query_id``. Returns ``{display_name, lat, lon, query_id}``.
  * ``get_place_list``   — the COMPLETE place roster for this portal in one call
        (no params). Returns a JSON list of items carrying ``query_id``, ``name``,
        ``state_name``, ``latitude``, ``longitude``, ``num_meetings``,
        ``last_meeting_link`` and ``last_meeting_title``. This is the canonical
        place source for the harvester (replaces the old BFS discovery).
  * ``get_topics_by_city`` — ``query_id`` -> ``{issue_keywords, keywords, ...}``;
        per-place keyword lists, used here to drive the per-place meeting sweep.
"""
from __future__ import annotations

from typing import Any

from core_lib.http import BaseAsyncClient, HttpClientConfig

# CivicSearch runs two separate properties on two API hosts, each backed by a
# DISTINCT dataset (same endpoint shape). "schools" indexes school-district
# boards (locations like "Bellevue School District, Washington"); "cities"
# indexes municipal governments (locations like "Seattle, WA").
PORTAL_BASE_URLS: dict[str, str] = {
    "schools": "https://schools.civicsearch.org/api/",
    "cities": "https://www.civicsearch.org/api/",
}
PORTALS = tuple(PORTAL_BASE_URLS)

# Back-compat default (schools was the first property wired up).
API_BASE_URL = PORTAL_BASE_URLS["schools"]

# Polite identification; CivicSearch is a small public-interest service.
USER_AGENT = (
    "OpenNavigatorCivicSearchResearch/1.0 "
    "(+https://github.com/getcommunityone/open-navigator-for-engagement; "
    "public meeting topic/snippet research)"
)


class CivicSearchClient(BaseAsyncClient):
    """Thin typed wrapper over one CivicSearch property's ``/api/`` surface.

    ``portal`` selects which dataset/host to talk to ("schools" or "cities").
    """

    def __init__(self, *, portal: str = "schools", rate_limit_per_sec: float = 2.0) -> None:
        if portal not in PORTAL_BASE_URLS:
            raise ValueError(f"portal must be one of {PORTALS}, got {portal!r}")
        self.portal = portal
        super().__init__(
            HttpClientConfig(
                base_url=PORTAL_BASE_URLS[portal],
                source=f"civicsearch_{portal}",
                rate_limit_per_sec=rate_limit_per_sec,
                rate_limit_burst=4,
                default_headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
        )

    async def search(
        self,
        *,
        keywords: str | None = None,
        topics: list[int] | None = None,
        lonlat: tuple[float, float] | None = None,
        search_radius: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Run a meeting search. ``lonlat`` is ``(lon, lat)`` to match the API."""
        params: dict[str, Any] = {}
        if keywords:
            params["keywords"] = keywords
        if topics:
            params["topics"] = ",".join(str(t) for t in topics)
        if lonlat is not None:
            lon, lat = lonlat
            params["lonlat"] = f"{lon},{lat}"
        if search_radius is not None:
            params["search_radius"] = str(search_radius)
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        resp = await self.get("search", params=params)
        return resp.json()

    async def get_place(
        self,
        *,
        display_name: str | None = None,
        zip_code: str | None = None,
        query_id: str | None = None,
    ) -> dict[str, Any]:
        """Resolve a place to ``{display_name?, lat, lon, query_id?}``.

        Exactly one selector should be passed. ``get_place`` returns HTTP 400
        for an unrecognized display_name, which surfaces here as an
        ``httpx.HTTPStatusError`` from the base client.
        """
        if display_name is not None:
            params = {"display_name": display_name}
        elif zip_code is not None:
            params = {"zip_code": zip_code}
        elif query_id is not None:
            params = {"query_id": query_id}
        else:
            raise ValueError("get_place requires display_name, zip_code, or query_id")
        resp = await self.get("get_place", params=params)
        return resp.json()

    async def get_place_list(self) -> list[dict[str, Any]]:
        """All places for this portal in one call (no params). Items carry
        query_id, name, state_name, latitude, longitude, num_meetings,
        last_meeting_link, last_meeting_title."""
        resp = await self.get("get_place_list")
        data = resp.json()
        return data if isinstance(data, list) else (data.get("places") or [])

    async def get_topics_by_city(self, query_id: str) -> dict[str, Any]:
        """Per-place keyword lists: ``{issue_keywords: [...], keywords: [...], ...}``."""
        resp = await self.get("get_topics_by_city", params={"query_id": query_id})
        return resp.json()
