#!/usr/bin/env python3
"""CivicSearch location sweep: discover places, then harvest their meetings.

How the meeting sweep maximizes recall
--------------------------------------
A CivicSearch ``search`` scoped to a location *alone* returns NO meetings — even
with a date window. Every result set is gated by a ``keywords`` (or numeric
``topics``) axis. The fix for "capture ALL meetings" is therefore NOT to drop
the keyword axis but to BROADEN it: union several generic civic phrases plus the
place's own topic ids so routine meetings (not just topical ones) are surfaced.
This crawler runs in two phases:

  1. PLACE DISCOVERY (BFS). Seed a set of lon/lat points (US state centroids by
     default), call ``search(lonlat=..., search_radius=30)`` to list the up-to-8
     nearest places, resolve each to a centroid via ``get_place``, and expand
     outward from newly found places until no new ones appear (bounded by
     ``--max-places``).

  2. PER-PLACE MEETING HARVEST. For each discovered place, union three
     location-pinned (``search_radius=0``) axes by ``vid_id``: a fixed set of
     BROAD_RECALL_KEYWORDS ("city council", "regular meeting", "public
     hearing", …) that surface routine meetings, the place's own
     ``get_topics_by_city`` keyword list, and a follow-up ``topics=[id]`` sweep
     over every numeric topic id seen in those responses. Matched keywords,
     snippet lists, and topic ids are accumulated per meeting.

CivicSearch runs two separate properties on two API hosts, each a DISTINCT
dataset: ``schools`` (school-district boards) and ``cities`` (municipal govts).
``--portal`` selects which to crawl; output is kept in separate subdirs so the
two never mingle.

Output (FETCH-only — landing is ingestion.civicsearch.events):
  * ``data/cache/civicsearch/<portal>/places.jsonl``   — one discovered place per line.
  * ``data/cache/civicsearch/<portal>/meetings.jsonl`` — one meeting (vid_id) per line.

Both files are written **incrementally**: each place is appended as discovered,
and its meetings are flushed as soon as that place's keyword sweep finishes — so
the JSONL grows live instead of appearing only at the end. ``--incremental``
resumes from the prior run's files (re-loading known places and skipping
already-seen vid_ids) so a re-run appends only NEW meetings; without it the files
are truncated and re-harvested from scratch.

Usage (repo root):
    python -m scrapers.civicsearch.harvest --portal schools --max-places 50
    python -m scrapers.civicsearch.harvest --portal cities --max-places 50
    python -m scrapers.civicsearch.harvest --portal both --max-places 50
    python -m scrapers.civicsearch.harvest --portal both --incremental   # new only
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

# Cap on per-place self-driving keywords pulled from get_topics_by_city. The
# broad-recall axis already guarantees routine-meeting coverage, so this is just
# bounded extra topical coverage.
MAX_PLACE_KEYWORDS = 20

# Broad civic phrases that, unioned, surface a place's COMPLETE routine-meeting
# set regardless of topic. A bare location returns no meetings (the API gates
# every result set on a keyword/topic axis), but a single broad phrase like
# "city council" already returns all of a small city's meetings; the wider set
# covers places whose meeting titles differ (boards/commissions/work sessions).
BROAD_RECALL_KEYWORDS: tuple[str, ...] = (
    "city council",
    "council meeting",
    "board meeting",
    "regular meeting",
    "special meeting",
    "work session",
    "public hearing",
    "commission meeting",
    "board of",
    "committee meeting",
    "city of",
    "town of",
    "county",
    "meeting",
)


def _extract_topic_ids(payload: dict[str, Any]) -> set[int]:
    """Collect non-negative numeric topic ids from a search response.

    Topic ids appear both in the aggregate ``topic_counts`` and in each
    result's snippet ``topic_id``; we union both so a follow-up ``topics=[id]``
    sweep can pull meetings indexed only under a topic axis.
    """
    ids: set[int] = set()
    tc = payload.get("topic_counts")
    if isinstance(tc, list):
        for entry in tc:
            if isinstance(entry, dict):
                tid = entry.get("topic_id", entry.get("id", entry.get("topic")))
            elif isinstance(entry, (list, tuple)) and entry:
                tid = entry[0]
            else:
                tid = None
            if isinstance(tid, int) and tid >= 0:
                ids.add(tid)
    elif isinstance(tc, dict):
        for key in tc:
            try:
                tid = int(key)
            except (TypeError, ValueError):
                continue
            if tid >= 0:
                ids.add(tid)
    for result in payload.get("results") or []:
        for snip in result.get("snippets") or []:
            tid = snip.get("topic_id")
            if isinstance(tid, int) and tid >= 0:
                ids.add(tid)
    return ids

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


def _safe_json(line: str) -> dict[str, Any] | None:
    """Parse one JSONL line, returning None for blank or truncated records."""
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        logger.warning("skipping unparseable JSONL line during resume")
        return None


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
        cache_dir: Path,
        max_places: int,
        incremental: bool = False,
    ) -> None:
        self.client = client
        self.portal = client.portal
        self.max_places = max_places
        # Incremental mode resumes from the prior run's JSONL: known places are
        # re-loaded (so the sweep still re-harvests them for NEW meetings) and
        # already-seen vid_ids are skipped, so only genuinely new meetings are
        # appended. Non-incremental truncates and re-harvests everything.
        self.incremental = incremental
        # One subdir per portal so the two datasets never mingle on disk.
        self.portal_dir = cache_dir / self.portal
        self.places_path = self.portal_dir / "places.jsonl"
        self.meetings_path = self.portal_dir / "meetings.jsonl"
        # query_id -> {query_id, display_name, lat, lon, discovered_from}
        self.places: dict[str, dict[str, Any]] = {}
        # Cross-run dedupe state + streaming output handles.
        self._seen_place_ids: set[str] = set()
        self._seen_vids: set[str] = set()
        self._new_places = 0   # places discovered THIS run (caps max_places)
        self._new_meetings = 0  # meetings appended THIS run
        self._places_fh: Any = None
        self._meetings_fh: Any = None

    # ----------------------------------------------------------- streaming io
    def open(self) -> None:
        """Open the per-portal JSONL files for streaming append.

        Incremental: load prior places/vid_ids, then append. Otherwise truncate.
        """
        self.portal_dir.mkdir(parents=True, exist_ok=True)
        if self.incremental:
            self._load_existing()
        mode = "a" if self.incremental else "w"
        self._places_fh = self.places_path.open(mode, encoding="utf-8")
        self._meetings_fh = self.meetings_path.open(mode, encoding="utf-8")

    def close(self) -> None:
        for fh in (self._places_fh, self._meetings_fh):
            if fh is not None:
                fh.close()
        logger.success(
            "{}: +{} new place(s), +{} new meeting(s) "
            "({} places / {} meetings total on disk)",
            self.portal, self._new_places, self._new_meetings,
            len(self.places), len(self._seen_vids),
        )

    def _load_existing(self) -> None:
        """Stream prior JSONL into the resume state (places + seen vid_ids).

        Tolerant of a truncated trailing line — a prior run killed mid-write can
        leave one partial JSONL record; we skip it rather than abort the resume.
        """
        if self.places_path.is_file():
            with self.places_path.open(encoding="utf-8") as f:
                for line in f:
                    rec = _safe_json(line)
                    qid = (rec or {}).get("query_id")
                    if qid and qid not in self.places and "lat" in rec and "lon" in rec:
                        self.places[qid] = rec
                        self._seen_place_ids.add(qid)
        if self.meetings_path.is_file():
            with self.meetings_path.open(encoding="utf-8") as f:
                for line in f:
                    vid = (_safe_json(line) or {}).get("vid_id")
                    if vid:
                        self._seen_vids.add(vid)
        if self._seen_place_ids or self._seen_vids:
            logger.info(
                "resume: {} known place(s), {} known meeting(s)",
                len(self._seen_place_ids), len(self._seen_vids),
            )

    def _append_place(self, rec: dict[str, Any]) -> None:
        self._places_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._places_fh.flush()

    def _append_meeting(self, rec: dict[str, Any]) -> None:
        self._meetings_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._meetings_fh.flush()
        self._new_meetings += 1

    # ------------------------------------------------------------------ phase 1
    async def discover_places(self, seeds: list[tuple[float, float]]) -> None:
        """BFS outward from seeds until ``max_places`` NEW places or frontier empty.

        ``max_places`` caps places discovered *this run*; places resumed from a
        prior run (incremental) also seed the frontier so BFS keeps expanding
        around them, but don't count against the cap or get re-written.
        """
        frontier: deque[tuple[tuple[float, float], str]] = deque(
            (s, "seed") for s in seeds
        )
        # Expand around already-known places too (resumed incremental runs).
        for p in self.places.values():
            frontier.append(((p["lon"], p["lat"]), p["query_id"]))
        visited_points: set[tuple[float, float]] = set()
        while frontier and self._new_places < self.max_places:
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
                self._seen_place_ids.add(qid)
                self._append_place(resolved)
                self._new_places += 1
                logger.info(
                    "discovered place [{}/{}] {}",
                    self._new_places, self.max_places, resolved["display_name"],
                )
                frontier.append(((resolved["lon"], resolved["lat"]), qid))
                if self._new_places >= self.max_places:
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
        """Harvest ALL public meetings for every discovered place.

        The CivicSearch ``search`` endpoint returns NO meetings for a bare
        location (with or without a date window) — every result set is gated by
        a ``keywords`` or numeric ``topics`` axis. To recover a place's COMPLETE
        meeting set (routine council/board meetings included, not just topical
        ones) we union three keyword/topic axes per place, all pinned to the
        place via ``search_radius=0`` and merged by ``vid_id``:

          1. ``BROAD_RECALL_KEYWORDS`` — generic civic phrases ("city council",
             "board meeting", "regular meeting", "public hearing", …) that
             collectively surface a place's routine meetings regardless of
             topic. (A single broad keyword like "city council" already returns
             all of Andalusia's 27 meetings; the wider set is belt-and-braces
             for places whose meetings are titled differently.)
          2. ``get_topics_by_city`` keywords — the place's own self-driving
             keyword list (kept from the prior implementation; cheap extra
             coverage of topical meetings).
          3. NUMERIC TOPIC IDS surfaced in each response's ``topic_counts`` /
             snippet ``topic_id`` — re-queried via ``topics=[id]`` to pull in
             any meeting indexed only under a topic axis.

        Each place is isolated: every individual search is wrapped in
        try/except inside :meth:`_search` so a single failing call (including
        retry-exhaustion, which the client raises as an ``httpx.HTTPError``
        subclass) never aborts the place or the run.
        """
        # Snapshot: discovery may keep mutating self.places elsewhere, and a
        # meeting is only final for a place after ALL its axes are merged —
        # so we buffer per-place, then stream the new ones out.
        places = list(self.places.values())
        for i, place in enumerate(places, 1):
            logger.info(
                "[{}/{}] {} — full meeting sweep",
                i, len(places), place["display_name"],
            )
            place_meetings = await self._harvest_place_meetings(place)
            logger.info(
                "  {} unique meeting(s) found for {}",
                len(place_meetings), place["query_id"],
            )
            self._flush_place_meetings(place_meetings)

    async def _harvest_place_meetings(
        self, place: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Union all of a place's meetings across the broad-keyword/topic axes."""
        lonlat = (place["lon"], place["lat"])
        place_meetings: dict[str, dict[str, Any]] = {}
        topic_ids: set[int] = set()

        # Axis 1+2: broad-recall keywords + the place's own keyword list. Both
        # use the same code path; broad keywords are tried first so a place with
        # an empty/failed topic list still gets full routine-meeting recall.
        keywords = list(BROAD_RECALL_KEYWORDS) + await self._place_keyword_list(place)
        seen_kw: set[str] = set()
        for kw in keywords:
            key = kw.lower()
            if key in seen_kw:
                continue
            seen_kw.add(key)
            payload = await self._search(place["query_id"], keywords=kw, lonlat=lonlat)
            self._merge_search_payload(place_meetings, payload, place, topic_ids, kw)

        # Axis 3: re-query any numeric topic ids surfaced above (some meetings
        # are indexed only under a topic axis, not the broad keywords).
        for tid in sorted(topic_ids):
            payload = await self._search(place["query_id"], topics=[tid], lonlat=lonlat)
            self._merge_search_payload(place_meetings, payload, place, topic_ids=None)

        return place_meetings

    async def _place_keyword_list(self, place: dict[str, Any]) -> list[str]:
        """The place's self-driving keyword list from get_topics_by_city (best-effort)."""
        try:
            payload = await self.client.get_topics_by_city(place["query_id"])
        except httpx.HTTPError as exc:
            logger.warning(
                "get_topics_by_city({}) failed: {}", place["query_id"], exc
            )
            return []
        return _place_keywords(payload)[:MAX_PLACE_KEYWORDS]

    async def _search(
        self,
        query_id: str,
        *,
        keywords: str | None = None,
        topics: list[int] | None = None,
        lonlat: tuple[float, float] | None = None,
    ) -> dict[str, Any]:
        """One location-pinned search; ``{}`` on any HTTP error.

        Returns ``{}`` (not raising) on any ``httpx.HTTPError`` — including
        retry-exhaustion, which the client raises as an ``httpx.HTTPError``
        subclass — so one bad call never aborts the place.
        """
        try:
            return await self.client.search(
                keywords=keywords,
                topics=topics,
                lonlat=lonlat,
                search_radius=0,
            )
        except httpx.HTTPError as exc:
            axis = f"kw={keywords!r}" if keywords else f"topics={topics}"
            logger.warning("search({} {}) failed: {}", query_id, axis, exc)
            return {}

    def _merge_search_payload(
        self,
        store: dict[str, dict[str, Any]],
        payload: dict[str, Any],
        place: dict[str, Any],
        topic_ids: set[int] | None,
        keyword: str | None = None,
    ) -> None:
        """Merge a search response's results and harvest its numeric topic ids."""
        for result in payload.get("results") or []:
            self._merge_meeting(store, result, place, keyword)
        if topic_ids is not None:
            topic_ids.update(_extract_topic_ids(payload))

    def _flush_place_meetings(self, place_meetings: dict[str, dict[str, Any]]) -> None:
        """Append meetings for one place, skipping vid_ids already on disk."""
        new = 0
        for vid, rec in place_meetings.items():
            if vid in self._seen_vids:
                continue  # already harvested (this run or a prior incremental run)
            self._seen_vids.add(vid)
            self._append_meeting(rec)
            new += 1
        if new:
            logger.info("  +{} new meeting(s) [{} this run]", new, self._new_meetings)

    def _merge_meeting(
        self,
        store: dict[str, dict[str, Any]],
        result: dict[str, Any],
        place: dict[str, Any],
        keyword: str | None = None,
    ) -> None:
        vid = result.get("vid_id")
        if not vid:
            return
        rec = store.get(vid)
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
            store[vid] = rec
        # Keyword-free location sweeps pass keyword=None; only record a real
        # matched keyword when one was supplied (and not already present).
        if keyword and keyword not in rec["matched_keywords"]:
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
    parser.add_argument("--discover-only", action="store_true",
                        help="Run place discovery only; skip the meeting harvest.")
    parser.add_argument("--incremental", action="store_true",
                        help="Resume from the prior run: re-load known places, "
                             "append only NEW places/meetings (--max-places caps "
                             "newly discovered places). Default truncates & re-harvests.")
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
            cache_dir=args.cache_dir,
            max_places=args.max_places,
            incremental=args.incremental,
        )
        harvester.open()
        try:
            await harvester.discover_places(seeds)
            if not args.discover_only:
                await harvester.harvest_meetings()
        finally:
            harvester.close()


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
