#!/usr/bin/env python3
"""
Add secondary NTEE columns to bronze_topics table.
"""

import psycopg2
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


def migrate():
    """Add secondary NTEE columns to bronze_topics and bronze_decisions."""
    
    logger.info("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    
    try:
        with conn.cursor() as cur:
            logger.info("Adding secondary NTEE columns to bronze_topics...")
            
            cur.execute("""
                DO $$ 
                BEGIN
                    -- Add secondary_ntee_code column
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'bronze_topics' 
                        AND column_name = 'secondary_ntee_code'
                    ) THEN
                        ALTER TABLE bronze_topics ADD COLUMN secondary_ntee_code VARCHAR(10);
                    END IF;
                    
                    -- Add secondary_ntee_major_group column
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'bronze_topics' 
                        AND column_name = 'secondary_ntee_major_group'
                    ) THEN
                        ALTER TABLE bronze_topics ADD COLUMN secondary_ntee_major_group VARCHAR(100);
                    END IF;
                    
                    -- Add secondary_ntee_category_label column
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'bronze_topics' 
                        AND column_name = 'secondary_ntee_category_label'
                    ) THEN
                        ALTER TABLE bronze_topics ADD COLUMN secondary_ntee_category_label VARCHAR(255);
                    END IF;
                END $$;
            """)
            
            logger.info("✅ Successfully added secondary NTEE columns to bronze_topics")
            
            logger.info("Adding secondary NTEE columns to bronze_decisions...")
            
            cur.execute("""
                DO $$ 
                BEGIN
                    -- Add secondary_ntee_code column
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'bronze_decisions' 
                        AND column_name = 'secondary_ntee_code'
                    ) THEN
                        ALTER TABLE bronze_decisions ADD COLUMN secondary_ntee_code VARCHAR(10);
                    END IF;
                    
                    -- Add secondary_ntee_major_group column
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'bronze_decisions' 
                        AND column_name = 'secondary_ntee_major_group'
                    ) THEN
                        ALTER TABLE bronze_decisions ADD COLUMN secondary_ntee_major_group VARCHAR(100);
                    END IF;
                    
                    -- Add secondary_ntee_category_label column
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'bronze_decisions' 
                        AND column_name = 'secondary_ntee_category_label'
                    ) THEN
                        ALTER TABLE bronze_decisions ADD COLUMN secondary_ntee_category_label VARCHAR(255);
                    END IF;
                END $$;
            """)
            
            logger.info("✅ Successfully added secondary NTEE columns to bronze_decisions")
            
            # Create index on secondary_ntee_code
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_bronze_topics_secondary_ntee_code 
                ON bronze_topics(secondary_ntee_code);
            """)
            
            logger.info("✅ Created index on secondary_ntee_code")
            
            conn.commit()
            logger.info("✅ Migration complete!")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    migrate()
