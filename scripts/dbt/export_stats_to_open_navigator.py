#!/usr/bin/env python3
"""
Export stats_aggregates from bronze DB to open_navigator DB

This syncs the dbt-generated stats from open_navigator_bronze to the 
production-ready open_navigator database for fast queries.

Usage:
    python scripts/dbt/export_stats_to_open_navigator.py
"""

import psycopg2
from psycopg2.extras import execute_values, Json
from loguru import logger
from datetime import datetime
import json

# Database connections
BRONZE_DB = "postgresql://postgres:password@localhost:5433/open_navigator_bronze"
PROD_DB = "postgresql://postgres:password@localhost:5433/open_navigator"


def sync_stats():
    """Copy stats_aggregates from bronze to production database"""
    
    logger.info("🔄 Starting stats sync: bronze → open_navigator")
    
    # Connect to both databases
    bronze_conn = psycopg2.connect(BRONZE_DB)
    prod_conn = psycopg2.connect(PROD_DB)
    
    try:
        bronze_cursor = bronze_conn.cursor()
        prod_cursor = prod_conn.cursor()
        
        # Step 1: Read stats from bronze
        logger.info("📥 Reading stats from bronze database...")
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
                contacts_count,
                total_revenue,
                total_assets,
                trending_causes,
                last_updated
            FROM stats_aggregates
            ORDER BY level, state_code, county, city
        """)
        
        stats_rows = bronze_cursor.fetchall()
        logger.info(f"  Found {len(stats_rows)} stats records")
        
        if not stats_rows:
            logger.warning("⚠️  No stats found in bronze database. Run dbt first!")
            return False
        
        # Step 2: Clear existing stats in production
        logger.info("🗑️  Clearing existing stats in open_navigator...")
        prod_cursor.execute("DELETE FROM stats_aggregates")
        deleted_count = prod_cursor.rowcount
        logger.info(f"  Deleted {deleted_count} old records")
        
        # Step 3: Insert new stats (id will auto-generate)
        logger.info("💾 Inserting updated stats...")
        
        # Convert rows: wrap JSONB dict in Json() for psycopg2
        processed_rows = []
        for row in stats_rows:
            row_list = list(row)
            # trending_causes is at index 13
            if row_list[13] is not None:
                row_list[13] = Json(row_list[13])
            processed_rows.append(tuple(row_list))
        
        insert_query = """
            INSERT INTO stats_aggregates (
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
                contacts_count,
                total_revenue,
                total_assets,
                trending_causes,
                last_updated
            ) VALUES %s
        """
        
        execute_values(prod_cursor, insert_query, processed_rows)
        prod_conn.commit()
        
        # Step 4: Verify the sync
        prod_cursor.execute("SELECT COUNT(*) FROM stats_aggregates")
        final_count = prod_cursor.fetchone()[0]
        
        # Show sample of trending causes
        prod_cursor.execute("""
            SELECT level, state_code, 
                   jsonb_array_length(trending_causes) as cause_count
            FROM stats_aggregates 
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
    logger.info("Stats Sync: open_navigator_bronze → open_navigator")
    logger.info("=" * 60)
    
    success = sync_stats()
    
    if success:
        logger.success("✅ All done! Stats are ready for API queries.")
    else:
        logger.error("❌ Sync failed. Check errors above.")
        exit(1)


if __name__ == "__main__":
    main()
