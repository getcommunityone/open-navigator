#!/usr/bin/env python3
"""
Export jurisdiction_state_aggregate from bronze DB to open_navigator DB

This syncs the dbt-generated stats from open_navigator (bronze schema) to the
production-ready open_navigator database for fast queries.

Usage:
    python dbt_project/scripts/export_stats_to_open_navigator.py
"""

import psycopg2
from psycopg2.extras import execute_values, Json
from loguru import logger
from datetime import datetime
import json

# Database connections
BRONZE_DB = "postgresql://postgres:password@localhost:5433/open_navigator"
PROD_DB = "postgresql://postgres:password@localhost:5433/open_navigator"


def sync_stats():
    """Copy jurisdiction_state_aggregate from bronze to production database"""
    
    logger.info("🔄 Starting stats sync: bronze → open_navigator")
    
    # Connect to both databases
    bronze_conn = psycopg2.connect(BRONZE_DB)
    prod_conn = psycopg2.connect(PROD_DB)
    
    try:
        bronze_cursor = bronze_conn.cursor()
        prod_cursor = prod_conn.cursor()
        
        # Step 1: Read stats from bronze schema (same database)
        logger.info("📥 Reading stats from bronze schema...")
        bronze_cursor.execute("""
            SELECT 
                level,
                state_code,
                state,
                county,
                city,
                jurisdictions_count,
                school_districts_count,
                nonprofits_count,
                events_count,
                bills_count,
                persons_count,
                leaders_count,
                total_revenue,
                total_assets,
                trending_causes,
                last_updated
            FROM bronze.jurisdiction_state_aggregate
            ORDER BY level, state_code, county, city
        """)
        
        stats_rows = bronze_cursor.fetchall()
        logger.info(f"  Found {len(stats_rows)} stats records")
        
        if not stats_rows:
            logger.warning("⚠️  No stats found in bronze schema. Run dbt first!")
            return False
        
        # Step 2: Clear existing stats in production
        logger.info("🗑️  Clearing existing stats in open_navigator...")
        prod_cursor.execute("DELETE FROM jurisdiction_state_aggregate")
        deleted_count = prod_cursor.rowcount
        logger.info(f"  Deleted {deleted_count} old records")
        
        # Step 3: Insert new stats (id will auto-generate)
        logger.info("💾 Inserting updated stats...")
        
        # Convert rows: wrap JSONB dict in Json() for psycopg2
        processed_rows = []
        for row in stats_rows:
            row_list = list(row)
            # trending_causes is at index 14
            if row_list[14] is not None:
                row_list[14] = Json(row_list[14])
            processed_rows.append(tuple(row_list))
        
        insert_query = """
            INSERT INTO jurisdiction_state_aggregate (
                level,
                state_code,
                state,
                county,
                city,
                jurisdictions_count,
                school_districts_count,
                nonprofits_count,
                events_count,
                bills_count,
                persons_count,
                leaders_count,
                total_revenue,
                total_assets,
                trending_causes,
                last_updated
            ) VALUES %s
        """
        
        execute_values(prod_cursor, insert_query, processed_rows)
        prod_conn.commit()
        
        # Step 4: Verify the sync
        prod_cursor.execute("SELECT COUNT(*) FROM jurisdiction_state_aggregate")
        final_count = prod_cursor.fetchone()[0]
        
        # Show sample of trending causes
        prod_cursor.execute("""
            SELECT level, state_code, 
                   jsonb_array_length(trending_causes) as cause_count
            FROM jurisdiction_state_aggregate 
            WHERE trending_causes IS NOT NULL
            LIMIT 5
        """)
        samples = prod_cursor.fetchall()
        
        logger.success(f"✅ Sync complete: {final_count} records in open_navigator")
        
        if samples:
            logger.info("📊 Sample trending causes:")
            for level, state, count in samples:
                state_str = f"({state})" if state else ""
                logger.info(f"  - {level} {state_str}: {count} causes")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        prod_conn.rollback()
        return False
        
    finally:
        bronze_conn.close()
        prod_conn.close()


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("Stats Sync: open_navigator.bronze → open_navigator.public")
    logger.info("=" * 60)
    
    success = sync_stats()
    
    if success:
        logger.success("✅ All done! Stats are ready for API queries.")
    else:
        logger.error("❌ Sync failed. Check errors above.")
        exit(1)


if __name__ == "__main__":
    main()
