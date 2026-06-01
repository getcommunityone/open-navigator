#!/usr/bin/env python3
"""CivicSearch location sweep: list every place, then harvest its meetings.

How the meeting sweep maximizes recall
--------------------------------------
A CivicSearch ``search`` scoped to a location *alone* returns NO meetings — even
with a date window. Every result set is gated by a ``keywords`` (or numeric
``topics``) axis. The fix for "capture ALL meetings" is therefore NOT to drop
the keyword axis but to BROADEN it: union several generic civic phrases plus the
place's own topic ids so routine meetings (not just topical ones) are surfaced.
This crawler runs in two phases:

  1. PLACE LISTING. A single ``get_place_list`` call returns the COMPLETE place
     roster for the portal (626 cities / 1213 schools), each item carrying its
     ``query_id``, ``name``, lat/lon and a ``num_meetings`` count. No discovery
     crawl is needed — the API hands us every place at once.

  2. PER-PLACE MEETING HARVEST. For each listed place, union three
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
  * ``data/cache/civicsearch/<portal>/places.jsonl``   — one listed place per line.
  * ``data/cache/civicsearch/<portal>/meetings.jsonl`` — one meeting (vid_id) per line.

Both files are written **incrementally**: each place is appended as listed, and
its meetings are flushed as soon as that place's keyword sweep finishes — so the
JSONL grows live instead of appearing only at the end. ``--incremental`` resumes
from the prior run's files (re-loading known places and skipping already-seen
vid_ids), and additionally skips any place whose on-disk captured-meeting count
already meets its ``num_meetings`` (fully done), so a re-run appends only NEW
meetings; without it the files are truncated and re-harvested from scratch.

Usage (repo root):
    python -m scrapers.civicsearch.harvest --portal schools
    python -m scrapers.civicsearch.harvest --portal cities --max-places 3
    python -m scrapers.civicsearch.harvest --portal both --incremental   # new only
"""
from __future__ import annotations

import argparse
import asyncio
import json
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


def _place_from_list_item(item: dict[str, Any], portal: str) -> dict[str, Any] | None:
    """Map a ``get_place_list`` item to the place dict the harvester expects.

    Returns ``None`` for an item missing the essentials (query_id / lat / lon).
    """
    qid = item.get("query_id")
    lat = item.get("latitude")
    lon = item.get("longitude")
    if not qid or lat is None or lon is None:
        return None
    return {
        "portal": portal,
        "query_id": qid,
        "display_name": item.get("name") or qid,
        "lat": lat,
        "lon": lon,
        "num_meetings": item.get("num_meetings"),
        "state_name": item.get("state_name"),
        "scraped_at": _iso_now(),
    }


class CivicSearchHarvester:
    """Drives place listing + per-place meeting harvest over the API."""

    def __init__(
        self,
        client: CivicSearchClient,
        *,
        cache_dir: Path,
        max_places: int | None = None,
        incremental: bool = False,
    ) -> None:
        self.client = client
        self.portal = client.portal
        # Optional cap that simply truncates the listed places (useful for
        # tests / smoke runs). ``None`` = unbounded (the full roster).
        self.max_places = max_places
        # Incremental mode resumes from the prior run's JSONL: known places are
        # re-loaded, already-seen vid_ids are skipped, and a place whose on-disk
        # captured count already meets its num_meetings is skipped entirely, so
        # only genuinely new meetings are appended. Non-incremental truncates
        # and re-harvests everything.
        self.incremental = incremental
        # One subdir per portal so the two datasets never mingle on disk.
        self.portal_dir = cache_dir / self.portal
        self.places_path = self.portal_dir / "places.jsonl"
        self.meetings_path = self.portal_dir / "meetings.jsonl"
        # query_id -> place dict (query_id, display_name, lat, lon, num_meetings, ...)
        self.places: dict[str, dict[str, Any]] = {}
        # Cross-run dedupe state + streaming output handles.
        self._seen_place_ids: set[str] = set()
        self._seen_vids: set[str] = set()
        # query_id -> captured meeting count on disk (for the fully-done skip).
        self._disk_counts: dict[str, int] = {}
        self._new_places = 0   # places written THIS run
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
        Per-place captured counts are tallied from meetings.jsonl so a fully-done
        place (captured >= num_meetings) can be skipped on resume.
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
                    rec = _safe_json(line)
                    if not rec:
                        continue
                    vid = rec.get("vid_id")
                    if vid:
                        self._seen_vids.add(vid)
                    pq = rec.get("place_query_id")
                    if pq:
                        self._disk_counts[pq] = self._disk_counts.get(pq, 0) + 1
        if self._seen_place_ids or self._seen_vids:
            logger.info(
                "resume: {} known place(s), {} known meeting(s)",
                len(self._seen_place_ids), len(self._seen_vids),
            )

    def _append_place(self, rec: dict[str, Any]) -> None:
        self._places_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._places_fh.flush()
        self._new_places += 1

    def _append_meeting(self, rec: dict[str, Any]) -> None:
        self._meetings_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._meetings_fh.flush()
        self._new_meetings += 1

    # ------------------------------------------------------------------ phase 1
    async def list_places(self) -> None:
        """Populate ``self.places`` from the portal's full ``get_place_list``.

        One call returns the COMPLETE roster; each item is mapped to the place
        dict the meeting sweep expects and (if not already known from a resumed
        run) streamed to places.jsonl. ``max_places`` optionally truncates the
        roster for smoke runs/tests.
        """
        items = await self.client.get_place_list()
        if self.max_places is not None:
            items = items[: self.max_places]
        logger.info("{}: get_place_list returned {} place(s)", self.portal, len(items))
        for item in items:
            place = _place_from_list_item(item, self.portal)
            if place is None:
                continue
            qid = place["query_id"]
            if qid in self.places:
                # Resumed from disk: refresh num_meetings/state from the live
                # list so the fully-done check uses the current target.
                self.places[qid].update(
                    num_meetings=place.get("num_meetings"),
                    state_name=place.get("state_name"),
                )
                continue
            self.places[qid] = place
            self._seen_place_ids.add(qid)
            self._append_place(place)

    # ------------------------------------------------------------------ phase 2
    async def harvest_meetings(self) -> None:
        """Harvest ALL public meetings for every listed place.

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
             keyword list (cheap extra coverage of topical meetings).
          3. NUMERIC TOPIC IDS surfaced in each response's ``topic_counts`` /
             snippet ``topic_id`` — re-queried via ``topics=[id]`` to pull in
             any meeting indexed only under a topic axis.

        Each place is isolated: every individual search is wrapped in
        try/except inside :meth:`_search` so a single failing call (including
        retry-exhaustion, which the client raises as an ``httpx.HTTPError``
        subclass) never aborts the place or the run.
        """
        places = list(self.places.values())
        total = len(places)
        for i, place in enumerate(places, 1):
            qid = place["query_id"]
            target = place.get("num_meetings")
            captured = self._disk_counts.get(qid, 0)
            # Incremental fully-done skip: this place's on-disk captured count
            # already meets its advertised num_meetings, so nothing new to fetch.
            if (
                self.incremental
                and isinstance(target, int)
                and target > 0
                and captured >= target
            ):
                logger.info(
                    "[{}/{}] {} — skip (captured {} / num_meetings {})",
                    i, total, place["display_name"], captured, target,
                )
                continue
            try:
                place_meetings = await self._harvest_place_meetings(place)
            except httpx.HTTPError as exc:
                logger.warning(
                    "[{}/{}] {} — sweep aborted: {}",
                    i, total, place["display_name"], exc,
                )
                continue
            self._flush_place_meetings(place_meetings)
            captured = self._disk_counts.get(qid, 0)
            logger.info(
                "[{}/{}] {} — captured {} / num_meetings {}",
                i, total, place["display_name"], captured,
                target if target is not None else "?",
            )

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
            pq = rec.get("place_query_id")
            if pq:
                self._disk_counts[pq] = self._disk_counts.get(pq, 0) + 1
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
    parser.add_argument("--max-places", type=int, default=None,
                        help="Optional cap: truncate the get_place_list roster to "
                             "this many places (default: unbounded / full roster). "
                             "Useful for smoke runs and tests.")
    parser.add_argument("--incremental", action="store_true",
                        help="Resume from the prior run: re-load known places, skip "
                             "fully-harvested places (captured >= num_meetings), and "
                             "append only NEW meetings. Default truncates & re-harvests.")
    parser.add_argument("--rate-limit", type=float, default=2.0,
                        help="Max requests/sec to the CivicSearch API.")
    return parser


async def _run_portal(portal: str, args: argparse.Namespace) -> None:
    logger.info("=== portal: {} ===", portal)
    async with CivicSearchClient(portal=portal, rate_limit_per_sec=args.rate_limit) as client:
        harvester = CivicSearchHarvester(
            client,
            cache_dir=args.cache_dir,
            max_places=args.max_places,
            incremental=args.incremental,
        )
        harvester.open()
        try:
            await harvester.list_places()
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
