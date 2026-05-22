#!/usr/bin/env python3
"""
Clean Up Incorrect Counties in jurisdictions_wikidata

WikiData queries returned counties from wrong states:
- Washington (WA) has 49 phantom counties (Ohio counties)
- Alabama (AL) has 1 phantom county (Decatur County)
- Massachusetts (MA) has 1 phantom county (York County)
- Indiana (IN) has 1 phantom county (Swanson County)

This script deletes WikiData counties that don't exist in jurisdiction
(the authoritative Census Bureau source).

Usage:
    python scripts/datasources/wikidata/cleanup_bad_counties.py
"""
import os
import psycopg2
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')


def cleanup_bad_counties():
    """Delete WikiData counties that don't exist in authoritative Census data."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Find WikiData counties that don't match any real county by GEOID or name
    logger.info("Finding phantom counties in jurisdictions_wikidata...")
    cursor.execute("""
        WITH bad_counties AS (
            SELECT 
                w.id,
                w.wikidata_id,
                w.jurisdiction_name,
                w.state_code,
                w.geoid as wiki_geoid,
                w.fips_code as wiki_fips
            FROM jurisdictions_wikidata w
            LEFT JOIN jurisdiction s 
                ON (
                    (w.geoid = s.geoid AND w.geoid IS NOT NULL)
                    OR (UPPER(TRIM(w.jurisdiction_name)) = UPPER(TRIM(s.name)) AND w.state_code = s.state_code)
                )
                AND s.type = 'county'
            WHERE w.jurisdiction_type = 'county'
              AND w.state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI')
              AND s.id IS NULL
        )
        SELECT 
            state_code,
            COUNT(*) as phantom_count,
            STRING_AGG(jurisdiction_name, ', ' ORDER BY jurisdiction_name) FILTER (WHERE jurisdiction_name IS NOT NULL) as sample_names
        FROM bad_counties
        GROUP BY state_code
        ORDER BY state_code
    """)
    
    summary = cursor.fetchall()
    total_to_delete = 0
    
    if summary:
        logger.info("Phantom counties found:")
        for state, count, samples in summary:
            logger.warning(f"  {state}: {count} phantom counties")
            if samples:
                sample_list = samples.split(', ')[:5]
                logger.info(f"      Examples: {', '.join(sample_list)}")
            total_to_delete += count
    else:
        logger.success("No phantom counties found!")
        cursor.close()
        conn.close()
        return
    
    logger.info(f"\nTotal phantom counties to delete: {total_to_delete}")
    
    # Delete phantom counties
    logger.info("Deleting phantom counties...")
    cursor.execute("""
        DELETE FROM jurisdictions_wikidata w
        WHERE w.jurisdiction_type = 'county'
          AND w.state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI')
          AND NOT EXISTS (
              SELECT 1 FROM jurisdiction s
              WHERE (
                  (w.geoid = s.geoid AND w.geoid IS NOT NULL)
                  OR (UPPER(TRIM(w.jurisdiction_name)) = UPPER(TRIM(s.name)) AND w.state_code = s.state_code)
              )
              AND s.type = 'county'
          )
    """)
    
    deleted = cursor.rowcount
    conn.commit()
    logger.success(f"✅ Deleted {deleted} phantom counties")
    
    # Verify cleanup
    logger.info("\n📊 County counts after cleanup:")
    cursor.execute("""
        SELECT 
            COALESCE(s.state_code, w.state_code) as state,
            COUNT(DISTINCT s.id) as search_counties,
            COUNT(DISTINCT w.wikidata_id) as wiki_counties,
            COUNT(DISTINCT CASE WHEN s.id IS NOT NULL AND w.wikidata_id IS NOT NULL THEN w.wikidata_id END) as matched
        FROM jurisdiction s
        FULL OUTER JOIN jurisdictions_wikidata w 
            ON s.geoid = w.geoid
            AND s.type = 'county'
            AND w.jurisdiction_type = 'county'
        WHERE (s.state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI') AND s.type = 'county')
           OR (w.state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI') AND w.jurisdiction_type = 'county')
        GROUP BY COALESCE(s.state_code, w.state_code)
        ORDER BY state
    """)
    
    for row in cursor.fetchall():
        state, search_count, wiki_count, matched = row
        pct = (matched * 100 // search_count) if search_count > 0 else 0
        status = "✅" if wiki_count == matched else "⚠️"
        logger.info(f"  {status} {state}: {search_count} real, {wiki_count} WikiData, {matched} matched ({pct}%)")
    
    # Final matching stats
    logger.info("\n🔗 Final GEOID matching:")
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT w.wikidata_id) as wiki_total,
            COUNT(DISTINCT CASE WHEN s.id IS NOT NULL THEN w.wikidata_id END) as matched,
            ROUND(COUNT(DISTINCT CASE WHEN s.id IS NOT NULL THEN w.wikidata_id END) * 100.0 / 
                  COUNT(DISTINCT w.wikidata_id), 1) as match_pct
        FROM jurisdictions_wikidata w
        LEFT JOIN jurisdiction s ON w.geoid = s.geoid AND s.type = 'county'
        WHERE w.jurisdiction_type = 'county'
          AND w.state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI')
    """)
    
    result = cursor.fetchone()
    logger.success(f"  {result[1]}/{result[0]} counties matched by GEOID ({result[2]}%)")
    
    cursor.close()
    conn.close()


if __name__ == "__main__":
    cleanup_bad_counties()
