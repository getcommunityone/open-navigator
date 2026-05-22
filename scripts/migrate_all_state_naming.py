#!/usr/bin/env python3
"""
Comprehensive State Naming Migration Script

This script migrates ALL tables to use the standard naming convention:
- state_code: 2-letter state code (e.g., 'AL', 'MA')  
- state: Full state name (e.g., 'Alabama', 'Massachusetts')

Tables to migrate:
- jurisdiction_state_aggregate
- organization_nonprofit
- contact
- event
- bills_search
"""
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from loguru import logger

load_dotenv()

# State code to full name mapping
STATE_NAMES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
    'DC': 'District of Columbia', 'PR': 'Puerto Rico'
}

TABLES_TO_MIGRATE = [
    'jurisdiction_state_aggregate',
    'organization_nonprofit',
    'contact',
    'event',
    'bills_search'
]


def migrate_table(conn, table_name):
    """Migrate a single table to new naming convention."""
    
    logger.info(f"📦 Migrating {table_name}...")
    
    try:
        # Check if already migrated
        result = conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}' AND column_name IN ('state', 'state_code')
        """))
        existing_cols = [row[0] for row in result]
        
        if 'state_code' in existing_cols and 'state' in existing_cols:
            # Check if state has full names
            result = conn.execute(text(f"""
                SELECT state FROM {table_name} 
                WHERE state IS NOT NULL AND LENGTH(state) > 2 
                LIMIT 1
            """))
            if result.fetchone():
                logger.info(f"  ✅ Already migrated")
                return True
        
        # Add new columns
        logger.info(f"  Adding state_code and state_name columns...")
        conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS state_code VARCHAR(2)'))
        conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS state_name VARCHAR(50)'))
        conn.commit()
        
        # Populate state_code from existing state column (if it's 2-letter codes)
        logger.info(f"  Populating state_code from state...")
        conn.execute(text(f"""
            UPDATE {table_name} 
            SET state_code = state 
            WHERE state_code IS NULL AND (state IS NULL OR LENGTH(state) <= 2)
        """))
        conn.commit()
        
        # Populate state_name from state_code
        logger.info(f"  Populating state_name...")
        for code, name in STATE_NAMES.items():
            conn.execute(text(f"""
                UPDATE {table_name} 
                SET state_name = '{name}' 
                WHERE state_code = '{code}'
            """))
        conn.commit()
        
        # Drop old state column and rename
        logger.info(f"  Renaming columns...")
        conn.execute(text(f'ALTER TABLE {table_name} DROP COLUMN IF EXISTS state'))
        conn.execute(text(f'ALTER TABLE {table_name} RENAME COLUMN state_name TO state'))
        conn.commit()
        
        # Recreate indexes
        logger.info(f"  Recreating indexes...")
        conn.execute(text(f'DROP INDEX IF EXISTS idx_{table_name.replace("_search", "")}_state'))
        conn.execute(text(f'CREATE INDEX idx_{table_name.replace("_search", "")}_state_code ON {table_name}(state_code)'))
        conn.execute(text(f'CREATE INDEX idx_{table_name.replace("_search", "")}_state ON {table_name}(state)'))
        conn.commit()
        
        # Update unique constraints if needed
        if table_name == 'jurisdiction_state_aggregate':
            logger.info(f"  Updating unique constraint...")
            conn.execute(text(f"""
                ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS jurisdiction_state_aggregate_level_state_county_city_key
            """))
            conn.execute(text(f"""
                ALTER TABLE {table_name} ADD CONSTRAINT jurisdiction_state_aggregate_level_state_code_county_city_key 
                UNIQUE (level, state_code, county, city)
            """))
            conn.commit()
        
        logger.success(f"  ✅ Migrated {table_name}")
        
        # Verify
        result = conn.execute(text(f"""
            SELECT state_code, state 
            FROM {table_name} 
            WHERE state_code IS NOT NULL 
            LIMIT 1
        """))
        sample = result.fetchone()
        if sample:
            logger.info(f"     Sample: state_code={sample[0]}, state={sample[1]}")
        
        return True
        
    except Exception as e:
        logger.error(f"  ❌ Failed to migrate {table_name}: {e}")
        conn.rollback()
        return False


def main():
    """Main migration function."""
    
    logger.info("=" * 80)
    logger.info("STATE NAMING CONVENTION MIGRATION")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Standard:")
    logger.info("  - state_code: 2-letter code (AL, MA, etc.)")
    logger.info("  - state: Full name (Alabama, Massachusetts, etc.)")
    logger.info("")
    
    # Connect to database
    DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV') or os.getenv('NEON_DATABASE_URL')
    if not DATABASE_URL:
        logger.error("❌ No database URL found in environment")
        return False
    
    logger.info(f"Database: {'DEV' if 'NEON_DATABASE_URL_DEV' in os.environ else 'PROD'}")
    logger.info("")
    
    engine = create_engine(DATABASE_URL)
    
    success_count = 0
    fail_count = 0
    
    with engine.connect() as conn:
        for table in TABLES_TO_MIGRATE:
            if migrate_table(conn, table):
                success_count += 1
            else:
                fail_count += 1
            logger.info("")
    
    logger.info("=" * 80)
    logger.info("MIGRATION COMPLETE")
    logger.info("=" * 80)
    logger.success(f"✅ Successfully migrated: {success_count} tables")
    if fail_count > 0:
        logger.error(f"❌ Failed: {fail_count} tables")
    logger.info("")
    
    return fail_count == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
