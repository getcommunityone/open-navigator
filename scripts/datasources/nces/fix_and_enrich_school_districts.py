"""
Fix School District State Codes and Enrich with NCES Data

PROBLEM: The jurisdiction table has 13,326 school districts with NULL state_code
SOLUTION: Extract state from geoid (first 2 digits = state FIPS code) then match to NCES

This script:
1. Updates jurisdiction.state_code from geoid for school districts
2. Matches NCES districts to jurisdiction by name + state
3. Updates jurisdictions_details_search with NCES website + metadata

Usage:
    python fix_and_enrich_school_districts.py --dry-run
    python fix_and_enrich_school_districts.py --states MA,CA
    python fix_and_enrich_school_districts.py
"""
import argparse
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger


# State FIPS code to state code mapping
FIPS_TO_STATE = {
    '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA', '08': 'CO', '09': 'CT',
    '10': 'DE', '11': 'DC', '12': 'FL', '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL',
    '18': 'IN', '19': 'IA', '20': 'KS', '21': 'KY', '22': 'LA', '23': 'ME', '24': 'MD',
    '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS', '29': 'MO', '30': 'MT', '31': 'NE',
    '32': 'NV', '33': 'NH', '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND',
    '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI', '45': 'SC', '46': 'SD',
    '47': 'TN', '48': 'TX', '49': 'UT', '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV',
    '55': 'WI', '56': 'WY', '72': 'PR'
}

STATE_TO_NAME = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'DC': 'District of Columbia',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois',
    'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana',
    'ME': 'Maine', 'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota',
    'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon',
    'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota',
    'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia',
    'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming', 'PR': 'Puerto Rico'
}


def fix_school_district_state_codes(conn, dry_run=False):
    """
    Fix NULL state_code in jurisdiction for school districts.
    Extract state from geoid (first 2 digits = state FIPS code).
    """
    logger.info("=" * 80)
    logger.info("STEP 1: FIX SCHOOL DISTRICT STATE CODES")
    logger.info("=" * 80)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get school districts with NULL state_code but valid geoid
    cur.execute("""
        SELECT id, name, geoid
        FROM jurisdiction
        WHERE type = 'school_district'
        AND (state_code IS NULL OR state_code = '')
        AND geoid IS NOT NULL
        AND LENGTH(geoid) >= 2
    """)
    
    districts = cur.fetchall()
    logger.info(f"Found {len(districts):,} school districts with NULL state_code")
    
    if dry_run:
        logger.warning("DRY RUN - Would update state codes (first 10):")
        for district in districts[:10]:
            fips = district['geoid'][:2]
            state_code = FIPS_TO_STATE.get(fips, '??')
            state_name = STATE_TO_NAME.get(state_code, 'Unknown')
            logger.info(f"  {district['name']}: geoid={district['geoid']} → {state_code} ({state_name})")
        return 0
    
    # Update state_code and state from geoid
    updates = []
    for district in districts:
        fips = district['geoid'][:2]
        state_code = FIPS_TO_STATE.get(fips)
        
        if state_code:
            state_name = STATE_TO_NAME.get(state_code, state_code)
            updates.append((state_code, state_name, district['id']))
    
    if updates:
        cur.execute("BEGIN")
        cur.executemany("""
            UPDATE jurisdiction
            SET state_code = %s, state = %s
            WHERE id = %s
        """, updates)
        conn.commit()
        
        logger.success(f"✅ Updated {len(updates):,} school district state codes")
        
        # Show breakdown by state
        cur.execute("""
            SELECT state_code, COUNT(*) as count
            FROM jurisdiction
            WHERE type = 'school_district'
            AND state_code IS NOT NULL
            GROUP BY state_code
            ORDER BY count DESC
            LIMIT 10
        """)
        
        logger.info("\nTop 10 states by school district count:")
        for row in cur.fetchall():
            logger.info(f"  {row['state_code']}: {row['count']:,} districts")
    
    return len(updates)


def match_and_enrich_nces(conn, states=None, dry_run=False):
    """
    Match NCES districts to jurisdictions and enrich with website + metadata.
    """
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: MATCH AND ENRICH WITH NCES DATA")
    logger.info("=" * 80)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Build state filter for the CTE
    state_filter = ""
    if states:
        state_list = "','".join(states)
        state_filter = f"AND state_code IN ('{state_list}')"
    
    # Match NCES to jurisdictions
    # Try multiple matching strategies
    match_query = f"""
        WITH nces_data AS (
            SELECT 
                nces_id,
                district_name,
                state_code,
                website,
                phone,
                district_type,
                num_schools,
                city,
                street_address,
                zip
            FROM jurisdictions_details_schools
            WHERE website IS NOT NULL AND website != ''
            {state_filter}
        )
        SELECT 
            n.*,
            js.id as jurisdiction_id,
            js.name as jurisdiction_name
        FROM nces_data n
        LEFT JOIN jurisdiction js ON (
            js.type = 'school_district'
            AND js.state_code = n.state_code
            AND (
                -- Strategy 1: Exact match
                LOWER(TRIM(js.name)) = LOWER(TRIM(n.district_name))
                -- Strategy 2: Name without "School District" suffix
                OR LOWER(TRIM(REGEXP_REPLACE(js.name, ' (School District|Public Schools)$', '', 'i'))) 
                   = LOWER(TRIM(REGEXP_REPLACE(n.district_name, ' (School District|Public Schools)$', '', 'i')))
                -- Strategy 3: geoid matches nces_id
                OR js.geoid = n.nces_id
            )
        )
        ORDER BY n.state_code, n.district_name
    """
    
    cur.execute(match_query)
    results = cur.fetchall()
    
    matched = sum(1 for r in results if r['jurisdiction_id'] is not None)
    unmatched = len(results) - matched
    
    logger.info(f"Total NCES districts with websites: {len(results):,}")
    logger.info(f"✅ Matched to jurisdictions: {matched:,}")
    logger.info(f"⚠️  Unmatched: {unmatched:,}")
    
    if dry_run:
        logger.warning("\nDRY RUN - Would update (first 10 matched):")
        shown = 0
        for row in results:
            if row['jurisdiction_id'] and shown < 10:
                logger.info(f"  {row['district_name']} ({row['state_code']})")
                logger.info(f"    → Website: {row['website']}")
                logger.info(f"    → NCES ID: {row['nces_id']}")
                if row['num_schools']:
                    logger.info(f"    → Schools: {row['num_schools']}")
                shown += 1
        return {'matched': matched, 'unmatched': unmatched, 'updated': 0}
    
    # Perform updates
    updated_count = 0
    for row in results:
        if not row['jurisdiction_id']:
            continue
        
        # Build NCES metadata
        nces_metadata = {
            'nces_id': row['nces_id'],
            'district_type': row['district_type'],
            'num_schools': row['num_schools'],
            'phone': row['phone'],
            'school_year': '2024-25',
            'source': 'nces_ccd'
        }
        
        # Add address if available
        if row['street_address'] or row['city'] or row['zip']:
            nces_metadata['address'] = {
                'street': row['street_address'],
                'city': row['city'],
                'zip': row['zip']
            }
            nces_metadata['address'] = {k: v for k, v in nces_metadata['address'].items() if v}
        
        # Remove None values
        nces_metadata = {k: v for k, v in nces_metadata.items() if v is not None}
        
        cur.execute("""
            INSERT INTO jurisdiction (
                jurisdiction_id,
                name,
                type,
                state_code,
                website_url,
                social_media,
                discovery_status,
                last_updated
            ) VALUES (
                %s, %s, 'school_district', %s, %s,
                jsonb_build_object('nces_metadata', %s::jsonb),
                'nces_enriched',
                %s
            )
            ON CONFLICT (jurisdiction_id) DO UPDATE SET
                website_url = COALESCE(jurisdiction.website_url, EXCLUDED.website_url),
                social_media = COALESCE(jurisdiction.social_media, '{}'::jsonb) || EXCLUDED.social_media,
                last_updated = EXCLUDED.last_updated
        """, (
            str(row['jurisdiction_id']),
            row['district_name'],
            row['state_code'],
            row['website'],
            psycopg2.extras.Json(nces_metadata),
            datetime.now()
        ))
        
        updated_count += 1
    
    conn.commit()
    logger.success(f"✅ Updated {updated_count:,} jurisdiction records")
    
    return {'matched': matched, 'unmatched': unmatched, 'updated': updated_count}


def main():
    parser = argparse.ArgumentParser(
        description="Fix school district state codes and enrich with NCES data"
    )
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated state codes (e.g., MA,CA,TX)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without updating database'
    )
    parser.add_argument(
        '--skip-fix',
        action='store_true',
        help='Skip fixing state codes (assume already fixed)'
    )
    
    args = parser.parse_args()
    
    states = None
    if args.states:
        states = [s.strip().upper() for s in args.states.split(',')]
        logger.info(f"Filtering to states: {', '.join(states)}")
    
    # Connect to database
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        database="open_navigator",
        user="postgres",
        password="password"
    )
    
    try:
        # Step 1: Fix state codes
        if not args.skip_fix:
            fixed_count = fix_school_district_state_codes(conn, dry_run=args.dry_run)
        else:
            logger.info("Skipping state code fix (--skip-fix)")
            fixed_count = 0
        
        # Step 2: Match and enrich
        stats = match_and_enrich_nces(conn, states=states, dry_run=args.dry_run)
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        if not args.skip_fix:
            logger.info(f"Fixed state codes: {fixed_count:,}")
        logger.info(f"NCES districts matched: {stats['matched']:,}")
        logger.info(f"NCES districts unmatched: {stats['unmatched']:,}")
        if not args.dry_run:
            logger.info(f"Jurisdictions enriched: {stats['updated']:,}")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
