#!/usr/bin/env python3
"""
Load HIFLD Infrastructure Data to PostgreSQL

This script loads downloaded HIFLD datasets (places of worship, schools, hospitals, 
emergency services, government buildings) into a unified PostgreSQL table.

Usage:
    # Load all cached HIFLD parquet files
    python load_hifld_to_postgres.py
    
    # Load specific file
    python load_hifld_to_postgres.py --file data/cache/hifld/Law_Enforcement.parquet
    
    # Load with custom organization type
    python load_hifld_to_postgres.py --file data/cache/hifld/Hospitals.parquet --org-type hospital
"""
import argparse
from pathlib import Path
from typing import Optional

import pandas as pd
import geopandas as gpd
import psycopg2
from psycopg2.extras import execute_values
from loguru import logger


# PostgreSQL connection
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "database": "open_navigator",
    "user": "postgres",
    "password": "password"
}

# Cache directory
CACHE_DIR = Path("data/cache/hifld")


def get_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(**DB_CONFIG)


def create_table(conn):
    """
    Create bronze.bronze_locations table if it doesn't exist.

    Unified schema for all HIFLD infrastructure types.
    """
    with conn.cursor() as cur:
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS bronze;

            CREATE TABLE IF NOT EXISTS bronze.bronze_locations (
                id SERIAL PRIMARY KEY,
                source_id VARCHAR(100),
                name VARCHAR(500),
                organization_type VARCHAR(100),
                address VARCHAR(500),
                city VARCHAR(200),
                state VARCHAR(2),
                state_name VARCHAR(100),
                zip VARCHAR(10),
                county VARCHAR(200),
                latitude DECIMAL(10, 7),
                longitude DECIMAL(10, 7),
                telephone VARCHAR(50),
                website VARCHAR(500),
                data_source VARCHAR(100) DEFAULT 'HIFLD',
                source_dataset VARCHAR(200),
                additional_info JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT uq_bronze_locations_source UNIQUE (source_dataset, source_id)
            );

            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_bronzeloc_type ON bronze.bronze_locations(organization_type);
            CREATE INDEX IF NOT EXISTS idx_bronzeloc_state ON bronze.bronze_locations(state);
            CREATE INDEX IF NOT EXISTS idx_bronzeloc_city ON bronze.bronze_locations(city);
            CREATE INDEX IF NOT EXISTS idx_bronzeloc_coords ON bronze.bronze_locations(latitude, longitude);
            CREATE INDEX IF NOT EXISTS idx_bronzeloc_source ON bronze.bronze_locations(source_dataset);
        """)
        conn.commit()

    logger.success("✅ Created bronze.bronze_locations table")


def map_organization_type(dataset_name: str, row: dict) -> str:
    """
    Determine organization type from dataset name and row data.
    
    Args:
        dataset_name: Name of the source dataset
        row: Data row with fields
    
    Returns:
        Organization type string
    """
    dataset_lower = dataset_name.lower()
    
    # Law enforcement
    if 'law_enforcement' in dataset_lower or 'police' in dataset_lower:
        return row.get('TYPE', 'law_enforcement').lower().replace(' ', '_')
    
    # Places of worship
    if 'worship' in dataset_lower or 'church' in dataset_lower or 'religious' in dataset_lower:
        return 'place_of_worship'
    
    # Schools
    if 'school' in dataset_lower or 'education' in dataset_lower:
        return 'school'
    
    # Hospitals
    if 'hospital' in dataset_lower or 'healthcare' in dataset_lower or 'medical' in dataset_lower:
        return 'hospital'
    
    # Fire stations
    if 'fire' in dataset_lower:
        return 'fire_station'
    
    # Government buildings
    if 'government' in dataset_lower or 'courthouse' in dataset_lower or 'city_hall' in dataset_lower:
        return 'government_building'
    
    return 'other'


def normalize_field_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize field names across different HIFLD datasets.
    
    Different datasets use different field names - standardize them.
    """
    # Common field name mappings
    field_map = {
        # Name variations
        'NAME': 'name',
        'FACNAME': 'name',
        'FACILITY_NAME': 'name',
        'SCHOOL_NAME': 'name',
        'HOSPITAL_NAME': 'name',
        
        # Address variations
        'ADDRESS': 'address',
        'STREET': 'address',
        'ADDR': 'address',
        'LOCATION': 'address',
        
        # City variations
        'CITY': 'city',
        'CITYNAME': 'city',
        
        # State variations
        'STATE': 'state',
        'ST': 'state',
        'STATE_ABBR': 'state',
        
        # ZIP variations
        'ZIP': 'zip',
        'ZIPCODE': 'zip',
        'ZIP_CODE': 'zip',
        
        # County variations
        'COUNTY': 'county',
        'COUNTYNAME': 'county',
        
        # Coordinates
        'LATITUDE': 'latitude',
        'LAT': 'latitude',
        'Y': 'latitude',
        'LONGITUDE': 'longitude',
        'LON': 'longitude',
        'LONG': 'longitude',
        'X': 'longitude',
        
        # Contact info
        'TELEPHONE': 'telephone',
        'PHONE': 'telephone',
        'TEL': 'telephone',
        'WEBSITE': 'website',
        'URL': 'website',
        'WEB': 'website',
        
        # IDs
        'FID': 'source_id',
        'ID': 'source_id',
        'OBJECTID': 'source_id',
        'FACILITY_ID': 'source_id',
    }
    
    # Rename columns
    rename_dict = {}
    for col in df.columns:
        if col.upper() in field_map:
            rename_dict[col] = field_map[col.upper()]
    
    if rename_dict:
        df = df.rename(columns=rename_dict)
        logger.info(f"Normalized {len(rename_dict)} field names")
    
    return df


def load_parquet_to_postgres(
    parquet_file: Path,
    org_type: Optional[str] = None,
    batch_size: int = 1000
):
    """
    Load HIFLD parquet file into PostgreSQL.
    
    Args:
        parquet_file: Path to parquet file
        org_type: Override organization type (optional)
        batch_size: Number of records per batch
    """
    logger.info(f"Loading {parquet_file.name}...")
    
    # Read parquet file
    try:
        gdf = gpd.read_parquet(parquet_file)
        logger.info(f"Read {len(gdf):,} records from {parquet_file.name}")
    except Exception as e:
        # Fallback to pandas if not a GeoDataFrame
        gdf = pd.read_parquet(parquet_file)
        logger.info(f"Read {len(gdf):,} records from {parquet_file.name} (no geometry)")
    
    # Normalize field names
    df = normalize_field_names(gdf)
    
    # Drop geometry column for now (we have lat/lon)
    if 'geometry' in df.columns:
        df = df.drop(columns=['geometry'])
    
    # Dataset name from filename
    dataset_name = parquet_file.stem
    
    # Prepare records for insertion
    records = []
    for idx, row in df.iterrows():
        # Determine organization type
        if org_type:
            organization_type = org_type
        else:
            organization_type = map_organization_type(dataset_name, row.to_dict())
        
        # Collect additional fields as JSON
        standard_fields = {
            'name', 'address', 'city', 'state', 'zip', 'county',
            'latitude', 'longitude', 'telephone', 'website', 'source_id'
        }
        additional_info = {}
        for k, v in row.to_dict().items():
            if k not in standard_fields and pd.notna(v):
                # Convert Timestamp objects to strings
                if isinstance(v, pd.Timestamp):
                    additional_info[k] = str(v)
                else:
                    additional_info[k] = v
        
        record = {
            'source_id': str(row.get('source_id', '')),
            'name': str(row.get('name', ''))[:500],
            'organization_type': organization_type,
            'address': str(row.get('address', ''))[:500] if pd.notna(row.get('address')) else None,
            'city': str(row.get('city', ''))[:200] if pd.notna(row.get('city')) else None,
            'state': str(row.get('state', ''))[:2] if pd.notna(row.get('state')) else None,
            'zip': str(row.get('zip', ''))[:10] if pd.notna(row.get('zip')) else None,
            'county': str(row.get('county', ''))[:200] if pd.notna(row.get('county')) else None,
            'latitude': float(row.get('latitude')) if pd.notna(row.get('latitude')) else None,
            'longitude': float(row.get('longitude')) if pd.notna(row.get('longitude')) else None,
            'telephone': str(row.get('telephone', ''))[:50] if pd.notna(row.get('telephone')) else None,
            'website': str(row.get('website', ''))[:500] if pd.notna(row.get('website')) and str(row.get('website', '')).upper() != 'NOT AVAILABLE' else None,
            'source_dataset': dataset_name,
            'additional_info': additional_info if additional_info else None
        }
        
        records.append(record)
    
    # Insert into PostgreSQL
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Insert in batches
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                
                insert_query = """
                    INSERT INTO bronze.bronze_locations (
                        source_id, name, organization_type, address, city, state, zip,
                        county, latitude, longitude, telephone, website,
                        source_dataset, additional_info
                    ) VALUES %s
                    ON CONFLICT ON CONSTRAINT uq_bronze_locations_source DO NOTHING
                """
                
                values = [
                    (
                        r['source_id'], r['name'], r['organization_type'],
                        r['address'], r['city'], r['state'], r['zip'],
                        r['county'], r['latitude'], r['longitude'],
                        r['telephone'], r['website'], r['source_dataset'],
                        psycopg2.extras.Json(r['additional_info']) if r['additional_info'] else None
                    )
                    for r in batch
                ]
                
                execute_values(cur, insert_query, values)
                conn.commit()
                
                logger.info(f"Inserted batch {i//batch_size + 1}/{(len(records)-1)//batch_size + 1} ({len(batch):,} records)")
        
        logger.success(f"✅ Loaded {len(records):,} records from {parquet_file.name}")
        
    finally:
        conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Load HIFLD infrastructure data to PostgreSQL"
    )
    parser.add_argument(
        '--file',
        type=str,
        help='Specific parquet file to load (optional, loads all in cache if not specified)'
    )
    parser.add_argument(
        '--org-type',
        type=str,
        help='Override organization type (e.g., hospital, school, place_of_worship)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Number of records per batch (default: 1000)'
    )
    parser.add_argument(
        '--create-table',
        action='store_true',
        help='Create table (done automatically if not exists)'
    )
    
    args = parser.parse_args()
    
    # Create table
    conn = get_connection()
    create_table(conn)
    conn.close()
    
    # Load specific file or all files
    if args.file:
        parquet_file = Path(args.file)
        if not parquet_file.exists():
            logger.error(f"File not found: {parquet_file}")
            return
        
        load_parquet_to_postgres(parquet_file, args.org_type, args.batch_size)
    else:
        # Load all parquet files in cache
        parquet_files = list(CACHE_DIR.glob("*.parquet"))
        
        if not parquet_files:
            logger.warning(f"No parquet files found in {CACHE_DIR}")
            logger.info("Download datasets first using download_arcgis_dataset.py")
            return
        
        logger.info(f"Found {len(parquet_files)} parquet files in {CACHE_DIR}")
        
        for parquet_file in parquet_files:
            try:
                load_parquet_to_postgres(parquet_file, args.org_type, args.batch_size)
            except Exception as e:
                logger.error(f"Failed to load {parquet_file.name}: {e}")
                continue
    
    # Summary
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM bronze.bronze_locations")
        total_count = cur.fetchone()[0]

        cur.execute("""
            SELECT organization_type, COUNT(*)
            FROM bronze.bronze_locations
            GROUP BY organization_type
            ORDER BY COUNT(*) DESC
        """)
        type_counts = cur.fetchall()
    
    conn.close()
    
    logger.info("\n" + "=" * 80)
    logger.info("DATABASE SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total organizations: {total_count:,}")
    logger.info("\nBy type:")
    for org_type, count in type_counts:
        logger.info(f"  {org_type}: {count:,}")


if __name__ == "__main__":
    main()
