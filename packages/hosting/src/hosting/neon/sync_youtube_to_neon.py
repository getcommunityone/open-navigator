#!/usr/bin/env python3
"""
Sync bronze_events_youtube from Local to Neon (Cloud)

This script copies data from the local PostgreSQL database to Neon cloud database.
It's a data MOVEMENT script (not transformation), so Python is appropriate here.

For transformations, use dbt models instead.

Usage:
    python sync_youtube_to_neon.py
    
Prerequisites:
    - NEON_DATABASE_URL or NEON_DATABASE_URL_DEV in .env
    - Local database at localhost:5433
    - bronze.bronze_events_youtube table exists in Neon (run dbt first)
"""

import os
import sys
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Database connections
LOCAL_DB_URL = os.getenv(
    'LOCAL_DATABASE_URL',
    'postgresql://postgres:password@localhost:5433/open_navigator'
)
# Use NEON_DATABASE_URL (cloud), NOT NEON_DATABASE_URL_DEV (which is local)
NEON_DB_URL = os.getenv('NEON_DATABASE_URL')

if not NEON_DB_URL:
    logger.error("❌ NEON_DATABASE_URL not found in environment")
    logger.error("   Set it in .env file to your Neon cloud database URL")
    logger.error("   (NEON_DATABASE_URL_DEV is for local development, not cloud)")
    sys.exit(1)


def count_records(conn, table_name):
    """Count records in a table."""
    with conn.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM bronze.{table_name}")
        return cursor.fetchone()[0]


def get_latest_video_date(conn):
    """Get the most recent video date in Neon."""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT MAX(event_date) 
            FROM bronze.bronze_events_youtube
        """)
        result = cursor.fetchone()[0]
        return result


def sync_youtube_data(batch_size=1000, incremental=True):
    """
    Sync bronze_events_youtube data from local to Neon.
    
    Args:
        batch_size: Number of records to insert per batch
        incremental: If True, only copy new records (based on video_id)
    """
    logger.info("=" * 80)
    logger.info("SYNC BRONZE_EVENTS_YOUTUBE: LOCAL → NEON")
    logger.info("=" * 80)
    
    # Connect to both databases
    logger.info("📡 Connecting to databases...")
    local_conn = psycopg2.connect(LOCAL_DB_URL)
    neon_conn = psycopg2.connect(NEON_DB_URL)
    
    try:
        # Check current counts
        local_count = count_records(local_conn, 'bronze_events_youtube')
        neon_count = count_records(neon_conn, 'bronze_events_youtube')
        
        logger.info(f"📊 Local database: {local_count:,} records")
        logger.info(f"☁️  Neon database:  {neon_count:,} records")
        logger.info("")
        
        if local_count == 0:
            logger.warning("⚠️  No data in local database. Nothing to sync.")
            return
        
        # Build query based on sync mode
        if incremental and neon_count > 0:
            logger.info("🔄 Incremental sync mode: Only copying new records")
            latest_date = get_latest_video_date(neon_conn)
            logger.info(f"   Latest Neon date: {latest_date}")
            
            query = """
                SELECT * FROM bronze.bronze_events_youtube
                WHERE video_id NOT IN (
                    SELECT video_id FROM bronze.bronze_events_youtube
                )
                OR event_date > %s
                ORDER BY event_date DESC, id
            """
            params = (latest_date,) if latest_date else None
        else:
            logger.info("📦 Full sync mode: Copying all records")
            query = """
                SELECT * FROM bronze.bronze_events_youtube
                ORDER BY id
            """
            params = None
        
        # Fetch data from local
        logger.info("📥 Fetching data from local database...")
        with local_conn.cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Get column names
            columns = [desc[0] for desc in cursor.description]
            
            # Fetch all rows
            rows = cursor.fetchall()
            total_rows = len(rows)
        
        if total_rows == 0:
            logger.success("✅ No new records to sync. Already up to date!")
            return
        
        logger.info(f"   Found {total_rows:,} records to sync")
        logger.info("")
        
        # Prepare INSERT query
        placeholders = ', '.join(['%s'] * len(columns))
        column_names = ', '.join(columns)
        insert_query = f"""
            INSERT INTO bronze.bronze_events_youtube ({column_names})
            VALUES ({placeholders})
            ON CONFLICT (video_id) DO UPDATE SET
                event_date = EXCLUDED.event_date,
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                view_count = EXCLUDED.view_count,
                like_count = EXCLUDED.like_count,
                last_updated = EXCLUDED.last_updated
        """
        
        # Insert data in batches
        logger.info(f"📤 Uploading to Neon (batch size: {batch_size})...")
        with neon_conn.cursor() as cursor:
            execute_batch(cursor, insert_query, rows, page_size=batch_size)
        
        neon_conn.commit()
        
        # Verify
        new_neon_count = count_records(neon_conn, 'bronze_events_youtube')
        logger.success("=" * 80)
        logger.success("✅ SYNC COMPLETE")
        logger.success("=" * 80)
        logger.success(f"📊 Records synced: {total_rows:,}")
        logger.success(f"☁️  Neon total:    {new_neon_count:,} records")
        logger.info("")
        
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        neon_conn.rollback()
        raise
    
    finally:
        local_conn.close()
        neon_conn.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Sync bronze_events_youtube from local to Neon"
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Full sync (replace all data, default: incremental)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Batch size for inserts (default: 1000)'
    )
    
    args = parser.parse_args()
    
    sync_youtube_data(
        batch_size=args.batch_size,
        incremental=not args.full
    )


if __name__ == '__main__':
    main()
