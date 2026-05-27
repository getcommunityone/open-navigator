#!/usr/bin/env python3
"""
Census counties pipeline: load Census Gazetteer counties into bronze_jurisdictions.

Ported from load_census_counties.py to the core_lib DataSourcePipeline contract.

The Census Gazetteer county file contains all ~3,144 U.S. counties and county
equivalents (parishes, boroughs, etc.).

**Source**: US Census Bureau Gazetteer Files
**URL**: https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html
**Table**: bronze_jurisdictions

**GEOID Column**: 5-digit Census county code (primary identifier)
**FIPS Column**: 5-digit FIPS code (same as GEOID for counties)

Gazetteer columns:
- USPS: State abbreviation
- GEOID: Geographic identifier (5 digits for counties) -> loaded as geoid
- NAME: County name
- ALAND: Land area in square meters
- AWATER: Water area in square meters
- ALAND_SQMI: Land area in square miles
- AWATER_SQMI: Water area in square miles
- INTPTLAT: Latitude of internal point
- INTPTLONG: Longitude of internal point

Usage:
    python -m ingestion.census.counties
    python -m ingestion.census.counties --force-download
    python -m ingestion.census.counties --limit 10  # Test with 10 counties

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded localhost:5433 / open_navigator_bronze credentials).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

import requests
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


# Census Gazetteer Files for counties
GAZETTEER_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip"
CACHE_DIR = Path("data/cache/census")


def download_gazetteer_file(force_download: bool = False) -> Path:
    """
    Download Census Gazetteer county file.

    Args:
        force_download: If True, re-download even if cached file exists

    Returns:
        Path to extracted CSV file
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Cache file with date
    cache_file = CACHE_DIR / f"counties_{datetime.now().strftime('%Y%m%d')}.csv"

    # Use cached file if exists and not forcing download
    if cache_file.exists() and not force_download:
        logger.info(f"Using cached file: {cache_file}")
        return cache_file

    logger.info(f"Downloading Census Gazetteer from: {GAZETTEER_URL}")
    logger.info("This may take 1-2 minutes...")

    try:
        response = requests.get(GAZETTEER_URL, timeout=120)
        response.raise_for_status()

        logger.success(f"Downloaded {len(response.content):,} bytes")

        # Extract ZIP file
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
            # Find the .txt file (tab-delimited)
            txt_files = [f for f in zip_ref.namelist() if f.endswith('.txt')]
            if not txt_files:
                raise FileNotFoundError("No .txt file found in ZIP")

            txt_file = txt_files[0]
            logger.info(f"Extracting: {txt_file}")

            # Read tab-delimited file
            with zip_ref.open(txt_file) as f:
                content = f.read().decode('latin-1')

            # Convert tab-delimited to CSV
            lines = content.split('\n')
            csv_lines = []
            for line in lines:
                if line.strip():
                    # Replace tabs with commas
                    csv_lines.append(','.join(line.split('\t')))

            # Write to cache file
            cache_file.write_text('\n'.join(csv_lines))
            logger.success(f"Saved to: {cache_file}")

        return cache_file

    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading file: {e}")
        raise
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        raise


def _parse_float(val: str | None) -> float | None:
    """Parse a Gazetteer numeric field, returning None on bad/empty input."""
    try:
        return float(val or 0)
    except (ValueError, TypeError):
        return None


class CountyRow(RawRow):
    """One US county/county-equivalent, validated before upsert into bronze_jurisdictions."""

    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    state_code: str = Field(min_length=1)
    geoid: str = Field(min_length=1)
    fips_code: str = Field(min_length=1)
    area_sq_miles: float | None = None
    latitude: float | None = None
    longitude: float | None = None


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
        :type,
        :state_code,
        NULL,
        NULL,
        :geoid,
        :fips_code,
        NULL,
        NULL,
        NULL,
        :area_sq_miles,
        :latitude,
        :longitude,
        NULL,
        :source
    )
    ON CONFLICT (name, type, state_code, county) DO UPDATE
    SET geoid = EXCLUDED.geoid,
        fips_code = EXCLUDED.fips_code,
        area_sq_miles = EXCLUDED.area_sq_miles,
        latitude = EXCLUDED.latitude,
        longitude = EXCLUDED.longitude,
        source = EXCLUDED.source,
        updated_at = CURRENT_TIMESTAMP
    """
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze_jurisdictions")


class CensusCountiesPipeline(DataSourcePipeline[CountyRow]):
    source = "census_counties"
    batch_size = 1_000
    row_schema = CountyRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or download_gazetteer_file()
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for i, row in enumerate(reader):
                if self._limit is not None and i >= self._limit:
                    break

                # Extract data
                state_code = row.get('USPS', '').strip()
                geoid = row.get('GEOID', '').strip()  # 5-digit county code
                name = row.get('NAME', '').strip()

                # Area in square miles
                area_sq_miles = _parse_float(row.get('ALAND_SQMI'))

                # Coordinates
                latitude = _parse_float(row.get('INTPTLAT'))
                longitude = _parse_float(row.get('INTPTLONG'))

                yield {
                    "source": self.source,
                    "source_version": "2024",
                    "natural_key": f"county:{geoid}",
                    "name": name,
                    "type": "county",  # All are type='county'
                    "state_code": state_code,
                    "geoid": geoid,  # 5-digit county code
                    "fips_code": geoid,  # same as geoid for counties
                    "area_sq_miles": area_sq_miles,
                    "latitude": latitude,
                    "longitude": longitude,
                }

                if (i + 1) % 1000 == 0:
                    logger.info(f"Processed {i + 1:,} records...")

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[CountyRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "name": r.name,
                "type": r.type,
                "state_code": r.state_code,
                "geoid": r.geoid,
                "fips_code": r.fips_code,
                "area_sq_miles": r.area_sq_miles,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "source": "census_gazetteer_2024",
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    # The bronze_jurisdictions table is shared with the census states loader and
    # is created by upstream migrations; this loader only optionally truncates.
    if truncate:
        async with async_session() as session:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load Census Gazetteer counties into bronze_jurisdictions"
    )
    parser.add_argument(
        "--force-download", action="store_true",
        help="Force re-download even if cached",
    )
    parser.add_argument("--limit", type=int, help="Limit number of records (for testing)")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    csv_file = download_gazetteer_file(force_download=args.force_download)
    pipeline = CensusCountiesPipeline(path=csv_file, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
