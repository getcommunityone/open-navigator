#!/usr/bin/env python3
"""
Add NTEE columns to bronze_topics table.

This migration adds the following columns:
- ntee_code: NTEE letter code (e.g., 'K', 'E', 'P')
- ntee_major_group: Top-level category (e.g., 'Food Agriculture and Nutrition')
- ntee_category_label: Full hierarchical label (e.g., 'Food Agriculture and Nutrition > Food Banks, Food Pantries')
- primary_org_ids: Array of organization IDs involved in the decision
"""

import psycopg2
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


def migrate():
    """Add NTEE columns to bronze_topics and primary_org_ids to bronze_decisions."""
    
    logger.info("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    
    try:
        with conn.cursor() as cur:
            logger.info("Adding primary_org_ids to bronze_decisions...")
            
            # Add primary_org_ids to bronze_decisions
            cur.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'bronze_decisions' 
                        AND column_name = 'primary_org_ids'
                    ) THEN
                        ALTER TABLE bronze_decisions ADD COLUMN primary_org_ids JSONB;
                    END IF;
                END $$;
            """)
            
            logger.info("✅ Successfully added primary_org_ids to bronze_decisions")
            
            logger.info("Adding NTEE columns to bronze_topics...")
            
            # Add columns to bronze_topics
            cur.execute("""
                DO $$ 
                BEGIN
                    -- Add ntee_code column
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'bronze_topics' 
                        AND column_name = 'ntee_code'
                    ) THEN
                        ALTER TABLE bronze_topics ADD COLUMN ntee_code VARCHAR(10);
                    END IF;
                    
                    -- Add ntee_major_group column
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'bronze_topics' 
                        AND column_name = 'ntee_major_group'
                    ) THEN
                        ALTER TABLE bronze_topics ADD COLUMN ntee_major_group VARCHAR(100);
                    END IF;
                    
                    -- Add ntee_category_label column
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'bronze_topics' 
                        AND column_name = 'ntee_category_label'
                    ) THEN
                        ALTER TABLE bronze_topics ADD COLUMN ntee_category_label VARCHAR(255);
                    END IF;
                    
                    -- Add primary_org_ids column (JSONB array)
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'bronze_topics' 
                        AND column_name = 'primary_org_ids'
                    ) THEN
                        ALTER TABLE bronze_topics ADD COLUMN primary_org_ids JSONB;
                    END IF;
                END $$;
            """)
            
            logger.info("✅ Successfully added NTEE columns to bronze_topics")
            
            # Create index on ntee_code for faster queries
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_bronze_topics_ntee_code 
                ON bronze_topics(ntee_code);
            """)
            
            logger.info("✅ Created index on ntee_code")
            
            conn.commit()
            
            # Show summary
            cur.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(ntee_code) as records_with_ntee
                FROM bronze_topics
            """)
            total, with_ntee = cur.fetchone()
            logger.info(f"📊 bronze_topics: {total} total records, {with_ntee} with NTEE data")
            
            cur.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(primary_org_ids) as records_with_orgs
                FROM bronze_decisions
            """)
            total_dec, with_orgs = cur.fetchone()
            logger.info(f"📊 bronze_decisions: {total_dec} total records, {with_orgs} with org IDs")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    migrate()
