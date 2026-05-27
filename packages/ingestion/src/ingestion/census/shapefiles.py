#!/usr/bin/env python3
"""
Load Census TIGER/Line Shapefiles into bronze geometry tables.

Reads cached shapefiles from data/cache/census/shapefiles/{year}/ and loads into:
  states    → bronze.bronze_geo_states
  counties  → bronze.bronze_geo_counties
  places    → bronze.bronze_geo_places
  zcta      → bronze.bronze_geo_zcta

Geometry is stored as WKT text (EPSG:4269 / NAD83, as shipped by Census).
Run download_census_shapefiles.py first to populate the cache.

Usage:
    python scripts/datasources/census/load_census_shapefiles.py
    python scripts/datasources/census/load_census_shapefiles.py --year 2023
    python scripts/datasources/census/load_census_shapefiles.py --types states counties
    python scripts/datasources/census/load_census_shapefiles.py --truncate
    python scripts/datasources/census/load_census_shapefiles.py --dry-run
    python scripts/datasources/census/load_census_shapefiles.py --limit 100
"""
import argparse
import os
import zipfile
from pathlib import Path

import geopandas as gpd
import psycopg2
from psycopg2.extras import execute_batch
from loguru import logger


CACHE_DIR = Path("data/cache/census/shapefiles")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DATABASE_URL = f"postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator"
BATCH_SIZE = 500

# ZIP filename patterns per type (formatted with year)
ZIP_PATTERNS = {
    "states":   "cb_{year}_us_state_500k.zip",
    "counties": "cb_{year}_us_county_500k.zip",
    "places":   "cb_{year}_us_place_500k.zip",
    "zcta":     "tl_{year}_us_zcta520.zip",
}

TYPES = {
    "states": {
        "table": "bronze.bronze_geo_states",
        "geoid_col": "GEOID",
        "ddl": """
            CREATE SCHEMA IF NOT EXISTS bronze;
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
            );
        """,
        "insert": """
            INSERT INTO bronze.bronze_geo_states
                (geoid, statefp, statens, geoidfq, stusps, name, lsad, aland, awater,
                 geom_wkt, vintage_year)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
        """,
        "row_fn": lambda row, year: (
            row["GEOID"], row["STATEFP"], row.get("STATENS"), row.get("GEOIDFQ"),
            row["STUSPS"], row["NAME"], row.get("LSAD"),
            int(row["ALAND"]) if row["ALAND"] is not None else None,
            int(row["AWATER"]) if row["AWATER"] is not None else None,
            row["geometry"].wkt if row["geometry"] is not None else None,
            str(year),
        ),
    },

    "counties": {
        "table": "bronze.bronze_geo_counties",
        "geoid_col": "GEOID",
        "ddl": """
            CREATE SCHEMA IF NOT EXISTS bronze;
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
            );
            CREATE INDEX IF NOT EXISTS idx_bgco_statefp ON bronze.bronze_geo_counties(statefp);
            CREATE INDEX IF NOT EXISTS idx_bgco_stusps  ON bronze.bronze_geo_counties(stusps);
        """,
        "insert": """
            INSERT INTO bronze.bronze_geo_counties
                (geoid, statefp, countyfp, countyns, geoidfq, name, namelsad,
                 stusps, state_name, lsad, aland, awater, geom_wkt, vintage_year)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
        """,
        "row_fn": lambda row, year: (
            row["GEOID"], row["STATEFP"], row.get("COUNTYFP"), row.get("COUNTYNS"),
            row.get("GEOIDFQ"), row["NAME"], row.get("NAMELSAD"),
            row.get("STUSPS"), row.get("STATE_NAME"), row.get("LSAD"),
            int(row["ALAND"]) if row["ALAND"] is not None else None,
            int(row["AWATER"]) if row["AWATER"] is not None else None,
            row["geometry"].wkt if row["geometry"] is not None else None,
            str(year),
        ),
    },

    "places": {
        "table": "bronze.bronze_geo_places",
        "geoid_col": "GEOID",
        "ddl": """
            CREATE SCHEMA IF NOT EXISTS bronze;
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
            );
            CREATE INDEX IF NOT EXISTS idx_bgpl_statefp ON bronze.bronze_geo_places(statefp);
            CREATE INDEX IF NOT EXISTS idx_bgpl_stusps  ON bronze.bronze_geo_places(stusps);
        """,
        "insert": """
            INSERT INTO bronze.bronze_geo_places
                (geoid, statefp, placefp, placens, geoidfq, name, namelsad,
                 stusps, state_name, lsad, aland, awater, geom_wkt, vintage_year)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
        """,
        "row_fn": lambda row, year: (
            row["GEOID"], row["STATEFP"], row.get("PLACEFP"), row.get("PLACENS"),
            row.get("GEOIDFQ"), row["NAME"], row.get("NAMELSAD"),
            row.get("STUSPS"), row.get("STATE_NAME"), row.get("LSAD"),
            int(row["ALAND"]) if row["ALAND"] is not None else None,
            int(row["AWATER"]) if row["AWATER"] is not None else None,
            row["geometry"].wkt if row["geometry"] is not None else None,
            str(year),
        ),
    },

    "zcta": {
        "table": "bronze.bronze_geo_zcta",
        "geoid_col": "GEOID20",
        "ddl": """
            CREATE SCHEMA IF NOT EXISTS bronze;
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
            );
        """,
        "insert": """
            INSERT INTO bronze.bronze_geo_zcta
                (geoid20, zcta5ce20, geoidfq20, classfp20, mtfcc20, funcstat20,
                 aland20, awater20, intptlat20, intptlon20, geom_wkt, vintage_year)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
        """,
        "row_fn": lambda row, year: (
            row["GEOID20"], row.get("ZCTA5CE20"), row.get("GEOIDFQ20"),
            row.get("CLASSFP20"), row.get("MTFCC20"), row.get("FUNCSTAT20"),
            int(row["ALAND20"]) if row.get("ALAND20") is not None else None,
            int(row["AWATER20"]) if row.get("AWATER20") is not None else None,
            float(row["INTPTLAT20"]) if row.get("INTPTLAT20") is not None else None,
            float(row["INTPTLON20"]) if row.get("INTPTLON20") is not None else None,
            row["geometry"].wkt if row["geometry"] is not None else None,
            str(year),
        ),
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


def load_shapefile(
    shapefile_type: str,
    year: int,
    conn,
    truncate: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict:
    cfg = TYPES[shapefile_type]
    table = cfg["table"]

    logger.info(f"--- {shapefile_type.upper()} → {table} ---")

    shp_path = find_shp(year, shapefile_type)
    if shp_path is None:
        return {"type": shapefile_type, "ok": False, "loaded": 0, "skipped": 0}

    logger.info(f"Reading {shp_path.name}...")
    gdf = gpd.read_file(shp_path)

    if limit:
        gdf = gdf.head(limit)

    total = len(gdf)
    logger.info(f"Rows: {total:,}  |  CRS: {gdf.crs}")

    if dry_run:
        logger.info(f"[dry-run] Would load {total:,} rows into {table}")
        return {"type": shapefile_type, "ok": True, "loaded": 0, "skipped": total}

    cur = conn.cursor()

    # Create table
    cur.execute(cfg["ddl"])

    if truncate:
        cur.execute(f"TRUNCATE TABLE {table}")
        logger.info(f"Truncated {table}")

    conn.commit()

    # Build rows
    row_fn = cfg["row_fn"]
    rows = [row_fn(row, year) for _, row in gdf.iterrows()]

    execute_batch(cur, cfg["insert"], rows, page_size=BATCH_SIZE)
    conn.commit()
    cur.close()

    logger.success(f"Loaded {total:,} rows → {table}")
    return {"type": shapefile_type, "ok": True, "loaded": total, "skipped": 0}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load Census TIGER/Line shapefiles into bronze geometry tables",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Load all types for default year (2025):
    python scripts/datasources/census/load_census_shapefiles.py

  Load 2023 states and counties:
    python scripts/datasources/census/load_census_shapefiles.py --year 2023 --types states counties

  Truncate and reload:
    python scripts/datasources/census/load_census_shapefiles.py --truncate

  Preview without writing:
    python scripts/datasources/census/load_census_shapefiles.py --dry-run
        """,
    )
    parser.add_argument("--year", type=int, default=2025, help="Shapefile vintage year (default: 2025)")
    parser.add_argument(
        "--types", nargs="+", choices=list(TYPES.keys()),
        default=list(TYPES.keys()),
        help="Shapefile types to load (default: all)",
    )
    parser.add_argument("--truncate", action="store_true", help="TRUNCATE table before loading")
    parser.add_argument("--dry-run", action="store_true", help="Parse files but skip DB writes")
    parser.add_argument("--limit", type=int, default=None, help="Load only the first N rows (for testing)")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("CENSUS SHAPEFILE LOADER")
    logger.info(f"  year={args.year}  types={args.types}  truncate={args.truncate}  dry_run={args.dry_run}")
    logger.info("=" * 70)

    conn = None if args.dry_run else psycopg2.connect(DATABASE_URL)

    results = []
    for shapefile_type in args.types:
        try:
            result = load_shapefile(
                shapefile_type, args.year, conn,
                truncate=args.truncate,
                dry_run=args.dry_run,
                limit=args.limit,
            )
        except Exception as e:
            logger.error(f"{shapefile_type}: {e}")
            if conn:
                conn.rollback()
            results.append({"type": shapefile_type, "ok": False, "loaded": 0, "skipped": 0})
            continue
        results.append(result)

    if conn:
        conn.close()

    logger.info("")
    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    failed = 0
    for r in results:
        status = "OK" if r["ok"] else "FAIL"
        logger.info(f"  {status:<6}  {r['type']:<10}  loaded={r['loaded']:>8,}  skipped={r['skipped']:>8,}")
        if not r["ok"]:
            failed += 1

    if failed:
        logger.error(f"{failed} type(s) failed")
        return 1

    logger.success("Done")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
