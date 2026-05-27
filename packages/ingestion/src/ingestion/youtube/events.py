#!/usr/bin/env python3
"""YouTube events pipeline: land PRE-COLLECTED video records into bronze.

Decomposed out of scripts/datasources/youtube/load_youtube_events_to_postgres.py
(a ~3,400-line scraper+loader+transform monolith) into the core_lib
DataSourcePipeline contract.

What this module does (LAND only):
  * Reads pre-collected YouTube video records (JSON or JSONL) from
    data/cache/youtube/ — one object per video, in the shape the scraper
    emits (video_id, title, description, published_at, duration_minutes,
    view_count, like_count, language, video_url, channel_id, jurisdiction
    context, and an optional `transcript` block).
  * Lands them RAW into two bronze tables (multi-table routing, like
    ingestion.nccs.bulk / ingestion.localview.events):
      - bronze.bronze_events_youtube       (one row per video)
      - bronze.bronze_events_text_ai       (one row per video that has a
                                            transcript, linked by video_id)

What this module deliberately does NOT do:
  * It does NOT fetch from YouTube. The live acquisition (YouTube Data API,
    yt-dlp catalog + subtitle download, youtube-transcript-api captions) is
    irreducible scraping that stays a scraper at
    scripts/datasources/youtube/load_youtube_events_to_postgres.py
    (the YouTubeEventsLoader class). That code emits the JSON/JSONL this
    pipeline consumes.
  * It does NO derivation. The legacy loader derived event_date from the
    video title (resolve_meeting_event_date), classified channels/jurisdictions,
    and de-duplicated meetings inline. All of that moves DOWNSTREAM to dbt
    (stg_youtube__event etc.) per dbt_project/CONVENTIONS.md. The raw title,
    published_at, and channel metadata land verbatim here.

event_id is a stable SHA-1 based integer derived from the video_id (NOT
Python's built-in hash(), which is non-deterministic across processes). The
real surrogate key in bronze is the BIGSERIAL `id` and the UNIQUE `video_id`;
event_id is kept for backward compatibility with the legacy table shape.

Usage:
    python -m ingestion.youtube.events
    python -m ingestion.youtube.events --truncate
    python -m ingestion.youtube.events --file data/cache/youtube/northport.jsonl --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/youtube")

# event_id is INTEGER in the legacy bronze table; keep generated ids inside
# PostgreSQL's signed 32-bit range.
_EVENT_ID_MODULUS = 2_147_483_647


def find_record_files() -> list[Path]:
    """Pre-collected video-record dumps in the YouTube cache (JSON + JSONL)."""
    files = sorted(CACHE_DIR.glob("*.jsonl")) + sorted(CACHE_DIR.glob("*.json"))
    if not files:
        raise FileNotFoundError(
            f"No pre-collected YouTube records found in {CACHE_DIR}. "
            "Run the scraper "
            "(scripts/datasources/youtube/load_youtube_events_to_postgres.py) "
            "to emit JSON/JSONL first."
        )
    return files


def stable_event_id(video_id: str) -> int:
    """Deterministic 32-bit event_id from a video_id.

    Replaces the legacy ``hash(f"youtube_{video_id}") % 2147483647``, which is
    process-salted (PYTHONHASHSEED) and therefore non-reproducible across runs.
    A SHA-1 digest is stable, so the same video always maps to the same id.
    """
    digest = hashlib.sha1(f"youtube_{video_id}".encode("utf-8")).hexdigest()
    return (int(digest, 16) % (_EVENT_ID_MODULUS - 1)) + 1


def _clean_str(val: Any, maxlen: int | None = None) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def _clean_int(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _clean_dt(val: Any) -> datetime | None:
    """Parse an ISO-ish timestamp; tolerant of trailing 'Z' and date-only."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            return datetime.fromisoformat(s[:10])
        except ValueError:
            return None


def video_to_record(obj: dict, *, source_version: str) -> dict | None:
    """Map one pre-collected video object to a raw landing dict (no derivation).

    Returns None when the object has no video_id (the upsert key). The title,
    published_at, channel metadata, and any transcript land verbatim — date
    parsing / classification / dedup happen downstream in dbt.
    """
    video_id = _clean_str(obj.get("video_id"), 20)
    if not video_id:
        return None

    transcript = obj.get("transcript") or obj.get("youtube") or None
    raw_text = None
    segments = None
    transcript_language = None
    is_auto_generated = None
    transcript_source = None
    if isinstance(transcript, dict):
        raw_text = _clean_str(transcript.get("raw_text"))
        segs = transcript.get("segments")
        segments = segs if isinstance(segs, (list, dict)) else None
        transcript_language = _clean_str(transcript.get("language"), 10)
        is_auto = transcript.get("is_auto_generated")
        is_auto_generated = bool(is_auto) if is_auto is not None else None
        transcript_source = _clean_str(transcript.get("transcript_source"), 50)

    return {
        "source": YoutubeEventsPipeline.source,
        "source_version": source_version,
        "natural_key": video_id,
        # --- bronze.bronze_events_youtube columns (raw, verbatim) ---
        "event_id": stable_event_id(video_id),
        "video_id": video_id,
        "jurisdiction_id": _clean_str(obj.get("jurisdiction_id"), 50),
        "channel_id": _clean_str(obj.get("channel_id"), 50),
        "channel_url": _clean_str(obj.get("channel_url")),
        "title": _clean_str(obj.get("title"), 500),
        "description": _clean_str(obj.get("description")),
        # published_at lands raw; meeting event_date is DERIVED in dbt from title.
        "published_at": _clean_dt(obj.get("published_at")),
        "jurisdiction_name": _clean_str(obj.get("jurisdiction_name"), 500),
        "jurisdiction_type": _clean_str(obj.get("jurisdiction_type"), 100),
        "state_code": _clean_str(obj.get("state_code"), 2),
        "state": _clean_str(obj.get("state"), 100),
        "city": _clean_str(obj.get("city"), 255),
        "location": _clean_str(obj.get("location")),
        "location_description": _clean_str(obj.get("location_description")),
        "meeting_type": _clean_str(obj.get("meeting_type"), 255),
        "video_url": _clean_str(obj.get("video_url"))
        or f"https://www.youtube.com/watch?v={video_id}",
        "view_count": _clean_int(obj.get("view_count")),
        "duration_minutes": _clean_int(obj.get("duration_minutes")),
        "like_count": _clean_int(obj.get("like_count")),
        "language": _clean_str(obj.get("language"), 10) or "en",
        "channel_type": _clean_str(obj.get("channel_type"), 50),
        "datasource": "youtube",
        "datasource_id": video_id,
        # --- transcript block routed to bronze.bronze_events_text_ai ---
        "raw_text": raw_text,
        "segments": segments,
        "transcript_language": transcript_language,
        "is_auto_generated": is_auto_generated,
        "transcript_source": transcript_source,
    }


# ---------------------------------------------------------------------------
# Row schema
# ---------------------------------------------------------------------------


class YoutubeEventRow(RawRow):
    """One pre-collected YouTube video, validated before landing.

    Every bronze column is nullable except video_id, which is the upsert key
    (NOT NULL + UNIQUE). Transcript fields are carried alongside and routed to
    bronze.bronze_events_text_ai in load_batch.
    """

    event_id: int
    video_id: str = Field(min_length=1, max_length=20)
    jurisdiction_id: str | None = Field(default=None, max_length=50)
    channel_id: str | None = Field(default=None, max_length=50)
    channel_url: str | None = None
    title: str | None = Field(default=None, max_length=500)
    description: str | None = None
    published_at: datetime | None = None
    jurisdiction_name: str | None = Field(default=None, max_length=500)
    jurisdiction_type: str | None = Field(default=None, max_length=100)
    state_code: str | None = Field(default=None, max_length=2)
    state: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=255)
    location: str | None = None
    location_description: str | None = None
    meeting_type: str | None = Field(default=None, max_length=255)
    video_url: str | None = None
    view_count: int | None = None
    duration_minutes: int | None = None
    like_count: int | None = None
    language: str | None = Field(default=None, max_length=10)
    channel_type: str | None = Field(default=None, max_length=50)
    datasource: str | None = Field(default=None, max_length=100)
    datasource_id: str | None = Field(default=None, max_length=255)
    # Transcript block (lands in bronze_events_text_ai, not bronze_events_youtube).
    raw_text: str | None = None
    segments: list[Any] | dict[str, Any] | None = None
    transcript_language: str | None = Field(default=None, max_length=10)
    is_auto_generated: bool | None = None
    transcript_source: str | None = Field(default=None, max_length=50)

    @property
    def has_transcript(self) -> bool:
        return bool(self.raw_text and self.raw_text.strip())


# ---------------------------------------------------------------------------
# DDL (preserve the original loader's schema verbatim)
# ---------------------------------------------------------------------------

_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_YOUTUBE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_events_youtube (
        id                   BIGSERIAL PRIMARY KEY,
        event_id             INTEGER,
        video_id             VARCHAR(20) NOT NULL,
        jurisdiction_id      VARCHAR(50),
        channel_id           VARCHAR(50),
        channel_url          TEXT,
        title                VARCHAR(500),
        description          TEXT,
        event_date           DATE,
        event_time           TIME,
        published_at         TIMESTAMP,
        jurisdiction_name    VARCHAR(500),
        jurisdiction_type    VARCHAR(100),
        state_code           VARCHAR(2),
        state                VARCHAR(100),
        city                 VARCHAR(255),
        location             TEXT,
        location_description  TEXT,
        meeting_type         VARCHAR(255),
        video_url            TEXT,
        view_count           INTEGER,
        duration_minutes     INTEGER,
        like_count           INTEGER,
        language             VARCHAR(10),
        channel_type         VARCHAR(50),
        datasource           VARCHAR(100),
        datasource_id        VARCHAR(255),
        loaded_at            TIMESTAMP DEFAULT NOW(),
        last_updated         TIMESTAMP DEFAULT NOW(),
        CONSTRAINT uq_youtube_video_id UNIQUE (video_id)
    )
    """
)

_CREATE_TEXT_AI_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_events_text_ai (
        id                    SERIAL PRIMARY KEY,
        event_id              INTEGER,
        video_id              VARCHAR(20) NOT NULL,
        raw_text              TEXT,
        segments              JSONB,
        language              VARCHAR(10),
        is_auto_generated     BOOLEAN DEFAULT FALSE,
        transcript_source     VARCHAR(50),
        ai_model              VARCHAR(100),
        ai_extraction_version VARCHAR(20),
        has_transcript        BOOLEAN DEFAULT FALSE,
        transcript_quality    VARCHAR(20),
        created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bey_jurisdiction_id ON bronze.bronze_events_youtube(jurisdiction_id)"),
    text("CREATE INDEX IF NOT EXISTS idx_bey_channel_id      ON bronze.bronze_events_youtube(channel_id)"),
    text("CREATE INDEX IF NOT EXISTS idx_bey_state_code      ON bronze.bronze_events_youtube(state_code)"),
    text("CREATE UNIQUE INDEX IF NOT EXISTS idx_betai_video_id_unique ON bronze.bronze_events_text_ai(video_id)"),
    text("CREATE INDEX IF NOT EXISTS idx_betai_event_id      ON bronze.bronze_events_text_ai(event_id)"),
)

_TRUNCATE_YOUTUBE_SQL = text("TRUNCATE TABLE bronze.bronze_events_youtube")
_TRUNCATE_TEXT_AI_SQL = text("TRUNCATE TABLE bronze.bronze_events_text_ai")

_UPSERT_YOUTUBE_SQL = text(
    """
    INSERT INTO bronze.bronze_events_youtube AS y (
        event_id, video_id, jurisdiction_id, channel_id, channel_url,
        title, description, published_at,
        jurisdiction_name, jurisdiction_type, state_code, state, city,
        location, location_description, meeting_type,
        video_url, view_count, duration_minutes, like_count,
        language, channel_type, datasource, datasource_id, last_updated
    ) VALUES (
        :event_id, :video_id, :jurisdiction_id, :channel_id, :channel_url,
        :title, :description, :published_at,
        :jurisdiction_name, :jurisdiction_type, :state_code, :state, :city,
        :location, :location_description, :meeting_type,
        :video_url, :view_count, :duration_minutes, :like_count,
        :language, :channel_type, :datasource, :datasource_id, NOW()
    )
    ON CONFLICT (video_id) DO UPDATE SET
        jurisdiction_id   = COALESCE(EXCLUDED.jurisdiction_id,   y.jurisdiction_id),
        jurisdiction_name = COALESCE(EXCLUDED.jurisdiction_name, y.jurisdiction_name),
        jurisdiction_type = COALESCE(EXCLUDED.jurisdiction_type, y.jurisdiction_type),
        state_code        = COALESCE(EXCLUDED.state_code,        y.state_code),
        state             = COALESCE(EXCLUDED.state,             y.state),
        city              = COALESCE(EXCLUDED.city,              y.city),
        channel_id        = COALESCE(EXCLUDED.channel_id,        y.channel_id),
        channel_url       = COALESCE(EXCLUDED.channel_url,       y.channel_url),
        title             = COALESCE(EXCLUDED.title,             y.title),
        description       = COALESCE(EXCLUDED.description,       y.description),
        published_at      = COALESCE(EXCLUDED.published_at,      y.published_at),
        view_count        = EXCLUDED.view_count,
        like_count        = EXCLUDED.like_count,
        duration_minutes  = COALESCE(EXCLUDED.duration_minutes,  y.duration_minutes),
        language          = COALESCE(EXCLUDED.language,          y.language),
        channel_type      = COALESCE(EXCLUDED.channel_type,      y.channel_type),
        last_updated      = NOW()
    """
)

_UPSERT_TEXT_AI_SQL = text(
    """
    INSERT INTO bronze.bronze_events_text_ai (
        event_id, video_id, raw_text, segments, language,
        is_auto_generated, transcript_source, has_transcript, transcript_quality
    ) VALUES (
        :event_id, :video_id, :raw_text, CAST(:segments AS jsonb), :language,
        :is_auto_generated, :transcript_source, :has_transcript, :transcript_quality
    )
    ON CONFLICT (video_id) DO UPDATE SET
        raw_text           = EXCLUDED.raw_text,
        segments           = EXCLUDED.segments,
        language           = EXCLUDED.language,
        is_auto_generated  = EXCLUDED.is_auto_generated,
        transcript_source  = EXCLUDED.transcript_source,
        has_transcript     = EXCLUDED.has_transcript,
        transcript_quality = EXCLUDED.transcript_quality,
        last_updated       = CURRENT_TIMESTAMP
    """
)


class YoutubeEventsPipeline(DataSourcePipeline[YoutubeEventRow]):
    source = "youtube_events"
    batch_size = 500
    row_schema = YoutubeEventRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    def _discover_files(self) -> list[Path]:
        if self._path is not None:
            return [self._path]
        return find_record_files()

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        emitted = 0
        for path in self._discover_files():
            source_version = path.stem
            for obj in _read_objects(path):
                if self._limit is not None and emitted >= self._limit:
                    return
                if not isinstance(obj, dict):
                    continue
                record = video_to_record(obj, source_version=source_version)
                if record is None:
                    # No video_id — let validate() reject visibly via metrics.
                    continue
                yield record
                emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[YoutubeEventRow],
        ctx: PipelineContext,
    ) -> None:
        # Route 1: every video lands in bronze.bronze_events_youtube.
        youtube_params = [
            {
                "event_id": r.event_id,
                "video_id": r.video_id,
                "jurisdiction_id": r.jurisdiction_id,
                "channel_id": r.channel_id,
                "channel_url": r.channel_url,
                "title": r.title,
                "description": r.description,
                "published_at": r.published_at,
                "jurisdiction_name": r.jurisdiction_name,
                "jurisdiction_type": r.jurisdiction_type,
                "state_code": r.state_code,
                "state": r.state,
                "city": r.city,
                "location": r.location,
                "location_description": r.location_description,
                "meeting_type": r.meeting_type,
                "video_url": r.video_url,
                "view_count": r.view_count,
                "duration_minutes": r.duration_minutes,
                "like_count": r.like_count,
                "language": r.language,
                "channel_type": r.channel_type,
                "datasource": r.datasource,
                "datasource_id": r.datasource_id,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_YOUTUBE_SQL, youtube_params)

        # Route 2: videos that carry a transcript also land in
        # bronze.bronze_events_text_ai. transcript_quality is the only
        # light flag (high vs auto-generated medium) — no NLP/derivation.
        transcript_params = [
            {
                "event_id": r.event_id,
                "video_id": r.video_id,
                "raw_text": r.raw_text,
                "segments": json.dumps(r.segments) if r.segments is not None else None,
                "language": r.transcript_language or r.language,
                "is_auto_generated": r.is_auto_generated,
                "transcript_source": r.transcript_source,
                "has_transcript": True,
                "transcript_quality": "medium" if r.is_auto_generated else "high",
            }
            for r in rows
            if r.has_transcript
        ]
        if transcript_params:
            await session.execute(_UPSERT_TEXT_AI_SQL, transcript_params)


def _read_objects(path: Path) -> list[dict]:
    """Read a JSONL file (one object per line) or a JSON file.

    A JSON file may be a top-level list, or an object with a ``videos`` /
    ``records`` list. Anything else is treated as a single record.
    """
    text_body = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        out: list[dict] = []
        for line in text_body.splitlines():
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
        return out
    data = json.loads(text_body)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("videos", "records", "items"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    return []


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_YOUTUBE_TABLE_SQL)
        await session.execute(_CREATE_TEXT_AI_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_TEXT_AI_SQL)
            await session.execute(_TRUNCATE_YOUTUBE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Land pre-collected YouTube video records (JSON/JSONL) into "
            "bronze.bronze_events_youtube + bronze.bronze_events_text_ai"
        )
    )
    parser.add_argument(
        "--file", type=Path,
        help="Path to a JSON/JSONL record dump (default: all in data/cache/youtube/)",
    )
    parser.add_argument("--limit", type=int, help="Load only the first N records")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE both bronze tables before loading (full reload)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = YoutubeEventsPipeline(path=args.file, limit=args.limit)
    await pipeline.run()


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
