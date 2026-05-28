#!/usr/bin/env python3
"""Census municipalities pipeline: load Gazetteer places into bronze_jurisdictions.

Ported from load_census_municipalities.py to the core_lib DataSourcePipeline
contract.

Reads the cached CSV produced by download_census_municipalities.py and loads all
active places (FUNCSTAT == 'A') into the bronze_jurisdictions table.

**Source**: US Census Bureau Gazetteer Files
**Table**: bronze_jurisdictions

GEOID    -> 7-digit Census place code (loaded as geoid AND fips_code)
ANSICODE -> 8-digit ANSI standard code (loaded as ansicode AND legacy ncsid)

Gazetteer columns of interest:
- USPS: State abbreviation               -> state_code
- GEOID: Geographic identifier           -> geoid / fips_code
- ANSICODE: ANSI standard code           -> ansicode / ncsid
- NAME: Place name                       -> name
- LSAD: Legal/Statistical Area Desc.     -> jurisdiction type via LSAD_TYPE_MAP
- FUNCSTAT: Functional status (A=Active) -> filter
- ALAND_SQMI: Land area in square miles  -> area_sq_miles
- INTPTLAT / INTPTLONG: internal point   -> latitude / longitude

Usage:
    python -m scrapers.census.download_census_municipalities (FETCH); python -m ingestion.census.municipalities (LAND)
    python scripts/datasources/census/municipalities.py \\
        --csv data/cache/census/municipalities_20240101.csv
    python scripts/datasources/census/municipalities.py --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded psycopg2 / localhost:5433 / open_navigator).
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


CACHE_DIR = Path("data/cache/census")

LSAD_TYPE_MAP = {
    '25': 'city',
    '43': 'town',
    '47': 'village',
    '21': 'borough',
    '57': 'cdp',
}


# --- Pure helpers (preserved from the legacy loader) --------------------------


def find_latest_cache_file() -> Path:
    """Return the most recent municipalities CSV from cache."""
    files = sorted(CACHE_DIR.glob("municipalities_*.csv"), reverse=True)
    if not files:
        raise FileNotFoundError(
            f"No municipalities CSV found in {CACHE_DIR}. "
            "Run download_census_municipalities.py first."
        )
    return files[0]


def _parse_float(val) -> float | None:
    """Parse a float, mirroring the legacy try/except behavior."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# --- Row schema ---------------------------------------------------------------


class MunicipalityRow(RawRow):
    """One Census Gazetteer place, validated before upsert into bronze_jurisdictions."""

    name: str = Field(min_length=1)
    jurisdiction_type: str = Field(min_length=1)
    state_code: str
    geoid: str
    ansicode: str | None = None
    area_sq_miles: float | None = None
    latitude: float | None = None
    longitude: float | None = None


# --- DDL / target prep --------------------------------------------------------
#
# The legacy loader inserts into a pre-existing bronze_jurisdictions table
# (created by migrations); it issues no CREATE statements. Faithful port keeps
# the table reference unqualified (matching census/states.py) and only performs
# the opt-in TRUNCATE of municipality rows.

_TRUNCATE_SQL = text(
    """
    DELETE FROM bronze_jurisdictions
    WHERE type IN ('city', 'town', 'village', 'borough', 'cdp', 'place')
    """
)

_UPSERT_SQL = text(
    """
    INSERT INTO bronze_jurisdictions (
        name,
        type,
        state_code,
        state,
        county,
        geoid,
        fips_code,
        ncsid,
        ansicode,
        population,
        area_sq_miles,
        latitude,
        longitude,
        website_url,
        source
    ) VALUES (
        :name,
        :jurisdiction_type,
        :state_code,
        NULL,
        NULL,
        :geoid,
        :geoid,
        :ansicode,
        :ansicode,
        NULL,
        :area_sq_miles,
        :latitude,
        :longitude,
        NULL,
        'census_gazetteer_2024'
    )
    ON CONFLICT (name, type, state_code, county) DO UPDATE
    SET geoid = EXCLUDED.geoid,
        fips_code = EXCLUDED.fips_code,
        ncsid = EXCLUDED.ncsid,
        ansicode = EXCLUDED.ansicode,
        area_sq_miles = EXCLUDED.area_sq_miles,
        latitude = EXCLUDED.latitude,
        longitude = EXCLUDED.longitude,
        source = EXCLUDED.source,
        updated_at = CURRENT_TIMESTAMP
    """
)


class CensusMunicipalitiesPipeline(DataSourcePipeline[MunicipalityRow]):
    source = "census_municipalities"
    batch_size = 1_000  # legacy execute_values page_size
    row_schema = MunicipalityRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or find_latest_cache_file()
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if self._limit is not None and i >= self._limit:
                    break

                if row.get('FUNCSTAT') != 'A':
                    continue

                state_code = row.get('USPS', '').strip()
                geoid = row.get('GEOID', '').strip()
                ansicode = row.get('ANSICODE', '').strip()
                name = row.get('NAME', '').strip()
                lsad = row.get('LSAD', '').strip()

                area_sq_miles = _parse_float(row.get('ALAND_SQMI', 0))

                # Legacy: lat/long share a single try block - if either fails,
                # both are dropped.
                latitude = _parse_float(row.get('INTPTLAT', 0))
                longitude = _parse_float(row.get('INTPTLONG', 0))
                if latitude is None or longitude is None:
                    latitude = None
                    longitude = None

                jurisdiction_type = LSAD_TYPE_MAP.get(lsad, 'place')

                yield {
                    "source": self.source,
                    "source_version": path.stem,
                    "natural_key": f"{state_code}:{jurisdiction_type}:{name}",
                    "name": name,
                    "jurisdiction_type": jurisdiction_type,
                    "state_code": state_code,
                    "geoid": geoid,
                    "ansicode": ansicode if ansicode else None,
                    "area_sq_miles": area_sq_miles,
                    "latitude": latitude,
                    "longitude": longitude,
                }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[MunicipalityRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "name": r.name,
                "jurisdiction_type": r.jurisdiction_type,
                "state_code": r.state_code,
                "geoid": r.geoid,
                "ansicode": r.ansicode,
                "area_sq_miles": r.area_sq_miles,
                "latitude": r.latitude,
                "longitude": r.longitude,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    if not truncate:
        return
    async with async_session() as session:
        await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load Census municipalities into bronze_jurisdictions"
    )
    parser.add_argument(
        "--csv", type=Path, help="Path to municipalities CSV (default: latest in cache)"
    )
    parser.add_argument("--limit", type=int, help="Limit number of records (for testing)")
    parser.add_argument(
        "--truncate", action="store_true",
        help="Delete existing municipality rows before loading",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = CensusMunicipalitiesPipeline(path=args.csv, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
