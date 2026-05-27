#!/usr/bin/env python3
"""
Load Census Gazetteer municipalities (cities/towns) into bronze_jurisdictions

Reads the cached CSV produced by download_census_municipalities.py and loads
all active places into the bronze_jurisdictions table.

**Source**: US Census Bureau Gazetteer Files
**Table**: bronze_jurisdictions (in open_navigator database)
**Type**: Loading script (raw data → bronze layer)

**GEOID Column**: 7-digit Census place code (primary identifier)
**ANSICODE Column**: 8-digit ANSI standard code from Census Gazetteer
**NCSID Column**: Legacy column, consider using ansicode instead
                  NULL for all other jurisdiction types (states, counties, etc.)

Gazetteer columns:
- USPS: State abbreviation
- GEOID: Geographic identifier (7 digits for places) → **loaded as geoid**
- ANSICODE: ANSI standard code for the place → **loaded as ansicode**
- NAME: Place name
- LSAD: Legal/Statistical Area Description
- FUNCSTAT: Functional status (A=Active, I=Inactive, etc.)
- ALAND: Land area in square meters
- AWATER: Water area in square meters
- ALAND_SQMI: Land area in square miles
- AWATER_SQMI: Water area in square miles
- INTPTLAT: Latitude of internal point
- INTPTLONG: Longitude of internal point

Usage:
    python scripts/datasources/census/load_census_municipalities.py
    python scripts/datasources/census/load_census_municipalities.py --csv data/cache/census/municipalities_20240101.csv
    python scripts/datasources/census/load_census_municipalities.py --limit 100  # Test with 100 records
"""
import argparse
import csv
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values
from loguru import logger


CACHE_DIR = Path("data/cache/census")

LSAD_TYPE_MAP = {
    '25': 'city',
    '43': 'town',
    '47': 'village',
    '21': 'borough',
    '57': 'cdp',
}


def get_connection():
    return psycopg2.connect(
        host="localhost",
        port=5433,
        database="open_navigator",
        user="postgres",
        password="password"
    )


def find_latest_cache_file() -> Path:
    """Return the most recent municipalities CSV from cache."""
    files = sorted(CACHE_DIR.glob("municipalities_*.csv"), reverse=True)
    if not files:
        raise FileNotFoundError(
            f"No municipalities CSV found in {CACHE_DIR}. "
            "Run download_census_municipalities.py first."
        )
    return files[0]


def load_municipalities_to_bronze(csv_file: Path, limit: int = None):
    """
    Load municipalities from Census Gazetteer CSV into bronze_jurisdictions.

    Args:
        csv_file: Path to CSV file produced by download_census_municipalities.py
        limit: Optional limit for testing (loads only first N records)
    """
    conn = get_connection()
    cur = conn.cursor()

    logger.info(f"Loading municipalities from {csv_file}...")

    records = []
    skipped = 0

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader):
            if limit and i >= limit:
                break

            if row.get('FUNCSTAT') != 'A':
                skipped += 1
                continue

            state_code = row.get('USPS', '').strip()
            geoid = row.get('GEOID', '').strip()
            ansicode = row.get('ANSICODE', '').strip()
            name = row.get('NAME', '').strip()
            lsad = row.get('LSAD', '').strip()

            try:
                area_sq_miles = float(row.get('ALAND_SQMI', 0))
            except (ValueError, TypeError):
                area_sq_miles = None

            try:
                latitude = float(row.get('INTPTLAT', 0))
                longitude = float(row.get('INTPTLONG', 0))
            except (ValueError, TypeError):
                latitude = None
                longitude = None

            jurisdiction_type = LSAD_TYPE_MAP.get(lsad, 'place')

            records.append((
                name,
                jurisdiction_type,
                state_code,
                None,                           # state (enriched later)
                None,                           # county (enriched later)
                geoid,
                geoid,                          # fips_code same as geoid for places
                ansicode if ansicode else None,  # ncsid (legacy)
                ansicode if ansicode else None,  # ansicode
                None,                           # population (enriched from ACS)
                area_sq_miles,
                latitude,
                longitude,
                None,                           # website_url (enriched later)
                'census_gazetteer_2024'
            ))

            if (i + 1) % 5000 == 0:
                logger.info(f"Processed {i + 1:,} records...")

    logger.info(f"Prepared {len(records):,} municipality records (skipped {skipped} inactive)")
    logger.info("Inserting into bronze_jurisdictions...")

    insert_query = """
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
        ) VALUES %s
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
        RETURNING id
    """

    execute_values(cur, insert_query, records, page_size=1000)
    inserted_ids = cur.fetchall()
    conn.commit()

    logger.success(f"Successfully loaded {len(inserted_ids):,} municipalities")

    cur.execute("""
        SELECT type, COUNT(*) as count
        FROM bronze_jurisdictions
        WHERE type IN ('city', 'town', 'village', 'borough', 'cdp', 'place')
        GROUP BY type
        ORDER BY count DESC
    """)
    logger.info("\nMunicipality breakdown by type:")
    for jurisdiction_type, count in cur.fetchall():
        logger.info(f"  {jurisdiction_type}: {count:,}")

    cur.execute("""
        SELECT name, type, state_code, geoid, ansicode
        FROM bronze_jurisdictions
        WHERE ansicode IS NOT NULL
        ORDER BY random()
        LIMIT 5
    """)
    logger.info("\nSample municipalities with Census IDs:")
    for name, jtype, state, geoid, ansicode in cur.fetchall():
        logger.info(f"  {name}, {state} ({jtype}) - GEOID: {geoid}, ANSICODE: {ansicode}")

    cur.close()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Load Census municipalities into bronze_jurisdictions")
    parser.add_argument("--csv", type=Path, help="Path to municipalities CSV (default: latest in cache)")
    parser.add_argument("--limit", type=int, help="Limit number of records (for testing)")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Census Municipalities → bronze_jurisdictions")
    logger.info("=" * 70)

    csv_file = args.csv or find_latest_cache_file()
    logger.info(f"Using: {csv_file}")

    load_municipalities_to_bronze(csv_file, limit=args.limit)

    logger.success("Municipality loading complete!")


if __name__ == "__main__":
    main()
