#!/usr/bin/env python3
"""CivicSearch location sweep: discover places, then harvest their meetings.

Why a location sweep needs a query axis
---------------------------------------
A CivicSearch ``search`` scoped to a location *alone* returns NO meetings — only
the nearby ``places`` and aggregate counts. Meetings only come back when a
``keywords`` (or numeric ``topics``) axis is supplied. So this crawler runs in
two phases:

  1. PLACE DISCOVERY (BFS). Seed a set of lon/lat points (US state centroids by
     default), call ``search(lonlat=..., search_radius=30)`` to list the up-to-8
     nearest places, resolve each to a centroid via ``get_place``, and expand
     outward from newly found places until no new ones appear (bounded by
     ``--max-places``).

  2. PER-PLACE MEETING HARVEST. For each discovered place, pull its own keyword
     list from ``get_topics_by_city`` (so the sweep is self-driving — no global
     keyword file) and run one ``search(lonlat=place, search_radius=0,
     keywords=kw)`` per keyword. Meetings are merged by ``vid_id``: matched
     keywords, snippet list, and topic ids are accumulated.

CivicSearch runs two separate properties on two API hosts, each a DISTINCT
dataset: ``schools`` (school-district boards) and ``cities`` (municipal govts).
``--portal`` selects which to crawl; output is kept in separate subdirs so the
two never mingle.

Output (FETCH-only — landing is ingestion.civicsearch.events):
  * ``data/cache/civicsearch/<portal>/places.jsonl``   — one discovered place per line.
  * ``data/cache/civicsearch/<portal>/meetings.jsonl`` — one meeting (vid_id) per line.

Usage (repo root):
    python -m scrapers.civicsearch.harvest --portal schools --max-places 50
    python -m scrapers.civicsearch.harvest --portal cities --max-places 50
    python -m scrapers.civicsearch.harvest --portal both --max-places 50
    python -m scrapers.civicsearch.harvest --portal cities --seed-zip 98101 02139
    python -m scrapers.civicsearch.harvest --portal schools --discover-only
"""
from __future__ import annotations

import argparse
import asyncio
import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from core_lib.logging import setup_logging
from loguru import logger

from .client import PORTALS, CivicSearchClient

REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_CACHE = REPO_ROOT / "data" / "cache" / "civicsearch"

SCHEMA_VERSION = 2  # v2 adds the `portal` field (schools vs cities)
DISCOVERY_RADIUS_MI = 30

# Fallback keyword axis when a place exposes no get_topics_by_city keywords.
DEFAULT_KEYWORDS = (
    "budget", "housing", "public safety", "zoning", "schools", "taxes",
)

# US state + DC centroid seeds (lon, lat) for BFS place discovery. Coarse on
# purpose — discovery snowballs outward from whatever the nearest places are.
STATE_CENTROIDS: dict[str, tuple[float, float]] = {
    "AL": (-86.83, 32.80), "AK": (-152.00, 64.00), "AZ": (-111.66, 34.17),
    "AR": (-92.44, 34.97), "CA": (-119.68, 37.18), "CO": (-105.55, 38.998),
    "CT": (-72.76, 41.52), "DE": (-75.51, 39.00), "DC": (-77.03, 38.90),
    "FL": (-81.69, 28.62), "GA": (-83.64, 32.64), "HI": (-156.37, 20.29),
    "ID": (-114.48, 44.24), "IL": (-89.20, 40.06), "IN": (-86.26, 39.89),
    "IA": (-93.49, 42.01), "KS": (-98.38, 38.53), "KY": (-84.86, 37.65),
    "LA": (-91.96, 31.07), "ME": (-69.25, 45.37), "MD": (-76.80, 39.06),
    "MA": (-71.81, 42.26), "MI": (-84.71, 43.33), "MN": (-94.31, 46.31),
    "MS": (-89.66, 32.74), "MO": (-92.46, 38.36), "MT": (-109.65, 46.92),
    "NE": (-99.81, 41.54), "NV": (-116.66, 39.33), "NH": (-71.58, 43.45),
    "NJ": (-74.52, 40.30), "NM": (-106.25, 34.84), "NY": (-75.50, 42.95),
    "NC": (-79.81, 35.63), "ND": (-100.47, 47.45), "OH": (-82.79, 40.39),
    "OK": (-96.93, 35.57), "OR": (-122.07, 44.57), "PA": (-77.21, 40.59),
    "RI": (-71.51, 41.68), "SC": (-80.95, 33.86), "SD": (-99.44, 44.30),
    "TN": (-86.69, 35.75), "TX": (-97.56, 31.05), "UT": (-111.86, 40.15),
    "VT": (-72.71, 44.05), "VA": (-78.17, 37.77), "WA": (-121.49, 47.40),
    "WV": (-80.95, 38.49), "WI": (-89.62, 44.27), "WY": (-107.30, 42.76),
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _place_keywords(topics_payload: dict[str, Any]) -> list[str]:
    """Merge issue_keywords + keywords from get_topics_by_city, de-duplicated
    case-insensitively while preserving first-seen casing and order."""
    out: list[str] = []
    used: set[str] = set()
    for key in ("issue_keywords", "keywords"):
        for kw in topics_payload.get(key) or []:
            kw = (kw or "").strip()
            if kw and kw.lower() not in used:
                used.add(kw.lower())
                out.append(kw)
    return out


class CivicSearchHarvester:
    """Drives place discovery + per-place meeting harvest over the API."""

    def __init__(
        self,
        client: CivicSearchClient,
        *,
        max_places: int,
        keywords_override: list[str] | None = None,
        max_keywords_per_place: int = 20,
    ) -> None:
        self.client = client
        self.portal = client.portal
        self.max_places = max_places
        self.keywords_override = keywords_override
        self.max_keywords_per_place = max_keywords_per_place
        # query_id -> {query_id, display_name, lat, lon, discovered_from}
        self.places: dict[str, dict[str, Any]] = {}
        # vid_id -> merged meeting record
        self.meetings: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------ phase 1
    async def discover_places(self, seeds: list[tuple[float, float]]) -> None:
        """BFS outward from seed centroids until max_places or frontier empty."""
        frontier: deque[tuple[tuple[float, float], str]] = deque(
            (s, "seed") for s in seeds
        )
        visited_points: set[tuple[float, float]] = set()
        while frontier and len(self.places) < self.max_places:
            point, origin = frontier.popleft()
            key = (round(point[0], 3), round(point[1], 3))
            if key in visited_points:
                continue
            visited_points.add(key)
            try:
                payload = await self.client.search(
                    lonlat=point, search_radius=DISCOVERY_RADIUS_MI
                )
            except httpx.HTTPError as exc:
                logger.warning("discovery search failed at {}: {}", point, exc)
                continue
            for place in payload.get("places") or []:
                qid = place.get("query_id")
                if not qid or qid in self.places:
                    continue
                resolved = await self._resolve_place(qid, origin)
                if resolved is None:
                    continue
                self.places[qid] = resolved
                logger.info(
                    "discovered place [{}/{}] {}",
                    len(self.places), self.max_places, resolved["display_name"],
                )
                frontier.append(((resolved["lon"], resolved["lat"]), qid))
                if len(self.places) >= self.max_places:
                    break

    async def _resolve_place(self, query_id: str, origin: str) -> dict[str, Any] | None:
        try:
            p = await self.client.get_place(query_id=query_id)
        except httpx.HTTPError as exc:
            logger.warning("get_place({}) failed: {}", query_id, exc)
            return None
        if "lat" not in p or "lon" not in p:
            return None
        return {
            "portal": self.portal,
            "query_id": query_id,
            "display_name": p.get("display_name") or query_id,
            "lat": p["lat"],
            "lon": p["lon"],
            "discovered_from": origin,
            "scraped_at": _iso_now(),
        }

    # ------------------------------------------------------------------ phase 2
    async def harvest_meetings(self) -> None:
        for i, place in enumerate(self.places.values(), 1):
            keywords = await self._keywords_for(place)
            logger.info(
                "[{}/{}] {} — {} keyword(s)",
                i, len(self.places), place["display_name"], len(keywords),
            )
            for kw in keywords:
                try:
                    payload = await self.client.search(
                        keywords=kw,
                        lonlat=(place["lon"], place["lat"]),
                        search_radius=0,
                    )
                except httpx.HTTPError as exc:
                    logger.warning("search({!r} @ {}) failed: {}", kw, place["query_id"], exc)
                    continue
                for result in payload.get("results") or []:
                    self._merge_meeting(result, place, kw)

    async def _keywords_for(self, place: dict[str, Any]) -> list[str]:
        if self.keywords_override:
            return self.keywords_override[: self.max_keywords_per_place]
        try:
            payload = await self.client.get_topics_by_city(place["query_id"])
        except httpx.HTTPError as exc:
            logger.warning("get_topics_by_city({}) failed: {}", place["query_id"], exc)
            return list(DEFAULT_KEYWORDS)
        kws = _place_keywords(payload)
        return (kws or list(DEFAULT_KEYWORDS))[: self.max_keywords_per_place]

    def _merge_meeting(
        self, result: dict[str, Any], place: dict[str, Any], keyword: str
    ) -> None:
        vid = result.get("vid_id")
        if not vid:
            return
        rec = self.meetings.get(vid)
        if rec is None:
            rec = {
                "schema_version": SCHEMA_VERSION,
                "portal": self.portal,
                "vid_id": vid,
                "title": result.get("title"),
                "meeting_date": result.get("date"),
                "location": result.get("location"),
                "location_query_id": result.get("location_query_id"),
                "distance": result.get("distance"),
                "has_approximate_timings": result.get("has_approximate_timings"),
                "youtube_url": f"https://www.youtube.com/watch?v={vid}",
                "place_query_id": place["query_id"],
                "place_lat": place["lat"],
                "place_lon": place["lon"],
                "matched_keywords": [],
                "snippets": [],
                "topic_ids": [],
                "scraped_at": _iso_now(),
            }
            self.meetings[vid] = rec
        if keyword not in rec["matched_keywords"]:
            rec["matched_keywords"].append(keyword)
        existing = {(s["timestamp"], s["text"]) for s in rec["snippets"]}
        for snip in result.get("snippets") or []:
            key = (snip.get("timestamp"), snip.get("text"))
            if key in existing:
                continue
            existing.add(key)
            rec["snippets"].append({
                "text": snip.get("text"),
                "timestamp": snip.get("timestamp"),
                "topic_id": snip.get("topic_id"),
            })
            tid = snip.get("topic_id")
            if isinstance(tid, int) and tid >= 0 and tid not in rec["topic_ids"]:
                rec["topic_ids"].append(tid)

    # --------------------------------------------------------------------- io
    def write(self, cache_dir: Path) -> tuple[Path, Path]:
        # One subdir per portal so the two datasets never mingle on disk.
        portal_dir = cache_dir / self.portal
        portal_dir.mkdir(parents=True, exist_ok=True)
        places_path = portal_dir / "places.jsonl"
        meetings_path = portal_dir / "meetings.jsonl"
        with places_path.open("w", encoding="utf-8") as f:
            for place in self.places.values():
                f.write(json.dumps(place, ensure_ascii=False) + "\n")
        with meetings_path.open("w", encoding="utf-8") as f:
            for rec in self.meetings.values():
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        logger.success(
            "wrote {} places -> {} and {} meetings -> {}",
            len(self.places), places_path, len(self.meetings), meetings_path,
        )
        return places_path, meetings_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CivicSearch location sweep (FETCH).")
    parser.add_argument("--portal", choices=[*PORTALS, "both"], default="schools",
                        help="Which CivicSearch property to crawl: schools "
                             "(school districts), cities (municipal govts), or both.")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE,
                        help="Base cache dir; output goes to <cache-dir>/<portal>/.")
    parser.add_argument("--max-places", type=int, default=50,
                        help="Stop discovery after this many distinct places.")
    parser.add_argument("--states", nargs="*", metavar="USPS",
                        help="Seed only these state centroids (default: all 50 + DC).")
    parser.add_argument("--seed-zip", nargs="*", metavar="ZIP", default=[],
                        help="Extra seed points resolved from these ZIP codes.")
    parser.add_argument("--keywords", nargs="*",
                        help="Override per-place keyword discovery with this fixed list.")
    parser.add_argument("--max-keywords-per-place", type=int, default=20)
    parser.add_argument("--discover-only", action="store_true",
                        help="Run place discovery only; skip the meeting harvest.")
    parser.add_argument("--rate-limit", type=float, default=2.0,
                        help="Max requests/sec to the CivicSearch API.")
    return parser


async def _resolve_seed_zips(client: CivicSearchClient, zips: list[str]) -> list[tuple[float, float]]:
    seeds: list[tuple[float, float]] = []
    for z in zips:
        try:
            p = await client.get_place(zip_code=z)
            seeds.append((p["lon"], p["lat"]))
        except (httpx.HTTPError, KeyError) as exc:
            logger.warning("seed zip {} failed: {}", z, exc)
    return seeds


async def _run_portal(portal: str, args: argparse.Namespace) -> None:
    if args.states:
        wanted = {s.upper() for s in args.states}
        centroids = [v for k, v in STATE_CENTROIDS.items() if k in wanted]
    else:
        centroids = list(STATE_CENTROIDS.values())

    logger.info("=== portal: {} ===", portal)
    async with CivicSearchClient(portal=portal, rate_limit_per_sec=args.rate_limit) as client:
        seeds = centroids + await _resolve_seed_zips(client, args.seed_zip)
        harvester = CivicSearchHarvester(
            client,
            max_places=args.max_places,
            keywords_override=args.keywords,
            max_keywords_per_place=args.max_keywords_per_place,
        )
        await harvester.discover_places(seeds)
        if not args.discover_only:
            await harvester.harvest_meetings()
    harvester.write(args.cache_dir)


async def _run(args: argparse.Namespace) -> None:
    portals = list(PORTALS) if args.portal == "both" else [args.portal]
    for portal in portals:
        await _run_portal(portal, args)


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
