#!/usr/bin/env python3
"""
Fix GEOID Format in jurisdiction

⚠️ DEPRECATION NOTICE:
This data cleanup script should be migrated to dbt as a transformation model.
Data quality fixes belong in the transformation layer (bronze → silver), not in loading scripts.

TODO: Create dbt model: dbt_project/models/silver/silver_jurisdictions_clean.sql
      - Apply GEOID formatting rules from this script
      - Standardize data types
      - Add data quality tests

This script:
1. Adds leading zeros to GEOID to match Census Bureau format
2. Populates fips_code from GEOID for counties

GEOID formats:
- State: 2 digits (e.g., "01" for Alabama)
- County: 5 digits (2-digit state + 3-digit county, e.g., "01001")
- City: 7 digits (2-digit state + 5-digit place, e.g., "0151000")
- School District: 7 digits
- Township: 10 digits

Usage:
    python scripts/datasources/census/fix_geoid_format.py
"""
import os
import psycopg2
import warnings
from loguru import logger
from dotenv import load_dotenv

# Deprecation warning
warnings.warn(
    "fix_geoid_format.py is deprecated and should be migrated to dbt. "
    "Data quality fixes should happen in transformation layer (dbt), not in loading scripts.",
    DeprecationWarning,
    stacklevel=2
)

load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')


def fix_geoid_format():
    """Fix GEOID format by adding leading zeros."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Define expected GEOID lengths by type
    geoid_lengths = {
        'county': 5,
        'city': 7,
        'school_district': 7,
        'township': 10
    }
    
    for jurisdiction_type, expected_length in geoid_lengths.items():
        logger.info(f"Fixing GEOID format for {jurisdiction_type} (expected length: {expected_length})...")
        
        # Update GEOID to have leading zeros
        cursor.execute(f"""
            UPDATE jurisdiction
            SET geoid = LPAD(geoid, {expected_length}, '0')
            WHERE type = %s
              AND geoid IS NOT NULL
              AND LENGTH(geoid) < {expected_length}
        """, (jurisdiction_type,))
        
        updated = cursor.rowcount
        logger.success(f"  ✅ Updated {updated:,} {jurisdiction_type} GEOIDs")
    
    # For counties, populate fips_code from GEOID (they're the same)
    logger.info("Populating fips_code for counties...")
    cursor.execute("""
        UPDATE jurisdiction
        SET fips_code = geoid
        WHERE type = 'county'
          AND geoid IS NOT NULL
          AND (fips_code IS NULL OR fips_code = '')
    """)
    
    updated = cursor.rowcount
    logger.success(f"  ✅ Populated fips_code for {updated:,} counties")
    
    conn.commit()
    
    # Show summary
    logger.info("\n📊 Summary of GEOID formats:")
    cursor.execute("""
        SELECT 
            type,
            COUNT(*) as total,
            COUNT(geoid) as with_geoid,
            MIN(LENGTH(geoid)) as min_len,
            MAX(LENGTH(geoid)) as max_len,
            COUNT(fips_code) as with_fips
        FROM jurisdiction
        GROUP BY type
        ORDER BY type
    """)
    
    for row in cursor.fetchall():
        logger.info(f"  {row[0]:15s}: {row[1]:6,} total, {row[2]:6,} with GEOID (len {row[3]}-{row[4]}), {row[5]:6,} with FIPS")
    
    cursor.close()
    conn.close()
    
    logger.success("\n✅ GEOID format fix complete!")


if __name__ == "__main__":
    fix_geoid_format()
