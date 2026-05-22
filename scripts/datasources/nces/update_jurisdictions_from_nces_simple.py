"""
Simple NCES to Jurisdictions Website Update

This script shows the core concept of how to:
1. Match NCES school districts to jurisdiction by name and state
2. Update jurisdictions_details_search with NCES website URLs

Usage:
    python update_jurisdictions_from_nces_simple.py --dry-run    # Preview changes
    python update_jurisdictions_from_nces_simple.py --states MA,CA,TX  # Specific states
    python update_jurisdictions_from_nces_simple.py              # Update all
"""
import argparse
from datetime import datetime

import psycopg2
from loguru import logger


def normalize_district_name(name: str) -> str:
    """Remove common school district suffixes for matching."""
    if not name:
        return ""
    
    name = name.lower().strip()
    
    # Remove common suffixes
    suffixes = [
        ' school district',
        ' public schools',
        ' unified school district',
        ' independent school district',
        ' community schools',
        ' city schools'
    ]
    
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    
    return name


def update_jurisdictions_from_nces(states: list = None, dry_run: bool = False):
    """
    Update jurisdictions_details_search with NCES website data.
    
    Strategy:
    1. For each NCES district with a website
    2. Try to find matching jurisdiction in jurisdiction
    3. If found, update/create jurisdictions_details_search record
    4. Store NCES metadata (district type, num schools, phone) in social_media JSON
    """
    
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        database="open_navigator",
        user="postgres",
        password="password"
    )
    cur = conn.cursor()
    
    # Build WHERE clause for states filter
    state_filter = ""
    if states:
        state_list = "','".join(states)
        state_filter = f"AND nces.state_code IN ('{state_list}')"
    
    # Query to match NCES districts to jurisdictions
    # This query does a LEFT JOIN to find existing jurisdictions
    match_query = f"""
        SELECT 
            nces.nces_id,
            nces.district_name,
            nces.state_code,
            nces.website,
            nces.phone,
            nces.district_type,
            nces.num_schools,
            nces.city,
            nces.street_address,
            nces.zip,
            js.id as jurisdiction_id,
            js.name as jurisdiction_name
        FROM jurisdictions_details_schools nces
        LEFT JOIN jurisdiction js ON (
            -- Try exact name match first
            LOWER(nces.district_name) = LOWER(js.name)
            AND nces.state_code = js.state_code
            AND js.type = 'school_district'
        )
        WHERE nces.website IS NOT NULL
        AND nces.website != ''
        {state_filter}
        ORDER BY nces.state_code, nces.district_name
    """
    
    cur.execute(match_query)
    results = cur.fetchall()
    
    logger.info(f"Found {len(results):,} NCES districts with websites")
    
    stats = {
        'total': len(results),
        'matched': 0,
        'unmatched': 0,
        'updated': 0
    }
    
    updates = []
    
    for row in results:
        (nces_id, district_name, state_code, website, phone, 
         district_type, num_schools, city, street, zip_code,
         jurisdiction_id, jurisdiction_name) = row
        
        if jurisdiction_id:
            stats['matched'] += 1
            
            # Build NCES metadata JSON
            nces_metadata = {
                'nces_id': nces_id,
                'district_type': district_type,
                'num_schools': num_schools,
                'phone': phone,
                'school_year': '2024-25',
                'address': {
                    'street': street,
                    'city': city,
                    'zip': zip_code
                }
            }
            
            # Remove None values
            nces_metadata = {k: v for k, v in nces_metadata.items() if v is not None}
            if 'address' in nces_metadata:
                nces_metadata['address'] = {k: v for k, v in nces_metadata['address'].items() if v}
                if not nces_metadata['address']:
                    del nces_metadata['address']
            
            updates.append({
                'jurisdiction_id': str(jurisdiction_id),
                'jurisdiction_name': district_name,
                'state_code': state_code,
                'website': website,
                'nces_metadata': nces_metadata
            })
        else:
            stats['unmatched'] += 1
    
    logger.info(f"✅ Matched: {stats['matched']:,}")
    logger.info(f"⚠️  Unmatched: {stats['unmatched']:,}")
    
    if dry_run:
        logger.warning("🔍 DRY RUN - Showing first 10 updates that would be made:")
        for update in updates[:10]:
            logger.info(f"  {update['jurisdiction_name']} ({update['state_code']})")
            logger.info(f"    → Website: {update['website']}")
            logger.info(f"    → NCES ID: {update['nces_metadata'].get('nces_id')}")
            if 'num_schools' in update['nces_metadata']:
                logger.info(f"    → Schools: {update['nces_metadata']['num_schools']}")
    else:
        # Perform the updates
        for update in updates:
            upsert_query = """
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
                    social_media = COALESCE(jurisdiction.social_media, '{}'::jsonb) 
                                   || EXCLUDED.social_media,
                    discovery_status = CASE 
                        WHEN jurisdiction.discovery_status IS NULL 
                        THEN EXCLUDED.discovery_status 
                        ELSE jurisdiction.discovery_status 
                    END,
                    last_updated = EXCLUDED.last_updated
            """
            
            cur.execute(upsert_query, (
                update['jurisdiction_id'],
                update['jurisdiction_name'],
                update['state_code'],
                update['website'],
                psycopg2.extras.Json(update['nces_metadata']),
                datetime.now()
            ))
        
        conn.commit()
        stats['updated'] = len(updates)
        logger.success(f"✅ Updated {stats['updated']:,} jurisdiction records")
        
        # Show sample results
        logger.info("\nSample enriched jurisdictions:")
        cur.execute("""
            SELECT 
                name,
                state_code,
                website_url,
                social_media->'nces_metadata'->>'nces_id' as nces_id,
                social_media->'nces_metadata'->>'num_schools' as num_schools
            FROM jurisdiction
            WHERE social_media ? 'nces_metadata'
            LIMIT 5
        """)
        
        for row in cur.fetchall():
            logger.info(f"  {row[0]} ({row[1]}): {row[2]} | NCES: {row[3]} | Schools: {row[4]}")
    
    cur.close()
    conn.close()
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Update jurisdictions with NCES website data"
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
    
    args = parser.parse_args()
    
    states = None
    if args.states:
        states = [s.strip().upper() for s in args.states.split(',')]
        logger.info(f"Filtering to states: {', '.join(states)}")
    
    stats = update_jurisdictions_from_nces(states=states, dry_run=args.dry_run)
    
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total NCES districts with websites: {stats['total']:,}")
    logger.info(f"Matched to jurisdiction: {stats['matched']:,}")
    logger.info(f"Unmatched (would need new records): {stats['unmatched']:,}")
    if not args.dry_run:
        logger.info(f"Updated in jurisdictions_details_search: {stats['updated']:,}")


if __name__ == "__main__":
    main()
