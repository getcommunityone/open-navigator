#!/usr/bin/env python3
"""
Migrate ONLY bills map aggregates to Neon PostgreSQL (lightweight version).

This script computes state-level summaries from parquet files and stores them in Neon.
Detailed bills remain in parquet to save Neon storage space.

Storage comparison:
- Full bills: ~75K rows per state = ~500K total rows
- Map aggregates: 1 row per state = ~50 total rows (10,000x smaller!)

Usage:
    python neon/migrate_bills.py
    
Environment variables:
    NEON_DATABASE_URL: PostgreSQL connection string (required)
"""

import os
import sys
from pathlib import Path
import pandas as pd
import psycopg2
from loguru import logger
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Database connection - prioritize dev over production
NEON_DATABASE_URL_DEV = os.getenv("NEON_DATABASE_URL_DEV")
NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL")
DATABASE_URL = NEON_DATABASE_URL_DEV or NEON_DATABASE_URL

if not DATABASE_URL:
    logger.error("❌ Neither NEON_DATABASE_URL_DEV nor NEON_DATABASE_URL environment variable set")
    sys.exit(1)

logger.info(f"Using: {'DEV' if NEON_DATABASE_URL_DEV else 'PROD'} database")

GOLD_DIR = Path("data/gold")
STATES_DIR = GOLD_DIR / "states"


def get_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(DATABASE_URL)


def execute_schema():
    """Create database schema from SQL file."""
    schema_file = Path(__file__).parent / "schema_bills.sql"
    
    logger.info("📋 Creating bills database schema...")
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            with open(schema_file, 'r') as f:
                cur.execute(f.read())
        conn.commit()
    
    logger.success("✅ Schema created successfully")


def clean_value(val):
    """Clean pandas NaN and None values for PostgreSQL."""
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)) and pd.isna(val):
        return None
    return val


def parse_date(date_str):
    """Parse date string to proper format."""
    if pd.isna(date_str) or date_str is None:
        return None
    
    try:
        # Handle various date formats
        if isinstance(date_str, str):
            return date_str.split()[0]  # Extract date part from timestamp
        return str(date_str).split()[0]
    except:
        return None


def load_bills_from_state(state_code: str, conn):
    """Compute map aggregates from a state's bills parquet file."""
    bills_file = STATES_DIR / state_code / "bills_bills.parquet"
    
    if not bills_file.exists():
        logger.warning(f"⚠️  Bills file not found for {state_code}: {bills_file}")
        return None
    
    logger.info(f"📥 Computing aggregates for {state_code}...")
    
    # Read parquet file
    df = pd.read_parquet(bills_file)
    
    if len(df) == 0:
        logger.warning(f"⚠️  No bills found for {state_code}")
        return None
    
    # Count by classification type
    type_counts = {
        'bill': 0,
        'resolution': 0,
        'concurrent_resolution': 0,
        'joint_resolution': 0,
        'constitutional_amendment': 0
    }
    
    for _, row in df.iterrows():
        classification = row['classification']
        if isinstance(classification, (list, tuple)) and len(classification) > 0:
            class_type = classification[0].lower().replace(' ', '_')
            if class_type in type_counts:
                type_counts[class_type] += 1
            elif class_type == 'concurrent resolution':
                type_counts['concurrent_resolution'] += 1
            elif class_type == 'joint resolution':
                type_counts['joint_resolution'] += 1
            elif class_type == 'constitutional amendment':
                type_counts['constitutional_amendment'] += 1
            else:
                type_counts['bill'] += 1  # Default to bill
    
    total_bills = len(df)
    
    # Determine primary type (most common)
    primary_type = max(type_counts, key=type_counts.get)
    
    # Determine map category based on total bills
    if total_bills > 1000:
        map_category = 'high'
    elif total_bills > 100:
        map_category = 'medium'
    else:
        map_category = 'low'
    
    # Get sample bills (top 3 most recent)
    # Convert date column to datetime for proper sorting
    df['latest_action_date_dt'] = pd.to_datetime(df['latest_action_date'], errors='coerce')
    sample_df = df.nlargest(3, 'latest_action_date_dt', keep='first')[['bill_number', 'title', 'latest_action_date']]
    sample_bills = []
    for _, row in sample_df.iterrows():
        sample_bills.append({
            'bill_number': str(row['bill_number']),
            'title': str(row['title']),
            'latest_action_date': str(row['latest_action_date']) if pd.notna(row['latest_action_date']) else None
        })
    
    # Insert aggregate into database
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bill_map_aggregate (
                state_code, topic, total_bills,
                type_bill, type_resolution, type_concurrent_resolution,
                type_joint_resolution, type_constitutional_amendment,
                status_pending, primary_type, primary_status, map_category, sample_bills
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (state_code, topic) DO UPDATE SET
                total_bills = EXCLUDED.total_bills,
                type_bill = EXCLUDED.type_bill,
                type_resolution = EXCLUDED.type_resolution,
                type_concurrent_resolution = EXCLUDED.type_concurrent_resolution,
                type_joint_resolution = EXCLUDED.type_joint_resolution,
                type_constitutional_amendment = EXCLUDED.type_constitutional_amendment,
                status_pending = EXCLUDED.status_pending,
                primary_type = EXCLUDED.primary_type,
                primary_status = EXCLUDED.primary_status,
                map_category = EXCLUDED.map_category,
                sample_bills = EXCLUDED.sample_bills,
                last_updated = NOW()
            """,
            (
                state_code,
                'all',  # topic
                total_bills,
                type_counts['bill'],
                type_counts['resolution'],
                type_counts['concurrent_resolution'],
                type_counts['joint_resolution'],
                type_counts['constitutional_amendment'],
                total_bills,  # All treated as pending (we don't track status)
                primary_type,
                'pending',  # Default status
                map_category,
                json.dumps(sample_bills)
            )
        )
    
    logger.success(f"✅ {state_code}: {total_bills:,} bills → 1 aggregate row")
    return 1  # Return 1 aggregate row created


def calculate_sessions(conn):
    """Skip - sessions will use parquet for drill-down."""
    logger.info("⏭️  Skipping sessions (using parquet for drill-down)")
    return 0


def calculate_map_aggregates(conn):
    """Skip - already calculated during state processing."""
    logger.info("⏭️  Map aggregates already calculated")
    return 0


def record_sync(conn, table_name: str, rows: int, status: str = "success", error: str = None):
    """Record sync operation in log table."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO log_neon_sync (table_name, rows_inserted, status, error_message)
            VALUES (%s, %s, %s, %s)
            """,
            (table_name, rows, status, error)
        )


def main():
    """Main migration function."""
    logger.info("🚀 Starting lightweight bills map migration to Neon PostgreSQL")
    logger.info("📦 Strategy: Map aggregates in Neon, detailed bills in parquet")
    logger.info(f"📂 Gold directory: {GOLD_DIR}")
    logger.info(f"🔗 Database: {DATABASE_URL.split('@')[1].split('/')[0] if DATABASE_URL and '@' in DATABASE_URL else 'localhost'}")
    
    try:
        # Create schema
        execute_schema()
        
        # Get list of states
        states = [d.name for d in STATES_DIR.iterdir() if d.is_dir() and len(d.name) == 2]
        logger.info(f"📍 Found {len(states)} states: {', '.join(sorted(states))}")
        
        # Compute and load map aggregates from all states
        total_aggregates = 0
        with get_connection() as conn:
            for state in sorted(states):
                agg_count = load_bills_from_state(state, conn)
                if agg_count:
                    total_aggregates += agg_count
            
            conn.commit()
            record_sync(conn, "bill_map_aggregate", total_aggregates, "success")
            conn.commit()
        
        logger.success("🎉 Migration completed successfully!")
        logger.info("📊 Summary:")
        logger.info(f"   - States processed: {len(states)}")
        logger.info(f"   - Map aggregates: {total_aggregates:,} rows")
        logger.info("   - Space saved: Aggregates only (not storing full bills)")
        logger.info("   - Drill-down: Uses parquet files for detailed queries")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
