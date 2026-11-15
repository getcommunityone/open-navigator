#!/usr/bin/env python3
"""LocalView YouTube video -> channel mapping pipeline.

Ported from scripts/datasources/localview/backfill_localview_youtube_channel_map.py
to the core_lib DataSourcePipeline contract.

Reads cached LocalView parquet files (data/cache/localview/meetings.*.parquet)
and upserts distinct video_id -> (channel_id, channel_title, youtube_url)
mappings into intermediate.int_localview_youtube_video_channels.

Usage:
    python -m ingestion.localview.channel_map
    python -m ingestion.localview.channel_map --limit 5000
    python -m ingestion.localview.channel_map --file data/cache/localview/meetings.2023.parquet
    python -m ingestion.localview.channel_map --truncate
    python -m ingestion.localview.channel_map --drop-bronze-channel-id

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433/open_navigator).
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import pandas as pd
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/localview")
MAPPING_TABLE = "intermediate.int_localview_youtube_video_channels"


def find_parquet_files(cache_dir: Path | None = None) -> list[Path]:
    """Return sorted LocalView meeting parquet files under cache_dir."""
    root = cache_dir if cache_dir is not None else CACHE_DIR
    files = sorted(root.glob("meetings.*.parquet"))
    if not files:
        raise FileNotFoundError(
            f"No LocalView parquet files found in {root}. "
            "Run the LocalView downloader first."
        )
    return files


def extract_parquet_mappings(
    limit: int | None = 5000,
    *,
    files: list[Path] | None = None,
    cache_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Extract deduplicated vid_id -> (channel_id, channel_title) dicts from parquet files."""
    parquet_files = files if files is not None else find_parquet_files(cache_dir=cache_dir)
    mappings: dict[str, tuple[str, str | None, str]] = {}

    for pf in parquet_files:
        try:
            df = pd.read_parquet(pf, columns=["vid_id", "channel_id", "channel_title"])
        except Exception:
            df_full = pd.read_parquet(pf)
            if "vid_id" not in df_full.columns or "channel_id" not in df_full.columns:
                continue
            if "channel_title" not in df_full.columns:
                df_full["channel_title"] = None
            df = df_full[["vid_id", "channel_id", "channel_title"]]
        df = df[df["vid_id"].notna() & df["channel_id"].notna()].copy()
        if df.empty:
            continue

        for vid, ch_id, ch_title in zip(df["vid_id"], df["channel_id"], df["channel_title"]):
            if vid is None or ch_id is None or pd.isna(vid) or pd.isna(ch_id):
                continue
            vid_s = str(vid).strip()[:255]
            ch_s = str(ch_id).strip()[:255]
            if not vid_s or not ch_s:
                continue
            title_s: str | None = None
            if ch_title is not None and not pd.isna(ch_title):
                stripped = str(ch_title).strip()
                title_s = stripped[:500] if stripped else None
            if vid_s not in mappings:
                mappings[vid_s] = (ch_s, title_s, pf.stem)
            elif mappings[vid_s][1] is None and title_s is not None:
                prev_ch, _, prev_stem = mappings[vid_s]
                mappings[vid_s] = (prev_ch, title_s, prev_stem)

        if limit is not None and len(mappings) >= limit:
            break

    items = list(mappings.items())
    if limit is not None:
        items = items[:limit]

    out: list[dict[str, Any]] = []
    for vid, (ch_id, ch_title, source_version) in items:
        out.append(
            {
                "video_id": vid,
                "youtube_url": f"https://www.youtube.com/watch?v={vid}",
                "channel_id": ch_id,
                "channel_title": ch_title,
                "source_version": source_version,
            }
        )
    return out


class LocalviewVideoChannelRow(RawRow):
    """One LocalView YouTube video -> channel mapping row."""

    video_id: str = Field(min_length=1, max_length=255)
    youtube_url: str | None = None
    channel_id: str = Field(min_length=1, max_length=255)
    channel_title: str | None = Field(default=None, max_length=500)


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS intermediate")

_CREATE_TABLE_SQL = text(
    f"""
    CREATE TABLE IF NOT EXISTS {MAPPING_TABLE} (
        video_id       VARCHAR(255) PRIMARY KEY,
        youtube_url    TEXT,
        channel_id     VARCHAR(255) NOT NULL,
        channel_title  VARCHAR(500),
        fetched_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_CREATE_INDEX_SQL = text(
    f"CREATE INDEX IF NOT EXISTS idx_ilvyvc_channel_id ON {MAPPING_TABLE}(channel_id)"
)

_TRUNCATE_SQL = text(f"TRUNCATE TABLE {MAPPING_TABLE}")

_DROP_BRONZE_CHANNEL_ID_SQL = text(
    """
    DO $$
    BEGIN
      IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'bronze'
          AND table_name = 'bronze_events_localview'
          AND column_name = 'channel_id'
      ) THEN
        ALTER TABLE bronze.bronze_events_localview DROP COLUMN channel_id;
      END IF;
    END $$;
    """
)

_UPSERT_SQL = text(
    f"""
    INSERT INTO {MAPPING_TABLE}
      (video_id, youtube_url, channel_id, channel_title, fetched_at)
    VALUES
      (:video_id, :youtube_url, :channel_id, :channel_title, :fetched_at)
    ON CONFLICT (video_id) DO UPDATE SET
      youtube_url = COALESCE(EXCLUDED.youtube_url, {MAPPING_TABLE}.youtube_url),
      channel_id = EXCLUDED.channel_id,
      channel_title = COALESCE(EXCLUDED.channel_title, {MAPPING_TABLE}.channel_title),
      fetched_at = EXCLUDED.fetched_at
    """
)


class LocalviewVideoChannelsPipeline(DataSourcePipeline[LocalviewVideoChannelRow]):
    source = "localview_video_channels"
    batch_size = 500
    row_schema = LocalviewVideoChannelRow

    def __init__(
        self,
        *,
        path: Path | None = None,
        cache_dir: Path | None = None,
        limit: int | None = 5000,
        dry_run: bool = False,
    ):
        self._path = path
        self._cache_dir = cache_dir
        self._limit = limit
        self._dry_run = dry_run

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        files = [self._path] if self._path is not None else None
        records = extract_parquet_mappings(
            limit=self._limit,
            files=files,
            cache_dir=self._cache_dir,
        )
        for rec in records:
            yield {
                "source": self.source,
                "source_version": rec["source_version"],
                "natural_key": rec["video_id"],
                "video_id": rec["video_id"],
                "youtube_url": rec["youtube_url"],
                "channel_id": rec["channel_id"],
                "channel_title": rec["channel_title"],
            }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[LocalviewVideoChannelRow],
        ctx: PipelineContext,
    ) -> None:
        if self._dry_run:
            return
        now = datetime.now()
        params = [
            {
                "video_id": r.video_id,
                "youtube_url": r.youtube_url,
                "channel_id": r.channel_id,
                "channel_title": r.channel_title,
                "fetched_at": now,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool, drop_bronze_channel_id: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        await session.execute(_CREATE_INDEX_SQL)
        if drop_bronze_channel_id:
            logger.warning("Dropping bronze.bronze_events_localview.channel_id (if exists)...")
            await session.execute(_DROP_BRONZE_CHANNEL_ID_SQL)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill LocalView video->channel mapping table (intermediate.int_localview_youtube_video_channels)"
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Single parquet file path (default: all meetings.*.parquet in data/cache/localview/)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Max distinct LocalView video IDs to extract this run (default: 5000)",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="TRUNCATE mapping table before loading",
    )
    parser.add_argument(
        "--drop-bronze-channel-id",
        action="store_true",
        help="Drop bronze.bronze_events_localview.channel_id if present",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and validate rows without writing to the database",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    if not args.dry_run:
        await _prepare_target(
            truncate=args.truncate,
            drop_bronze_channel_id=args.drop_bronze_channel_id,
        )
    pipeline = LocalviewVideoChannelsPipeline(
        path=args.file,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
