#!/usr/bin/env python3
"""Jurisdictions counties pipeline: load gold parquet into the jurisdiction table.

Ported from load_counties_to_postgres.py to the core_lib
DataSourcePipeline contract.

Data source: data/gold/jurisdictions_counties.parquet (Census county shapes,
columns NAME / USPS / GEOID / download_date). Counties are upserted into the
shared `jurisdiction` table alongside cities.

Usage:
    python -m ingestion.jurisdictions.counties
    python -m ingestion.jurisdictions.counties --states AL,GA,IN
    python -m ingestion.jurisdictions.counties \\
        --file data/gold/jurisdictions_counties.parquet --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433).
"""
from __future__ import annotations

import argparse
import asyncio
import re
from pathlib import Path
from typing import AsyncIterator, Optional

import pandas as pd
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


# Source parquet file (gold layer).
COUNTIES_FILE = Path("data/gold/jurisdictions_counties.parquet")

# Default development states when --states is not provided (preserved from loader).
DEFAULT_STATES = ["AL", "GA", "IN", "MA", "WA", "WI"]


# --- pure helpers (canonical jurisdiction_id slug logic, preserved from
# scripts/jurisdictions/jurisdiction_id.py so the loader is self-contained) ---

_UNICODE_SPACE_RE = re.compile(r"[\u00a0\u2000-\u200a\u202f\u205f\u3000]+")
_PLACE_OF_PREFIX_RE = re.compile(
    r"^(?:city|town|village|borough|township|county)\s+of\s+",
    re.I,
)
_PLACE_LSAD_SUFFIX_RE = re.compile(
    r"\s+(?:city|town|village|county|borough|cdp|municipality|township|parish|ccd)\s*$",
    re.I,
)
_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SLUG_MAX_LEN = 56


def normalize_place_label_for_slug(name: str) -> str:
    """Census-style place name with LSAD / ``City of`` prefixes removed."""
    n = _UNICODE_SPACE_RE.sub(" ", (name or "").strip())
    n = _PLACE_OF_PREFIX_RE.sub("", n)
    n = _PLACE_LSAD_SUFFIX_RE.sub("", n).strip()
    return re.sub(r"\s+", " ", n).strip()


def place_slug_for_jurisdiction_id(name: str, *, max_length: int = _SLUG_MAX_LEN) -> str:
    """Lowercase snake_case slug used as the prefix in ``{slug}_{geoid}`` ids."""
    label = normalize_place_label_for_slug(name)
    slug = _NON_SLUG_RE.sub("_", label.lower()).strip("_")
    return slug[:max_length].strip("_")


def jurisdiction_id_from_name_geoid(
    name: str,
    geoid: str,
    *,
    jurisdiction_type: Optional[str] = None,
) -> str:
    """Build canonical ``{slug}_{geoid}`` jurisdiction_id."""
    g = str(geoid or "").strip().replace("-", "")
    if not g or not g.isdigit():
        return ""
    jt = (jurisdiction_type or "").lower()
    if jt == "state" and len(g) == 2:
        return ""
    slug = place_slug_for_jurisdiction_id(name or g)
    return f"{slug}_{g}"


class CountyRow(RawRow):
    """One county jurisdiction row, validated before upsert."""

    model_config = RawRow.model_config | {"arbitrary_types_allowed": True}

    jurisdiction_id: str = Field(min_length=1)
    jurisdiction_name: str = Field(min_length=1)
    state_code: str | None = Field(default=None, max_length=2)
    state: str | None = Field(default=None, max_length=2)
    jurisdiction_type: str = Field(default="county")
    population: int = 0
    discovery_timestamp: pd.Timestamp
    website_url: str | None = None
    youtube_channel_count: int = 0
    youtube_channels: str = "[]"
    meeting_platform_count: int = 0
    meeting_platforms: str = "[]"
    social_media: str = "{}"
    agenda_portal_count: int = 0
    status: str = "pending_discovery"


_INSERT_SQL = text(
    """
    INSERT INTO jurisdiction (
        jurisdiction_id, name, state_code, state, type,
        population, discovery_timestamp, website_url,
        youtube_channel_count, youtube_channels,
        meeting_platform_count, meeting_platforms,
        social_media, agenda_portal_count, discovery_status,
        source
    ) VALUES (
        :jurisdiction_id, :jurisdiction_name, :state_code, :state, :jurisdiction_type,
        :population, :discovery_timestamp, :website_url,
        :youtube_channel_count, CAST(:youtube_channels AS jsonb),
        :meeting_platform_count, CAST(:meeting_platforms AS jsonb),
        CAST(:social_media AS jsonb), :agenda_portal_count, :status,
        'discovery'
    )
    ON CONFLICT (jurisdiction_id)
    DO UPDATE SET
        name = EXCLUDED.name,
        state = EXCLUDED.state,
        type = EXCLUDED.type,
        last_updated = CURRENT_TIMESTAMP
    """
)


class JurisdictionsCountiesPipeline(DataSourcePipeline[CountyRow]):
    source = "jurisdictions_counties"
    batch_size = 1_000
    row_schema = CountyRow

    def __init__(
        self,
        *,
        path: Path | None = None,
        states: list[str] | None = None,
        limit: int | None = None,
    ):
        self._path = path
        self._states = states
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or COUNTIES_FILE
        df = pd.read_parquet(path)

        if self._states:
            df = df[df["USPS"].isin(self._states)]

        emitted = 0
        for _, row in df.iterrows():
            if self._limit is not None and emitted >= self._limit:
                return
            jurisdiction_name = row["NAME"].replace(" County", "").strip()
            jurisdiction_id = jurisdiction_id_from_name_geoid(
                row["NAME"], str(row["GEOID"]), jurisdiction_type="county"
            )
            discovery_timestamp = (
                pd.to_datetime(row["download_date"])
                if pd.notna(row.get("download_date"))
                else pd.Timestamp.now()
            )
            yield {
                "source": self.source,
                "source_version": path.stem,
                "natural_key": jurisdiction_id,
                "jurisdiction_id": jurisdiction_id,
                "jurisdiction_name": jurisdiction_name,
                "state_code": row["USPS"],
                "state": row["USPS"],
                "jurisdiction_type": "county",
                "population": 0,
                "discovery_timestamp": discovery_timestamp,
                "website_url": None,
                "youtube_channel_count": 0,
                "youtube_channels": "[]",
                "meeting_platform_count": 0,
                "meeting_platforms": "[]",
                "social_media": "{}",
                "agenda_portal_count": 0,
                "status": "pending_discovery",
            }
            emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[CountyRow],
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
                "status": r.status,
            }
            for r in rows
        ]
        await session.execute(_INSERT_SQL, params)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load counties into jurisdiction")
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to parquet (default: data/gold/jurisdictions_counties.parquet)",
    )
    parser.add_argument(
        "--states",
        type=str,
        help="Comma-separated list of state codes (e.g., AL,GA,IN,MA,MT,WA,WI)",
    )
    parser.add_argument("--limit", type=int, help="Limit records (for testing)")
    return parser


async def _run(args: argparse.Namespace) -> None:
    if args.states:
        states = [s.strip().upper() for s in args.states.split(",")]
    else:
        states = list(DEFAULT_STATES)
    pipeline = JurisdictionsCountiesPipeline(
        path=args.file, states=states, limit=args.limit
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
