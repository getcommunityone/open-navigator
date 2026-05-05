#!/usr/bin/env python3
"""
Load Census Geographic Relationship Files to Bronze Database

Loads Census Bureau relationship files into bronze database tables:
1. bronze_jurisdictions_zip_county - ZIP Code to County mappings
2. bronze_jurisdictions_zip_place - ZIP Code to City/Place mappings

These tables enable:
- Looking up which county a ZIP code belongs to
- Looking up which city/town a ZIP code belongs to
- Handling multi-county and multi-city ZIP codes

Prerequisites:
    Run download_census_relationships.py first to download the data files

Usage:
    python scripts/datasources/census/load_census_relationships.py
    python scripts/datasources/census/load_census_relationships.py --types zcta_county
    python scripts/datasources/census/load_census_relationships.py --verify-only
"""
import psycopg2
from psycopg2.extras import execute_batch
import pandas as pd
from pathlib import Path
from loguru import logger
import argparse
import os
from typing import Optional, List


# Bronze database connection
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
BRONZE_DATABASE_URL = f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator_bronze'

# Cache directory (where download script saves files)
CACHE_DIR = Path("data/cache/census_relationships")


def create_bronze_jurisdictions_zip_county_table():
    """
    Create bronze_jurisdictions_zip_county table for ZIP to county relationships.
    
    This table stores which counties each ZIP code overlaps with, including
    the area of overlap. Multiple rows per ZIP code indicate multi-county ZIPs.
    """
    conn = psycopg2.connect(BRONZE_DATABASE_URL)
    cur = conn.cursor()
    
    logger.info("📋 Creating bronze_jurisdictions_zip_county table...")
    
    cur.execute("""
        DROP TABLE IF EXISTS bronze_jurisdictions_zip_county CASCADE;
        
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
        );
        
        CREATE INDEX idx_bronze_jurisdictions_zip_county_zcta ON bronze_jurisdictions_zip_county(zcta);
        CREATE INDEX idx_bronze_jurisdictions_zip_county_geoid ON bronze_jurisdictions_zip_county(county_geoid);
        CREATE INDEX idx_bronze_jurisdictions_zip_county_state ON bronze_jurisdictions_zip_county(state_fips);
        
        COMMENT ON TABLE bronze_jurisdictions_zip_county IS 'Census ZCTA (ZIP Code) to County relationships - shows which counties each ZIP overlaps';
        COMMENT ON COLUMN bronze_jurisdictions_zip_county.zcta IS '5-digit ZIP Code Tabulation Area';
        COMMENT ON COLUMN bronze_jurisdictions_zip_county.county_geoid IS '5-digit county FIPS code (state+county)';
        COMMENT ON COLUMN bronze_jurisdictions_zip_county.state_fips IS '2-digit state FIPS code (first 2 of county GEOID)';
        COMMENT ON COLUMN bronze_jurisdictions_zip_county.arealand_part IS 'Land area of overlap in square meters';
        COMMENT ON COLUMN bronze_jurisdictions_zip_county.areawater_part IS 'Water area of overlap in square meters';
    """)
    
    conn.commit()
    logger.success("✅ Table created")
    conn.close()


def create_bronze_jurisdictions_zip_place_table():
    """
    Create bronze_jurisdictions_zip_place table for ZIP to city/place relationships.
    
    This table stores which cities/places each ZIP code overlaps with, including
    the area of overlap. Multiple rows per ZIP code indicate multi-city ZIPs.
    """
    conn = psycopg2.connect(BRONZE_DATABASE_URL)
    cur = conn.cursor()
    
    logger.info("📋 Creating bronze_jurisdictions_zip_place table...")
    
    cur.execute("""
        DROP TABLE IF EXISTS bronze_jurisdictions_zip_place CASCADE;
        
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
        );
        
        CREATE INDEX idx_bronze_jurisdictions_zip_place_zcta ON bronze_jurisdictions_zip_place(zcta);
        CREATE INDEX idx_bronze_jurisdictions_zip_place_geoid ON bronze_jurisdictions_zip_place(place_geoid);
        CREATE INDEX idx_bronze_jurisdictions_zip_place_state ON bronze_jurisdictions_zip_place(state_fips);
        
        COMMENT ON TABLE bronze_jurisdictions_zip_place IS 'Census ZCTA (ZIP Code) to Place (city/town) relationships - shows which cities each ZIP overlaps';
        COMMENT ON COLUMN bronze_jurisdictions_zip_place.zcta IS '5-digit ZIP Code Tabulation Area';
        COMMENT ON COLUMN bronze_jurisdictions_zip_place.place_geoid IS '7-digit place FIPS code (state+place)';
        COMMENT ON COLUMN bronze_jurisdictions_zip_place.state_fips IS '2-digit state FIPS code (first 2 of place GEOID)';
        COMMENT ON COLUMN bronze_jurisdictions_zip_place.arealand_part IS 'Land area of overlap in square meters';
        COMMENT ON COLUMN bronze_jurisdictions_zip_place.areawater_part IS 'Water area of overlap in square meters';
    """)
    
    conn.commit()
    logger.success("✅ Table created")
    conn.close()


def load_zcta_county_data():
    """Load ZCTA to county relationship data into bronze_jurisdictions_zip_county table."""
    input_file = CACHE_DIR / "zcta_county.txt"
    
    if not input_file.exists():
        logger.error(f"❌ File not found: {input_file}")
        logger.info("   Run: python scripts/datasources/census/download_census_relationships.py")
        return False
    
    logger.info(f"📊 Processing ZCTA to county data from {input_file}...")
    
    # Read pipe-delimited file
    df = pd.read_csv(input_file, sep='|', dtype=str, low_memory=False)
    
    logger.info(f"   Loaded {len(df):,} rows")
    logger.info(f"   Columns: {len(df.columns)}")
    
    # Extract relevant columns
    # Column names: GEOID_ZCTA5_20, GEOID_COUNTY_20, NAMELSAD_COUNTY_20, AREALAND_PART, AREAWATER_PART
    records = []
    
    # Helper to safely get string values
    def safe_str(val):
        if pd.isna(val):
            return ''
        return str(val).strip()
    
    for _, row in df.iterrows():
        zcta = safe_str(row.get('GEOID_ZCTA5_20', ''))
        county_geoid = safe_str(row.get('GEOID_COUNTY_20', ''))
        county_name = safe_str(row.get('NAMELSAD_COUNTY_20', ''))
        
        # Skip empty rows
        if not zcta or not county_geoid:
            continue
        
        # Extract state FIPS (first 2 digits of county GEOID)
        state_fips = county_geoid[:2] if len(county_geoid) >= 2 else None
        
        # Convert area to int
        def safe_int(val):
            try:
                return int(float(val)) if pd.notna(val) and val else None
            except:
                return None
        
        arealand_part = safe_int(row.get('AREALAND_PART'))
        areawater_part = safe_int(row.get('AREAWATER_PART'))
        
        records.append((
            zcta,
            county_geoid,
            county_name,
            state_fips,
            arealand_part,
            areawater_part,
            'Census 2020 ZCTA-County Relationship File'
        ))
    
    if not records:
        logger.error("❌ No valid records to insert")
        return False
    
    logger.info(f"💾 Inserting {len(records):,} ZCTA-county relationships...")
    
    conn = psycopg2.connect(BRONZE_DATABASE_URL)
    cur = conn.cursor()
    
    insert_query = """
        INSERT INTO bronze_jurisdictions_zip_county 
        (zcta, county_geoid, county_name, state_fips, arealand_part, areawater_part, source_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (zcta, county_geoid) DO UPDATE SET
            county_name = EXCLUDED.county_name,
            state_fips = EXCLUDED.state_fips,
            arealand_part = EXCLUDED.arealand_part,
            areawater_part = EXCLUDED.areawater_part,
            source_file = EXCLUDED.source_file,
            ingestion_date = NOW()
    """
    
    execute_batch(cur, insert_query, records, page_size=5000)
    conn.commit()
    
    logger.success(f"✅ Inserted {len(records):,} ZCTA-county relationships")
    
    # Show stats
    cur.execute("""
        SELECT 
            COUNT(DISTINCT zcta) as unique_zctas,
            COUNT(*) as total_relationships,
            COUNT(*) FILTER (WHERE arealand_part IS NOT NULL) as with_area_data
        FROM bronze_jurisdictions_zip_county
    """)
    
    stats = cur.fetchone()
    logger.info(f"📊 Table statistics:")
    logger.info(f"   Unique ZCTAs: {stats[0]:,}")
    logger.info(f"   Total relationships: {stats[1]:,}")
    logger.info(f"   With area data: {stats[2]:,}")
    logger.info(f"   Avg counties per ZIP: {stats[1] / stats[0]:.2f}")
    
    conn.close()
    return True


def load_zcta_place_data():
    """Load ZCTA to place (city) relationship data into bronze_jurisdictions_zip_place table."""
    input_file = CACHE_DIR / "zcta_place.txt"
    
    if not input_file.exists():
        logger.error(f"❌ File not found: {input_file}")
        logger.info("   Run: python scripts/datasources/census/download_census_relationships.py")
        return False
    
    logger.info(f"📊 Processing ZCTA to place data from {input_file}...")
    
    # Read pipe-delimited file
    df = pd.read_csv(input_file, sep='|', dtype=str, low_memory=False)
    
    logger.info(f"   Loaded {len(df):,} rows")
    logger.info(f"   Columns: {len(df.columns)}")
    
    # Extract relevant columns
    # Column names: GEOID_ZCTA5_20, GEOID_PLACE_20, NAMELSAD_PLACE_20, AREALAND_PART, AREAWATER_PART
    records = []
    
    # Helper to safely get string values
    def safe_str(val):
        if pd.isna(val):
            return ''
        return str(val).strip()
    
    for _, row in df.iterrows():
        zcta = safe_str(row.get('GEOID_ZCTA5_20', ''))
        place_geoid = safe_str(row.get('GEOID_PLACE_20', ''))
        place_name = safe_str(row.get('NAMELSAD_PLACE_20', ''))
        
        # Skip empty rows
        if not zcta or not place_geoid:
            continue
        
        # Extract state FIPS (first 2 digits of place GEOID)
        state_fips = place_geoid[:2] if len(place_geoid) >= 2 else None
        
        # Convert area to int
        def safe_int(val):
            try:
                return int(float(val)) if pd.notna(val) and val else None
            except:
                return None
        
        arealand_part = safe_int(row.get('AREALAND_PART'))
        areawater_part = safe_int(row.get('AREAWATER_PART'))
        
        records.append((
            zcta,
            place_geoid,
            place_name,
            state_fips,
            arealand_part,
            areawater_part,
            'Census 2020 ZCTA-Place Relationship File'
        ))
    
    if not records:
        logger.error("❌ No valid records to insert")
        return False
    
    logger.info(f"💾 Inserting {len(records):,} ZCTA-place relationships...")
    
    conn = psycopg2.connect(BRONZE_DATABASE_URL)
    cur = conn.cursor()
    
    insert_query = """
        INSERT INTO bronze_jurisdictions_zip_place 
        (zcta, place_geoid, place_name, state_fips, arealand_part, areawater_part, source_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (zcta, place_geoid) DO UPDATE SET
            place_name = EXCLUDED.place_name,
            state_fips = EXCLUDED.state_fips,
            arealand_part = EXCLUDED.arealand_part,
            areawater_part = EXCLUDED.areawater_part,
            source_file = EXCLUDED.source_file,
            ingestion_date = NOW()
    """
    
    execute_batch(cur, insert_query, records, page_size=5000)
    conn.commit()
    
    logger.success(f"✅ Inserted {len(records):,} ZCTA-place relationships")
    
    # Show stats
    cur.execute("""
        SELECT 
            COUNT(DISTINCT zcta) as unique_zctas,
            COUNT(*) as total_relationships,
            COUNT(*) FILTER (WHERE arealand_part IS NOT NULL) as with_area_data
        FROM bronze_jurisdictions_zip_place
    """)
    
    stats = cur.fetchone()
    logger.info(f"📊 Table statistics:")
    logger.info(f"   Unique ZCTAs: {stats[0]:,}")
    logger.info(f"   Total relationships: {stats[1]:,}")
    logger.info(f"   With area data: {stats[2]:,}")
    logger.info(f"   Avg places per ZIP: {stats[1] / stats[0]:.2f}")
    
    conn.close()
    return True


def verify_data_quality():
    """Run data quality checks on loaded relationship data."""
    conn = psycopg2.connect(BRONZE_DATABASE_URL)
    cur = conn.cursor()
    
    logger.info("=" * 80)
    logger.info("🔍 DATA QUALITY VERIFICATION")
    logger.info("=" * 80)
    
    checks_passed = []
    checks_failed = []
    
    # Check 1: ZCTA-County table exists and has data
    try:
        cur.execute("SELECT COUNT(*) FROM bronze_jurisdictions_zip_county")
        county_count = cur.fetchone()[0]
        
        if county_count > 50000:
            checks_passed.append(f"✅ ZCTA-County: {county_count:,} relationships")
        else:
            checks_failed.append(f"❌ ZCTA-County: {county_count:,} (expected >50,000)")
    except Exception as e:
        checks_failed.append(f"❌ ZCTA-County table error: {e}")
    
    # Check 2: ZCTA-Place table exists and has data
    try:
        cur.execute("SELECT COUNT(*) FROM bronze_jurisdictions_zip_place")
        place_count = cur.fetchone()[0]
        
        if place_count > 200000:
            checks_passed.append(f"✅ ZCTA-Place: {place_count:,} relationships")
        else:
            checks_failed.append(f"❌ ZCTA-Place: {place_count:,} (expected >200,000)")
    except Exception as e:
        checks_failed.append(f"❌ ZCTA-Place table error: {e}")
    
    # Check 3: Sample lookups
    try:
        # Check if common ZCTAs exist
        cur.execute("""
            SELECT zcta, county_name, state_fips
            FROM bronze_jurisdictions_zip_county
            WHERE zcta IN ('02101', '10001', '90210', '60601')
            ORDER BY zcta
        """)
        samples = cur.fetchall()
        
        if len(samples) >= 3:
            checks_passed.append(f"✅ Sample ZCTAs found: {len(samples)}")
            for zcta, county, state in samples[:3]:
                logger.info(f"   • ZIP {zcta} → {county} ({state})")
        else:
            checks_failed.append(f"⚠️  Only {len(samples)} sample ZCTAs found")
    except Exception as e:
        checks_failed.append(f"❌ Sample lookup error: {e}")
    
    # Print results
    logger.info("")
    for check in checks_passed:
        logger.info(check)
    for check in checks_failed:
        logger.warning(check)
    logger.info("=" * 80)
    
    if checks_failed:
        logger.warning(f"⚠️  {len(checks_failed)} checks failed")
    else:
        logger.success(f"✅ All {len(checks_passed)} quality checks passed!")
    
    conn.close()
    return len(checks_failed) == 0


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Load Census Geographic Relationship Files to Bronze Database"
    )
    parser.add_argument(
        '--types',
        nargs='+',
        choices=['zcta_county', 'zcta_place'],
        help='Relationship types to load (default: all)'
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only run verification checks (no loading)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("🗄️  CENSUS RELATIONSHIP DATA LOAD TO BRONZE")
    logger.info("=" * 80)
    logger.info(f"Target database: open_navigator_bronze")
    logger.info("")
    
    if args.verify_only:
        verify_data_quality()
        return
    
    # Determine which tables to load
    load_county = not args.types or 'zcta_county' in args.types
    load_place = not args.types or 'zcta_place' in args.types
    
    success_count = 0
    total_count = 0
    
    try:
        # Load ZCTA to County
        if load_county:
            total_count += 1
            logger.info("-" * 80)
            create_bronze_jurisdictions_zip_county_table()
            if load_zcta_county_data():
                success_count += 1
            logger.info("")
        
        # Load ZCTA to Place
        if load_place:
            total_count += 1
            logger.info("-" * 80)
            create_bronze_jurisdictions_zip_place_table()
            if load_zcta_place_data():
                success_count += 1
            logger.info("")
        
        # Verify data quality
        logger.info("-" * 80)
        quality_ok = verify_data_quality()
        
        logger.info("")
        logger.info("=" * 80)
        if success_count == total_count and quality_ok:
            logger.success("✅ RELATIONSHIP DATA LOAD COMPLETE!")
        else:
            logger.warning(f"⚠️  Loaded {success_count}/{total_count} tables")
        logger.info("=" * 80)
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Create dbt silver models to identify primary county/place per ZIP")
        logger.info("  2. Use in API for ZIP code lookups and filtering")
        logger.info("  3. Enrich nonprofit data with ZIP→county/city mappings")
        logger.info("")
        
    except Exception as e:
        logger.error(f"❌ Load failed: {e}")
        raise


if __name__ == '__main__':
    main()
