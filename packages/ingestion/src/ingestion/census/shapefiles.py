#!/usr/bin/env python3
"""Census TIGER/Line shapefiles pipeline: load cached shapefiles into bronze geometry tables.

Ported from load_census_shapefiles.py to the core_lib DataSourcePipeline contract.

Reads cached shapefiles from data/cache/census/shapefiles/{year}/ and loads into:
  states    -> bronze.bronze_geo_states
  counties  -> bronze.bronze_geo_counties
  places    -> bronze.bronze_geo_places
  zcta      -> bronze.bronze_geo_zcta

Geometry is stored as WKT text (EPSG:4269 / NAD83, as shipped by Census).
Run download_census_shapefiles.py first to populate the cache.

Usage:
    python -m ingestion.census.shapefiles
    python -m ingestion.census.shapefiles --year 2023
    python -m ingestion.census.shapefiles --types states counties
    python -m ingestion.census.shapefiles --truncate
    python -m ingestion.census.shapefiles --limit 100

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433/open_navigator).
"""
from __future__ import annotations

import argparse
import asyncio
import zipfile
from pathlib import Path
from typing import Any, AsyncIterator

from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/census/shapefiles")
BATCH_SIZE = 500

# ZIP filename patterns per type (formatted with year)
ZIP_PATTERNS = {
    "states":   "cb_{year}_us_state_500k.zip",
    "counties": "cb_{year}_us_county_500k.zip",
    "places":   "cb_{year}_us_place_500k.zip",
    "zcta":     "tl_{year}_us_zcta520.zip",
}

# Per-type config: target table, geoid source column, DDL (split into a CREATE
# TABLE statement plus separate CREATE INDEX statements), the upsert SQL, and a
# row_fn producing the bound-parameter dict for a single GeoDataFrame row.
TYPES: dict[str, dict[str, Any]] = {
    "states": {
        "table": "bronze.bronze_geo_states",
        "geoid_col": "GEOID",
        "create_table": text(
            """
            CREATE TABLE IF NOT EXISTS bronze.bronze_geo_states (
                geoid          VARCHAR(2)    PRIMARY KEY,
                statefp        VARCHAR(2),
                statens        VARCHAR(8),
                geoidfq        VARCHAR(30),
                stusps         VARCHAR(2),
                name           VARCHAR(100),
                lsad           VARCHAR(2),
                aland          BIGINT,
                awater         BIGINT,
                geom_wkt       TEXT,
                vintage_year   VARCHAR(4),
                ingestion_date TIMESTAMP DEFAULT NOW()
            )
            """
        ),
        "indexes": (),
        "upsert": text(
            """
            INSERT INTO bronze.bronze_geo_states
                (geoid, statefp, statens, geoidfq, stusps, name, lsad, aland, awater,
                 geom_wkt, vintage_year)
            VALUES (:geoid, :statefp, :statens, :geoidfq, :stusps, :name, :lsad,
                    :aland, :awater, :geom_wkt, :vintage_year)
            ON CONFLICT (geoid) DO UPDATE SET
                statefp        = EXCLUDED.statefp,
                statens        = EXCLUDED.statens,
                geoidfq        = EXCLUDED.geoidfq,
                stusps         = EXCLUDED.stusps,
                name           = EXCLUDED.name,
                lsad           = EXCLUDED.lsad,
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                geom_wkt       = EXCLUDED.geom_wkt,
                vintage_year   = EXCLUDED.vintage_year,
                ingestion_date = NOW()
            """
        ),
        "row_fn": lambda row, year: {
            "geoid": row["GEOID"],
            "statefp": row["STATEFP"],
            "statens": row.get("STATENS"),
            "geoidfq": row.get("GEOIDFQ"),
            "stusps": row["STUSPS"],
            "name": row["NAME"],
            "lsad": row.get("LSAD"),
            "aland": int(row["ALAND"]) if row["ALAND"] is not None else None,
            "awater": int(row["AWATER"]) if row["AWATER"] is not None else None,
            "geom_wkt": row["geometry"].wkt if row["geometry"] is not None else None,
            "vintage_year": str(year),
        },
    },

    "counties": {
        "table": "bronze.bronze_geo_counties",
        "geoid_col": "GEOID",
        "create_table": text(
            """
            CREATE TABLE IF NOT EXISTS bronze.bronze_geo_counties (
                geoid          VARCHAR(5)    PRIMARY KEY,
                statefp        VARCHAR(2),
                countyfp       VARCHAR(3),
                countyns       VARCHAR(8),
                geoidfq        VARCHAR(30),
                name           VARCHAR(100),
                namelsad       VARCHAR(120),
                stusps         VARCHAR(2),
                state_name     VARCHAR(100),
                lsad           VARCHAR(2),
                aland          BIGINT,
                awater         BIGINT,
                geom_wkt       TEXT,
                vintage_year   VARCHAR(4),
                ingestion_date TIMESTAMP DEFAULT NOW()
            )
            """
        ),
        "indexes": (
            text("CREATE INDEX IF NOT EXISTS idx_bgco_statefp ON bronze.bronze_geo_counties(statefp)"),
            text("CREATE INDEX IF NOT EXISTS idx_bgco_stusps  ON bronze.bronze_geo_counties(stusps)"),
        ),
        "upsert": text(
            """
            INSERT INTO bronze.bronze_geo_counties
                (geoid, statefp, countyfp, countyns, geoidfq, name, namelsad,
                 stusps, state_name, lsad, aland, awater, geom_wkt, vintage_year)
            VALUES (:geoid, :statefp, :countyfp, :countyns, :geoidfq, :name,
                    :namelsad, :stusps, :state_name, :lsad, :aland, :awater,
                    :geom_wkt, :vintage_year)
            ON CONFLICT (geoid) DO UPDATE SET
                statefp        = EXCLUDED.statefp,
                countyfp       = EXCLUDED.countyfp,
                countyns       = EXCLUDED.countyns,
                geoidfq        = EXCLUDED.geoidfq,
                name           = EXCLUDED.name,
                namelsad       = EXCLUDED.namelsad,
                stusps         = EXCLUDED.stusps,
                state_name     = EXCLUDED.state_name,
                lsad           = EXCLUDED.lsad,
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                geom_wkt       = EXCLUDED.geom_wkt,
                vintage_year   = EXCLUDED.vintage_year,
                ingestion_date = NOW()
            """
        ),
        "row_fn": lambda row, year: {
            "geoid": row["GEOID"],
            "statefp": row["STATEFP"],
            "countyfp": row.get("COUNTYFP"),
            "countyns": row.get("COUNTYNS"),
            "geoidfq": row.get("GEOIDFQ"),
            "name": row["NAME"],
            "namelsad": row.get("NAMELSAD"),
            "stusps": row.get("STUSPS"),
            "state_name": row.get("STATE_NAME"),
            "lsad": row.get("LSAD"),
            "aland": int(row["ALAND"]) if row["ALAND"] is not None else None,
            "awater": int(row["AWATER"]) if row["AWATER"] is not None else None,
            "geom_wkt": row["geometry"].wkt if row["geometry"] is not None else None,
            "vintage_year": str(year),
        },
    },

    "places": {
        "table": "bronze.bronze_geo_places",
        "geoid_col": "GEOID",
        "create_table": text(
            """
            CREATE TABLE IF NOT EXISTS bronze.bronze_geo_places (
                geoid          VARCHAR(7)    PRIMARY KEY,
                statefp        VARCHAR(2),
                placefp        VARCHAR(5),
                placens        VARCHAR(8),
                geoidfq        VARCHAR(30),
                name           VARCHAR(100),
                namelsad       VARCHAR(120),
                stusps         VARCHAR(2),
                state_name     VARCHAR(100),
                lsad           VARCHAR(2),
                aland          BIGINT,
                awater         BIGINT,
                geom_wkt       TEXT,
                vintage_year   VARCHAR(4),
                ingestion_date TIMESTAMP DEFAULT NOW()
            )
            """
        ),
        "indexes": (
            text("CREATE INDEX IF NOT EXISTS idx_bgpl_statefp ON bronze.bronze_geo_places(statefp)"),
            text("CREATE INDEX IF NOT EXISTS idx_bgpl_stusps  ON bronze.bronze_geo_places(stusps)"),
        ),
        "upsert": text(
            """
            INSERT INTO bronze.bronze_geo_places
                (geoid, statefp, placefp, placens, geoidfq, name, namelsad,
                 stusps, state_name, lsad, aland, awater, geom_wkt, vintage_year)
            VALUES (:geoid, :statefp, :placefp, :placens, :geoidfq, :name,
                    :namelsad, :stusps, :state_name, :lsad, :aland, :awater,
                    :geom_wkt, :vintage_year)
            ON CONFLICT (geoid) DO UPDATE SET
                statefp        = EXCLUDED.statefp,
                placefp        = EXCLUDED.placefp,
                placens        = EXCLUDED.placens,
                geoidfq        = EXCLUDED.geoidfq,
                name           = EXCLUDED.name,
                namelsad       = EXCLUDED.namelsad,
                stusps         = EXCLUDED.stusps,
                state_name     = EXCLUDED.state_name,
                lsad           = EXCLUDED.lsad,
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                geom_wkt       = EXCLUDED.geom_wkt,
                vintage_year   = EXCLUDED.vintage_year,
                ingestion_date = NOW()
            """
        ),
        "row_fn": lambda row, year: {
            "geoid": row["GEOID"],
            "statefp": row["STATEFP"],
            "placefp": row.get("PLACEFP"),
            "placens": row.get("PLACENS"),
            "geoidfq": row.get("GEOIDFQ"),
            "name": row["NAME"],
            "namelsad": row.get("NAMELSAD"),
            "stusps": row.get("STUSPS"),
            "state_name": row.get("STATE_NAME"),
            "lsad": row.get("LSAD"),
            "aland": int(row["ALAND"]) if row["ALAND"] is not None else None,
            "awater": int(row["AWATER"]) if row["AWATER"] is not None else None,
            "geom_wkt": row["geometry"].wkt if row["geometry"] is not None else None,
            "vintage_year": str(year),
        },
    },

    "zcta": {
        "table": "bronze.bronze_geo_zcta",
        "geoid_col": "GEOID20",
        "create_table": text(
            """
            CREATE TABLE IF NOT EXISTS bronze.bronze_geo_zcta (
                geoid20        VARCHAR(5)    PRIMARY KEY,
                zcta5ce20      VARCHAR(5),
                geoidfq20      VARCHAR(30),
                classfp20      VARCHAR(2),
                mtfcc20        VARCHAR(5),
                funcstat20     VARCHAR(1),
                aland20        BIGINT,
                awater20       BIGINT,
                intptlat20     NUMERIC(11,8),
                intptlon20     NUMERIC(12,8),
                geom_wkt       TEXT,
                vintage_year   VARCHAR(4),
                ingestion_date TIMESTAMP DEFAULT NOW()
            )
            """
        ),
        "indexes": (),
        "upsert": text(
            """
            INSERT INTO bronze.bronze_geo_zcta
                (geoid20, zcta5ce20, geoidfq20, classfp20, mtfcc20, funcstat20,
                 aland20, awater20, intptlat20, intptlon20, geom_wkt, vintage_year)
            VALUES (:geoid20, :zcta5ce20, :geoidfq20, :classfp20, :mtfcc20,
                    :funcstat20, :aland20, :awater20, :intptlat20, :intptlon20,
                    :geom_wkt, :vintage_year)
            ON CONFLICT (geoid20) DO UPDATE SET
                zcta5ce20      = EXCLUDED.zcta5ce20,
                geoidfq20      = EXCLUDED.geoidfq20,
                classfp20      = EXCLUDED.classfp20,
                mtfcc20        = EXCLUDED.mtfcc20,
                funcstat20     = EXCLUDED.funcstat20,
                aland20        = EXCLUDED.aland20,
                awater20       = EXCLUDED.awater20,
                intptlat20     = EXCLUDED.intptlat20,
                intptlon20     = EXCLUDED.intptlon20,
                geom_wkt       = EXCLUDED.geom_wkt,
                vintage_year   = EXCLUDED.vintage_year,
                ingestion_date = NOW()
            """
        ),
        "row_fn": lambda row, year: {
            "geoid20": row["GEOID20"],
            "zcta5ce20": row.get("ZCTA5CE20"),
            "geoidfq20": row.get("GEOIDFQ20"),
            "classfp20": row.get("CLASSFP20"),
            "mtfcc20": row.get("MTFCC20"),
            "funcstat20": row.get("FUNCSTAT20"),
            "aland20": int(row["ALAND20"]) if row.get("ALAND20") is not None else None,
            "awater20": int(row["AWATER20"]) if row.get("AWATER20") is not None else None,
            "intptlat20": float(row["INTPTLAT20"]) if row.get("INTPTLAT20") is not None else None,
            "intptlon20": float(row["INTPTLON20"]) if row.get("INTPTLON20") is not None else None,
            "geom_wkt": row["geometry"].wkt if row["geometry"] is not None else None,
            "vintage_year": str(year),
        },
    },
}


def find_shp(year: int, shapefile_type: str) -> Path | None:
    """Return path to .shp file for the given type/year, extracting ZIP if needed."""
    zip_name = ZIP_PATTERNS[shapefile_type].format(year=year)
    year_dir = CACHE_DIR / str(year)
    zip_path = year_dir / zip_name
    extract_dir = year_dir / zip_path.stem

    if not zip_path.exists():
        logger.error(f"ZIP not found: {zip_path}")
        logger.error(f"Run: python scripts/datasources/census/download_census_shapefiles.py --year {year} --types {shapefile_type}")
        return None

    if not extract_dir.exists():
        logger.info(f"Extracting {zip_name}...")
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
        logger.info(f"Extracted to {extract_dir}")

    shp_files = list(extract_dir.glob("*.shp"))
    if not shp_files:
        logger.error(f"No .shp file found in {extract_dir}")
        return None

    return shp_files[0]


class ShapefileRow(RawRow):
    """One Census TIGER/Line geometry row, validated before upsert.

    The four shapefile types (states / counties / places / zcta) target distinct
    bronze tables with disjoint column sets, so this envelope carries the type
    discriminator + resolved target table plus the ordered upsert parameter dict
    (column name -> value). Geometry is stored as WKT text in `values["geom_wkt"]`.
    """

    shapefile_type: str = Field(min_length=1)
    table: str = Field(min_length=1)
    values: dict[str, Any]


class CensusShapefilesPipeline(DataSourcePipeline[ShapefileRow]):
    source = "census_shapefiles"
    batch_size = BATCH_SIZE
    row_schema = ShapefileRow

    def __init__(
        self,
        *,
        year: int = 2025,
        types: list[str] | None = None,
        path: Path | None = None,
        limit: int | None = None,
    ):
        self._year = year
        self._types = types or list(TYPES.keys())
        self._path = path
        self._limit = limit

    def _resolve_shp(self, shapefile_type: str) -> Path | None:
        """Resolve the .shp path for a type, honoring an explicit override path."""
        if self._path is not None:
            return self._path
        return find_shp(self._year, shapefile_type)

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        for shapefile_type in self._types:
            cfg = TYPES[shapefile_type]
            table = cfg["table"]
            logger.info(f"--- {shapefile_type.upper()} -> {table} ---")

            shp_path = self._resolve_shp(shapefile_type)
            if shp_path is None:
                continue

            logger.info(f"Reading {shp_path.name}...")
            import geopandas as gpd  # lazy: geopandas is an optional heavy dep

            gdf = gpd.read_file(shp_path)

            if self._limit:
                gdf = gdf.head(self._limit)

            total = len(gdf)
            logger.info(f"Rows: {total:,}  |  CRS: {gdf.crs}")

            row_fn = cfg["row_fn"]
            geoid_col = cfg["geoid_col"]
            for _, row in gdf.iterrows():
                values = row_fn(row, self._year)
                yield {
                    "source": self.source,
                    "source_version": str(self._year),
                    "natural_key": f"{shapefile_type}:{row[geoid_col]}",
                    "shapefile_type": shapefile_type,
                    "table": table,
                    "values": values,
                }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[ShapefileRow],
        ctx: PipelineContext,
    ) -> None:
        # Group by shapefile type so each upsert runs against its own table with
        # a homogeneous parameter set (executemany under the hood).
        by_type: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            by_type.setdefault(r.shapefile_type, []).append(r.values)
        for shapefile_type, params in by_type.items():
            await session.execute(TYPES[shapefile_type]["upsert"], params)


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")


async def _prepare_target(types: list[str], truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        for shapefile_type in types:
            cfg = TYPES[shapefile_type]
            await session.execute(cfg["create_table"])
            for idx in cfg["indexes"]:
                await session.execute(idx)
            if truncate:
                await session.execute(text(f"TRUNCATE TABLE {cfg['table']}"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load Census TIGER/Line shapefiles into bronze geometry tables",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Load all types for default year (2025):
    python -m ingestion.census.shapefiles

  Load 2023 states and counties:
    python -m ingestion.census.shapefiles --year 2023 --types states counties

  Truncate and reload:
    python -m ingestion.census.shapefiles --truncate

  Load only the first 100 rows (testing):
    python -m ingestion.census.shapefiles --limit 100
        """,
    )
    parser.add_argument("--year", type=int, default=2025, help="Shapefile vintage year (default: 2025)")
    parser.add_argument(
        "--types", nargs="+", choices=list(TYPES.keys()),
        default=list(TYPES.keys()),
        help="Shapefile types to load (default: all)",
    )
    parser.add_argument("--truncate", action="store_true", help="TRUNCATE table before loading")
    parser.add_argument("--limit", type=int, default=None, help="Load only the first N rows (for testing)")
    return parser


async def _run(args: argparse.Namespace) -> None:
    logger.info("=" * 70)
    logger.info("CENSUS SHAPEFILE LOADER")
    logger.info(f"  year={args.year}  types={args.types}  truncate={args.truncate}")
    logger.info("=" * 70)

    await _prepare_target(args.types, args.truncate)
    pipeline = CensusShapefilesPipeline(
        year=args.year, types=args.types, limit=args.limit
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
