#!/usr/bin/env python3
"""
Clean up null raw_response records from events_text_ai table.

These records are from failed API calls that don't have any useful data.
Running this script will delete all records where raw_response IS NULL.

Usage:
    python scripts/datasources/gemini/cleanup_null_records.py
    
    # Dry run (see what would be deleted)
    python scripts/datasources/gemini/cleanup_null_records.py --dry-run
"""

import os
import sys
from pathlib import Path
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import psycopg2
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')


def cleanup_null_records(dry_run: bool = False):
    """Delete records where raw_response is NULL."""
    
    # First, count how many will be deleted
    count_sql = """
    SELECT COUNT(*) FROM events_text_ai WHERE raw_response IS NULL
    """
    
    delete_sql = """
    DELETE FROM events_text_ai WHERE raw_response IS NULL
    """
    
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Count null records
            cur.execute(count_sql)
            null_count = cur.fetchone()[0]
            
            if null_count == 0:
                logger.info("✅ No null records found - database is clean!")
                return
            
            logger.info(f"📊 Found {null_count} records with null raw_response")
            
            if dry_run:
                logger.info("🏃 DRY RUN - Would delete these records")
                logger.info("   Run without --dry-run to actually delete")
                return
            
            # Delete null records
            cur.execute(delete_sql)
            deleted_count = cur.rowcount
        
        conn.commit()
    
    logger.info(f"🧹 Deleted {deleted_count} records with null raw_response")
    logger.info("✅ Cleanup complete!")


def show_null_records():
    """Show details about null records before deletion."""
    
    query_sql = """
    SELECT 
        id,
        event_id,
        video_id,
        ai_model,
        error_message,
        created_at
    FROM events_text_ai 
    WHERE raw_response IS NULL
    ORDER BY created_at DESC
    LIMIT 20
    """
    
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(query_sql)
            rows = cur.fetchall()
            
            if not rows:
                logger.info("✅ No null records found")
                return
            
            logger.info(f"\n📋 Sample of null records (showing up to 20):\n")
            logger.info(f"{'ID':<8} {'Event ID':<12} {'Video ID':<15} {'Model':<20} {'Created':<20} {'Error'}")
            logger.info("-" * 120)
            
            for row in rows:
                id_, event_id, video_id, model, error, created = row
                error_preview = (error[:50] + '...') if error and len(error) > 50 else (error or 'None')
                logger.info(f"{id_:<8} {event_id:<12} {video_id:<15} {model:<20} {str(created)[:19]:<20} {error_preview}")


def main():
    parser = argparse.ArgumentParser(
        description='Clean up null raw_response records from events_text_ai table'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    
    parser.add_argument(
        '--show',
        action='store_true',
        help='Show details about null records before cleanup'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("CLEANUP NULL RECORDS FROM events_text_ai")
    logger.info("=" * 70)
    logger.info("")
    
    if args.show:
        show_null_records()
        logger.info("")
    
    cleanup_null_records(dry_run=args.dry_run)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
