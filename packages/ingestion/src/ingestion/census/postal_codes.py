#!/usr/bin/env python3
"""Census postal codes (ZCTA) pipeline: load Census Gazetteer ZCTAs into bronze.

Ported from load_census_postal_codes.py to the core_lib DataSourcePipeline
contract.

This loads Census Bureau ZIP Code Tabulation Areas (ZCTAs) into the
bronze_jurisdictions_postal_codes table. ZCTAs are generalized areal
representations of USPS ZIP Code service areas. They are not exact matches to
ZIP codes but provide geographic boundaries for analysis.

**Source**: US Census Bureau Gazetteer Files
**URL**: https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html
**Table**: bronze_jurisdictions_postal_codes

Gazetteer columns used:
- GEOID: 5-digit ZCTA code (loaded as both zcta and geoid)
- ALAND: Land area in square meters
- AWATER: Water area in square meters
- ALAND_SQMI: Land area in square miles
- AWATER_SQMI: Water area in square miles
- INTPTLAT: Latitude of internal point
- INTPTLONG: Longitude of internal point

Usage:
    python -m ingestion.census.postal_codes
    python -m ingestion.census.postal_codes --year 2024
    python -m ingestion.census.postal_codes --limit 10  # Test with 10 ZCTAs

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded localhost:5433 / open_navigator_bronze credentials).
"""
from __future__ import annotations

import argparse
import asyncio
import zipfile
from io import BytesIO
from pathlib import Path
from typing import AsyncIterator

import pandas as pd
import requests
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/census/zcta")

# Census Bureau Gazetteer ZCTA file (2024 - latest available)
# This file contains all 33,000+ ZIP Code Tabulation Areas with:
# - GEOID (5-digit ZCTA code)
# - INTPTLAT, INTPTLONG (latitude, longitude)
# - ALAND, AWATER (land and water area in square meters)
ZCTA_GAZETTEER_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip"


def find_cached_csv(year: int = 2024) -> Path:
    """Return the cached ZCTA CSV for ``year`` or raise if it is missing.

    Mirrors the cache lookup inside ``download_census_zcta_data`` so callers
    (and tests) can resolve a cached file without triggering a network
    download.
    """
    cache_file = CACHE_DIR / f"zcta_{year}.csv"
    if not cache_file.exists():
        raise FileNotFoundError(
            f"No cached ZCTA CSV found at {cache_file}. "
            "Run download_census_zcta_data() first."
        )
    return cache_file


def safe_int(val):
    try:
        return int(float(val)) if pd.notna(val) else None
    except:
        return None


def safe_float(val):
    try:
        return float(val) if pd.notna(val) else None
    except:
        return None


def download_census_zcta_data(year: int = 2024) -> pd.DataFrame:
    """
    Download Census Bureau ZCTA Gazetteer file

    The Gazetteer file is a tab-delimited text file inside a ZIP archive containing
    all 33,000+ ZIP Code Tabulation Areas with geographic coordinates and area measurements.

    Args:
        year: Census year (default: 2024)

    Returns:
        pandas DataFrame with ZCTA data
    """
    # Create cache directory
    cache_dir = CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_file = cache_dir / f"zcta_{year}.csv"

    # Check if cached file exists (< 30 days old)
    if cache_file.exists():
        file_age_days = (pd.Timestamp.now() - pd.Timestamp(cache_file.stat().st_mtime, unit='s')).days
        if file_age_days < 30:
            logger.info(f"Using cached ZCTA data from {cache_file}")
            logger.info(f"   File age: {file_age_days} days old")
            return pd.read_csv(cache_file)

    logger.info(f"Downloading Census ZCTA Gazetteer data...")
    logger.info(f"   URL: {ZCTA_GAZETTEER_URL}")
    logger.info(f"   This may take 2-5 minutes for large files...")

    try:
        response = requests.get(ZCTA_GAZETTEER_URL, timeout=300)
        response.raise_for_status()

        logger.info(f"Downloaded {len(response.content) / 1024 / 1024:.2f} MB")

        # Extract ZIP file
        with zipfile.ZipFile(BytesIO(response.content)) as zip_ref:
            # Find the .txt file (Gazetteer files are tab-delimited)
            txt_files = [f for f in zip_ref.namelist() if f.endswith('.txt')]

            if not txt_files:
                raise FileNotFoundError("No .txt file found in ZIP archive")

            txt_file = txt_files[0]
            logger.info(f"Extracting {txt_file}...")

            # Read tab-delimited file
            with zip_ref.open(txt_file) as f:
                df = pd.read_csv(f, sep='\t', encoding='latin-1', dtype=str)

        logger.info(f"Loaded {len(df):,} ZCTAs")
        logger.info(f"   Columns: {list(df.columns)}")

        # Cache the data
        df.to_csv(cache_file, index=False)
        logger.info(f"Cached data to {cache_file}")

        return df

    except requests.exceptions.Timeout:
        logger.error(f"Timeout downloading ZCTA data after 5 minutes")
        logger.error(f"   Census server may be slow. Try again later.")
        raise
    except Exception as e:
        logger.error(f"Failed to download Census ZCTA data: {e}")
        raise


class PostalCodeRow(RawRow):
    """One Census ZCTA, validated before upsert into bronze_jurisdictions_postal_codes."""

    zcta: str = Field(min_length=1, max_length=10)
    geoid: str = Field(min_length=1, max_length=10)
    aland: int | None = None
    awater: int | None = None
    aland_sqmi: float | None = None
    awater_sqmi: float | None = None
    intptlat: float | None = None
    intptlong: float | None = None
    source_file: str | None = Field(default=None, max_length=255)


_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze_jurisdictions_postal_codes (
        zcta VARCHAR(10) PRIMARY KEY,
        geoid VARCHAR(10) NOT NULL,
        aland BIGINT,
        awater BIGINT,
        aland_sqmi NUMERIC(12, 6),
        awater_sqmi NUMERIC(12, 6),
        intptlat NUMERIC(11, 8),
        intptlong NUMERIC(12, 8),
        source_file VARCHAR(255),
        ingestion_date TIMESTAMP DEFAULT NOW()
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bronze_postal_codes_zcta ON bronze_jurisdictions_postal_codes(zcta)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_postal_codes_geoid ON bronze_jurisdictions_postal_codes(geoid)"),
    text("CREATE INDEX IF NOT EXISTS idx_bronze_postal_codes_location ON bronze_jurisdictions_postal_codes(intptlat, intptlong)"),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze_jurisdictions_postal_codes")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze_jurisdictions_postal_codes
        (zcta, geoid, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, source_file)
    VALUES
        (:zcta, :geoid, :aland, :awater, :aland_sqmi, :awater_sqmi, :intptlat, :intptlong, :source_file)
    ON CONFLICT (zcta) DO UPDATE SET
        geoid = EXCLUDED.geoid,
        aland = EXCLUDED.aland,
        awater = EXCLUDED.awater,
        aland_sqmi = EXCLUDED.aland_sqmi,
        awater_sqmi = EXCLUDED.awater_sqmi,
        intptlat = EXCLUDED.intptlat,
        intptlong = EXCLUDED.intptlong,
        source_file = EXCLUDED.source_file,
        ingestion_date = NOW()
    """
)


class CensusPostalCodesPipeline(DataSourcePipeline[PostalCodeRow]):
    source = "census_postal_codes"
    batch_size = 5_000
    row_schema = PostalCodeRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        source = self._path if self._path is not None else download_census_zcta_data()
        df = pd.read_csv(source, dtype=str) if isinstance(source, Path) else source

        emitted = 0
        for _, row in df.iterrows():
            if self._limit is not None and emitted >= self._limit:
                return

            try:
                geoid = str(row.get('GEOID', '')).strip()

                if not geoid or len(geoid) != 5:
                    continue

                yield {
                    "source": self.source,
                    "source_version": "2024",
                    "natural_key": f"zcta:{geoid}",
                    "zcta": geoid,  # zcta
                    "geoid": geoid,  # geoid (same as ZCTA)
                    "aland": safe_int(row.get('ALAND')),
                    "awater": safe_int(row.get('AWATER')),
                    "aland_sqmi": safe_float(row.get('ALAND_SQMI')),
                    "awater_sqmi": safe_float(row.get('AWATER_SQMI')),
                    "intptlat": safe_float(row.get('INTPTLAT')),
                    "intptlong": safe_float(row.get('INTPTLONG')),
                    "source_file": "Census Gazetteer 2024",
                }
                emitted += 1

            except Exception as e:
                logger.warning(f"Error processing ZCTA {row.get('GEOID', 'unknown')}: {e}")
                continue

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[PostalCodeRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "zcta": r.zcta,
                "geoid": r.geoid,
                "aland": r.aland,
                "awater": r.awater,
                "aland_sqmi": r.aland_sqmi,
                "awater_sqmi": r.awater_sqmi,
                "intptlat": r.intptlat,
                "intptlong": r.intptlong,
                "source_file": r.source_file,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load Census Bureau ZIP Code Tabulation Areas (ZCTAs) to bronze_jurisdictions_postal_codes"
    )
    parser.add_argument(
        "--year", type=int, default=2024,
        help="Census vintage year (default: 2024)",
    )
    parser.add_argument("--limit", type=int, help="Limit number of records (for testing)")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    df = download_census_zcta_data(year=args.year)
    pipeline = CensusPostalCodesPipeline(path=df, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
