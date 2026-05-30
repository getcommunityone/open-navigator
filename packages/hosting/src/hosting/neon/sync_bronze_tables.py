#!/usr/bin/env python3
"""
Sync Bronze Tables from Local to Neon (Cloud)

Flexible script to sync any bronze schema tables from local PostgreSQL to Neon cloud.
Supports selecting specific tables or syncing all bronze tables.

Usage:
    # Sync specific tables
    python sync_bronze_tables.py bronze_events_youtube bronze_events_text_ai
    
    # Sync all bronze tables
    python sync_bronze_tables.py --all
    
    # Sync with options
    python sync_bronze_tables.py bronze_events_youtube --full --batch-size 500
    
Prerequisites:
    - NEON_DATABASE_URL in .env (cloud database)
    - Local database at localhost:5433
    - Bronze schema exists in both databases
"""

import os
import sys
import psycopg2
from psycopg2.extras import execute_batch, RealDictCursor
from dotenv import load_dotenv
from loguru import logger
import argparse
from typing import List

# Load environment variables
load_dotenv()

# Database connections
LOCAL_DB_URL = os.getenv(
    'LOCAL_DATABASE_URL',
    'postgresql://postgres:password@localhost:5433/open_navigator'
)
NEON_DB_URL = os.getenv('NEON_DATABASE_URL')

if not NEON_DB_URL:
    logger.error("❌ NEON_DATABASE_URL not found in environment")
    logger.error("   Set it in .env file to your Neon cloud database URL")
    sys.exit(1)


def get_all_bronze_tables(conn) -> List[str]:
    """Get list of all bronze schema tables from local database."""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'bronze'
            ORDER BY tablename
        """)
        return [row[0] for row in cursor.fetchall()]


def table_exists(conn, table_name: str) -> bool:
    """Check if table exists in bronze schema."""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM pg_tables 
                WHERE schemaname = 'bronze' AND tablename = %s
            )
        """, (table_name,))
        return cursor.fetchone()[0]


def get_table_info(conn, table_name: str) -> dict:
    """Get table metadata (row count, size, primary key)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        # Get row count
        cursor.execute(f"SELECT COUNT(*) as count FROM bronze.{table_name}")
        count = cursor.fetchone()['count']
        
        # Get table size
        cursor.execute(f"""
            SELECT pg_size_pretty(pg_total_relation_size('bronze.{table_name}')) as size
        """)
        size = cursor.fetchone()['size']
        
        # Get primary key column(s)
        cursor.execute(f"""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = 'bronze.{table_name}'::regclass
            AND i.indisprimary
        """)
        pk_cols = [row['attname'] for row in cursor.fetchall()]
        
        return {
            'count': count,
            'size': size,
            'primary_keys': pk_cols
        }


def get_columns(conn, table_name: str) -> List[str]:
    """Get column names for a table."""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'bronze' AND table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        return [row[0] for row in cursor.fetchall()]


def sync_table(
    local_conn, 
    neon_conn, 
    table_name: str, 
    batch_size: int = 1000,
    incremental: bool = True
) -> bool:
    """
    Sync a single bronze table from local to Neon.
    
    Args:
        local_conn: Local database connection
        neon_conn: Neon database connection
        table_name: Name of the table (without schema prefix)
        batch_size: Number of records per batch
        incremental: If True, skip records that already exist in Neon
    
    Returns:
        True if successful, False otherwise
    """
    logger.info("")
    logger.info(f"{'='*80}")
    logger.info(f"SYNCING: bronze.{table_name}")
    logger.info(f"{'='*80}")
    
    try:
        # Check if table exists in both databases
        if not table_exists(local_conn, table_name):
            logger.error(f"❌ Table bronze.{table_name} not found in local database")
            return False
        
        if not table_exists(neon_conn, table_name):
            logger.error(f"❌ Table bronze.{table_name} not found in Neon database")
            logger.error(f"   Create it first with: dbt run --select {table_name} --target prod")
            return False
        
        # Get table info
        local_info = get_table_info(local_conn, table_name)
        neon_info = get_table_info(neon_conn, table_name)
        
        logger.info(f"📊 Local: {local_info['count']:,} rows ({local_info['size']})")
        logger.info(f"☁️  Neon:  {neon_info['count']:,} rows ({neon_info['size']})")
        
        if local_info['count'] == 0:
            logger.warning("⏭️  Skipping: No data in local table")
            return True
        
        # Get columns
        columns = get_columns(local_conn, table_name)
        primary_key = local_info['primary_keys'][0] if local_info['primary_keys'] else None
        
        # Build query
        if incremental and neon_info['count'] > 0 and primary_key:
            logger.info(f"🔄 Incremental sync (checking {primary_key} column)")
            
            # Get existing IDs from Neon
            with neon_conn.cursor() as cursor:
                cursor.execute(f"SELECT {primary_key} FROM bronze.{table_name}")
                existing_ids = {row[0] for row in cursor.fetchall()}
            
            logger.info(f"   Found {len(existing_ids):,} existing records in Neon")
            
            # Fetch only new records from local
            with local_conn.cursor() as cursor:
                # Create temporary table with existing IDs
                if existing_ids:
                    placeholders = ','.join(['%s'] * len(existing_ids))
                    cursor.execute(f"""
                        SELECT * FROM bronze.{table_name}
                        WHERE {primary_key} NOT IN ({placeholders})
                        ORDER BY {primary_key}
                    """, tuple(existing_ids))
                else:
                    cursor.execute(f"SELECT * FROM bronze.{table_name} ORDER BY {primary_key}")
                
                rows = cursor.fetchall()
        else:
            logger.info("📦 Full sync (copying all records)")
            with local_conn.cursor() as cursor:
                cursor.execute(f"SELECT * FROM bronze.{table_name}")
                rows = cursor.fetchall()
        
        total_rows = len(rows)
        
        if total_rows == 0:
            logger.success("✅ No new records to sync")
            return True
        
        logger.info(f"📥 Fetched {total_rows:,} records to sync")
        
        # Prepare INSERT query
        column_names = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))
        
        # Build ON CONFLICT clause
        if primary_key:
            # Update all columns except primary key on conflict
            update_cols = [col for col in columns if col != primary_key]
            update_set = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_cols])
            on_conflict = f"ON CONFLICT ({primary_key}) DO UPDATE SET {update_set}"
        else:
            # No primary key - just insert and hope for no duplicates
            on_conflict = "ON CONFLICT DO NOTHING"
        
        insert_query = f"""
            INSERT INTO bronze.{table_name} ({column_names})
            VALUES ({placeholders})
            {on_conflict}
        """
        
        # Insert in batches
        logger.info(f"📤 Uploading to Neon (batch size: {batch_size})...")
        with neon_conn.cursor() as cursor:
            execute_batch(cursor, insert_query, rows, page_size=batch_size)
        
        neon_conn.commit()
        
        # Verify
        new_neon_info = get_table_info(neon_conn, table_name)
        
        logger.success("")
        logger.success(f"✅ SYNC COMPLETE: bronze.{table_name}")
        logger.success(f"   Records synced: {total_rows:,}")
        logger.success(f"   Neon total:     {new_neon_info['count']:,} rows")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Sync failed for bronze.{table_name}: {e}")
        neon_conn.rollback()
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync bronze tables from local to Neon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync specific tables
  python sync_bronze_tables.py bronze_events_youtube bronze_events_text_ai
  
  # Sync all bronze tables
  python sync_bronze_tables.py --all
  
  # Full sync (replace data)
  python sync_bronze_tables.py bronze_events_youtube --full
  
  # Custom batch size
  python sync_bronze_tables.py bronze_events_youtube --batch-size 500
        """
    )
    
    parser.add_argument(
        'tables',
        nargs='*',
        help='Table names to sync (without bronze. prefix)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Sync all bronze schema tables'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Full sync (default: incremental)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Batch size for inserts (default: 1000)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available bronze tables and exit'
    )
    
    args = parser.parse_args()
    
    # Connect to databases
    logger.info("📡 Connecting to databases...")
    local_conn = psycopg2.connect(LOCAL_DB_URL)
    
    # List tables if requested
    if args.list:
        logger.info("📋 Available bronze tables in local database:")
        tables = get_all_bronze_tables(local_conn)
        for i, table in enumerate(tables, 1):
            info = get_table_info(local_conn, table)
            logger.info(f"   {i:2}. {table:40} {info['count']:>10,} rows ({info['size']})")
        local_conn.close()
        return 0
    
    neon_conn = psycopg2.connect(NEON_DB_URL)
    
    try:
        # Determine which tables to sync
        if args.all:
            tables_to_sync = get_all_bronze_tables(local_conn)
            logger.info(f"🔄 Syncing ALL {len(tables_to_sync)} bronze tables")
        elif args.tables:
            tables_to_sync = args.tables
            logger.info(f"🔄 Syncing {len(tables_to_sync)} selected tables")
        else:
            parser.print_help()
            logger.error("\n❌ No tables specified. Use table names or --all flag.")
            return 1
        
        logger.info(f"   Mode: {'Full sync' if args.full else 'Incremental'}")
        logger.info(f"   Batch size: {args.batch_size:,}")
        logger.info("")
        
        # Sync each table
        success_count = 0
        fail_count = 0
        
        for table in tables_to_sync:
            # Remove bronze. prefix if user included it
            table_name = table.replace('bronze.', '')
            
            if sync_table(
                local_conn, 
                neon_conn, 
                table_name,
                batch_size=args.batch_size,
                incremental=not args.full
            ):
                success_count += 1
            else:
                fail_count += 1
        
        # Summary
        logger.info("")
        logger.info("="*80)
        logger.info("SYNC SUMMARY")
        logger.info("="*80)
        logger.success(f"✅ Successful: {success_count} tables")
        if fail_count > 0:
            logger.error(f"❌ Failed:     {fail_count} tables")
        logger.info("")
        
        return 0 if fail_count == 0 else 1
        
    finally:
        local_conn.close()
        neon_conn.close()


if __name__ == '__main__':
    sys.exit(main())
