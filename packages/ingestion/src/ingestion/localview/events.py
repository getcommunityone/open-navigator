#!/usr/bin/env python3
"""LocalView meeting-events pipeline: load cached parquet into
bronze.bronze_events_localview.

Ported from load_localview_to_postgres.py to the core_lib DataSourcePipeline
contract.

This reads LocalView meeting parquet files and upserts meeting (video) rows
into bronze.bronze_events_localview following the medallion architecture.
Uniqueness is enforced on datasource_id (the YouTube video ID); event_id is a
BIGSERIAL surrogate key — never hash-derived, which was non-deterministic.

The source parquet also carries a video→channel mapping, which is upserted into
intermediate.int_localview_youtube_video_channels for lineage.

Usage:
    python -m scripts.datasources.localview.events
    python scripts/datasources/localview/events.py --truncate
    python scripts/datasources/localview/events.py --truncate --year 2023
    python scripts/datasources/localview/events.py \\
        --file data/cache/localview/meetings.2023.parquet --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433).
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

import pandas as pd
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/localview")


# ---------------------------------------------------------------------------
# Pure helpers (preserved verbatim from the original loader)
# ---------------------------------------------------------------------------

JURISDICTION_TYPE_MAP = {
    # Municipal
    'MUNICIPAL COUNCIL':              'city',
    'BOARD OF ALDERMEN':              'city',
    'CITY COMMISSION':                'city',
    'BOARD OF TRUSTEES':              'city',
    'BOARD OF HEALTH':                'city',
    'PARKS/REC BOARD/COMMISSION':     'city',
    'PLANNING/ZONING BOARD/COMMISSION': 'city',
    'COMMITTEE':                      'city',
    'SPECIAL COMMISSION':             'city',
    'DEVELOPMENT CORPORATION':        'city',
    'HOUSING AUTHORITY':              'city',
    'OTHER BOARD':                    'city',
    # Town / Township
    'BOARD OF SELECTMEN':             'town',
    'TOWN BOARD':                     'town',
    'VILLAGE BOARD':                  'village',
    # County
    'COUNTY COMMISSION':              'county',
    'COUNTY BOARD':                   'county',
    'COUNTY COUNCIL':                 'county',
    'BOARD OF COMMISSIONERS':         'county',
    'BOARD OF SUPERVISORS':           'county',
    # School district
    'SCHOOL BOARD':                   'school_district',
    'BOARD OF EDUCATION':             'school_district',
}


def infer_jurisdiction_type(place_govt: Any) -> str:
    if pd.isna(place_govt) or not place_govt:
        return 'unknown'
    return JURISDICTION_TYPE_MAP.get(str(place_govt).strip().upper(), 'city')


STATE_ABBREV = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
    'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA',
    'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
    'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO',
    'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
    'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
    'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
    'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
}


def get_state_abbrev(state_name: str) -> Optional[str]:
    if pd.isna(state_name):
        return None
    return STATE_ABBREV.get(state_name, state_name[:2].upper())


def row_to_event(row: pd.Series) -> Dict[str, Any]:
    event_date = None
    if pd.notna(row.get('meeting_date')):
        try:
            event_date = pd.to_datetime(row['meeting_date']).date()
        except Exception:
            pass

    vid_id = row.get('vid_id')
    video_url = f"https://www.youtube.com/watch?v={vid_id}" if pd.notna(vid_id) else None

    state_name = row.get('state_name')
    state_code = get_state_abbrev(state_name)

    place_name = row.get('place_name')
    title = row.get('vid_title')
    if pd.isna(title) or not title:
        date_str = event_date.strftime('%B %d, %Y') if event_date else ''
        title = f"{place_name} Meeting - {date_str}" if date_str else f"{place_name} Meeting"

    return {
        'event_date':        event_date,
        'jurisdiction_name': place_name,
        'jurisdiction_type': infer_jurisdiction_type(row.get('place_govt')),
        'city':              place_name,
        'city_name':         place_name,
        'state_code':        state_code,
        'state':             state_name,
        'meeting_type':      row.get('place_govt', 'City Council'),
        'title':             (title or '')[:500],
        'video_url':         video_url,
        'datasource':        'localview',
        'datasource_id':     vid_id,
        'loaded_at':         datetime.now(),
        'st_fips':           row.get('st_fips'),
        'place_govt':        row.get('place_govt'),
        'channel_title':     row.get('channel_title'),
        'vid_title':         row.get('vid_title'),
        'vid_desc':          row.get('vid_desc'),
        'vid_length_min':    row.get('vid_length_min'),
        'vid_upload_date':   pd.to_datetime(row.get('vid_upload_date'), errors='coerce') if row.get('vid_upload_date') is not None else None,
        'vid_livestreamed':  bool(row.get('vid_livestreamed')) if pd.notna(row.get('vid_livestreamed')) else None,
        'vid_views':         row.get('vid_views'),
        'vid_likes':         row.get('vid_likes'),
        'vid_dislikes':      row.get('vid_dislikes'),
        'vid_comments':      row.get('vid_comments'),
        'vid_favorites':     row.get('vid_favorites'),
        'meeting_date_raw':  str(row.get('meeting_date')) if pd.notna(row.get('meeting_date')) else None,
        'caption_text':      row.get('caption_text'),
        'caption_text_clean': row.get('caption_text_clean'),
        'channel_type':      row.get('channel_type'),
        'acs_18_amind':      row.get('acs_18_amind'),
        'acs_18_asian':      row.get('acs_18_asian'),
        'acs_18_black':      row.get('acs_18_black'),
        'acs_18_hispanic':   row.get('acs_18_hispanic'),
        'acs_18_median_age': row.get('acs_18_median_age'),
        'acs_18_median_gross_rent': row.get('acs_18_median_gross_rent'),
        'acs_18_median_hh_inc':     row.get('acs_18_median_hh_inc'),
        'acs_18_nhapi':      row.get('acs_18_nhapi'),
        'acs_18_pop':        row.get('acs_18_pop'),
        'acs_18_white':      row.get('acs_18_white'),
    }


def _row_to_channel_mapping(row: pd.Series) -> Optional[Dict[str, Any]]:
    """Build the video→channel mapping for one row, or None if not mappable.

    Mirrors upsert_video_channel_mappings: require non-empty vid_id + channel_id,
    trim both, cap channel_title to 500 chars.
    """
    vid_id = row.get("vid_id")
    channel_id = row.get("channel_id")
    if pd.isna(vid_id) or pd.isna(channel_id):
        return None
    vid_id = str(vid_id).strip()
    channel_id = str(channel_id).strip()
    if not vid_id or not channel_id:
        return None
    channel_title = row.get("channel_title")
    channel_title = str(channel_title)[:500] if pd.notna(channel_title) else None
    return {
        "video_id": vid_id,
        "youtube_url": f"https://www.youtube.com/watch?v={vid_id}",
        "channel_id": channel_id,
        "channel_title": channel_title,
        "fetched_at": datetime.now(),
    }


def find_parquet_files(year: int | None = None) -> list[Path]:
    files = sorted(CACHE_DIR.glob("meetings.*.parquet"))
    if year is not None:
        files = [f for f in files if f.name == f"meetings.{year}.parquet"]
    if not files:
        raise FileNotFoundError(
            f"No LocalView parquet files found in {CACHE_DIR}. "
            "Run the LocalView downloader first."
        )
    return files


# ---------------------------------------------------------------------------
# Row schema
# ---------------------------------------------------------------------------

class LocalviewEventRow(RawRow):
    """One LocalView meeting (video) event row, validated before upsert.

    Nullability mirrors the loader: every bronze column is nullable except
    datasource_id, which is the upsert key (NOT NULL + UNIQUE).
    """

    event_date: datetime | None = None
    jurisdiction_name: str | None = Field(default=None, max_length=500)
    jurisdiction_type: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=255)
    city_name: str | None = Field(default=None, max_length=255)
    state_code: str | None = Field(default=None, max_length=2)
    state: str | None = Field(default=None, max_length=100)
    meeting_type: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=500)
    video_url: str | None = None
    datasource: str | None = Field(default=None, max_length=100)
    datasource_id: str = Field(min_length=1, max_length=255)
    loaded_at: datetime | None = None
    st_fips: str | None = Field(default=None, max_length=10)
    place_govt: str | None = Field(default=None, max_length=255)
    channel_title: str | None = Field(default=None, max_length=500)
    vid_title: str | None = Field(default=None, max_length=500)
    vid_desc: str | None = None
    vid_length_min: float | None = None
    vid_upload_date: datetime | None = None
    vid_livestreamed: bool | None = None
    vid_views: float | None = None
    vid_likes: float | None = None
    vid_dislikes: float | None = None
    vid_comments: float | None = None
    vid_favorites: float | None = None
    meeting_date_raw: str | None = Field(default=None, max_length=50)
    caption_text: str | None = None
    caption_text_clean: str | None = None
    channel_type: str | None = Field(default=None, max_length=100)
    acs_18_amind: float | None = None
    acs_18_asian: float | None = None
    acs_18_black: float | None = None
    acs_18_hispanic: float | None = None
    acs_18_median_age: float | None = None
    acs_18_median_gross_rent: float | None = None
    acs_18_median_hh_inc: float | None = None
    acs_18_nhapi: float | None = None
    acs_18_pop: float | None = None
    acs_18_white: float | None = None
    # Carried for the intermediate video→channel mapping (not a bronze column).
    channel_id: str | None = Field(default=None, max_length=255)


# ---------------------------------------------------------------------------
# DDL (each statement separate; preserve original schema verbatim)
# ---------------------------------------------------------------------------

_CREATE_MAPPING_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS intermediate")

_CREATE_MAPPING_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS intermediate.int_localview_youtube_video_channels (
        video_id       VARCHAR(255) PRIMARY KEY,
        youtube_url    TEXT,
        channel_id     VARCHAR(255) NOT NULL,
        channel_title  VARCHAR(500),
        fetched_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_CREATE_MAPPING_INDEX_SQL = text(
    "CREATE INDEX IF NOT EXISTS idx_ilvyvc_channel_id "
    "ON intermediate.int_localview_youtube_video_channels(channel_id)"
)

_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_events_localview (
        event_id          BIGSERIAL PRIMARY KEY,
        event_date        DATE,
        jurisdiction_name VARCHAR(500),
        jurisdiction_type VARCHAR(100),
        city              VARCHAR(255),
        city_name         VARCHAR(255),
        state_code        VARCHAR(2),
        state             VARCHAR(100),
        meeting_type      VARCHAR(255),
        title             VARCHAR(500),
        video_url         TEXT,
        datasource        VARCHAR(100),
        datasource_id     VARCHAR(255) NOT NULL,
        loaded_at         TIMESTAMP DEFAULT NOW(),

        -- Raw LocalView columns (kept for lineage/debugging)
        st_fips                  VARCHAR(10),
        place_govt               VARCHAR(255),
        channel_title            VARCHAR(500),
        vid_title                VARCHAR(500),
        vid_desc                 TEXT,
        vid_length_min           DOUBLE PRECISION,
        vid_upload_date          TIMESTAMP,
        vid_livestreamed         BOOLEAN,
        vid_views                DOUBLE PRECISION,
        vid_likes                DOUBLE PRECISION,
        vid_dislikes             DOUBLE PRECISION,
        vid_comments             DOUBLE PRECISION,
        vid_favorites            DOUBLE PRECISION,
        meeting_date_raw         VARCHAR(50),
        caption_text             TEXT,
        caption_text_clean       TEXT,
        channel_type             VARCHAR(100),
        acs_18_amind             DOUBLE PRECISION,
        acs_18_asian             DOUBLE PRECISION,
        acs_18_black             DOUBLE PRECISION,
        acs_18_hispanic          DOUBLE PRECISION,
        acs_18_median_age        DOUBLE PRECISION,
        acs_18_median_gross_rent DOUBLE PRECISION,
        acs_18_median_hh_inc     DOUBLE PRECISION,
        acs_18_nhapi             DOUBLE PRECISION,
        acs_18_pop               DOUBLE PRECISION,
        acs_18_white             DOUBLE PRECISION,

        CONSTRAINT uq_localview_datasource_id UNIQUE (datasource_id)
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_belv_event_date  ON bronze.bronze_events_localview(event_date)"),
    text("CREATE INDEX IF NOT EXISTS idx_belv_state_code  ON bronze.bronze_events_localview(state_code)"),
    text("CREATE INDEX IF NOT EXISTS idx_belv_datasource  ON bronze.bronze_events_localview(datasource)"),
)

_DROP_TABLE_SQL = text("DROP TABLE IF EXISTS bronze.bronze_events_localview CASCADE")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_events_localview (
        event_date, jurisdiction_name, jurisdiction_type,
        city, city_name, state_code, state, meeting_type,
        title, video_url, datasource, datasource_id, loaded_at,
        st_fips, place_govt, channel_title, vid_title, vid_desc,
        vid_length_min, vid_upload_date, vid_livestreamed,
        vid_views, vid_likes, vid_dislikes, vid_comments, vid_favorites,
        meeting_date_raw, caption_text, caption_text_clean, channel_type,
        acs_18_amind, acs_18_asian, acs_18_black, acs_18_hispanic,
        acs_18_median_age, acs_18_median_gross_rent, acs_18_median_hh_inc,
        acs_18_nhapi, acs_18_pop, acs_18_white
    ) VALUES (
        :event_date, :jurisdiction_name, :jurisdiction_type,
        :city, :city_name, :state_code, :state, :meeting_type,
        :title, :video_url, :datasource, :datasource_id, :loaded_at,
        :st_fips, :place_govt, :channel_title, :vid_title, :vid_desc,
        :vid_length_min, :vid_upload_date, :vid_livestreamed,
        :vid_views, :vid_likes, :vid_dislikes, :vid_comments, :vid_favorites,
        :meeting_date_raw, :caption_text, :caption_text_clean, :channel_type,
        :acs_18_amind, :acs_18_asian, :acs_18_black, :acs_18_hispanic,
        :acs_18_median_age, :acs_18_median_gross_rent, :acs_18_median_hh_inc,
        :acs_18_nhapi, :acs_18_pop, :acs_18_white
    )
    ON CONFLICT (datasource_id) DO UPDATE SET
        event_date        = COALESCE(EXCLUDED.event_date,        bronze_events_localview.event_date),
        jurisdiction_name = COALESCE(EXCLUDED.jurisdiction_name, bronze_events_localview.jurisdiction_name),
        city              = COALESCE(EXCLUDED.city,              bronze_events_localview.city),
        city_name         = COALESCE(EXCLUDED.city_name,         bronze_events_localview.city_name),
        state_code        = COALESCE(EXCLUDED.state_code,        bronze_events_localview.state_code),
        state             = COALESCE(EXCLUDED.state,             bronze_events_localview.state),
        meeting_type      = COALESCE(EXCLUDED.meeting_type,      bronze_events_localview.meeting_type),
        title             = COALESCE(EXCLUDED.title,             bronze_events_localview.title),
        video_url         = COALESCE(EXCLUDED.video_url,         bronze_events_localview.video_url),
        st_fips           = COALESCE(EXCLUDED.st_fips,           bronze_events_localview.st_fips),
        place_govt        = COALESCE(EXCLUDED.place_govt,        bronze_events_localview.place_govt),
        channel_title     = COALESCE(EXCLUDED.channel_title,     bronze_events_localview.channel_title),
        vid_title         = COALESCE(EXCLUDED.vid_title,         bronze_events_localview.vid_title),
        vid_desc          = COALESCE(EXCLUDED.vid_desc,          bronze_events_localview.vid_desc),
        vid_length_min    = COALESCE(EXCLUDED.vid_length_min,    bronze_events_localview.vid_length_min),
        vid_upload_date   = COALESCE(EXCLUDED.vid_upload_date,   bronze_events_localview.vid_upload_date),
        vid_livestreamed  = COALESCE(EXCLUDED.vid_livestreamed,  bronze_events_localview.vid_livestreamed),
        vid_views         = COALESCE(EXCLUDED.vid_views,         bronze_events_localview.vid_views),
        vid_likes         = COALESCE(EXCLUDED.vid_likes,         bronze_events_localview.vid_likes),
        vid_dislikes      = COALESCE(EXCLUDED.vid_dislikes,      bronze_events_localview.vid_dislikes),
        vid_comments      = COALESCE(EXCLUDED.vid_comments,      bronze_events_localview.vid_comments),
        vid_favorites     = COALESCE(EXCLUDED.vid_favorites,     bronze_events_localview.vid_favorites),
        meeting_date_raw  = COALESCE(EXCLUDED.meeting_date_raw,  bronze_events_localview.meeting_date_raw),
        caption_text      = COALESCE(EXCLUDED.caption_text,      bronze_events_localview.caption_text),
        caption_text_clean= COALESCE(EXCLUDED.caption_text_clean,bronze_events_localview.caption_text_clean),
        channel_type      = COALESCE(EXCLUDED.channel_type,      bronze_events_localview.channel_type),
        acs_18_amind      = COALESCE(EXCLUDED.acs_18_amind,      bronze_events_localview.acs_18_amind),
        acs_18_asian      = COALESCE(EXCLUDED.acs_18_asian,      bronze_events_localview.acs_18_asian),
        acs_18_black      = COALESCE(EXCLUDED.acs_18_black,      bronze_events_localview.acs_18_black),
        acs_18_hispanic   = COALESCE(EXCLUDED.acs_18_hispanic,   bronze_events_localview.acs_18_hispanic),
        acs_18_median_age = COALESCE(EXCLUDED.acs_18_median_age, bronze_events_localview.acs_18_median_age),
        acs_18_median_gross_rent = COALESCE(EXCLUDED.acs_18_median_gross_rent, bronze_events_localview.acs_18_median_gross_rent),
        acs_18_median_hh_inc     = COALESCE(EXCLUDED.acs_18_median_hh_inc,    bronze_events_localview.acs_18_median_hh_inc),
        acs_18_nhapi      = COALESCE(EXCLUDED.acs_18_nhapi,      bronze_events_localview.acs_18_nhapi),
        acs_18_pop        = COALESCE(EXCLUDED.acs_18_pop,        bronze_events_localview.acs_18_pop),
        acs_18_white      = COALESCE(EXCLUDED.acs_18_white,      bronze_events_localview.acs_18_white),
        loaded_at         = NOW()
    """
)

_UPSERT_VIDEO_CHANNELS_SQL = text(
    """
    INSERT INTO intermediate.int_localview_youtube_video_channels
      (video_id, youtube_url, channel_id, channel_title, fetched_at)
    VALUES
      (:video_id, :youtube_url, :channel_id, :channel_title, :fetched_at)
    ON CONFLICT (video_id) DO UPDATE SET
      youtube_url = COALESCE(EXCLUDED.youtube_url, intermediate.int_localview_youtube_video_channels.youtube_url),
      channel_id = EXCLUDED.channel_id,
      channel_title = COALESCE(EXCLUDED.channel_title, intermediate.int_localview_youtube_video_channels.channel_title),
      fetched_at = EXCLUDED.fetched_at
    """
)


class LocalviewEventsPipeline(DataSourcePipeline[LocalviewEventRow]):
    source = "localview_events"
    batch_size = 1_000
    row_schema = LocalviewEventRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        paths = [self._path] if self._path is not None else find_parquet_files()
        emitted = 0
        for path in paths:
            df = pd.read_parquet(path)
            # Mirror the original: only rows with both a meeting_date and a vid_id.
            df_valid = df[df['meeting_date'].notna() & df['vid_id'].notna()].copy()
            for _, row in df_valid.iterrows():
                if self._limit is not None and emitted >= self._limit:
                    return
                event = row_to_event(row)
                mapping = _row_to_channel_mapping(row)
                yield {
                    "source": self.source,
                    "source_version": path.stem,
                    "natural_key": str(event["datasource_id"]),
                    **event,
                    "channel_id": mapping["channel_id"] if mapping else None,
                }
                emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[LocalviewEventRow],
        ctx: PipelineContext,
    ) -> None:
        event_params = [
            {
                "event_date": r.event_date,
                "jurisdiction_name": r.jurisdiction_name,
                "jurisdiction_type": r.jurisdiction_type,
                "city": r.city,
                "city_name": r.city_name,
                "state_code": r.state_code,
                "state": r.state,
                "meeting_type": r.meeting_type,
                "title": r.title,
                "video_url": r.video_url,
                "datasource": r.datasource,
                "datasource_id": r.datasource_id,
                "loaded_at": r.loaded_at,
                "st_fips": r.st_fips,
                "place_govt": r.place_govt,
                "channel_title": r.channel_title,
                "vid_title": r.vid_title,
                "vid_desc": r.vid_desc,
                "vid_length_min": r.vid_length_min,
                "vid_upload_date": r.vid_upload_date,
                "vid_livestreamed": r.vid_livestreamed,
                "vid_views": r.vid_views,
                "vid_likes": r.vid_likes,
                "vid_dislikes": r.vid_dislikes,
                "vid_comments": r.vid_comments,
                "vid_favorites": r.vid_favorites,
                "meeting_date_raw": r.meeting_date_raw,
                "caption_text": r.caption_text,
                "caption_text_clean": r.caption_text_clean,
                "channel_type": r.channel_type,
                "acs_18_amind": r.acs_18_amind,
                "acs_18_asian": r.acs_18_asian,
                "acs_18_black": r.acs_18_black,
                "acs_18_hispanic": r.acs_18_hispanic,
                "acs_18_median_age": r.acs_18_median_age,
                "acs_18_median_gross_rent": r.acs_18_median_gross_rent,
                "acs_18_median_hh_inc": r.acs_18_median_hh_inc,
                "acs_18_nhapi": r.acs_18_nhapi,
                "acs_18_pop": r.acs_18_pop,
                "acs_18_white": r.acs_18_white,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, event_params)

        # Keep the video→channel mapping in intermediate (the parquet carries it).
        mapping_params = [
            {
                "video_id": r.datasource_id,
                "youtube_url": f"https://www.youtube.com/watch?v={r.datasource_id}",
                "channel_id": r.channel_id,
                "channel_title": r.channel_title,
                "fetched_at": r.loaded_at or datetime.now(),
            }
            for r in rows
            if r.channel_id
        ]
        if mapping_params:
            await session.execute(_UPSERT_VIDEO_CHANNELS_SQL, mapping_params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        if truncate:
            await session.execute(_DROP_TABLE_SQL)
        await session.execute(_CREATE_MAPPING_SCHEMA_SQL)
        await session.execute(_CREATE_MAPPING_TABLE_SQL)
        await session.execute(_CREATE_MAPPING_INDEX_SQL)
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load LocalView parquet files into bronze.bronze_events_localview"
    )
    parser.add_argument("--file", type=Path, help="Path to a single parquet file (default: all in data/cache/localview/)")
    parser.add_argument("--limit", type=int, help="Load only the first N valid rows")
    parser.add_argument("--year", type=int, help="Load only a specific year (e.g. --year 2023)")
    parser.add_argument(
        "--truncate", action="store_true",
        help="Drop and recreate the table before loading (full reload)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    if args.file is None and args.year is not None:
        for f in find_parquet_files(year=args.year):
            await LocalviewEventsPipeline(path=f, limit=args.limit).run()
        return
    await LocalviewEventsPipeline(path=args.file, limit=args.limit).run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
