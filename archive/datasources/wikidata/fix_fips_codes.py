#!/usr/bin/env python3
"""
Fix Incorrect FIPS Codes in jurisdictions_wikidata

WikiData has incorrect FIPS codes for some states' counties:
- Indiana (IN) counties have 40xxx codes (Oklahoma) instead of 18xxx
- Washington (WA) counties have 39xxx codes (Ohio) instead of 53xxx
- Wisconsin (WI) counties have 41xxx codes (Oregon) instead of 55xxx

This script corrects the FIPS prefix to match the actual state.

Usage:
    python scripts/datasources/wikidata/fix_fips_codes.py
"""
import os
import psycopg2
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')

# Mapping of state codes to their correct FIPS prefix and the wrong prefix to replace
FIPS_CORRECTIONS = {
    'IN': {'correct': '18', 'wrong': '40'},  # Indiana has Oklahoma codes
    'WA': {'correct': '53', 'wrong': '39'},  # Washington has Ohio codes
    'WI': {'correct': '55', 'wrong': '41'},  # Wisconsin has Oregon codes
}


def fix_fips_codes():
    """Fix incorrect FIPS codes by replacing wrong state prefix with correct one."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    total_fixed = 0
    
    for state_code, prefixes in FIPS_CORRECTIONS.items():
        wrong_prefix = prefixes['wrong']
        correct_prefix = prefixes['correct']
        
        logger.info(f"Fixing {state_code} counties: replacing {wrong_prefix}xxx with {correct_prefix}xxx...")
        
        # Show what will be fixed
        cursor.execute("""
            SELECT 
                jurisdiction_name,
                fips_code,
                CONCAT(%s, SUBSTRING(fips_code, 3)) as corrected_fips
            FROM jurisdictions_wikidata
            WHERE jurisdiction_type = 'county'
              AND state_code = %s
              AND fips_code LIKE %s
            ORDER BY jurisdiction_name
            LIMIT 5
        """, (correct_prefix, state_code, f"{wrong_prefix}%"))
        
        samples = cursor.fetchall()
        if samples:
            logger.info(f"  Sample corrections for {state_code}:")
            for name, old_fips, new_fips in samples:
                logger.info(f"    {name}: {old_fips} → {new_fips}")
        
        # Fix fips_code
        cursor.execute("""
            UPDATE jurisdictions_wikidata
            SET fips_code = CONCAT(%s, SUBSTRING(fips_code, 3))
            WHERE jurisdiction_type = 'county'
              AND state_code = %s
              AND fips_code LIKE %s
        """, (correct_prefix, state_code, f"{wrong_prefix}%"))
        
        fips_updated = cursor.rowcount
        
        # Fix geoid to match corrected fips_code
        cursor.execute("""
            UPDATE jurisdictions_wikidata
            SET geoid = fips_code
            WHERE jurisdiction_type = 'county'
              AND state_code = %s
              AND geoid != fips_code
        """, (state_code,))
        
        geoid_updated = cursor.rowcount
        
        logger.success(f"  ✅ Fixed {fips_updated} FIPS codes and {geoid_updated} GEOIDs for {state_code}")
        total_fixed += fips_updated
    
    conn.commit()
    
    # Verify the fix
    logger.info("\n📊 Verification - FIPS prefix match by state:")
    cursor.execute("""
        SELECT 
            w.state_code,
            state_fips.fips as expected_prefix,
            COUNT(*) as total_counties,
            COUNT(CASE WHEN SUBSTRING(w.fips_code, 1, 2) = state_fips.fips THEN 1 END) as correct_prefix,
            COUNT(CASE WHEN SUBSTRING(w.fips_code, 1, 2) != state_fips.fips THEN 1 END) as wrong_prefix
        FROM jurisdictions_wikidata w
        JOIN (VALUES 
            ('AL', '01'), ('GA', '13'), ('IN', '18'), 
            ('MA', '25'), ('WA', '53'), ('WI', '55')
        ) AS state_fips(code, fips) ON w.state_code = state_fips.code
        WHERE w.jurisdiction_type = 'county'
          AND w.fips_code IS NOT NULL
        GROUP BY w.state_code, state_fips.fips
        ORDER BY w.state_code
    """)
    
    for row in cursor.fetchall():
        state, expected, total, correct, wrong = row
        status = "✅" if wrong == 0 else "❌"
        logger.info(f"  {status} {state}: {correct}/{total} correct, {wrong} wrong (expected prefix: {expected})")
    
    # Test matching with jurisdiction
    logger.info("\n🔗 Testing match with jurisdiction:")
    cursor.execute("""
        WITH wiki_counties AS (
            SELECT wikidata_id, jurisdiction_name, state_code, geoid, fips_code
            FROM jurisdictions_wikidata
            WHERE jurisdiction_type = 'county' 
              AND state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI')
              AND geoid IS NOT NULL
        ),
        search_counties AS (
            SELECT id, name, state_code, geoid, fips_code
            FROM jurisdiction
            WHERE type = 'county' 
              AND state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI')
              AND geoid IS NOT NULL
        )
        SELECT 
            (SELECT COUNT(*) FROM wiki_counties) as wikidata_total,
            (SELECT COUNT(*) FROM search_counties) as search_total,
            (SELECT COUNT(*) FROM wiki_counties w 
             INNER JOIN search_counties s ON w.geoid = s.geoid) as matched_by_geoid,
            (SELECT COUNT(*) FROM wiki_counties w 
             INNER JOIN search_counties s ON w.fips_code = s.fips_code) as matched_by_fips
    """)
    
    result = cursor.fetchone()
    logger.info(f"  WikiData counties: {result[0]}")
    logger.info(f"  Search counties: {result[1]}")
    logger.info(f"  Matched by GEOID: {result[2]} ({result[2]*100//result[0]}%)")
    logger.info(f"  Matched by FIPS: {result[3]} ({result[3]*100//result[0]}%)")
    
    cursor.close()
    conn.close()
    
    logger.success(f"\n✅ Fixed {total_fixed} FIPS codes total!")


if __name__ == "__main__":
    fix_fips_codes()
