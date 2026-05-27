#!/usr/bin/env python3
"""
Load Census Gazetteer counties into bronze_jurisdictions

This script downloads and loads the Census Gazetteer county file which contains
all 3,144 U.S. counties and county equivalents (parishes, boroughs, etc.).

**Source**: US Census Bureau Gazetteer Files
**URL**: https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html
**Table**: bronze_jurisdictions (in open_navigator_bronze database)
**Type**: Loading script (raw data → bronze layer)

**GEOID Column**: 5-digit Census county code (primary identifier)
**FIPS Column**: 5-digit FIPS code (same as GEOID for counties)

Gazetteer columns:
- USPS: State abbreviation
- GEOID: Geographic identifier (5 digits for counties) → **loaded as geoid**
- NAME: County name
- ALAND: Land area in square meters
- AWATER: Water area in square meters
- ALAND_SQMI: Land area in square miles
- AWATER_SQMI: Water area in square miles
- INTPTLAT: Latitude of internal point
- INTPTLONG: Longitude of internal point

Usage:
    python scripts/datasources/census/load_census_counties.py
    python scripts/datasources/census/load_census_counties.py --force-download
    python scripts/datasources/census/load_census_counties.py --limit 10  # Test with 10 counties
"""
import argparse
import csv
import io
import zipfile
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
import requests
from loguru import logger


# Census Gazetteer Files for counties
GAZETTEER_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip"
CACHE_DIR = Path("data/cache/census")


def get_connection():
    """Get connection to bronze database."""
    return psycopg2.connect(
        host="localhost",
        port=5433,
        database="open_navigator_bronze",
        user="postgres",
        password="password"
    )


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


def load_counties_to_bronze(csv_file: Path, limit: int = None):
    """
    Load counties from Census Gazetteer CSV into bronze_jurisdictions.
    
    Args:
        csv_file: Path to CSV file
        limit: Optional limit for testing (loads only first N records)
    """
    conn = get_connection()
    cur = conn.cursor()
    
    logger.info(f"Loading counties from {csv_file}...")
    
    records = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            
            # Extract data
            state_code = row.get('USPS', '').strip()
            geoid = row.get('GEOID', '').strip()  # 5-digit county code
            name = row.get('NAME', '').strip()
            
            # Population not in Gazetteer, will enrich from ACS later
            population = None
            
            # Area in square miles
            try:
                area_sq_miles = float(row.get('ALAND_SQMI', 0))
            except (ValueError, TypeError):
                area_sq_miles = None
            
            # Coordinates
            try:
                latitude = float(row.get('INTPTLAT', 0))
                longitude = float(row.get('INTPTLONG', 0))
            except (ValueError, TypeError):
                latitude = None
                longitude = None
            
            # All are type='county'
            jurisdiction_type = 'county'
            
            records.append((
                name,                           # name
                jurisdiction_type,              # type (always 'county')
                state_code,                     # state_code
                None,                          # state (full name, enrich later)
                None,                          # county (NULL for counties themselves)
                geoid,                         # geoid (5-digit county code)
                geoid,                         # fips_code (same as geoid for counties)
                None,                          # ncsid (not applicable for counties)
                None,                          # ansicode (not in county gazetteer)
                population,                     # population (NULL, enrich from ACS)
                area_sq_miles,                 # area_sq_miles
                latitude,                      # latitude
                longitude,                     # longitude
                None,                          # website_url (enrich later)
                'census_gazetteer_2024'        # source
            ))
            
            if (i + 1) % 1000 == 0:
                logger.info(f"Processed {i + 1:,} records...")
    
    logger.info(f"Prepared {len(records):,} county records")
    logger.info("Inserting into bronze_jurisdictions...")
    
    # Bulk insert with conflict handling
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
    
    logger.success(f"✅ Successfully loaded {len(inserted_ids):,} counties")
    
    # Verification
    cur.execute("""
        SELECT COUNT(*) as total_counties
        FROM bronze_jurisdictions
        WHERE type = 'county'
    """)
    
    total = cur.fetchone()[0]
    logger.info(f"\nTotal counties in database: {total:,}")
    
    # Show counties by state
    cur.execute("""
        SELECT state_code, COUNT(*) as county_count
        FROM bronze_jurisdictions
        WHERE type = 'county' AND state_code IS NOT NULL
        GROUP BY state_code
        ORDER BY county_count DESC
        LIMIT 10
    """)
    
    state_counts = cur.fetchall()
    logger.info("\nTop 10 states by county count:")
    for state, count in state_counts:
        logger.info(f"  {state}: {count:,} counties")
    
    # Show sample counties with details
    cur.execute("""
        SELECT name, state_code, geoid, area_sq_miles, latitude, longitude
        FROM bronze_jurisdictions
        WHERE type = 'county'
        ORDER BY random()
        LIMIT 5
    """)
    
    samples = cur.fetchall()
    logger.info("\nSample counties:")
    for name, state, geoid, area, lat, lon in samples:
        logger.info(f"  {name}, {state} - GEOID: {geoid}, Area: {area:.1f} sq mi, Coords: ({lat:.4f}, {lon:.4f})")
    
    cur.close()
    conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Load Census counties to bronze database")
    parser.add_argument("--force-download", action="store_true", help="Force re-download even if cached")
    parser.add_argument("--limit", type=int, help="Limit number of records (for testing)")
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("Census Counties → bronze_jurisdictions")
    logger.info("=" * 70)
    
    # Download file
    csv_file = download_gazetteer_file(force_download=args.force_download)
    
    # Load to database
    load_counties_to_bronze(csv_file, limit=args.limit)
    
    logger.success("=" * 70)
    logger.success("✅ County loading complete!")
    logger.success("=" * 70)
    logger.info("\nNext steps:")
    logger.info("1. Run dbt models to populate silver/gold layers")
    logger.info("2. Enrich with population data from ACS")
    logger.info("3. Add county websites if available")


if __name__ == "__main__":
    main()
