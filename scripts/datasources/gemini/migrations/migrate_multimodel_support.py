#!/usr/bin/env python3
"""
Enable multi-model comparison support in Bronze tables.

This migration:
1. Drops existing UNIQUE constraints that don't include source_ai_model
2. Adds new UNIQUE constraints that include source_ai_model
3. Allows storing multiple AI model extractions of the same decision/entity

This enables model comparison and ensemble approaches.

Usage:
    python scripts/datasources/gemini/migrate_multimodel_support.py
    
    # Dry run (show SQL without executing)
    python scripts/datasources/gemini/migrate_multimodel_support.py --dry-run
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import psycopg2
from loguru import logger

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Database URL
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
DATABASE_URL = os.getenv('LOCAL_BRONZE_DATABASE_URL', 
                         f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator_bronze')


def get_migration_steps() -> List[Tuple[str, str]]:
    """
    Get the list of migration steps.
    
    Returns:
        List of (description, sql) tuples
    """
    return [
        # 1. Drop existing constraints
        (
            "Drop old UNIQUE constraint on bronze_contacts",
            """
            DO $$ 
            BEGIN
                -- Find and drop the constraint
                EXECUTE (
                    SELECT 'ALTER TABLE bronze_contacts DROP CONSTRAINT ' || conname || ';'
                    FROM pg_constraint
                    WHERE conrelid = 'bronze_contacts'::regclass
                      AND contype = 'u'
                      AND conname LIKE '%source_event_id%person_id%'
                    LIMIT 1
                );
            EXCEPTION
                WHEN OTHERS THEN
                    RAISE NOTICE 'Constraint may not exist, continuing...';
            END $$;
            """
        ),
        (
            "Drop old UNIQUE constraint on bronze_organizations",
            """
            DO $$ 
            BEGIN
                EXECUTE (
                    SELECT 'ALTER TABLE bronze_organizations DROP CONSTRAINT ' || conname || ';'
                    FROM pg_constraint
                    WHERE conrelid = 'bronze_organizations'::regclass
                      AND contype = 'u'
                      AND conname LIKE '%source_event_id%org_id%'
                    LIMIT 1
                );
            EXCEPTION
                WHEN OTHERS THEN
                    RAISE NOTICE 'Constraint may not exist, continuing...';
            END $$;
            """
        ),
        (
            "Drop old UNIQUE constraint on bronze_bills",
            """
            DO $$ 
            BEGIN
                EXECUTE (
                    SELECT 'ALTER TABLE bronze_bills DROP CONSTRAINT ' || conname || ';'
                    FROM pg_constraint
                    WHERE conrelid = 'bronze_bills'::regclass
                      AND contype = 'u'
                      AND conname LIKE '%source_event_id%leg_id%'
                    LIMIT 1
                );
            EXCEPTION
                WHEN OTHERS THEN
                    RAISE NOTICE 'Constraint may not exist, continuing...';
            END $$;
            """
        ),
        (
            "Drop old UNIQUE constraint on bronze_decisions",
            """
            DO $$ 
            BEGIN
                EXECUTE (
                    SELECT 'ALTER TABLE bronze_decisions DROP CONSTRAINT ' || conname || ';'
                    FROM pg_constraint
                    WHERE conrelid = 'bronze_decisions'::regclass
                      AND contype = 'u'
                      AND conname LIKE '%source_event_id%decision_id%'
                    LIMIT 1
                );
            EXCEPTION
                WHEN OTHERS THEN
                    RAISE NOTICE 'Constraint may not exist, continuing...';
            END $$;
            """
        ),
        (
            "Drop old UNIQUE constraint on bronze_financial_items",
            """
            DO $$ 
            BEGIN
                EXECUTE (
                    SELECT 'ALTER TABLE bronze_financial_items DROP CONSTRAINT ' || conname || ';'
                    FROM pg_constraint
                    WHERE conrelid = 'bronze_financial_items'::regclass
                      AND contype = 'u'
                      AND conname LIKE '%source_event_id%financial_item_id%'
                    LIMIT 1
                );
            EXCEPTION
                WHEN OTHERS THEN
                    RAISE NOTICE 'Constraint may not exist, continuing...';
            END $$;
            """
        ),
        
        # 2. Add new constraints with source_ai_model
        (
            "Add new UNIQUE constraint to bronze_contacts (includes source_ai_model)",
            """
            ALTER TABLE bronze_contacts 
            ADD CONSTRAINT bronze_contacts_unique_per_model 
            UNIQUE (source_event_id, person_id, source_ai_model);
            """
        ),
        (
            "Add new UNIQUE constraint to bronze_organizations (includes source_ai_model)",
            """
            ALTER TABLE bronze_organizations 
            ADD CONSTRAINT bronze_organizations_unique_per_model 
            UNIQUE (source_event_id, org_id, source_ai_model);
            """
        ),
        (
            "Add new UNIQUE constraint to bronze_bills (includes source_ai_model)",
            """
            ALTER TABLE bronze_bills 
            ADD CONSTRAINT bronze_bills_unique_per_model 
            UNIQUE (source_event_id, leg_id, source_ai_model);
            """
        ),
        (
            "Add new UNIQUE constraint to bronze_decisions (includes source_ai_model)",
            """
            ALTER TABLE bronze_decisions 
            ADD CONSTRAINT bronze_decisions_unique_per_model 
            UNIQUE (source_event_id, decision_id, source_ai_model);
            """
        ),
        (
            "Add new UNIQUE constraint to bronze_financial_items (includes source_ai_model)",
            """
            ALTER TABLE bronze_financial_items 
            ADD CONSTRAINT bronze_financial_items_unique_per_model 
            UNIQUE (source_event_id, financial_item_id, source_ai_model);
            """
        ),
        (
            "Add UNIQUE constraint to bronze_topics (includes source_ai_model)",
            """
            -- Topics table didn't have a unique constraint before
            -- Adding one now for consistency
            ALTER TABLE bronze_topics 
            ADD CONSTRAINT bronze_topics_unique_per_model 
            UNIQUE (source_event_id, decision_id, source_ai_model);
            """
        ),
        (
            "Add UNIQUE constraint to bronze_causes (includes source_ai_model)",
            """
            -- Causes table didn't have a unique constraint before
            -- Adding one now for consistency
            ALTER TABLE bronze_causes 
            ADD CONSTRAINT bronze_causes_unique_per_model 
            UNIQUE (source_event_id, decision_id, cause_headline, source_ai_model);
            """
        ),
    ]


def run_migration(dry_run: bool = False):
    """
    Run the migration to enable multi-model support.
    
    Args:
        dry_run: If True, only print SQL without executing
    """
    logger.info("=" * 80)
    logger.info("🔧 Bronze Multi-Model Support Migration")
    logger.info("=" * 80)
    
    if dry_run:
        logger.warning("DRY RUN MODE - No changes will be made")
        logger.info("")
    
    steps = get_migration_steps()
    
    if dry_run:
        logger.info("Migration SQL (DRY RUN):")
        logger.info("=" * 80)
        for i, (description, sql) in enumerate(steps, 1):
            logger.info(f"\n-- Step {i}: {description}")
            logger.info(sql.strip())
        logger.info("\n" + "=" * 80)
        logger.info(f"✅ Dry run complete - {len(steps)} steps would be executed")
        return
    
    # Execute migration
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                for i, (description, sql) in enumerate(steps, 1):
                    logger.info(f"Step {i}/{len(steps)}: {description}")
                    try:
                        cur.execute(sql)
                        conn.commit()
                        logger.info(f"  ✅ Success")
                    except Exception as e:
                        logger.warning(f"  ⚠️  {e}")
                        conn.rollback()
                        # Continue with next step
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ Migration complete!")
        logger.info("")
        logger.info("Your bronze tables now support storing multiple AI model extractions")
        logger.info("of the same decisions, contacts, organizations, bills, and financial items.")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Run extract_to_bronze.py with different AI models")
        logger.info("  2. Query for model comparisons using source_ai_model column")
        logger.info("  3. Build consensus/ensemble approaches")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


def verify_migration():
    """Verify the migration was successful."""
    logger.info("")
    logger.info("🔍 Verifying migration...")
    
    verification_query = """
    SELECT 
        conrelid::regclass AS table_name,
        conname AS constraint_name,
        pg_get_constraintdef(oid) AS constraint_definition
    FROM pg_constraint
    WHERE conrelid::regclass::text LIKE 'bronze_%'
      AND contype = 'u'
      AND conname LIKE '%unique_per_model%'
    ORDER BY table_name;
    """
    
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(verification_query)
                results = cur.fetchall()
                
                if results:
                    logger.info("")
                    logger.info("✅ New UNIQUE constraints found:")
                    logger.info("")
                    for table, constraint, definition in results:
                        logger.info(f"  {table}")
                        logger.info(f"    → {constraint}")
                        logger.info(f"    → {definition}")
                        logger.info("")
                else:
                    logger.warning("⚠️  No new constraints found - migration may have failed")
    
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate bronze tables to support multi-model comparison"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show SQL without executing (dry run)'
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify existing constraints (no migration)'
    )
    
    args = parser.parse_args()
    
    if args.verify_only:
        verify_migration()
        return
    
    run_migration(dry_run=args.dry_run)
    
    if not args.dry_run:
        verify_migration()


if __name__ == '__main__':
    main()
