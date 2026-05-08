#!/usr/bin/env python3
"""
Load Census Gazetteer data into bronze jurisdiction tables.

Reads cached CSVs from data/cache/census/gazetteer/ and loads into:
  states                → bronze.bronze_jurisdictions_states
  counties              → bronze.bronze_jurisdictions_counties
  municipalities        → bronze.bronze_jurisdictions_municipalities
  school_districts      → bronze.bronze_jurisdictions_school_districts  (unified only)
  townships             → bronze.bronze_jurisdictions_townships
  zcta                  → bronze.bronze_jurisdictions_zcta

Run download_census_gazetteer.py first to populate the cache.

Usage:
    python3 scripts/datasources/census/load_census_gazetteer.py
    python3 scripts/datasources/census/load_census_gazetteer.py --types counties municipalities
    python3 scripts/datasources/census/load_census_gazetteer.py --limit 100
"""
import argparse
import os
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from loguru import logger


CACHE_DIR = Path("data/cache/census/gazetteer")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DATABASE_URL = f"postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator"

# Configuration for each jurisdiction type
TYPES = {
    "states": {
        "table": "bronze.bronze_jurisdictions_states",
        "cache_file": "states.csv",
        "geoid_len": 2,
        "ddl": """
            CREATE SCHEMA IF NOT EXISTS bronze;
            CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_states (
                geoid          VARCHAR(2)    PRIMARY KEY,
                usps           VARCHAR(2),
                ansicode       VARCHAR(8),
                name           VARCHAR(255),
                aland          BIGINT,
                awater         BIGINT,
                aland_sqmi     NUMERIC(12, 6),
                awater_sqmi    NUMERIC(12, 6),
                intptlat       NUMERIC(11, 8),
                intptlong      NUMERIC(12, 8),
                ingestion_date TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_bjs_usps   ON bronze.bronze_jurisdictions_states(usps);
            CREATE INDEX IF NOT EXISTS idx_bjs_coords ON bronze.bronze_jurisdictions_states(intptlat, intptlong);
        """,
        "insert": """
            INSERT INTO bronze.bronze_jurisdictions_states
                (geoid, usps, ansicode, name, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (geoid) DO UPDATE SET
                usps           = EXCLUDED.usps,
                ansicode       = EXCLUDED.ansicode,
                name           = EXCLUDED.name,
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                aland_sqmi     = EXCLUDED.aland_sqmi,
                awater_sqmi    = EXCLUDED.awater_sqmi,
                intptlat       = EXCLUDED.intptlat,
                intptlong      = EXCLUDED.intptlong,
                ingestion_date = NOW()
        """,
    },
    "counties": {
        "table": "bronze.bronze_jurisdictions_counties",
        "cache_file": "counties.csv",
        "geoid_len": 5,
        "ddl": """
            CREATE SCHEMA IF NOT EXISTS bronze;
            CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_counties (
                geoid          VARCHAR(5)    PRIMARY KEY,
                usps           VARCHAR(2),
                ansicode       VARCHAR(8),
                name           VARCHAR(255),
                aland          BIGINT,
                awater         BIGINT,
                aland_sqmi     NUMERIC(12, 6),
                awater_sqmi    NUMERIC(12, 6),
                intptlat       NUMERIC(11, 8),
                intptlong      NUMERIC(12, 8),
                ingestion_date TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_bjc_usps   ON bronze.bronze_jurisdictions_counties(usps);
            CREATE INDEX IF NOT EXISTS idx_bjc_coords ON bronze.bronze_jurisdictions_counties(intptlat, intptlong);
        """,
        "insert": """
            INSERT INTO bronze.bronze_jurisdictions_counties
                (geoid, usps, ansicode, name, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (geoid) DO UPDATE SET
                usps           = EXCLUDED.usps,
                ansicode       = EXCLUDED.ansicode,
                name           = EXCLUDED.name,
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                aland_sqmi     = EXCLUDED.aland_sqmi,
                awater_sqmi    = EXCLUDED.awater_sqmi,
                intptlat       = EXCLUDED.intptlat,
                intptlong      = EXCLUDED.intptlong,
                ingestion_date = NOW()
        """,
    },
    "municipalities": {
        "table": "bronze.bronze_jurisdictions_municipalities",
        "cache_file": "municipalities.csv",
        "geoid_len": 7,
        "ddl": """
            CREATE SCHEMA IF NOT EXISTS bronze;
            CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_municipalities (
                geoid          VARCHAR(7)    PRIMARY KEY,
                usps           VARCHAR(2),
                ansicode       VARCHAR(8),
                name           VARCHAR(255),
                lsad           VARCHAR(5),
                funcstat       VARCHAR(1),
                aland          BIGINT,
                awater         BIGINT,
                aland_sqmi     NUMERIC(12, 6),
                awater_sqmi    NUMERIC(12, 6),
                intptlat       NUMERIC(11, 8),
                intptlong      NUMERIC(12, 8),
                ingestion_date TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_bjm_usps     ON bronze.bronze_jurisdictions_municipalities(usps);
            CREATE INDEX IF NOT EXISTS idx_bjm_lsad     ON bronze.bronze_jurisdictions_municipalities(lsad);
            CREATE INDEX IF NOT EXISTS idx_bjm_funcstat ON bronze.bronze_jurisdictions_municipalities(funcstat);
            CREATE INDEX IF NOT EXISTS idx_bjm_coords   ON bronze.bronze_jurisdictions_municipalities(intptlat, intptlong);
        """,
        "insert": """
            INSERT INTO bronze.bronze_jurisdictions_municipalities
                (geoid, usps, ansicode, name, lsad, funcstat, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (geoid) DO UPDATE SET
                usps           = EXCLUDED.usps,
                ansicode       = EXCLUDED.ansicode,
                name           = EXCLUDED.name,
                lsad           = EXCLUDED.lsad,
                funcstat       = EXCLUDED.funcstat,
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                aland_sqmi     = EXCLUDED.aland_sqmi,
                awater_sqmi    = EXCLUDED.awater_sqmi,
                intptlat       = EXCLUDED.intptlat,
                intptlong      = EXCLUDED.intptlong,
                ingestion_date = NOW()
        """,
    },
    "school_districts": {
        "table": "bronze.bronze_jurisdictions_school_districts",
        "cache_file": "school_districts_unified.csv",
        "geoid_len": 7,
        "ddl": """
            CREATE SCHEMA IF NOT EXISTS bronze;
            CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_school_districts (
                geoid          VARCHAR(7)    PRIMARY KEY,
                usps           VARCHAR(2),
                name           VARCHAR(255),
                lograde        VARCHAR(5),
                higrade        VARCHAR(5),
                aland          BIGINT,
                awater         BIGINT,
                aland_sqmi     NUMERIC(12, 6),
                awater_sqmi    NUMERIC(12, 6),
                intptlat       NUMERIC(11, 8),
                intptlong      NUMERIC(12, 8),
                ingestion_date TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_bjsd_usps   ON bronze.bronze_jurisdictions_school_districts(usps);
            CREATE INDEX IF NOT EXISTS idx_bjsd_coords ON bronze.bronze_jurisdictions_school_districts(intptlat, intptlong);
        """,
        "insert": """
            INSERT INTO bronze.bronze_jurisdictions_school_districts
                (geoid, usps, name, lograde, higrade, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (geoid) DO UPDATE SET
                usps           = EXCLUDED.usps,
                name           = EXCLUDED.name,
                lograde        = EXCLUDED.lograde,
                higrade        = EXCLUDED.higrade,
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                aland_sqmi     = EXCLUDED.aland_sqmi,
                awater_sqmi    = EXCLUDED.awater_sqmi,
                intptlat       = EXCLUDED.intptlat,
                intptlong      = EXCLUDED.intptlong,
                ingestion_date = NOW()
        """,
    },
    "townships": {
        "table": "bronze.bronze_jurisdictions_townships",
        "cache_file": "townships.csv",
        "geoid_len": 10,
        "ddl": """
            CREATE SCHEMA IF NOT EXISTS bronze;
            CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_townships (
                geoid          VARCHAR(10)   PRIMARY KEY,
                usps           VARCHAR(2),
                ansicode       VARCHAR(8),
                name           VARCHAR(255),
                funcstat       VARCHAR(1),
                aland          BIGINT,
                awater         BIGINT,
                aland_sqmi     NUMERIC(12, 6),
                awater_sqmi    NUMERIC(12, 6),
                intptlat       NUMERIC(11, 8),
                intptlong      NUMERIC(12, 8),
                ingestion_date TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_bjt_usps     ON bronze.bronze_jurisdictions_townships(usps);
            CREATE INDEX IF NOT EXISTS idx_bjt_funcstat ON bronze.bronze_jurisdictions_townships(funcstat);
            CREATE INDEX IF NOT EXISTS idx_bjt_coords   ON bronze.bronze_jurisdictions_townships(intptlat, intptlong);
        """,
        "insert": """
            INSERT INTO bronze.bronze_jurisdictions_townships
                (geoid, usps, ansicode, name, funcstat, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (geoid) DO UPDATE SET
                usps           = EXCLUDED.usps,
                ansicode       = EXCLUDED.ansicode,
                name           = EXCLUDED.name,
                funcstat       = EXCLUDED.funcstat,
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                aland_sqmi     = EXCLUDED.aland_sqmi,
                awater_sqmi    = EXCLUDED.awater_sqmi,
                intptlat       = EXCLUDED.intptlat,
                intptlong      = EXCLUDED.intptlong,
                ingestion_date = NOW()
        """,
    },
    "zcta": {
        "table": "bronze.bronze_jurisdictions_zcta",
        "cache_file": "zcta.csv",
        "geoid_len": 5,
        "ddl": """
            CREATE SCHEMA IF NOT EXISTS bronze;
            CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_zcta (
                geoid          VARCHAR(5)    PRIMARY KEY,
                aland          BIGINT,
                awater         BIGINT,
                aland_sqmi     NUMERIC(12, 6),
                awater_sqmi    NUMERIC(12, 6),
                intptlat       NUMERIC(11, 8),
                intptlong      NUMERIC(12, 8),
                ingestion_date TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_bjz_coords ON bronze.bronze_jurisdictions_zcta(intptlat, intptlong);
        """,
        "insert": """
            INSERT INTO bronze.bronze_jurisdictions_zcta
                (geoid, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (geoid) DO UPDATE SET
                aland          = EXCLUDED.aland,
                awater         = EXCLUDED.awater,
                aland_sqmi     = EXCLUDED.aland_sqmi,
                awater_sqmi    = EXCLUDED.awater_sqmi,
                intptlat       = EXCLUDED.intptlat,
                intptlong      = EXCLUDED.intptlong,
                ingestion_date = NOW()
        """,
    },
}


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def safe_int(val):
    try:
        return int(float(val)) if pd.notna(val) else None
    except (ValueError, TypeError):
        return None


def safe_float(val):
    try:
        return float(val) if pd.notna(val) else None
    except (ValueError, TypeError):
        return None


def safe_str(val, maxlen=None):
    if pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    return s[:maxlen] if maxlen else s


def build_records(df: pd.DataFrame, jtype: str) -> list:
    geoid_len = TYPES[jtype]["geoid_len"]
    records = []

    for _, row in df.iterrows():
        raw_geoid = safe_str(row.get("GEOID"))
        if not raw_geoid:
            continue
        geoid = raw_geoid.zfill(geoid_len)

        common = (
            safe_int(row.get("ALAND")),
            safe_int(row.get("AWATER")),
            safe_float(row.get("ALAND_SQMI")),
            safe_float(row.get("AWATER_SQMI")),
            safe_float(row.get("INTPTLAT")),
            safe_float(row.get("INTPTLONG")),
        )

        if jtype == "states":
            records.append((
                geoid,
                safe_str(row.get("USPS"), 2),
                safe_str(row.get("ANSICODE"), 8),
                safe_str(row.get("NAME"), 255),
                *common,
            ))
        elif jtype == "counties":
            records.append((
                geoid,
                safe_str(row.get("USPS"), 2),
                safe_str(row.get("ANSICODE"), 8),
                safe_str(row.get("NAME"), 255),
                *common,
            ))
        elif jtype == "municipalities":
            records.append((
                geoid,
                safe_str(row.get("USPS"), 2),
                safe_str(row.get("ANSICODE"), 8),
                safe_str(row.get("NAME"), 255),
                safe_str(row.get("LSAD"), 5),
                safe_str(row.get("FUNCSTAT"), 1),
                *common,
            ))
        elif jtype == "school_districts":
            records.append((
                geoid,
                safe_str(row.get("USPS"), 2),
                safe_str(row.get("NAME"), 255),
                safe_str(row.get("LOGRADE"), 5),
                safe_str(row.get("HIGRADE"), 5),
                *common,
            ))
        elif jtype == "townships":
            records.append((
                geoid,
                safe_str(row.get("USPS"), 2),
                safe_str(row.get("ANSICODE"), 8),
                safe_str(row.get("NAME"), 255),
                safe_str(row.get("FUNCSTAT"), 1),
                *common,
            ))
        elif jtype == "zcta":
            records.append((geoid, *common))

    return records


def load_type(jtype: str, limit: int = None) -> int:
    cfg = TYPES[jtype]
    cache_file = CACHE_DIR / cfg["cache_file"]

    if not cache_file.exists():
        logger.error(f"Cache file not found: {cache_file}. Run download_census_gazetteer.py first.")
        return 0

    logger.info(f"Reading {jtype} from {cache_file}...")
    df = pd.read_csv(cache_file, dtype=str, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    if limit:
        df = df.head(limit)

    records = build_records(df, jtype)
    logger.info(f"Prepared {len(records):,} {jtype} records")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(cfg["ddl"])
    conn.commit()

    execute_batch(cur, cfg["insert"], records, page_size=5000)
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {cfg['table']}")
    total = cur.fetchone()[0]
    logger.success(f"Loaded {len(records):,} {jtype} → {cfg['table']} (total in table: {total:,})")

    cur.close()
    conn.close()
    return len(records)


def main():
    parser = argparse.ArgumentParser(description="Load Census Gazetteer CSVs into bronze tables")
    parser.add_argument(
        "--types", nargs="+", choices=list(TYPES.keys()), default=list(TYPES.keys()),
        help="Types to load (default: all)",
    )
    parser.add_argument("--limit", type=int, help="Limit records per type (for testing)")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Census Gazetteer → Bronze Jurisdiction Tables")
    logger.info("=" * 70)
    logger.info(f"Types: {', '.join(args.types)}")
    if args.limit:
        logger.warning(f"Limit: {args.limit} records per type (test mode)")

    total = 0
    for jtype in args.types:
        total += load_type(jtype, limit=args.limit)

    logger.success("=" * 70)
    logger.success(f"Done. {total:,} total records loaded across {len(args.types)} type(s).")
    logger.success("=" * 70)


if __name__ == "__main__":
    main()
