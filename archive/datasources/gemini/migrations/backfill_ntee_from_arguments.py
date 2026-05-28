#!/usr/bin/env python3
"""
Backfill NTEE data by extracting organization IDs from arguments_for/arguments_against.

This script:
1. Extracts org_id from arguments_for/against JSONB fields
2. Populates primary_org_ids in bronze_decisions
3. Copies NTEE data to bronze_topics
"""

import psycopg2
import json
import logging
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Database URL - Bronze layer database
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
DATABASE_URL = os.getenv('LOCAL_BRONZE_DATABASE_URL', f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator_bronze')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_from_arguments():
    """Extract org_ids from arguments and backfill NTEE data."""
    
    logger.info("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    
    try:
        with conn.cursor() as cur:
            logger.info("Step 1: Extracting org_ids from arguments_for/against...")
            
            # Update bronze_decisions.primary_org_ids from arguments
            update_decisions_query = """
            WITH decision_orgs AS (
                SELECT 
                    id,
                    decision_id,
                    source_event_id,
                    -- Extract org_ids from arguments_for
                    COALESCE(
                        (SELECT jsonb_agg(DISTINCT arg->>'org_id') 
                         FROM jsonb_array_elements(arguments_for) arg 
                         WHERE arg->>'org_id' IS NOT NULL),
                        '[]'::jsonb
                    ) || 
                    -- Extract org_ids from arguments_against
                    COALESCE(
                        (SELECT jsonb_agg(DISTINCT arg->>'org_id') 
                         FROM jsonb_array_elements(arguments_against) arg 
                         WHERE arg->>'org_id' IS NOT NULL),
                        '[]'::jsonb
                    ) as extracted_org_ids
                FROM bronze_decisions
                WHERE primary_org_ids IS NULL
            )
            UPDATE bronze_decisions bd
            SET primary_org_ids = dorg.extracted_org_ids
            FROM decision_orgs dorg
            WHERE bd.id = dorg.id
            AND dorg.extracted_org_ids::text != '[]';
            """
            
            cur.execute(update_decisions_query)
            decisions_updated = cur.rowcount
            logger.info(f"✅ Updated {decisions_updated} decisions with org_ids")
            
            conn.commit()
            
            logger.info("Step 2: Copying NTEE data to bronze_topics...")
            
            # Now backfill topics from decisions
            update_topics_query = """
            WITH decision_orgs AS (
                SELECT 
                    bd.decision_id,
                    bd.primary_org_ids,
                    (bd.primary_org_ids->0)::text as first_org_id
                FROM bronze_decisions bd
                WHERE bd.primary_org_ids IS NOT NULL
                AND bd.primary_org_ids::text != '[]'
            ),
            topic_data AS (
                SELECT 
                    bt.id as topic_id,
                    dorg.primary_org_ids,
                    bo.ntee_code,
                    bo.ntee_major_group,
                    bo.ntee_category_label
                FROM bronze_topics bt
                JOIN decision_orgs dorg ON dorg.decision_id = bt.decision_id
                JOIN bronze_organizations_meetings bo ON bo.org_id = TRIM(BOTH '"' FROM dorg.first_org_id)
                WHERE bt.ntee_code IS NULL
                AND bo.ntee_code IS NOT NULL
            )
            UPDATE bronze_topics bt
            SET 
                ntee_code = td.ntee_code,
                ntee_major_group = td.ntee_major_group,
                ntee_category_label = td.ntee_category_label,
                primary_org_ids = td.primary_org_ids
            FROM topic_data td
            WHERE bt.id = td.topic_id;
            """
            
            cur.execute(update_topics_query)
            topics_updated = cur.rowcount
            logger.info(f"✅ Updated {topics_updated} topics with NTEE data")
            
            conn.commit()
            
            # Show summary
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(primary_org_ids) as with_orgs,
                    COUNT(primary_org_ids) FILTER (WHERE primary_org_ids::text != '[]') as with_actual_orgs
                FROM bronze_decisions
            """)
            total_dec, with_orgs, with_actual = cur.fetchone()
            logger.info(f"\n📊 bronze_decisions:")
            logger.info(f"  Total: {total_dec}")
            logger.info(f"  With org_ids populated: {with_orgs}")
            logger.info(f"  With actual org references: {with_actual}")
            
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(ntee_code) as with_ntee,
                    COUNT(primary_org_ids) as with_orgs
                FROM bronze_topics
            """)
            total_top, with_ntee, with_orgs = cur.fetchone()
            logger.info(f"\n📊 bronze_topics:")
            logger.info(f"  Total: {total_top}")
            logger.info(f"  With NTEE: {with_ntee} ({with_ntee/total_top*100:.1f}%)")
            logger.info(f"  With org_ids: {with_orgs}")
            
            # Show top NTEE categories
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
            
            logger.info(f"\n📋 Top NTEE categories in topics:")
            for code, group, count in cur.fetchall():
                logger.info(f"  {code} - {group}: {count}")
                
    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
        logger.info("\nDatabase connection closed")


if __name__ == "__main__":
    backfill_from_arguments()
