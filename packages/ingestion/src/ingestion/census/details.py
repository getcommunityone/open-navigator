#!/usr/bin/env python3
"""Jurisdictions details pipeline: load discovery/enrichment fields into jurisdiction.

Ported from load_details_to_postgres.py to the core_lib
DataSourcePipeline contract.

Data source: data/gold/jurisdictions_details.parquet. Upserts discovery
metadata (YouTube channels, websites, meeting platforms, social media) onto
jurisdiction rows keyed by jurisdiction_id.

Usage:
    python -m ingestion.census.details
    python -m ingestion.census.details \\
        --file data/gold/jurisdictions_details.parquet --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433).
"""
from __future__ import annotations

import argparse
import asyncio
import ast
import json
from pathlib import Path
from typing import AsyncIterator

import pandas as pd
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


# Source parquet file (gold layer).
DETAILS_FILE = Path("data/gold/jurisdictions_details.parquet")


# --- pure helpers (JSON coercion, preserved from the loader's per-column logic) ---


def _notna(value) -> bool:
    """Scalar-safe pandas notna (lists/dicts are always "present")."""
    if isinstance(value, (list, dict)):
        return True
    try:
        return bool(pd.notna(value))
    except (TypeError, ValueError):
        return value is not None


def _coerce_json(value, default: str) -> str:
    """Coerce a parquet cell into a JSON string.

    Mirrors the loader's per-column handling: NaN/None -> default literal,
    string -> ast.literal_eval round-tripped through json.dumps (falling back
    to default on failure), list/dict -> json.dumps.
    """
    if not _notna(value):
        return default
    if isinstance(value, str):
        try:
            return json.dumps(ast.literal_eval(value))
        except Exception:
            return default
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return default


class JurisdictionsDetailsRow(RawRow):
    """One jurisdiction discovery/enrichment row, validated before upsert."""

    model_config = RawRow.model_config | {"arbitrary_types_allowed": True}

    jurisdiction_id: str = Field(min_length=1, max_length=50)
    jurisdiction_name: str
    state_code: str | None = Field(default=None, max_length=2)
    state: str | None = Field(default=None, max_length=2)
    jurisdiction_type: str | None = None
    population: int = 0
    discovery_timestamp: pd.Timestamp
    website_url: str | None = None
    youtube_channel_count: int = 0
    youtube_channels: str = "[]"
    meeting_platform_count: int = 0
    meeting_platforms: str = "[]"
    social_media: str = "{}"
    agenda_portal_count: int = 0
    discovery_status: str = "unknown"
    in_localview: bool = False


# DDL (migration 038): jurisdiction pre-exists; ensure enrichment columns and the
# partial unique index on jurisdiction_id. Each statement is issued separately.
_DDL_STATEMENTS = (
    text("ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS jurisdiction_id VARCHAR(50)"),
    text("ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS discovery_timestamp TIMESTAMP"),
    text("ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS website_url TEXT"),
    text("ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS youtube_channel_count INTEGER DEFAULT 0"),
    text("ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS youtube_channels JSONB"),
    text("ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS meeting_platform_count INTEGER DEFAULT 0"),
    text("ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS meeting_platforms JSONB"),
    text("ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS social_media JSONB"),
    text("ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS agenda_portal_count INTEGER DEFAULT 0"),
    text("ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS discovery_status VARCHAR(50)"),
    text("ALTER TABLE jurisdiction ADD COLUMN IF NOT EXISTS in_localview BOOLEAN DEFAULT FALSE"),
    text(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_jurisdiction_jurisdiction_id
        ON jurisdiction (jurisdiction_id)
        WHERE jurisdiction_id IS NOT NULL AND BTRIM(jurisdiction_id) <> ''
        """
    ),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE jurisdiction")

_UPSERT_SQL = text(
    """
    INSERT INTO jurisdiction (
        jurisdiction_id, name, state_code, state, type,
        population, discovery_timestamp, website_url,
        youtube_channel_count, youtube_channels,
        meeting_platform_count, meeting_platforms,
        social_media, agenda_portal_count, discovery_status, in_localview,
        source
    ) VALUES (
        :jurisdiction_id, :jurisdiction_name, :state_code, :state, :jurisdiction_type,
        :population, :discovery_timestamp, :website_url,
        :youtube_channel_count, CAST(:youtube_channels AS jsonb),
        :meeting_platform_count, CAST(:meeting_platforms AS jsonb),
        CAST(:social_media AS jsonb), :agenda_portal_count, :discovery_status, :in_localview,
        'discovery'
    )
    ON CONFLICT (jurisdiction_id)
    DO UPDATE SET
        name = EXCLUDED.name,
        state_code = EXCLUDED.state_code,
        state = EXCLUDED.state,
        type = EXCLUDED.type,
        population = EXCLUDED.population,
        discovery_timestamp = EXCLUDED.discovery_timestamp,
        website_url = EXCLUDED.website_url,
        youtube_channel_count = EXCLUDED.youtube_channel_count,
        youtube_channels = EXCLUDED.youtube_channels,
        meeting_platform_count = EXCLUDED.meeting_platform_count,
        meeting_platforms = EXCLUDED.meeting_platforms,
        social_media = EXCLUDED.social_media,
        agenda_portal_count = EXCLUDED.agenda_portal_count,
        discovery_status = EXCLUDED.discovery_status,
        in_localview = EXCLUDED.in_localview,
        last_updated = CURRENT_TIMESTAMP
    """
)


class JurisdictionsDetailsPipeline(DataSourcePipeline[JurisdictionsDetailsRow]):
    source = "jurisdictions_details"
    batch_size = 1_000
    row_schema = JurisdictionsDetailsRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or DETAILS_FILE
        df = pd.read_parquet(path)
        df["discovery_timestamp"] = pd.to_datetime(df["discovery_timestamp"])

        emitted = 0
        for _, row in df.iterrows():
            if self._limit is not None and emitted >= self._limit:
                return
            jurisdiction_id = row["jurisdiction_id"]
            yield {
                "source": self.source,
                "source_version": path.stem,
                "natural_key": str(jurisdiction_id),
                "jurisdiction_id": jurisdiction_id,
                "jurisdiction_name": row["jurisdiction_name"],
                "state_code": row["state_code"],
                "state": row["state"],
                "jurisdiction_type": row["jurisdiction_type"],
                "population": int(row["population"]) if pd.notna(row["population"]) else 0,
                "discovery_timestamp": row["discovery_timestamp"],
                "website_url": row["website_url"] if pd.notna(row["website_url"]) else None,
                "youtube_channel_count": int(row["youtube_channel_count"])
                if pd.notna(row["youtube_channel_count"])
                else 0,
                "youtube_channels": _coerce_json(row["youtube_channels"], "[]"),
                "meeting_platform_count": int(row["meeting_platform_count"])
                if pd.notna(row["meeting_platform_count"])
                else 0,
                "meeting_platforms": _coerce_json(row["meeting_platforms"], "[]"),
                "social_media": _coerce_json(row["social_media"], "{}"),
                "agenda_portal_count": int(row["agenda_portal_count"])
                if pd.notna(row["agenda_portal_count"])
                else 0,
                "discovery_status": row["status"] if pd.notna(row["status"]) else "unknown",
                "in_localview": bool(row["in_localview"]) if pd.notna(row["in_localview"]) else False,
            }
            emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[JurisdictionsDetailsRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "jurisdiction_id": r.jurisdiction_id,
                "jurisdiction_name": r.jurisdiction_name,
                "state_code": r.state_code,
                "state": r.state,
                "jurisdiction_type": r.jurisdiction_type,
                "population": r.population,
                "discovery_timestamp": r.discovery_timestamp.to_pydatetime(),
                "website_url": r.website_url,
                "youtube_channel_count": r.youtube_channel_count,
                "youtube_channels": r.youtube_channels,
                "meeting_platform_count": r.meeting_platform_count,
                "meeting_platforms": r.meeting_platforms,
                "social_media": r.social_media,
                "agenda_portal_count": r.agenda_portal_count,
                "discovery_status": r.discovery_status,
                "in_localview": r.in_localview,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        for stmt in _DDL_STATEMENTS:
            await session.execute(stmt)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load jurisdictions_details.parquet into jurisdiction"
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to parquet (default: data/gold/jurisdictions_details.parquet)",
    )
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(truncate=False)
    pipeline = JurisdictionsDetailsPipeline(path=args.file, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
