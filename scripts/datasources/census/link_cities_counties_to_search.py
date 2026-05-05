"""
Link Cities and Counties to jurisdictions_search

⚠️ DEPRECATION NOTICE:
This enrichment script should be migrated to dbt as a transformation model.
Data enrichment belongs in the transformation layer (bronze → silver/gold), not in loading scripts.

TODO: Create dbt model: dbt_project/models/silver/silver_jurisdictions.sql
      - Match cities/counties by name + state_code
      - Update jurisdiction_id for proper linking
      - Join bronze_jurisdictions with jurisdictions_details

CURRENT FUNCTIONALITY (to be migrated):
- Matches cities/counties by name + state_code
- Updates jurisdiction_id in jurisdictions_details_search 
- Enables proper linkage between tables

PROBLEM: jurisdictions_details_search uses Census place codes (2500135) 
         but jurisdictions_search uses integer IDs (11714)
         Result: 0% mapping between tables

SOLUTION: Update jurisdictions_details_search.jurisdiction_id to use 
          jurisdictions_search.id::text (same approach as school districts)

Usage:
    python link_cities_counties_to_search.py --dry-run
    python link_cities_counties_to_search.py --states MA,CA,TX
    python link_cities_counties_to_search.py
"""
import argparse
import warnings

import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger

# Deprecation warning
warnings.warn(
    "link_cities_counties_to_search.py is deprecated and should be migrated to dbt. "
    "Data enrichment should happen in transformation layer (dbt), not in loading scripts.",
    DeprecationWarning,
    stacklevel=2
)


def normalize_name(name: str) -> str:
    """Normalize jurisdiction name for matching."""
    if not name:
        return ""
    
    # Convert to lowercase and strip
    normalized = name.lower().strip()
    
    # Remove common suffixes that differ between sources
    suffixes = [
        ' county',  # For county matching
        ' city',
        ' town',
        ' village',
        ' cdp',  # Census Designated Place
        ' borough',
        ' township'
    ]
    
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)].strip()
    
    return normalized


def link_jurisdictions(states=None, jurisdiction_types=None, dry_run=False):
    """
    Link jurisdictions_details_search to jurisdictions_search.
    
    Updates jurisdiction_id to use jurisdictions_search.id::text for proper linking.
    """
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        database="open_navigator",
        user="postgres",
        password="password"
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Build filters
    state_filter = ""
    if states:
        state_list = "','".join(states)
        state_filter = f"AND jd.state_code IN ('{state_list}')"
    
    type_filter = ""
    if jurisdiction_types:
        type_list = "','".join(jurisdiction_types)
        type_filter = f"AND jd.jurisdiction_type IN ('{type_list}')"
    
    # Match jurisdictions_details_search to jurisdictions_search
    # Try multiple matching strategies
    match_query = f"""
        SELECT 
            jd.id as details_id,
            jd.jurisdiction_id as old_id,
            jd.jurisdiction_name,
            jd.jurisdiction_type,
            jd.state_code,
            js.id as search_id,
            js.name as search_name,
            CASE 
                WHEN LOWER(TRIM(jd.jurisdiction_name)) = LOWER(TRIM(js.name)) THEN 'exact'
                WHEN LOWER(TRIM(REGEXP_REPLACE(jd.jurisdiction_name, ' (county|city|town|CDP|village|borough|township)$', '', 'i'))) 
                     = LOWER(TRIM(REGEXP_REPLACE(js.name, ' (county|city|town|CDP|village|borough|township)$', '', 'i'))) THEN 'normalized'
                ELSE 'no_match'
            END as match_type
        FROM jurisdictions_details_search jd
        LEFT JOIN jurisdictions_search js ON (
            js.state_code = jd.state_code
            AND js.type = jd.jurisdiction_type
            AND (
                -- Strategy 1: Exact match
                LOWER(TRIM(jd.jurisdiction_name)) = LOWER(TRIM(js.name))
                -- Strategy 2: Normalized (remove city/town/CDP/county suffixes)
                OR LOWER(TRIM(REGEXP_REPLACE(jd.jurisdiction_name, ' (county|city|town|CDP|village|borough|township)$', '', 'i'))) 
                   = LOWER(TRIM(REGEXP_REPLACE(js.name, ' (county|city|town|CDP|village|borough|township)$', '', 'i')))
            )
        )
        WHERE jd.jurisdiction_type IN ('city', 'county')
        {state_filter}
        {type_filter}
        ORDER BY jd.state_code, jd.jurisdiction_type, jd.jurisdiction_name
    """
    
    logger.info("=" * 80)
    logger.info("MATCHING JURISDICTIONS")
    logger.info("=" * 80)
    
    cur.execute(match_query)
    results = cur.fetchall()
    
    matched = [r for r in results if r['search_id'] is not None]
    unmatched = [r for r in results if r['search_id'] is None]
    
    logger.info(f"Total jurisdictions in details table: {len(results):,}")
    logger.info(f"✅ Matched to jurisdictions_search: {len(matched):,} ({100*len(matched)/len(results):.1f}%)")
    logger.info(f"⚠️  Unmatched: {len(unmatched):,} ({100*len(unmatched)/len(results):.1f}%)")
    
    # Show match type breakdown
    exact_matches = sum(1 for r in matched if r['match_type'] == 'exact')
    normalized_matches = sum(1 for r in matched if r['match_type'] == 'normalized')
    
    logger.info(f"\nMatch breakdown:")
    logger.info(f"  Exact matches: {exact_matches:,}")
    logger.info(f"  Normalized matches: {normalized_matches:,}")
    
    if dry_run:
        logger.warning("\n🔍 DRY RUN - Would update jurisdiction_id (first 10):")
        for r in matched[:10]:
            logger.info(f"  {r['jurisdiction_name']} ({r['state_code']}) [{r['match_type']}]")
            logger.info(f"    Old ID: {r['old_id']} → New ID: {r['search_id']}")
        
        if unmatched:
            logger.warning(f"\nUnmatched jurisdictions (first 10 of {len(unmatched):,}):")
            for r in unmatched[:10]:
                logger.info(f"  {r['jurisdiction_name']} ({r['state_code']}) - ID: {r['old_id']}")
        
        # Show by state/type
        logger.info("\nMatches by state and type:")
        cur.execute(f"""
            SELECT 
                jd.state_code,
                jd.jurisdiction_type,
                COUNT(*) as total,
                COUNT(js.id) as matched
            FROM jurisdictions_details_search jd
            LEFT JOIN jurisdictions_search js ON (
                js.state_code = jd.state_code
                AND js.type = jd.jurisdiction_type
                AND (
                    LOWER(TRIM(jd.jurisdiction_name)) = LOWER(TRIM(js.name))
                    OR LOWER(TRIM(REGEXP_REPLACE(jd.jurisdiction_name, ' (county|city|town|CDP|village|borough|township)$', '', 'i'))) 
                       = LOWER(TRIM(REGEXP_REPLACE(js.name, ' (county|city|town|CDP|village|borough|township)$', '', 'i')))
                )
            )
            WHERE jd.jurisdiction_type IN ('city', 'county')
            {state_filter}
            {type_filter}
            GROUP BY jd.state_code, jd.jurisdiction_type
            ORDER BY jd.state_code, jd.jurisdiction_type
        """)
        
        for row in cur.fetchall():
            pct = 100 * row['matched'] / row['total'] if row['total'] > 0 else 0
            logger.info(f"  {row['state_code']} {row['jurisdiction_type']}: {row['matched']}/{row['total']} ({pct:.1f}%)")
        
        return {
            'total': len(results),
            'matched': len(matched),
            'unmatched': len(unmatched),
            'updated': 0
        }
    
    # Perform updates
    logger.info("\n" + "=" * 80)
    logger.info("UPDATING JURISDICTION IDs")
    logger.info("=" * 80)
    
    # Temporarily drop FK constraint to allow updates
    logger.info("Temporarily dropping FK constraint...")
    cur.execute("""
        ALTER TABLE events_search 
        DROP CONSTRAINT IF EXISTS fk_events_jurisdiction
    """)
    
    updated = 0
    events_updated = 0
    skipped = 0
    seen_ids = set()
    
    for row in matched:
        old_id = row['old_id']
        new_id = str(row['search_id'])
        
        # Skip if we've already updated to this jurisdiction_id (handles duplicates)
        if new_id in seen_ids:
            skipped += 1
            continue
        
        seen_ids.add(new_id)
        
        # Update the jurisdiction_id in jurisdictions_details_search
        cur.execute("""
            UPDATE jurisdictions_details_search
            SET jurisdiction_id = %s
            WHERE id = %s
        """, (new_id, row['details_id']))
        
        # Update events_search that reference this jurisdiction  
        cur.execute("""
            UPDATE events_search
            SET jurisdiction_id = %s
            WHERE jurisdiction_id = %s
        """, (new_id, old_id))
        
        events_updated += cur.rowcount
        updated += 1
        
        if updated % 100 == 0:
            logger.info(f"Updated {updated:,} / {len(matched):,}...")
    
    # Recreate FK constraint
    logger.info("Recreating FK constraint...")
    cur.execute("""
        ALTER TABLE events_search 
        ADD CONSTRAINT fk_events_jurisdiction 
        FOREIGN KEY (jurisdiction_id) 
        REFERENCES jurisdictions_details_search(jurisdiction_id) 
        ON DELETE SET NULL
    """)
    
    conn.commit()
    
    logger.success(f"✅ Updated {updated:,} jurisdiction_id values")
    if skipped > 0:
        logger.warning(f"⚠️  Skipped {skipped:,} duplicates (multiple details records for same jurisdiction)")
    logger.success(f"✅ Updated {events_updated:,} events to use new jurisdiction_id")
    
    # Verify the update
    logger.info("\n" + "=" * 80)
    logger.info("VERIFICATION")
    logger.info("=" * 80)
    
    cur.execute(f"""
        SELECT 
            js.state_code,
            js.type,
            COUNT(js.id) as in_search,
            COUNT(jd.id) as in_details,
            ROUND(100.0 * COUNT(jd.id) / COUNT(js.id), 1) as mapping_pct
        FROM jurisdictions_search js
        LEFT JOIN jurisdictions_details_search jd ON jd.jurisdiction_id = js.id::text
        WHERE js.type IN ('city', 'county')
        {state_filter.replace('jd.state_code', 'js.state_code')}
        GROUP BY js.state_code, js.type
        ORDER BY js.state_code, js.type
    """)
    
    logger.info("Updated mapping percentages:")
    for row in cur.fetchall():
        logger.info(f"  {row['state_code']} {row['type']}: {row['in_details']}/{row['in_search']} ({row['mapping_pct']}%)")
    
    cur.close()
    conn.close()
    
    return {
        'total': len(results),
        'matched': len(matched),
        'unmatched': len(unmatched),
        'updated': updated
    }


def main():
    parser = argparse.ArgumentParser(
        description="Link cities/counties to jurisdictions_search by updating jurisdiction_id"
    )
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated state codes (e.g., MA,CA,TX)'
    )
    parser.add_argument(
        '--types',
        type=str,
        default='city,county',
        help='Comma-separated jurisdiction types (default: city,county)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without updating database'
    )
    
    args = parser.parse_args()
    
    states = None
    if args.states:
        states = [s.strip().upper() for s in args.states.split(',')]
        logger.info(f"Filtering to states: {', '.join(states)}")
    
    types = [t.strip().lower() for t in args.types.split(',')]
    logger.info(f"Processing jurisdiction types: {', '.join(types)}")
    
    stats = link_jurisdictions(states=states, jurisdiction_types=types, dry_run=args.dry_run)
    
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total jurisdictions: {stats['total']:,}")
    logger.info(f"Matched: {stats['matched']:,}")
    logger.info(f"Unmatched: {stats['unmatched']:,}")
    if not args.dry_run:
        logger.info(f"Updated: {stats['updated']:,}")


if __name__ == "__main__":
    main()
