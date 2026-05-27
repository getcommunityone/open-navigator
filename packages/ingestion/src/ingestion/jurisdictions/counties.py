#!/usr/bin/env python3
"""
Load Counties into PostgreSQL jurisdiction table

This script loads county data from data/gold/jurisdictions_counties.parquet
and adds them to the jurisdiction table alongside cities.

Usage:
    python scripts/datasources/jurisdictions/load_counties_to_postgres.py
    python scripts/datasources/jurisdictions/load_counties_to_postgres.py --states AL,GA,IN
"""
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')

# Source parquet file
COUNTIES_FILE = Path('data/gold/jurisdictions_counties.parquet')


def load_counties(conn, counties_file: Path, states_filter: list = None, batch_size: int = 1000):
    """Load counties from jurisdictions_counties.parquet."""
    
    logger.info(f"Loading counties from {counties_file.name}...")
    
    # Read parquet file
    df = pd.read_parquet(counties_file)
    logger.info(f"  Total counties in file: {len(df):,}")
    
    # Filter to specific states if provided
    if states_filter:
        df = df[df['USPS'].isin(states_filter)]
        logger.info(f"  Filtered to {len(df):,} counties in states: {', '.join(states_filter)}")
    
    # Prepare records for insertion
    records = []
    for _, row in df.iterrows():
        jurisdiction_name = row['NAME'].replace(' County', '').strip()
        from scripts.jurisdictions.jurisdiction_id import jurisdiction_id_from_name_geoid

        jurisdiction_id = jurisdiction_id_from_name_geoid(
            row['NAME'], str(row['GEOID']), jurisdiction_type="county"
        )
        
        record = {
            'jurisdiction_id': jurisdiction_id,
            'jurisdiction_name': jurisdiction_name,
            'state_code': row['USPS'],
            'state': row['USPS'],
            'jurisdiction_type': 'county',
            'population': 0,  # Counties file doesn't have population
            'discovery_timestamp': pd.to_datetime(row['download_date']) if pd.notna(row.get('download_date')) else pd.Timestamp.now(),
            'website_url': None,  # Will be discovered later
            'youtube_channel_count': 0,
            'youtube_channels': '[]',
            'meeting_platform_count': 0,
            'meeting_platforms': '[]',
            'social_media': '{}',
            'agenda_portal_count': 0,
            'status': 'pending_discovery'
        }
        records.append(record)
    
    logger.info(f"  Prepared {len(records):,} county records")
    
    # Insert into database
    insert_query = """
        INSERT INTO jurisdiction (
            jurisdiction_id, name, state_code, state, type,
            population, discovery_timestamp, website_url,
            youtube_channel_count, youtube_channels,
            meeting_platform_count, meeting_platforms,
            social_media, agenda_portal_count, discovery_status,
            source
        ) VALUES (
            %(jurisdiction_id)s, %(jurisdiction_name)s, %(state_code)s, %(state)s, %(jurisdiction_type)s,
            %(population)s, %(discovery_timestamp)s, %(website_url)s,
            %(youtube_channel_count)s, %(youtube_channels)s::jsonb,
            %(meeting_platform_count)s, %(meeting_platforms)s::jsonb,
            %(social_media)s::jsonb, %(agenda_portal_count)s, %(status)s,
            'discovery'
        )
        ON CONFLICT (jurisdiction_id) 
        DO UPDATE SET
            name = EXCLUDED.name,
            state = EXCLUDED.state,
            type = EXCLUDED.type,
            last_updated = CURRENT_TIMESTAMP
    """
    
    cursor = conn.cursor()
    inserted = 0
    
    try:
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            execute_batch(cursor, insert_query, batch, page_size=batch_size)
            inserted += len(batch)
            conn.commit()
            
            if i % 100 == 0 and i > 0:
                logger.info(f"  Inserted {i:,} / {len(records):,} counties...")
        
        logger.success(f"  ✓ Inserted/updated {inserted:,} counties")
        return inserted
        
    except Exception as e:
        conn.rollback()
        logger.error(f"  ✗ Error inserting counties: {e}")
        raise
    finally:
        cursor.close()


def main():
    """Main loading function."""
    parser = argparse.ArgumentParser(description='Load counties into jurisdiction')
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated list of state codes (e.g., AL,GA,IN,MA,MT,WA,WI)'
    )
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("COUNTIES → JURISDICTIONS_DETAILS_SEARCH LOADER")
    logger.info("=" * 80)
    logger.info(f"Source: {COUNTIES_FILE}")
    logger.info(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")
    logger.info("")
    
    # Parse states filter
    states_filter = None
    if args.states:
        states_filter = [s.strip().upper() for s in args.states.split(',')]
        logger.info(f"Filtering to states: {', '.join(states_filter)}")
    else:
        # Default to development states
        states_filter = ['AL', 'GA', 'IN', 'MA', 'WA', 'WI']
        logger.info(f"Using development states: {', '.join(states_filter)}")
    
    # Check if file exists
    if not COUNTIES_FILE.exists():
        logger.error(f"Counties file not found: {COUNTIES_FILE}")
        return 1
    
    # Connect to database
    logger.info("Connecting to database...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.success("✓ Connected")
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return 1
    
    start_time = datetime.now()
    
    try:
        # Load counties
        inserted = load_counties(conn, COUNTIES_FILE, states_filter=states_filter)
        
        # Get final stats
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE jurisdiction_type = 'city') as cities,
                COUNT(*) FILTER (WHERE jurisdiction_type = 'county') as counties,
                COUNT(DISTINCT state) as states
            FROM jurisdiction
        """)
        stats = cursor.fetchone()
        cursor.close()
        
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info("")
        logger.success("=" * 80)
        logger.success("✓ COUNTIES LOADED")
        logger.success("=" * 80)
        logger.info(f"Counties loaded: {inserted:,}")
        logger.info("")
        logger.info("Database totals:")
        logger.info(f"  Total jurisdictions: {stats[0]:,}")
        logger.info(f"  - Cities: {stats[1]:,}")
        logger.info(f"  - Counties: {stats[2]:,}")
        logger.info(f"  States: {stats[3]}")
        logger.info(f"Duration: {duration:.1f} seconds")
        logger.info("")
        
        logger.info("Next steps:")
        logger.info("1. Re-run LocalView enrichment to match counties:")
        logger.info("   python scripts/datasources/localview/enrich_from_localview.py")
        logger.info("2. Query counties: SELECT * FROM jurisdiction WHERE jurisdiction_type='county' AND state='AL'")
        
        return 0
        
    except Exception as e:
        logger.error(f"✗ Loading failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
