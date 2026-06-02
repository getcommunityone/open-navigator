#!/usr/bin/env python3
"""CivicSearch meeting-events pipeline: land meetings.jsonl into
bronze.bronze_events_civicsearch.

Reads the JSONL emitted by the FETCH scraper ``scrapers.civicsearch.harvest``
and upserts one row per ``vid_id`` (a YouTube video id). Records are landed
VERBATIM — no derivation here; topic/snippet shaping is done downstream in dbt
(stg_civicsearch__event). Requires migration
095_create_bronze_events_civicsearch.sql to have been applied.

Post-land steps (so fresh meetings reach the event spine WITH geo): apply
migration 103 to promote new vid_ids into bronze.bronze_event_youtube, then run
``python -m scrapers.youtube.enrich_civicsearch_jurisdictions`` to resolve and
write jurisdiction_id/name/state onto those rows (the promotion leaves them NULL).

Usage:
    python -m scrapers.civicsearch.harvest                 (FETCH)
    python -m ingestion.civicsearch.events                 (LAND)
    python -m ingestion.civicsearch.events \\
        --jsonl data/cache/civicsearch/meetings.jsonl --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CACHE_ROOT = Path("data/cache/civicsearch")

# Two landing tables share an identical schema (see migrations 095 / 097):
#   BASE_TABLE    — general municipal CivicSearch meetings
#   SCHOOLS_TABLE — school-district meetings, harvested as a separate run
# The loader targets one or the other; --schools selects SCHOOLS_TABLE.
BASE_TABLE = "bronze.bronze_events_civicsearch"
SCHOOLS_TABLE = "bronze.bronze_events_civicsearch_schools"

# The harvester writes per-portal subdirs so the two datasets never mingle:
#   data/cache/civicsearch/cities/meetings.jsonl   -> BASE_TABLE
#   data/cache/civicsearch/schools/meetings.jsonl  -> SCHOOLS_TABLE
# Derive the default JSONL from the selected table so a plain (cities) load can
# never silently pick up the schools file (or vice versa).
def _default_jsonl(*, schools: bool) -> Path:
    portal = "schools" if schools else "cities"
    return CACHE_ROOT / portal / "meetings.jsonl"


def _parse_date_iso(s: Any) -> date | None:
    if not s or not str(s).strip():
        return None
    try:
        return date.fromisoformat(str(s).strip()[:10])
    except ValueError:
        return None


def _parse_scraped_at(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    s = (raw or "").strip() if isinstance(raw, str) else ""
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class CivicSearchMeetingRow(RawRow):
    """One CivicSearch meeting, validated before upsert into bronze."""

    vid_id: str = Field(min_length=1, max_length=20)
    title: str | None = None
    meeting_date: date | None = None
    location: str | None = None
    location_query_id: str | None = None
    distance: float | None = None
    has_approximate_timings: bool | None = None
    youtube_url: str | None = None
    place_query_id: str | None = None
    place_lat: float | None = None
    place_lon: float | None = None
    matched_keywords: list[Any] = Field(default_factory=list)
    snippets: list[Any] = Field(default_factory=list)
    topic_ids: list[int] = Field(default_factory=list)
    raw_record: dict[str, Any] = Field(default_factory=dict)
    scraped_at: datetime | None = None


def _build_upsert_sql(table: str):
    """Build the per-vid_id upsert for a given (identical-schema) landing table.

    ``table`` is a trusted internal constant (BASE_TABLE / SCHOOLS_TABLE), not
    user input — interpolating it is safe and necessary since a table name can't
    be a bind parameter.
    """
    return text(
        f"""
        INSERT INTO {table} (
            vid_id, title, meeting_date, location, location_query_id, distance,
            has_approximate_timings, youtube_url, place_query_id, place_lat,
            place_lon, matched_keywords, snippets, topic_ids, raw_record, scraped_at
        ) VALUES (
            :vid_id, :title, :meeting_date, :location, :location_query_id, :distance,
            :has_approximate_timings, :youtube_url, :place_query_id, :place_lat,
            :place_lon, CAST(:matched_keywords AS jsonb), CAST(:snippets AS jsonb),
            CAST(:topic_ids AS jsonb), CAST(:raw_record AS jsonb), :scraped_at
        )
        ON CONFLICT (vid_id) DO UPDATE SET
            title = EXCLUDED.title,
            meeting_date = EXCLUDED.meeting_date,
            location = EXCLUDED.location,
            location_query_id = EXCLUDED.location_query_id,
            distance = EXCLUDED.distance,
            has_approximate_timings = EXCLUDED.has_approximate_timings,
            youtube_url = EXCLUDED.youtube_url,
            place_query_id = EXCLUDED.place_query_id,
            place_lat = EXCLUDED.place_lat,
            place_lon = EXCLUDED.place_lon,
            matched_keywords = EXCLUDED.matched_keywords,
            snippets = EXCLUDED.snippets,
            topic_ids = EXCLUDED.topic_ids,
            raw_record = EXCLUDED.raw_record,
            scraped_at = EXCLUDED.scraped_at,
            last_updated = CURRENT_TIMESTAMP
        """
    )


class CivicSearchEventsPipeline(DataSourcePipeline[CivicSearchMeetingRow]):
    source = "civicsearch"
    batch_size = 500
    row_schema = CivicSearchMeetingRow

    def __init__(
        self,
        *,
        jsonl_path: Path | None = None,
        limit: int | None = None,
        table: str = BASE_TABLE,
    ):
        self._jsonl_path = jsonl_path or _default_jsonl(schools=table == SCHOOLS_TABLE)
        self._limit = limit
        self._table = table
        self._upsert_sql = _build_upsert_sql(table)

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._jsonl_path
        if not path.is_file():
            raise FileNotFoundError(f"JSONL not found: {path}")
        emitted = 0
        with path.open(encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                if self._limit is not None and emitted >= self._limit:
                    break
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Line {line_no}: {exc}") from exc
                vid = (obj.get("vid_id") or "").strip()
                if not vid:
                    logger.warning("line {}: missing vid_id, skipping", line_no)
                    continue
                emitted += 1
                topic_ids = [t for t in (obj.get("topic_ids") or []) if isinstance(t, int)]
                yield {
                    "source": self.source,
                    "source_version": f"meetings.jsonl.v{obj.get('schema_version', 1)}",
                    "natural_key": vid,
                    "vid_id": vid,
                    "title": obj.get("title"),
                    "meeting_date": _parse_date_iso(obj.get("meeting_date")),
                    "location": obj.get("location"),
                    "location_query_id": obj.get("location_query_id"),
                    "distance": obj.get("distance"),
                    "has_approximate_timings": obj.get("has_approximate_timings"),
                    "youtube_url": obj.get("youtube_url"),
                    "place_query_id": obj.get("place_query_id"),
                    "place_lat": obj.get("place_lat"),
                    "place_lon": obj.get("place_lon"),
                    "matched_keywords": obj.get("matched_keywords") or [],
                    "snippets": obj.get("snippets") or [],
                    "topic_ids": topic_ids,
                    "raw_record": obj,
                    "scraped_at": _parse_scraped_at(obj.get("scraped_at")),
                }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[CivicSearchMeetingRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "vid_id": r.vid_id,
                "title": r.title,
                "meeting_date": r.meeting_date,
                "location": r.location,
                "location_query_id": r.location_query_id,
                "distance": r.distance,
                "has_approximate_timings": r.has_approximate_timings,
                "youtube_url": r.youtube_url,
                "place_query_id": r.place_query_id,
                "place_lat": r.place_lat,
                "place_lon": r.place_lon,
                "matched_keywords": json.dumps(r.matched_keywords),
                "snippets": json.dumps(r.snippets),
                "topic_ids": json.dumps(r.topic_ids),
                "raw_record": json.dumps(r.raw_record),
                "scraped_at": r.scraped_at,
            }
            for r in rows
        ]
        await session.execute(self._upsert_sql, params)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Land CivicSearch meetings JSONL into bronze.bronze_events_civicsearch"
    )
    parser.add_argument("--jsonl", type=Path, default=None,
                        help="JSONL path (default: derived from the target "
                             "portal — schools/ vs cities/ subdir).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Land at most this many rows (smoke tests).")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--schools", action="store_true",
                        help=f"Land into the school-district table "
                             f"({SCHOOLS_TABLE}) instead of the general "
                             f"{BASE_TABLE}.")
    target.add_argument("--table", type=str, default=None,
                        help="Explicit target table (advanced; overrides "
                             "--schools). Must be an identical-schema "
                             "CivicSearch landing table.")
    return parser


async def _run(args: argparse.Namespace) -> None:
    table = args.table or (SCHOOLS_TABLE if args.schools else BASE_TABLE)
    jsonl = args.jsonl or _default_jsonl(schools=args.schools)
    logger.info("Landing CivicSearch meetings from {} into {}", jsonl, table)
    pipeline = CivicSearchEventsPipeline(
        jsonl_path=jsonl, limit=args.limit, table=table
    )
    await pipeline.run()


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
