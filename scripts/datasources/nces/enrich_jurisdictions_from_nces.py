"""
Enrich Jurisdictions with NCES School District Data

This script:
1. Matches NCES school districts to existing jurisdiction records
2. Updates jurisdictions_details_search with NCES data (website, phone, district type)
3. Creates new jurisdiction_details_search records for unmatched NCES districts
4. Classifies jurisdictions by adding district_type and num_schools metadata

Data Flow:
- Source: jurisdictions_details_schools (NCES data with 19,630 districts)
- Target 1: jurisdiction (basic jurisdiction records)
- Target 2: jurisdictions_details_search (enriched metadata)
"""
import argparse
import json
from datetime import datetime
from typing import Dict, List, Tuple

import psycopg2
from psycopg2.extras import execute_batch, RealDictCursor
from loguru import logger


class NCESJurisdictionEnricher:
    """Enrich jurisdiction data with NCES school district information."""
    
    # PostgreSQL connection
    DB_HOST = "localhost"
    DB_PORT = 5433
    DB_NAME = "open_navigator"
    DB_USER = "postgres"
    DB_PASSWORD = "password"
    
    def __init__(self, dry_run: bool = False):
        """Initialize enricher."""
        self.dry_run = dry_run
        self.conn = None
        self.stats = {
            'total_nces_districts': 0,
            'matched_to_jurisdictions': 0,
            'created_new_jurisdictions': 0,
            'updated_details': 0,
            'updated_search': 0,
            'skipped': 0
        }
    
    def get_connection(self):
        """Get PostgreSQL connection."""
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(
                host=self.DB_HOST,
                port=self.DB_PORT,
                database=self.DB_NAME,
                user=self.DB_USER,
                password=self.DB_PASSWORD
            )
        return self.conn
    
    def normalize_name(self, name: str) -> str:
        """Normalize jurisdiction name for matching."""
        if not name:
            return ""
        
        # Convert to lowercase and remove common suffixes
        normalized = name.lower().strip()
        
        # Remove common school district suffixes
        suffixes = [
            'school district',
            'public schools',
            'unified school district',
            'elementary school district',
            'high school district',
            'community schools',
            'city schools',
            'county schools',
            'independent school district',
            'isd',
            'usd',
            'esd',
            'hsd'
        ]
        
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
        
        return normalized
    
    def get_nces_districts(self) -> List[Dict]:
        """Get all NCES school districts with their data."""
        conn = self.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                nces_id,
                district_name,
                state_code,
                state_fips,
                city,
                website,
                phone,
                street_address,
                zip,
                district_type,
                num_schools,
                school_year
            FROM jurisdictions_details_schools
            WHERE district_name IS NOT NULL
            ORDER BY state_code, district_name
        """
        
        cur.execute(query)
        districts = cur.fetchall()
        
        self.stats['total_nces_districts'] = len(districts)
        logger.info(f"📚 Loaded {len(districts):,} NCES school districts")
        
        return districts
    
    def find_matching_jurisdiction(self, nces_district: Dict) -> Tuple[str, str]:
        """
        Find matching jurisdiction in jurisdiction.
        
        Returns: (jurisdiction_id, match_method)
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        district_name = nces_district['district_name']
        state_code = nces_district['state_code']
        normalized = self.normalize_name(district_name)
        
        # Strategy 1: Exact name match in same state
        cur.execute("""
            SELECT id::text as jurisdiction_id
            FROM jurisdiction
            WHERE LOWER(name) = %s
            AND state_code = %s
            AND type = 'school_district'
            LIMIT 1
        """, (district_name.lower(), state_code))
        
        result = cur.fetchone()
        if result:
            return (result[0], 'exact_match')
        
        # Strategy 2: Normalized name match
        cur.execute("""
            SELECT id::text as jurisdiction_id
            FROM jurisdiction
            WHERE type = 'school_district'
            AND state_code = %s
            LIMIT 1
        """, (state_code,))
        
        # Check each result for normalized match
        cur.execute("""
            SELECT jurisdiction_id, name
            FROM jurisdiction
            WHERE type = 'school_district'
            AND state_code = %s
              AND jurisdiction_id IS NOT NULL
        """, (state_code,))
        
        for row in cur.fetchall():
            if self.normalize_name(row[1]) == normalized:
                return (row[0], 'normalized_match')
        
        # No match found - will create new jurisdiction
        return (None, 'no_match')
    
    def create_jurisdiction_in_search(self, nces_district: Dict) -> str:
        """
        Create new jurisdiction record in jurisdiction.
        
        Returns: jurisdiction_id
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        # Use NCES ID as the geoid for school districts
        geoid = nces_district['nces_id']
        
        # Get state name from state_code (would need a lookup table, for now use state_code)
        state_name = nces_district.get('state_code', '')
        
        typed_jid = f"school_district_{str(geoid).zfill(7)}"
        insert_query = """
            INSERT INTO jurisdiction (
                jurisdiction_id,
                name,
                type,
                state_code,
                state,
                geoid,
                fips_code,
                source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (jurisdiction_id) DO UPDATE
            SET geoid = EXCLUDED.geoid,
                fips_code = EXCLUDED.fips_code,
                source = EXCLUDED.source
            RETURNING jurisdiction_id
        """
        cur.execute(insert_query, (
            typed_jid,
            nces_district['district_name'],
            'school_district',
            nces_district['state_code'],
            state_name,
            geoid,
            nces_district.get('state_fips'),
            'nces'
        ))
        jurisdiction_id = cur.fetchone()[0]
        conn.commit()
        
        self.stats['created_new_jurisdictions'] += 1
        return jurisdiction_id
    
    def update_jurisdiction_details(self, jurisdiction_id: str, nces_district: Dict):
        """
        Update or create jurisdictions_details_search with NCES data.
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        # Build metadata JSON for school district info
        school_metadata = {
            'nces_id': nces_district['nces_id'],
            'district_type': nces_district.get('district_type'),
            'num_schools': nces_district.get('num_schools'),
            'school_year': nces_district.get('school_year'),
            'phone': nces_district.get('phone'),
            'address': {
                'street': nces_district.get('street_address'),
                'city': nces_district.get('city'),
                'zip': nces_district.get('zip')
            }
        }
        
        # Clean up None values
        school_metadata = {k: v for k, v in school_metadata.items() if v is not None}
        if school_metadata.get('address'):
            school_metadata['address'] = {k: v for k, v in school_metadata['address'].items() if v is not None}
            if not school_metadata['address']:
                del school_metadata['address']
        
        upsert_query = """
            INSERT INTO jurisdiction (
                jurisdiction_id,
                name,
                type,
                state_code,
                state,
                website_url,
                social_media,
                discovery_status,
                last_updated
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s
            )
            ON CONFLICT (jurisdiction_id) DO UPDATE SET
                website_url = COALESCE(jurisdiction.website_url, EXCLUDED.website_url),
                social_media = COALESCE(jurisdiction.social_media, '{}')::jsonb || EXCLUDED.social_media,
                last_updated = EXCLUDED.last_updated
        """
        
        cur.execute(upsert_query, (
            jurisdiction_id,
            nces_district['district_name'],
            'school_district',
            nces_district['state_code'],
            nces_district.get('state_code', ''),  # Would need state name lookup
            nces_district.get('website'),
            json.dumps({'nces_metadata': school_metadata}),
            'nces_enriched',
            datetime.now()
        ))
        
        conn.commit()
        self.stats['updated_details'] += 1
    
    def enrich_all(self):
        """Main enrichment process."""
        logger.info("=" * 80)
        logger.info("NCES JURISDICTION ENRICHMENT")
        logger.info("=" * 80)
        
        if self.dry_run:
            logger.warning("🔍 DRY RUN MODE - No changes will be made")
        
        # Step 1: Get all NCES districts
        nces_districts = self.get_nces_districts()
        
        # Step 2: Process each district
        logger.info("\n" + "=" * 80)
        logger.info("MATCHING AND ENRICHING JURISDICTIONS")
        logger.info("=" * 80)
        
        for i, district in enumerate(nces_districts):
            if i > 0 and i % 1000 == 0:
                logger.info(f"Processed {i:,} / {len(nces_districts):,} districts...")
            
            # Find matching jurisdiction
            jurisdiction_id, match_method = self.find_matching_jurisdiction(district)
            
            if match_method == 'no_match':
                # Create new jurisdiction
                if not self.dry_run:
                    jurisdiction_id = self.create_jurisdiction_in_search(district)
                else:
                    logger.debug(f"Would create: {district['district_name']} ({district['state_code']})")
                    continue
            else:
                self.stats['matched_to_jurisdictions'] += 1
            
            # Update jurisdiction details
            if not self.dry_run and jurisdiction_id:
                self.update_jurisdiction_details(jurisdiction_id, district)
        
        # Step 3: Print statistics
        logger.info("\n" + "=" * 80)
        logger.info("ENRICHMENT COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total NCES districts: {self.stats['total_nces_districts']:,}")
        logger.info(f"Matched to existing jurisdictions: {self.stats['matched_to_jurisdictions']:,}")
        logger.info(f"Created new jurisdictions: {self.stats['created_new_jurisdictions']:,}")
        logger.info(f"Updated jurisdiction details: {self.stats['updated_details']:,}")
        
        # Sample query to show results
        if not self.dry_run:
            self.show_sample_results()
    
    def show_sample_results(self):
        """Show sample enriched jurisdictions."""
        logger.info("\n" + "=" * 80)
        logger.info("SAMPLE ENRICHED JURISDICTIONS")
        logger.info("=" * 80)
        
        conn = self.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                d.name,
                d.state_code,
                d.website_url,
                d.social_media->>'nces_metadata' as nces_data,
                d.discovery_status
            FROM jurisdiction d
            WHERE d.social_media ? 'nces_metadata'
            AND d.state_code = 'MA'
            ORDER BY d.jurisdiction_name
            LIMIT 10
        """
        
        cur.execute(query)
        results = cur.fetchall()
        
        for row in results:
            logger.info(f"\n  {row['jurisdiction_name']} ({row['state_code']})")
            logger.info(f"    Website: {row['website_url']}")
            if row['nces_data']:
                nces_info = json.loads(row['nces_data'])
                if 'nces_id' in nces_info:
                    logger.info(f"    NCES ID: {nces_info['nces_id']}")
                if 'num_schools' in nces_info:
                    logger.info(f"    Schools: {nces_info['num_schools']}")


def main():
    """Run NCES jurisdiction enrichment."""
    parser = argparse.ArgumentParser(
        description="Enrich jurisdictions with NCES school district data"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    args = parser.parse_args()
    
    enricher = NCESJurisdictionEnricher(dry_run=args.dry_run)
    enricher.enrich_all()
    
    if enricher.conn:
        enricher.conn.close()


if __name__ == "__main__":
    main()
