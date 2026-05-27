#!/usr/bin/env python3
"""
Load Census Bureau ZIP Code Tabulation Areas (ZCTAs) to Bronze Database

This script downloads and loads Census Gazetteer data for ZIP Code Tabulation Areas (ZCTAs)
into the bronze_jurisdictions_postal_codes table.

Data Source: Census Bureau Gazetteer Files
https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html

ZCTAs are generalized areal representations of USPS ZIP Code service areas.
They are not exact matches to ZIP codes but provide geographic boundaries for analysis.

Usage:
    python scripts/datasources/census/load_census_postal_codes.py
    python scripts/datasources/census/load_census_postal_codes.py --year 2024
"""
import psycopg2
from psycopg2.extras import execute_batch
import pandas as pd
import requests
import zipfile
from io import BytesIO
from pathlib import Path
from loguru import logger
import argparse
import os

# Bronze database connection
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
BRONZE_DATABASE_URL = f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator_bronze'

# Census Bureau Gazetteer ZCTA file (2024 - latest available)
# This file contains all 33,000+ ZIP Code Tabulation Areas with:
# - GEOID (5-digit ZCTA code)
# - INTPTLAT, INTPTLONG (latitude, longitude)
# - ALAND, AWATER (land and water area in square meters)
ZCTA_GAZETTEER_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip"


def create_bronze_postal_codes_table():
    """
    Create bronze_jurisdictions_postal_codes table for storing ZCTA data
    
    This table stores raw Census ZCTA (ZIP Code Tabulation Area) data.
    ZCTAs are generalized areal representations of USPS ZIP Code service areas.
    """
    conn = psycopg2.connect(BRONZE_DATABASE_URL)
    cur = conn.cursor()
    
    logger.info("📋 Creating bronze_jurisdictions_postal_codes table...")
    
    cur.execute("""
        DROP TABLE IF EXISTS bronze_jurisdictions_postal_codes CASCADE;
        
        CREATE TABLE bronze_jurisdictions_postal_codes (
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
        );
        
        CREATE INDEX idx_bronze_postal_codes_zcta ON bronze_jurisdictions_postal_codes(zcta);
        CREATE INDEX idx_bronze_postal_codes_geoid ON bronze_jurisdictions_postal_codes(geoid);
        CREATE INDEX idx_bronze_postal_codes_location ON bronze_jurisdictions_postal_codes(intptlat, intptlong);
        
        COMMENT ON TABLE bronze_jurisdictions_postal_codes IS 'Census Bureau ZIP Code Tabulation Areas (ZCTAs) - Raw bronze layer';
        COMMENT ON COLUMN bronze_jurisdictions_postal_codes.zcta IS '5-digit ZIP Code Tabulation Area code';
        COMMENT ON COLUMN bronze_jurisdictions_postal_codes.geoid IS 'Geographic identifier (same as ZCTA)';
        COMMENT ON COLUMN bronze_jurisdictions_postal_codes.aland IS 'Land area in square meters';
        COMMENT ON COLUMN bronze_jurisdictions_postal_codes.awater IS 'Water area in square meters';
        COMMENT ON COLUMN bronze_jurisdictions_postal_codes.aland_sqmi IS 'Land area in square miles';
        COMMENT ON COLUMN bronze_jurisdictions_postal_codes.awater_sqmi IS 'Water area in square miles';
        COMMENT ON COLUMN bronze_jurisdictions_postal_codes.intptlat IS 'Latitude of internal point';
        COMMENT ON COLUMN bronze_jurisdictions_postal_codes.intptlong IS 'Longitude of internal point';
    """)
    
    conn.commit()
    logger.info("✅ Table created")
    
    conn.close()


def download_census_zcta_data(year: int = 2024):
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
    cache_dir = Path("data/cache/census/zcta")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    cache_file = cache_dir / f"zcta_{year}.csv"
    
    # Check if cached file exists (< 30 days old)
    if cache_file.exists():
        file_age_days = (pd.Timestamp.now() - pd.Timestamp(cache_file.stat().st_mtime, unit='s')).days
        if file_age_days < 30:
            logger.info(f"✅ Using cached ZCTA data from {cache_file}")
            logger.info(f"   File age: {file_age_days} days old")
            return pd.read_csv(cache_file)
    
    logger.info(f"📥 Downloading Census ZCTA Gazetteer data...")
    logger.info(f"   URL: {ZCTA_GAZETTEER_URL}")
    logger.info(f"   This may take 2-5 minutes for large files...")
    
    try:
        response = requests.get(ZCTA_GAZETTEER_URL, timeout=300)
        response.raise_for_status()
        
        logger.info(f"✅ Downloaded {len(response.content) / 1024 / 1024:.2f} MB")
        
        # Extract ZIP file
        with zipfile.ZipFile(BytesIO(response.content)) as zip_ref:
            # Find the .txt file (Gazetteer files are tab-delimited)
            txt_files = [f for f in zip_ref.namelist() if f.endswith('.txt')]
            
            if not txt_files:
                raise FileNotFoundError("No .txt file found in ZIP archive")
            
            txt_file = txt_files[0]
            logger.info(f"📄 Extracting {txt_file}...")
            
            # Read tab-delimited file
            with zip_ref.open(txt_file) as f:
                df = pd.read_csv(f, sep='\t', encoding='latin-1', dtype=str)
        
        logger.info(f"📊 Loaded {len(df):,} ZCTAs")
        logger.info(f"   Columns: {list(df.columns)}")
        
        # Cache the data
        df.to_csv(cache_file, index=False)
        logger.info(f"💾 Cached data to {cache_file}")
        
        return df
        
    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout downloading ZCTA data after 5 minutes")
        logger.error(f"   Census server may be slow. Try again later.")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to download Census ZCTA data: {e}")
        raise


def load_zcta_to_bronze(df: pd.DataFrame):
    """
    Load ZCTA data into bronze_jurisdictions_postal_codes table
    
    Args:
        df: DataFrame with Census ZCTA Gazetteer data
    """
    conn = psycopg2.connect(BRONZE_DATABASE_URL)
    cur = conn.cursor()
    
    logger.info("📊 Processing ZCTA data for database insertion...")
    
    # Expected columns from Gazetteer file:
    # GEOID, ALAND, AWATER, ALAND_SQMI, AWATER_SQMI, INTPTLAT, INTPTLONG
    
    # Clean and prepare data
    records = []
    
    for _, row in df.iterrows():
        try:
            geoid = str(row.get('GEOID', '')).strip()
            
            if not geoid or len(geoid) != 5:
                continue
            
            # Convert numeric fields
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
            
            aland = safe_int(row.get('ALAND'))
            awater = safe_int(row.get('AWATER'))
            aland_sqmi = safe_float(row.get('ALAND_SQMI'))
            awater_sqmi = safe_float(row.get('AWATER_SQMI'))
            intptlat = safe_float(row.get('INTPTLAT'))
            intptlong = safe_float(row.get('INTPTLONG'))
            
            records.append((
                geoid,  # zcta
                geoid,  # geoid (same as ZCTA)
                aland,
                awater,
                aland_sqmi,
                awater_sqmi,
                intptlat,
                intptlong,
                'Census Gazetteer 2024'  # source_file
            ))
            
        except Exception as e:
            logger.warning(f"Error processing ZCTA {row.get('GEOID', 'unknown')}: {e}")
            continue
    
    if not records:
        logger.error("❌ No valid ZCTA records to insert")
        conn.close()
        return
    
    logger.info(f"💾 Inserting {len(records):,} ZCTAs into bronze_jurisdictions_postal_codes...")
    
    insert_query = """
        INSERT INTO bronze_jurisdictions_postal_codes 
        (zcta, geoid, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, source_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
    
    # Insert in batches of 5000
    execute_batch(cur, insert_query, records, page_size=5000)
    conn.commit()
    
    logger.success(f"✅ Inserted {len(records):,} ZCTAs")
    
    # Show statistics
    cur.execute("""
        SELECT 
            COUNT(*) as total_zctas,
            COUNT(*) FILTER (WHERE intptlat IS NOT NULL AND intptlong IS NOT NULL) as with_coordinates,
            COUNT(*) FILTER (WHERE aland_sqmi > 0) as with_land_area,
            AVG(aland_sqmi) as avg_land_area_sqmi
        FROM bronze_jurisdictions_postal_codes
    """)
    
    stats = cur.fetchone()
    logger.info(f"📊 Bronze table statistics:")
    logger.info(f"   Total ZCTAs: {stats[0]:,}")
    logger.info(f"   With coordinates: {stats[1]:,}")
    logger.info(f"   With land area: {stats[2]:,}")
    logger.info(f"   Avg land area: {stats[3]:.2f} sq mi" if stats[3] else "   Avg land area: N/A")
    
    conn.close()


def verify_data_quality():
    """Run data quality checks on loaded ZCTA data"""
    conn = psycopg2.connect(BRONZE_DATABASE_URL)
    cur = conn.cursor()
    
    logger.info("🔍 Running data quality checks...")
    
    checks_passed = []
    checks_failed = []
    
    # Check 1: Total count
    cur.execute("SELECT COUNT(*) FROM bronze_jurisdictions_postal_codes")
    total = cur.fetchone()[0]
    
    if total > 30000:
        checks_passed.append(f"✅ Total ZCTAs: {total:,} (expected ~33,000)")
    else:
        checks_failed.append(f"❌ Total ZCTAs: {total:,} (expected ~33,000)")
    
    # Check 2: Coordinates coverage
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE intptlat IS NOT NULL AND intptlong IS NOT NULL) * 100.0 / COUNT(*) as pct
        FROM bronze_jurisdictions_postal_codes
    """)
    coord_pct = cur.fetchone()[0]
    
    if coord_pct > 95:
        checks_passed.append(f"✅ Coordinates coverage: {coord_pct:.1f}%")
    else:
        checks_failed.append(f"❌ Coordinates coverage: {coord_pct:.1f}% (expected >95%)")
    
    # Check 3: Valid latitude/longitude ranges
    cur.execute("""
        SELECT COUNT(*) 
        FROM bronze_jurisdictions_postal_codes
        WHERE intptlat NOT BETWEEN 24.396308 AND 71.538800  -- Continental US + Alaska + Hawaii
           OR intptlong NOT BETWEEN -179.148909 AND -66.93457
    """)
    invalid_coords = cur.fetchone()[0]
    
    if invalid_coords == 0:
        checks_passed.append(f"✅ All coordinates within valid US ranges")
    else:
        checks_failed.append(f"⚠️  {invalid_coords} ZCTAs with coordinates outside US ranges")
    
    # Check 4: Duplicate ZCTAs
    cur.execute("""
        SELECT zcta, COUNT(*) as cnt
        FROM bronze_jurisdictions_postal_codes
        GROUP BY zcta
        HAVING COUNT(*) > 1
    """)
    duplicates = cur.fetchall()
    
    if not duplicates:
        checks_passed.append(f"✅ No duplicate ZCTAs")
    else:
        checks_failed.append(f"❌ {len(duplicates)} duplicate ZCTAs found")
    
    # Print results
    logger.info("=" * 60)
    for check in checks_passed:
        logger.info(check)
    for check in checks_failed:
        logger.warning(check)
    logger.info("=" * 60)
    
    if checks_failed:
        logger.warning(f"⚠️  {len(checks_failed)} checks failed")
    else:
        logger.success(f"✅ All {len(checks_passed)} quality checks passed!")
    
    conn.close()
    
    return len(checks_failed) == 0


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description="Load Census Bureau ZIP Code Tabulation Areas (ZCTAs) to Bronze Database"
    )
    parser.add_argument(
        '--year',
        type=int,
        default=2024,
        help='Census vintage year (default: 2024)'
    )
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("🗺️  CENSUS ZCTA DATA INGESTION TO BRONZE")
    logger.info("=" * 80)
    logger.info(f"Year: {args.year}")
    logger.info(f"Target: bronze_jurisdictions_postal_codes table")
    logger.info("")
    
    try:
        # Step 1: Create bronze table
        create_bronze_postal_codes_table()
        
        # Step 2: Download ZCTA Gazetteer data
        zcta_df = download_census_zcta_data(year=args.year)
        
        # Step 3: Load into bronze table
        load_zcta_to_bronze(zcta_df)
        
        # Step 4: Verify data quality
        quality_ok = verify_data_quality()
        
        logger.info("")
        logger.info("=" * 80)
        if quality_ok:
            logger.success("✅ ZCTA DATA INGESTION COMPLETE!")
        else:
            logger.warning("⚠️  ZCTA data loaded but quality checks failed")
        logger.info("=" * 80)
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Create dbt silver model to join ZCTAs with counties")
        logger.info("  2. Create dbt gold model for API-ready postal code search")
        logger.info("  3. Use data in frontend for ZIP code search and mapping")
        logger.info("")
        
    except Exception as e:
        logger.error(f"❌ ZCTA ingestion failed: {e}")
        raise


if __name__ == '__main__':
    main()