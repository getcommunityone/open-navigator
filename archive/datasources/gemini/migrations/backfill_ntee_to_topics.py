#!/usr/bin/env python3
"""
Backfill NTEE data into bronze_topics from bronze_organizations.

This script:
1. Joins bronze_topics with bronze_decisions to get primary_org_ids
2. Finds the primary organization from bronze_organizations_meetings
3. Copies NTEE fields from the organization to the topic
"""

import psycopg2
import json
import logging
import os
from pathlib import Path
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available, use environment variables directly

# Database URL - Bronze layer database
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
DATABASE_URL = os.getenv('LOCAL_BRONZE_DATABASE_URL', f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator_bronze')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_ntee():
    """Backfill NTEE data into bronze_topics from organizations."""
    
    logger.info("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    
    try:
        with conn.cursor() as cur:
            logger.info("Starting NTEE backfill for bronze_topics...")
            
            # Update bronze_topics with NTEE data from primary organization
            update_query = """
            WITH decision_orgs AS (
                -- Get primary_org_ids from bronze_decisions
                SELECT 
                    bd.decision_id,
                    bd.source_event_id,
                    bd.primary_org_ids
                FROM bronze_decisions bd
                WHERE bd.primary_org_ids IS NOT NULL
                AND bd.primary_org_ids::text != '[]'
            ),
            topic_orgs AS (
                -- Join topics with their decision's organizations
                SELECT 
                    bt.id as topic_id,
                    bt.decision_id,
                    dorg.primary_org_ids,
                    (dorg.primary_org_ids->0)::text as first_org_id
                FROM bronze_topics bt
                JOIN decision_orgs dorg ON dorg.decision_id = bt.decision_id
                WHERE bt.ntee_code IS NULL  -- Only update records without NTEE
            ),
            org_ntee AS (
                -- Get NTEE data from the first/primary organization
                SELECT 
                    torg.topic_id,
                    torg.primary_org_ids,
                    bo.ntee_code,
                    bo.ntee_major_group,
                    bo.ntee_category_label
                FROM topic_orgs torg
                JOIN bronze_organizations_meetings bo ON bo.org_id = TRIM(BOTH '"' FROM torg.first_org_id)
                WHERE bo.ntee_code IS NOT NULL
            )
            UPDATE bronze_topics bt
            SET 
                ntee_code = ont.ntee_code,
                ntee_major_group = ont.ntee_major_group,
                ntee_category_label = ont.ntee_category_label,
                primary_org_ids = ont.primary_org_ids
            FROM org_ntee ont
            WHERE bt.id = ont.topic_id;
            """
            
            cur.execute(update_query)
            updated_count = cur.rowcount
            
            logger.info(f"✅ Updated {updated_count} bronze_topics records with NTEE data")
            
            conn.commit()
            
            # Show summary statistics
            cur.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(ntee_code) as records_with_ntee,
                    COUNT(primary_org_ids) as records_with_orgs,
                    COUNT(DISTINCT ntee_code) as unique_ntee_codes
                FROM bronze_topics
            """)
            total, with_ntee, with_orgs, unique_codes = cur.fetchone()
            
            logger.info("📊 bronze_topics summary:")
            logger.info(f"  Total records: {total}")
            logger.info(f"  Records with NTEE: {with_ntee} ({with_ntee/total*100:.1f}%)")
            logger.info(f"  Records with org IDs: {with_orgs}")
            logger.info(f"  Unique NTEE codes: {unique_codes}")
            
            # Show breakdown by NTEE code
            cur.execute("""
                SELECT 
                    ntee_code,
                    ntee_major_group,
                    COUNT(*) as count
                FROM bronze_topics
                WHERE ntee_code IS NOT NULL
                GROUP BY ntee_code, ntee_major_group
                ORDER BY count DESC
                LIMIT 10
            """)
            
            logger.info("\n📋 Top 10 NTEE categories in topics:")
            for ntee_code, ntee_group, count in cur.fetchall():
                logger.info(f"  {ntee_code} - {ntee_group}: {count}")
                
    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    backfill_ntee()
