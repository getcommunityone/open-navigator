#!/usr/bin/env python3
"""Census county-mappings pipeline: load ZCTA -> county relationships into bronze.

Ported from load_county_mappings.py to the core_lib DataSourcePipeline
contract. Preserves the original ZCTA-to-county processing behavior: read the
pipe-delimited Census ZCTA relationship file, map columns, compute the primary
(highest population share) county per ZCTA, and emit one row per ZCTA.

**Source**: Census 2020 ZCTA (ZIP Code Tabulation Area) to County relationship
file (tab20_zcta520_county20_natl.txt), downloaded by
download_census_relationships.py into data/cache/census_relationships/.

**Table**: bronze_zcta_county_mappings (one primary county per ZCTA)

Output columns (mirroring the legacy zip_county_mapping.parquet):
- zcta: 5-digit ZIP Code Tabulation Area (primary identifier)
- county_geoid: 5-digit county FIPS code
- county_name: county name
- state_fips: 2-digit state FIPS (first 2 digits of county GEOID)
- population: population of the ZCTA-county overlap (optional)
- population_pct: population share of this county for the ZCTA

Usage:
    python -m ingestion.census.county_mappings
    python -m ingestion.census.county_mappings --truncate
    python -m ingestion.census.county_mappings --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded psycopg2/localhost credentials).
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import AsyncIterator

import pandas as pd
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


# Cache directory (where download_census_relationships.py saves files) and the
# pipe-delimited ZCTA-to-county relationship file produced there.
CACHE_DIR = Path("data/cache/census_relationships")
INPUT_FILENAME = "zcta_to_county.txt"


def find_input_file() -> Path:
    """Locate the cached ZCTA-to-county relationship file.

    Raises FileNotFoundError if the download has not been run yet.
    """
    input_file = CACHE_DIR / INPUT_FILENAME
    if not input_file.exists():
        raise FileNotFoundError(
            f"{input_file} not found. "
            "Run download_census_relationships.py first."
        )
    return input_file


def process_zcta_to_county(df: pd.DataFrame) -> pd.DataFrame | None:
    """Process ZCTA (ZIP Code Tabulation Area) to County relationships.

    Preserved verbatim (minus pandas read/write IO) from the legacy
    process_zcta_to_county(): map columns, compute the primary (highest
    population share) county per ZCTA, and return the result frame with columns
    zcta, county_geoid, county_name, state_fips, population_pct (and population
    when available). Returns None if required columns are missing.
    """
    # Rename columns (adapt to actual column names)
    column_mapping = {}
    for col in df.columns:
        if 'ZCTA' in col and 'GEOID' in col:
            column_mapping[col] = 'zcta'
        elif 'COUNTY' in col and 'GEOID' in col:
            column_mapping[col] = 'county_geoid'
        elif 'COUNTY' in col and 'NAME' in col:
            column_mapping[col] = 'county_name'
        elif col == 'POPPT':
            column_mapping[col] = 'population'

    df = df.rename(columns=column_mapping)

    # Check if we got the required columns
    required = ['zcta', 'county_geoid', 'county_name']
    missing = [c for c in required if c not in df.columns]
    if missing:
        return None

    # Convert population to numeric if available
    if 'population' in df.columns:
        df['population'] = pd.to_numeric(df['population'], errors='coerce').fillna(0)

        # Calculate population percentage for each ZCTA-county pair
        zcta_totals = df.groupby('zcta')['population'].sum().reset_index()
        zcta_totals.columns = ['zcta', 'total_population']
        df = df.merge(zcta_totals, on='zcta')
        df['population_pct'] = (df['population'] / df['total_population'] * 100).round(2)

        # For each ZCTA, keep the county with the highest population share
        df = df.sort_values('population_pct', ascending=False)
        df_primary = df.groupby('zcta').first().reset_index()
    else:
        # No population data, just take first county per ZCTA
        df_primary = df.groupby('zcta').first().reset_index()
        df_primary['population_pct'] = 100.0

    # Extract state FIPS from county GEOID (first 2 digits)
    df_primary['state_fips'] = df_primary['county_geoid'].str[:2]

    # Select columns
    result_columns = ['zcta', 'county_geoid', 'county_name', 'state_fips', 'population_pct']
    if 'population' in df_primary.columns:
        result_columns.insert(4, 'population')

    return df_primary[result_columns]


class CountyMappingRow(RawRow):
    """One primary ZCTA -> county mapping, validated before upsert."""

    zcta: str = Field(min_length=1, max_length=10)
    county_geoid: str = Field(min_length=1, max_length=5)
    county_name: str | None = Field(default=None, max_length=255)
    state_fips: str | None = Field(default=None, max_length=2)
    population: float | None = None
    population_pct: float | None = None


_UPSERT_SQL = text(
    """
    INSERT INTO bronze_zcta_county_mappings
        (zcta, county_geoid, county_name, state_fips, population, population_pct)
    VALUES
        (:zcta, :county_geoid, :county_name, :state_fips, :population, :population_pct)
    ON CONFLICT (zcta) DO UPDATE SET
        county_geoid   = EXCLUDED.county_geoid,
        county_name    = EXCLUDED.county_name,
        state_fips     = EXCLUDED.state_fips,
        population     = EXCLUDED.population,
        population_pct = EXCLUDED.population_pct,
        ingestion_date = NOW()
    """
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze_zcta_county_mappings")


class CensusCountyMappingsPipeline(DataSourcePipeline[CountyMappingRow]):
    source = "census_county_mappings"
    batch_size = 1_000
    row_schema = CountyMappingRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or find_input_file()

        # Read the pipe-delimited file (all string dtype, as in the legacy loader).
        df = pd.read_csv(path, sep='|', dtype=str, low_memory=False)
        result = process_zcta_to_county(df)
        if result is None:
            return

        has_population = 'population' in result.columns
        emitted = 0
        for _, row in result.iterrows():
            if self._limit is not None and emitted >= self._limit:
                return

            zcta = row['zcta']
            county_geoid = row['county_geoid']

            yield {
                "source": self.source,
                "source_version": "2020",
                "natural_key": f"zcta:{zcta}",
                "zcta": zcta,
                "county_geoid": county_geoid,
                "county_name": row.get('county_name'),
                "state_fips": row.get('state_fips'),
                "population": float(row['population']) if has_population else None,
                "population_pct": (
                    float(row['population_pct'])
                    if row.get('population_pct') is not None
                    else None
                ),
            }
            emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[CountyMappingRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "zcta": r.zcta,
                "county_geoid": r.county_geoid,
                "county_name": r.county_name,
                "state_fips": r.state_fips,
                "population": r.population,
                "population_pct": r.population_pct,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    # The legacy loader emitted a parquet file and defined no Postgres DDL; the
    # bronze_zcta_county_mappings table is created by upstream migrations, so this
    # loader only optionally truncates.
    if truncate:
        async with async_session() as session:
            await session.execute(_TRUNCATE_SQL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load Census ZCTA-to-county mappings into bronze_zcta_county_mappings"
    )
    parser.add_argument(
        "--file", type=Path,
        help="Path to ZCTA relationship file (default: data/cache/census_relationships/zcta_to_county.txt)",
    )
    parser.add_argument("--limit", type=int, help="Limit number of records (for testing)")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = CensusCountyMappingsPipeline(path=args.file, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
