#!/usr/bin/env python3
"""
Load LocalView Meeting Data into bronze.bronze_events_localview table

This script reads all LocalView parquet files and inserts meeting data
into the bronze.bronze_events_localview table following the medallion architecture.
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')

# LocalView data directory
LOCALVIEW_DIR = Path('data/cache/localview')

CREATE_TABLE_SQL = """
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE IF NOT EXISTS bronze.bronze_events_localview (
        event_id          BIGINT PRIMARY KEY,
        event_date        DATE,
        jurisdiction_name VARCHAR(500),
        jurisdiction_type VARCHAR(100),
        jurisdiction_id   INTEGER,
        city              VARCHAR(255),
        state_code        VARCHAR(2),
        state             VARCHAR(100),
        meeting_type      VARCHAR(255),
        title             VARCHAR(500),
        video_url         TEXT,
        channel_id        VARCHAR(255),
        datasource        VARCHAR(100),
        datasource_id     VARCHAR(255),
        loaded_at         TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_belv_event_date  ON bronze.bronze_events_localview(event_date);
    CREATE INDEX IF NOT EXISTS idx_belv_state_code  ON bronze.bronze_events_localview(state_code);
    CREATE INDEX IF NOT EXISTS idx_belv_datasource  ON bronze.bronze_events_localview(datasource);
"""

# State abbreviation mapping
STATE_ABBREV = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
    'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA',
    'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
    'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO',
    'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
    'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
    'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
    'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY'
}


def get_state_abbrev(state_name: str) -> str:
    """Convert state name to abbreviation."""
    if pd.isna(state_name):
        return None
    return STATE_ABBREV.get(state_name, state_name[:2].upper())


def construct_youtube_url(vid_id: str) -> str:
    """Construct YouTube URL from video ID."""
    if pd.isna(vid_id):
        return None
    return f"https://www.youtube.com/watch?v={vid_id}"


def extract_channel_id_from_url(video_url: str) -> str:
    """Extract YouTube channel ID from video URL."""
    if pd.isna(video_url):
        return None
    # We'll need to query YouTube API or lookup from existing data
    # For now, return None - will be enriched later
    return None


def row_to_event(row: pd.Series, row_index: int) -> Dict[str, Any]:
    """Convert LocalView row to bronze_events_localview format."""
    # Parse meeting date
    event_date = None
    if pd.notna(row.get('meeting_date')):
        try:
            event_date = pd.to_datetime(row['meeting_date']).date()
        except:
            pass
    
    # Get video URL
    video_url = construct_youtube_url(row.get('vid_id'))
    
    # Extract title - use video title or create from place + date
    title = row.get('vid_title')
    if pd.isna(title) or not title:
        place = row.get('place_name', 'City Council')
        date_str = event_date.strftime('%B %d, %Y') if event_date else ''
        title = f"{place} Meeting - {date_str}" if date_str else f"{place} Meeting"
    
    # Get state info
    state_name = row.get('state_name')
    state_code = get_state_abbrev(state_name)
    
    # Generate event_id from video_id
    vid_id = row.get('vid_id')
    event_id = hash(f"localview_{vid_id}") % 2147483647 if pd.notna(vid_id) else None
    
    # Get jurisdiction info
    jurisdiction_name = row.get('place_name')
    
    return {
        'event_id': event_id,
        'event_date': event_date,
        'jurisdiction_name': jurisdiction_name,
        'jurisdiction_type': 'city',  # LocalView is municipal data
        'jurisdiction_id': None,  # Will be enriched later
        'city': row.get('place_name'),
        'state_code': state_code,
        'state': state_name,
        'meeting_type': row.get('place_govt', 'City Council'),
        'title': title[:500] if title else 'City Council Meeting',  # Limit length
        'video_url': video_url,
        'channel_id': extract_channel_id_from_url(video_url),  # Will be enriched later
        'datasource': 'localview',
        'datasource_id': vid_id,  # YouTube video ID
        'loaded_at': datetime.now()
    }


def load_parquet_file(filepath: Path, conn, batch_size: int = 1000) -> int:
    """Load a single parquet file into database."""
    logger.info(f"Loading {filepath.name}...")
    
    # Read parquet file
    df = pd.read_parquet(filepath)
    logger.info(f"  Rows in file: {len(df):,}")
    
    # Filter: only rows with meeting_date and video URL
    df_valid = df[df['meeting_date'].notna() & df['vid_id'].notna()].copy()
    logger.info(f"  Valid meetings with dates and videos: {len(df_valid):,}")
    
    if len(df_valid) == 0:
        return 0
    
    # Convert to events
    events = [row_to_event(row, idx) for idx, row in df_valid.iterrows()]
    
    # Insert into bronze table in batches
    insert_query = """
        INSERT INTO bronze.bronze_events_localview (
            event_id, event_date, jurisdiction_name, jurisdiction_type,
            jurisdiction_id, city, state_code, state, meeting_type,
            title, video_url, channel_id, datasource, datasource_id, loaded_at
        ) VALUES (
            %(event_id)s, %(event_date)s, %(jurisdiction_name)s, %(jurisdiction_type)s,
            %(jurisdiction_id)s, %(city)s, %(state_code)s, %(state)s, %(meeting_type)s,
            %(title)s, %(video_url)s, %(channel_id)s, %(datasource)s, %(datasource_id)s, %(loaded_at)s
        )
        ON CONFLICT (event_id) DO NOTHING
    """
    
    cursor = conn.cursor()
    inserted = 0
    
    try:
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            execute_batch(cursor, insert_query, batch, page_size=batch_size)
            inserted += len(batch)
            conn.commit()
            
            if i % 10000 == 0 and i > 0:
                logger.info(f"  Inserted {i:,} / {len(events):,} events...")
        
        logger.success(f"  ✓ Inserted {inserted:,} events from {filepath.name}")
        return inserted
        
    except Exception as e:
        conn.rollback()
        logger.error(f"  ✗ Error inserting from {filepath.name}: {e}")
        raise
    finally:
        cursor.close()


def main():
    """Main loading function."""
    logger.info("=" * 80)
    logger.info("LOCALVIEW → POSTGRES LOADER")
    logger.info("=" * 80)
    logger.info(f"Source: {LOCALVIEW_DIR}")
    logger.info(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")
    logger.info("")
    
    # Find all parquet files
    parquet_files = sorted(LOCALVIEW_DIR.glob('meetings.*.parquet'))
    logger.info(f"Found {len(parquet_files)} parquet files")
    logger.info("")
    
    if not parquet_files:
        logger.error("No parquet files found!")
        return 1
    
    # Connect to database and ensure table exists
    logger.info("Connecting to database...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.success("✓ Connected")
        cur = conn.cursor()
        cur.execute(CREATE_TABLE_SQL)
        conn.commit()
        cur.close()
        logger.info("✓ bronze.bronze_events_localview ready")
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return 1
    
    # Load each file
    total_inserted = 0
    start_time = datetime.now()
    
    try:
        for filepath in parquet_files:
            inserted = load_parquet_file(filepath, conn)
            total_inserted += inserted
        
        # Get final count
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bronze.bronze_events_localview WHERE datasource = 'localview'")
        final_count = cursor.fetchone()[0]
        cursor.close()
        
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info("")
        logger.success("=" * 80)
        logger.success("✓ LOADING COMPLETE")
        logger.success("=" * 80)
        logger.success(f"Events inserted: {total_inserted:,}")
        logger.success(f"Total LocalView events in database: {final_count:,}")
        logger.success(f"Duration: {duration:.1f} seconds")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Query events: SELECT COUNT(*), state FROM events_search WHERE source='localview' GROUP BY state")
        logger.info("2. Test search: http://localhost:5173/meetings")
        
        return 0
        
    except Exception as e:
        logger.error(f"✗ Loading failed: {e}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
