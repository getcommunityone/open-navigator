#!/usr/bin/env python3
"""Census relationship-files pipeline: load ZCTA->county / ZCTA->place into bronze.

Ported from load_census_relationships.py to the core_lib DataSourcePipeline
contract.

Loads Census Bureau 2020 geographic relationship files into two bronze tables:

1. bronze_jurisdictions_zip_county - ZIP Code (ZCTA) to County mappings
2. bronze_jurisdictions_zip_place  - ZIP Code (ZCTA) to City/Place mappings

These enable looking up which county/city a ZIP code belongs to (including
multi-county and multi-city ZIPs).

**Source**: US Census Bureau 2020 ZCTA relationship files (pipe-delimited).
Downloaded by download_census_relationships.py into
data/cache/census_relationships/{zcta_county,zcta_place}.txt.

Usage:
    python -m ingestion.census.relationships
    python -m ingestion.census.relationships --types zcta_county
    python -m ingestion.census.relationships --limit 100 --truncate

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded psycopg2 / localhost:5433 / open_navigator_bronze).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
from typing import AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


# Cache directory (where download script saves files)
CACHE_DIR = Path("data/cache/census_relationships")

# Relationship types handled by this loader.
RELATIONSHIP_TYPES = ("zcta_county", "zcta_place")

_INPUT_FILES = {
    "zcta_county": "zcta_county.txt",
    "zcta_place": "zcta_place.txt",
}

_SOURCE_FILE_LABELS = {
    "zcta_county": "Census 2020 ZCTA-County Relationship File",
    "zcta_place": "Census 2020 ZCTA-Place Relationship File",
}

# (zcta column, geoid column, name column) for each relationship file.
_FILE_COLUMNS = {
    "zcta_county": ("GEOID_ZCTA5_20", "GEOID_COUNTY_20", "NAMELSAD_COUNTY_20"),
    "zcta_place": ("GEOID_ZCTA5_20", "GEOID_PLACE_20", "NAMELSAD_PLACE_20"),
}


# --- Pure helpers (preserved from the legacy loader) --------------------------


def safe_str(val) -> str:
    """Return a stripped string, mapping missing/NaN to empty string.

    Mirrors the legacy pandas-based helper: NaN -> '' (the file was read as
    str, so missing values surfaced as the literal "nan").
    """
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() == "nan":
        return ""
    return s


def safe_int(val) -> int | None:
    """Parse an area field to int, returning None on bad/empty input."""
    try:
        return int(float(val)) if val not in (None, "") else None
    except (ValueError, TypeError):
        return None


# --- Row schema ---------------------------------------------------------------


class RelationshipRow(RawRow):
    """One ZCTA->county or ZCTA->place relationship, validated before upsert.

    A single schema covers both target tables; ``relationship_type`` selects
    which one. Constraints mirror the legacy zip_county / zip_place column
    types: zcta VARCHAR(10) NOT NULL, geoid VARCHAR(5|7) NOT NULL, name
    VARCHAR(255) nullable, state_fips VARCHAR(2) nullable, area columns BIGINT
    nullable.
    """

    relationship_type: str = Field(min_length=1)
    zcta: str = Field(min_length=1, max_length=10)
    geoid: str = Field(min_length=1, max_length=7)
    name: str | None = Field(default=None, max_length=255)
    state_fips: str | None = Field(default=None, max_length=2)
    arealand_part: int | None = None
    areawater_part: int | None = None
    source_file: str | None = Field(default=None, max_length=255)


# --- DDL / target prep --------------------------------------------------------
#
# Faithful port of the legacy create_*_table() functions: each target table is
# dropped and recreated, then its three indexes are applied. The original
# issued one multi-statement string per table; here each statement is a
# separate text() call (DROP / CREATE TABLE / each CREATE INDEX), preserving
# the DDL verbatim.

_DROP_ZIP_COUNTY_SQL = text("DROP TABLE IF EXISTS bronze_jurisdictions_zip_county CASCADE")

_CREATE_ZIP_COUNTY_SQL = text(
    """
    CREATE TABLE bronze_jurisdictions_zip_county (
        zcta VARCHAR(10) NOT NULL,
        county_geoid VARCHAR(5) NOT NULL,
        county_name VARCHAR(255),
        state_fips VARCHAR(2),
        arealand_part BIGINT,
        areawater_part BIGINT,
        source_file VARCHAR(255),
        ingestion_date TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (zcta, county_geoid)
    )
    """
)

_CREATE_ZIP_COUNTY_INDEXES_SQL = (
    text("CREATE INDEX idx_bronze_jurisdictions_zip_county_zcta ON bronze_jurisdictions_zip_county(zcta)"),
    text("CREATE INDEX idx_bronze_jurisdictions_zip_county_geoid ON bronze_jurisdictions_zip_county(county_geoid)"),
    text("CREATE INDEX idx_bronze_jurisdictions_zip_county_state ON bronze_jurisdictions_zip_county(state_fips)"),
)

_TRUNCATE_ZIP_COUNTY_SQL = text("TRUNCATE TABLE bronze_jurisdictions_zip_county")

_DROP_ZIP_PLACE_SQL = text("DROP TABLE IF EXISTS bronze_jurisdictions_zip_place CASCADE")

_CREATE_ZIP_PLACE_SQL = text(
    """
    CREATE TABLE bronze_jurisdictions_zip_place (
        zcta VARCHAR(10) NOT NULL,
        place_geoid VARCHAR(7) NOT NULL,
        place_name VARCHAR(255),
        state_fips VARCHAR(2),
        arealand_part BIGINT,
        areawater_part BIGINT,
        source_file VARCHAR(255),
        ingestion_date TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (zcta, place_geoid)
    )
    """
)

_CREATE_ZIP_PLACE_INDEXES_SQL = (
    text("CREATE INDEX idx_bronze_jurisdictions_zip_place_zcta ON bronze_jurisdictions_zip_place(zcta)"),
    text("CREATE INDEX idx_bronze_jurisdictions_zip_place_geoid ON bronze_jurisdictions_zip_place(place_geoid)"),
    text("CREATE INDEX idx_bronze_jurisdictions_zip_place_state ON bronze_jurisdictions_zip_place(state_fips)"),
)

_TRUNCATE_ZIP_PLACE_SQL = text("TRUNCATE TABLE bronze_jurisdictions_zip_place")

_UPSERT_ZIP_COUNTY_SQL = text(
    """
    INSERT INTO bronze_jurisdictions_zip_county
        (zcta, county_geoid, county_name, state_fips, arealand_part, areawater_part, source_file)
    VALUES
        (:zcta, :geoid, :name, :state_fips, :arealand_part, :areawater_part, :source_file)
    ON CONFLICT (zcta, county_geoid) DO UPDATE SET
        county_name = EXCLUDED.county_name,
        state_fips = EXCLUDED.state_fips,
        arealand_part = EXCLUDED.arealand_part,
        areawater_part = EXCLUDED.areawater_part,
        source_file = EXCLUDED.source_file,
        ingestion_date = NOW()
    """
)

_UPSERT_ZIP_PLACE_SQL = text(
    """
    INSERT INTO bronze_jurisdictions_zip_place
        (zcta, place_geoid, place_name, state_fips, arealand_part, areawater_part, source_file)
    VALUES
        (:zcta, :geoid, :name, :state_fips, :arealand_part, :areawater_part, :source_file)
    ON CONFLICT (zcta, place_geoid) DO UPDATE SET
        place_name = EXCLUDED.place_name,
        state_fips = EXCLUDED.state_fips,
        arealand_part = EXCLUDED.arealand_part,
        areawater_part = EXCLUDED.areawater_part,
        source_file = EXCLUDED.source_file,
        ingestion_date = NOW()
    """
)

_UPSERT_BY_TYPE = {
    "zcta_county": _UPSERT_ZIP_COUNTY_SQL,
    "zcta_place": _UPSERT_ZIP_PLACE_SQL,
}


class CensusRelationshipsPipeline(DataSourcePipeline[RelationshipRow]):
    source = "census_relationships"
    batch_size = 5_000  # legacy execute_batch page_size
    row_schema = RelationshipRow

    def __init__(
        self,
        *,
        path: Path | None = None,
        limit: int | None = None,
        types: list[str] | None = None,
    ):
        # ``path`` overrides discovery for a single file (paired with a single
        # ``types`` entry); otherwise files are discovered under CACHE_DIR.
        self._path = path
        self._limit = limit
        self._types = list(types) if types else list(RELATIONSHIP_TYPES)

    def _input_path(self, rel_type: str) -> Path:
        if self._path is not None:
            return self._path
        return CACHE_DIR / _INPUT_FILES[rel_type]

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        for rel_type in self._types:
            input_file = self._input_path(rel_type)
            if not input_file.exists():
                raise FileNotFoundError(
                    f"File not found: {input_file}. "
                    "Run download_census_relationships.py first."
                )

            zcta_col, geoid_col, name_col = _FILE_COLUMNS[rel_type]
            source_label = _SOURCE_FILE_LABELS[rel_type]

            emitted = 0
            with input_file.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle, delimiter="|")
                for row in reader:
                    if self._limit is not None and emitted >= self._limit:
                        break

                    zcta = safe_str(row.get(zcta_col, ""))
                    geoid = safe_str(row.get(geoid_col, ""))
                    name = safe_str(row.get(name_col, ""))

                    # Skip empty rows (mirrors legacy guard)
                    if not zcta or not geoid:
                        continue

                    # Extract state FIPS (first 2 digits of geoid)
                    state_fips = geoid[:2] if len(geoid) >= 2 else None

                    arealand_part = safe_int(row.get("AREALAND_PART"))
                    areawater_part = safe_int(row.get("AREAWATER_PART"))

                    yield {
                        "source": self.source,
                        "source_version": "2020",
                        "natural_key": f"{rel_type}:{zcta}:{geoid}",
                        "relationship_type": rel_type,
                        "zcta": zcta,
                        "geoid": geoid,
                        "name": name or None,
                        "state_fips": state_fips,
                        "arealand_part": arealand_part,
                        "areawater_part": areawater_part,
                        "source_file": source_label,
                    }
                    emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[RelationshipRow],
        ctx: PipelineContext,
    ) -> None:
        # A batch may mix relationship types; route each to the right table.
        by_type: dict[str, list[dict]] = {}
        for r in rows:
            by_type.setdefault(r.relationship_type, []).append(
                {
                    "zcta": r.zcta,
                    "geoid": r.geoid,
                    "name": r.name,
                    "state_fips": r.state_fips,
                    "arealand_part": r.arealand_part,
                    "areawater_part": r.areawater_part,
                    "source_file": r.source_file,
                }
            )
        for rel_type, params in by_type.items():
            await session.execute(_UPSERT_BY_TYPE[rel_type], params)


async def _prepare_target(truncate: bool, types: list[str] | None = None) -> None:
    # Faithful to the legacy create_*_table() functions: drop + recreate each
    # target table and its indexes. Optional TRUNCATE clears rows after
    # (re)creation (a no-op on a freshly created table, kept for symmetry with
    # the other pipelines' --truncate contract).
    rel_types = list(types) if types else list(RELATIONSHIP_TYPES)
    async with async_session() as session:
        if "zcta_county" in rel_types:
            await session.execute(_DROP_ZIP_COUNTY_SQL)
            await session.execute(_CREATE_ZIP_COUNTY_SQL)
            for idx in _CREATE_ZIP_COUNTY_INDEXES_SQL:
                await session.execute(idx)
            if truncate:
                await session.execute(_TRUNCATE_ZIP_COUNTY_SQL)
        if "zcta_place" in rel_types:
            await session.execute(_DROP_ZIP_PLACE_SQL)
            await session.execute(_CREATE_ZIP_PLACE_SQL)
            for idx in _CREATE_ZIP_PLACE_INDEXES_SQL:
                await session.execute(idx)
            if truncate:
                await session.execute(_TRUNCATE_ZIP_PLACE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load Census Geographic Relationship Files to bronze tables"
    )
    parser.add_argument(
        "--types",
        nargs="+",
        choices=list(RELATIONSHIP_TYPES),
        help="Relationship types to load (default: all)",
    )
    parser.add_argument("--limit", type=int, help="Limit records per file (for testing)")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE tables after (re)creation (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    types = args.types or list(RELATIONSHIP_TYPES)
    await _prepare_target(args.truncate, types)
    pipeline = CensusRelationshipsPipeline(limit=args.limit, types=types)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
