#!/usr/bin/env python3
"""
Verify Census Bronze Migration

This script verifies that census data loading scripts are properly writing
to the bronze database and that enrichment logic has been flagged for dbt migration.

Run this after updating census scripts to ensure proper bronze layer setup.
"""
import psycopg2
from loguru import logger


def verify_bronze_database():
    """Verify bronze database setup."""
    logger.info("🔍 Verifying bronze database setup...")
    
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        database="open_navigator_bronze",
        user="postgres",
        password="password"
    )
    cur = conn.cursor()
    
    # Check if bronze_jurisdictions table exists
    cur.execute("""
        SELECT EXISTS (
           SELECT FROM information_schema.tables 
           WHERE table_schema = 'public'
           AND table_name = 'bronze_jurisdictions'
        )
    """)
    table_exists = cur.fetchone()[0]
    
    if not table_exists:
        logger.error("❌ bronze_jurisdictions table does not exist in open_navigator_bronze")
        return False
    
    logger.success("✅ bronze_jurisdictions table exists")
    
    # Check if states are loaded
    cur.execute("""
        SELECT COUNT(*) 
        FROM bronze_jurisdictions 
        WHERE type = 'state'
    """)
    state_count = cur.fetchone()[0]
    
    if state_count == 0:
        logger.warning("⚠️  No states loaded in bronze_jurisdictions")
        logger.info("   Run: python packages/scrapers/src/scrapers/census/load_census_states.py")
        return False
    elif state_count < 50:
        logger.warning(f"⚠️  Only {state_count} states loaded (expected 50+)")
        return False
    else:
        logger.success(f"✅ {state_count} states loaded in bronze_jurisdictions")
    
    # Check indexes
    cur.execute("""
        SELECT indexname 
        FROM pg_indexes 
        WHERE tablename = 'bronze_jurisdictions'
    """)
    indexes = [row[0] for row in cur.fetchall()]
    
    expected_indexes = [
        'idx_bronze_jurisdictions_state',
        'idx_bronze_jurisdictions_type',
        'idx_bronze_jurisdictions_geoid',
        'idx_bronze_jurisdictions_fips'
    ]
    
    missing_indexes = [idx for idx in expected_indexes if idx not in indexes]
    if missing_indexes:
        logger.warning(f"⚠️  Missing indexes: {missing_indexes}")
    else:
        logger.success(f"✅ All indexes present ({len(indexes)} total)")
    
    cur.close()
    conn.close()
    
    return True


def verify_deprecated_scripts():
    """Verify deprecated scripts have warnings."""
    logger.info("🔍 Checking deprecated scripts...")
    
    deprecated_files = [
        'packages/scrapers/src/scrapers/census/link_cities_counties_to_search.py',
        'packages/scrapers/src/scrapers/census/fix_geoid_format.py'
    ]
    
    for file_path in deprecated_files:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                if 'DEPRECATION NOTICE' in content or 'warnings.warn' in content:
                    logger.success(f"✅ {file_path} has deprecation notice")
                else:
                    logger.warning(f"⚠️  {file_path} missing deprecation notice")
        except FileNotFoundError:
            logger.error(f"❌ {file_path} not found")


def verify_documentation():
    """Verify migration documentation exists."""
    logger.info("🔍 Checking documentation...")
    
    docs = [
        'packages/scrapers/src/scrapers/census/MIGRATION_GUIDE.md',
        'packages/scrapers/src/scrapers/census/README_BRONZE_MIGRATION.md'
    ]
    
    for doc in docs:
        try:
            with open(doc, 'r') as f:
                content = f.read()
                if len(content) > 100:  # Basic check
                    logger.success(f"✅ {doc} exists")
                else:
                    logger.warning(f"⚠️  {doc} seems incomplete")
        except FileNotFoundError:
            logger.error(f"❌ {doc} not found")


def main():
    """Run all verification checks."""
    logger.info("=" * 70)
    logger.info("Census Bronze Migration Verification")
    logger.info("=" * 70)
    
    checks = [
        ("Bronze Database", verify_bronze_database),
        ("Deprecated Scripts", verify_deprecated_scripts),
        ("Documentation", verify_documentation)
    ]
    
    results = []
    for check_name, check_func in checks:
        logger.info(f"\n{'─' * 70}")
        logger.info(f"{check_name}")
        logger.info(f"{'─' * 70}")
        try:
            result = check_func()
            results.append((check_name, result if result is not None else True))
        except Exception as e:
            logger.error(f"❌ Error in {check_name}: {e}")
            results.append((check_name, False))
    
    # Summary
    logger.info(f"\n{'=' * 70}")
    logger.info("Summary")
    logger.info(f"{'=' * 70}")
    
    for check_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {check_name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        logger.success("\n🎉 All checks passed!")
        logger.info("\nNext steps:")
        logger.info("1. Update remaining loader scripts (load_census.py, load_county_mappings.py)")
        logger.info("2. Create dbt models for enrichment logic")
        logger.info("3. Test full bronze→dbt→gold pipeline")
    else:
        logger.warning("\n⚠️  Some checks failed. Review the output above.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
