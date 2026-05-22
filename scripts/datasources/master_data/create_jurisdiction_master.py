#!/usr/bin/env python3
"""
Master Data Management: Jurisdiction Consolidation Strategy

This script creates a unified master jurisdiction table that links:
- organization_location (schools, hospitals, etc.)
- jurisdictions_wikidata
- jurisdiction
- jurisdiction

Matching strategies:
1. Domain-based matching (extract and normalize domains from URLs)
2. ID-based matching (NCES, FIPS, GEOID)
3. Fuzzy name matching (city, county, state, school board)
4. Geographic hierarchy matching (city → county → state)

Output: master_jurisdictions table with cross-reference mappings
"""
import re
from urllib.parse import urlparse
from typing import Optional, List, Tuple
import psycopg2
from psycopg2.extras import execute_values
from loguru import logger
from difflib import SequenceMatcher


# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "database": "open_navigator",
    "user": "postgres",
    "password": "password"
}


def get_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(**DB_CONFIG)


def extract_domain(url: Optional[str]) -> Optional[str]:
    """
    Extract normalized domain from URL.
    
    Examples:
        http://www.yupiit.org → yupiit.org
        https://www.asdk12.org → asdk12.org
        http://www.sea-isle-city.nj.us → sea-isle-city.nj.us
    """
    if not url:
        return None
    
    try:
        parsed = urlparse(url.strip().lower())
        domain = parsed.netloc or parsed.path
        
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Remove trailing slashes
        domain = domain.rstrip('/')
        
        return domain if domain else None
    except:
        return None


def normalize_name(name: str) -> str:
    """
    Normalize jurisdiction/organization name for matching.
    
    - Convert to lowercase
    - Remove common suffixes (County, City, School District, etc.)
    - Remove punctuation
    - Collapse whitespace
    """
    if not name:
        return ""
    
    normalized = name.lower().strip()
    
    # Remove common suffixes
    suffixes = [
        'school district', 'unified school district', 'city school district',
        'county school district', 'independent school district',
        'board of education', 'public schools',
        'county', 'city', 'town', 'village', 'township', 'borough',
        'municipality', 'district'
    ]
    
    for suffix in suffixes:
        if normalized.endswith(' ' + suffix):
            normalized = normalized[:-len(suffix)-1]
    
    # Remove punctuation and collapse whitespace
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def fuzzy_match_score(str1: str, str2: str) -> float:
    """
    Calculate fuzzy match score between two strings.
    
    Returns: 0.0 to 1.0 (1.0 = exact match)
    """
    return SequenceMatcher(None, 
                           normalize_name(str1), 
                           normalize_name(str2)).ratio()


def create_master_tables(conn):
    """
    Create master data management tables.
    
    Tables:
    1. domain_registry: Normalized domain → source mapping
    2. jurisdiction_crosswalk: Cross-reference between all jurisdiction tables
    3. master_jurisdictions: Unified view of all jurisdictions
    """
    with conn.cursor() as cur:
        # 1. Domain Registry Table
        logger.info("Creating domain_registry table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS domain_registry (
                id SERIAL PRIMARY KEY,
                domain VARCHAR(500) UNIQUE NOT NULL,
                source_table VARCHAR(100) NOT NULL,
                source_id INTEGER NOT NULL,
                source_url TEXT,
                jurisdiction_name VARCHAR(500),
                state_code VARCHAR(2),
                city VARCHAR(200),
                organization_type VARCHAR(100),
                confidence_score DECIMAL(3,2) DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(source_table, source_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_domain_registry_domain 
                ON domain_registry(domain);
            CREATE INDEX IF NOT EXISTS idx_domain_registry_state 
                ON domain_registry(state_code);
            CREATE INDEX IF NOT EXISTS idx_domain_registry_source 
                ON domain_registry(source_table, source_id);
        """)
        
        # 2. Jurisdiction Crosswalk Table
        logger.info("Creating jurisdiction_crosswalk table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jurisdiction_crosswalk (
                id SERIAL PRIMARY KEY,
                master_jurisdiction_id INTEGER,
                
                -- Source IDs
                org_location_id INTEGER,
                wikidata_id INTEGER,
                search_id INTEGER,
                details_search_id INTEGER,
                
                -- Identifiers
                nces_id VARCHAR(20),
                fips_code VARCHAR(20),
                geoid VARCHAR(20),
                gnis_id VARCHAR(10),
                
                -- Names
                primary_name VARCHAR(500),
                normalized_name VARCHAR(500),
                
                -- Geography
                state_code VARCHAR(2),
                state VARCHAR(50),
                county VARCHAR(200),
                city VARCHAR(200),
                
                -- Type
                jurisdiction_type VARCHAR(100),
                organization_type VARCHAR(100),
                
                -- Matching metadata
                match_method VARCHAR(100),
                match_confidence DECIMAL(3,2),
                
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_crosswalk_master ON jurisdiction_crosswalk(master_jurisdiction_id);
            CREATE INDEX IF NOT EXISTS idx_crosswalk_nces ON jurisdiction_crosswalk(nces_id);
            CREATE INDEX IF NOT EXISTS idx_crosswalk_fips ON jurisdiction_crosswalk(fips_code);
            CREATE INDEX IF NOT EXISTS idx_crosswalk_geoid ON jurisdiction_crosswalk(geoid);
            CREATE INDEX IF NOT EXISTS idx_crosswalk_state ON jurisdiction_crosswalk(state_code);
            CREATE INDEX IF NOT EXISTS idx_crosswalk_name ON jurisdiction_crosswalk USING gin(to_tsvector('english', primary_name));
        """)
        
        # 3. Master Jurisdictions Table
        logger.info("Creating master_jurisdictions table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS master_jurisdictions (
                id SERIAL PRIMARY KEY,
                
                -- Primary identifiers
                nces_id VARCHAR(20),
                fips_code VARCHAR(20),
                geoid VARCHAR(20),
                wikidata_id VARCHAR(20),
                
                -- Names
                canonical_name VARCHAR(500) NOT NULL,
                alternate_names TEXT[],
                
                -- Geography
                state_code VARCHAR(2) NOT NULL,
                state VARCHAR(50) NOT NULL,
                county VARCHAR(200),
                city VARCHAR(200),
                
                -- Classification
                primary_type VARCHAR(100) NOT NULL,
                sub_types TEXT[],
                
                -- Contact
                primary_website TEXT,
                all_websites TEXT[],
                domains TEXT[],
                
                -- Metrics
                population INTEGER,
                area_sq_miles DECIMAL(12,2),
                
                -- Metadata
                source_count INTEGER DEFAULT 1,
                data_completeness_score DECIMAL(3,2),
                last_verified TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                
                UNIQUE(canonical_name, state_code, primary_type)
            );
            
            CREATE INDEX IF NOT EXISTS idx_master_nces ON master_jurisdictions(nces_id);
            CREATE INDEX IF NOT EXISTS idx_master_fips ON master_jurisdictions(fips_code);
            CREATE INDEX IF NOT EXISTS idx_master_geoid ON master_jurisdictions(geoid);
            CREATE INDEX IF NOT EXISTS idx_master_state ON master_jurisdictions(state_code);
            CREATE INDEX IF NOT EXISTS idx_master_name ON master_jurisdictions USING gin(to_tsvector('english', canonical_name));
            CREATE INDEX IF NOT EXISTS idx_master_domains ON master_jurisdictions USING gin(domains);
        """)
        
        conn.commit()
        logger.success("✅ Created master data tables")


def populate_domain_registry(conn):
    """
    Populate domain registry from all sources.
    
    Sources:
    1. organization_location (schools, hospitals, etc.)
    2. jurisdictions_wikidata (official_website)
    3. jurisdiction (website_url)
    """
    logger.info("Populating domain_registry...")
    
    with conn.cursor() as cur:
        # Clear existing data
        cur.execute("TRUNCATE domain_registry RESTART IDENTITY CASCADE")
        
        # 1. Extract from organization_location
        logger.info("Extracting domains from organization_location...")
        cur.execute("""
            SELECT id, name, city, state, website, organization_type
            FROM organization_location
            WHERE website IS NOT NULL
        """)
        
        org_domains = []
        for row in cur.fetchall():
            org_id, name, city, state, website, org_type = row
            domain = extract_domain(website)
            
            if domain:
                org_domains.append((
                    domain,
                    'organization_location',
                    org_id,
                    website,
                    name,
                    state,
                    city,
                    org_type,
                    1.0  # confidence
                ))
        
        if org_domains:
            execute_values(cur, """
                INSERT INTO domain_registry 
                (domain, source_table, source_id, source_url, jurisdiction_name, 
                 state_code, city, organization_type, confidence_score)
                VALUES %s
                ON CONFLICT (domain) DO NOTHING
            """, org_domains)
            logger.info(f"Inserted {len(org_domains)} domains from organization_location")
        
        # 2. Extract from jurisdictions_wikidata
        logger.info("Extracting domains from jurisdictions_wikidata...")
        cur.execute("""
            SELECT id, jurisdiction_name, state_code, official_website, jurisdiction_type
            FROM jurisdictions_wikidata
            WHERE official_website IS NOT NULL
        """)
        
        wiki_domains = []
        for row in cur.fetchall():
            wiki_id, name, state, website, jur_type = row
            domain = extract_domain(website)
            
            if domain:
                wiki_domains.append((
                    domain,
                    'jurisdictions_wikidata',
                    wiki_id,
                    website,
                    name,
                    state,
                    None,  # city
                    jur_type,
                    1.0  # confidence
                ))
        
        if wiki_domains:
            execute_values(cur, """
                INSERT INTO domain_registry 
                (domain, source_table, source_id, source_url, jurisdiction_name, 
                 state_code, city, organization_type, confidence_score)
                VALUES %s
                ON CONFLICT (domain) DO NOTHING
            """, wiki_domains)
            logger.info(f"Inserted {len(wiki_domains)} domains from jurisdictions_wikidata")
        
        # 3. Extract from jurisdiction
        logger.info("Extracting domains from jurisdiction...")
        cur.execute("""
            SELECT id, name AS jurisdiction_name, state_code, website_url, type AS jurisdiction_type
            FROM jurisdiction
            WHERE website_url IS NOT NULL
        """)
        
        details_domains = []
        for row in cur.fetchall():
            details_id, name, state, website, jur_type = row
            domain = extract_domain(website)
            
            if domain:
                details_domains.append((
                    domain,
                    'jurisdiction',
                    details_id,
                    website,
                    name,
                    state,
                    None,  # city
                    jur_type,
                    1.0  # confidence
                ))
        
        if details_domains:
            execute_values(cur, """
                INSERT INTO domain_registry 
                (domain, source_table, source_id, source_url, jurisdiction_name, 
                 state_code, city, organization_type, confidence_score)
                VALUES %s
                ON CONFLICT (domain) DO NOTHING
            """, details_domains)
            logger.info(f"Inserted {len(details_domains)} domains from jurisdiction")
        
        conn.commit()
        
        # Show stats
        cur.execute("SELECT COUNT(*) FROM domain_registry")
        total = cur.fetchone()[0]
        logger.success(f"✅ Domain registry populated with {total:,} unique domains")


def build_crosswalk_by_nces(conn):
    """
    Build crosswalk using NCES ID matching.
    
    Match school districts across:
    - organization_location (source_id = nces_id for school_district)
    - jurisdictions_wikidata (nces_id)
    - jurisdiction (may have nces_id in future)
    """
    logger.info("Building crosswalk by NCES ID...")
    
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO jurisdiction_crosswalk 
            (org_location_id, wikidata_id, nces_id, primary_name, state_code, 
             state, city, jurisdiction_type, organization_type, match_method, match_confidence)
            SELECT 
                ol.id as org_location_id,
                jw.id as wikidata_id,
                ol.source_id as nces_id,
                ol.name as primary_name,
                ol.state as state_code,
                NULL as state,
                ol.city,
                'school_district' as jurisdiction_type,
                ol.organization_type,
                'nces_id_exact' as match_method,
                1.0 as match_confidence
            FROM organization_location ol
            LEFT JOIN jurisdictions_wikidata jw 
                ON ol.source_id = jw.nces_id 
                AND ol.state = jw.state_code
            WHERE ol.organization_type = 'school_district'
              AND ol.source_id IS NOT NULL
              AND ol.source_id != ''
            ON CONFLICT DO NOTHING
        """)
        
        count = cur.rowcount
        conn.commit()
        logger.info(f"Matched {count:,} school districts by NCES ID")


def build_crosswalk_by_geoid(conn):
    """
    Build crosswalk using GEOID matching.
    
    Match jurisdictions using Census GEOID across:
    - jurisdiction (geoid)
    - jurisdictions_wikidata (geoid)
    """
    logger.info("Building crosswalk by GEOID...")
    
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO jurisdiction_crosswalk 
            (search_id, wikidata_id, geoid, primary_name, state_code, state, 
             county, city, jurisdiction_type, match_method, match_confidence)
            SELECT 
                js.id as search_id,
                jw.id as wikidata_id,
                js.geoid,
                js.name as primary_name,
                js.state_code,
                js.state,
                js.county,
                NULL as city,
                js.type as jurisdiction_type,
                'geoid_exact' as match_method,
                1.0 as match_confidence
            FROM jurisdiction js
            LEFT JOIN jurisdictions_wikidata jw 
                ON js.geoid = jw.geoid
                AND js.state_code = jw.state_code
            WHERE js.geoid IS NOT NULL
              AND js.geoid != ''
            ON CONFLICT DO NOTHING
        """)
        
        count = cur.rowcount
        conn.commit()
        logger.info(f"Matched {count:,} jurisdictions by GEOID")


def build_crosswalk_by_normalized_name(conn):
    """
    Build crosswalk using normalized name matching.
    
    Handles cases where names differ only by suffix (CDP, town, city, etc.)
    Example: "Appling" in wikidata matches "Appling CDP" in search
    """
    logger.info("Building crosswalk by normalized name (removes suffixes)...")
    
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO jurisdiction_crosswalk 
            (search_id, wikidata_id, primary_name, state_code, jurisdiction_type, 
             match_method, match_confidence)
            SELECT 
                js.id as search_id,
                jw.id as wikidata_id,
                jw.jurisdiction_name as primary_name,
                js.state_code,
                js.type as jurisdiction_type,
                'name_normalized' as match_method,
                0.90 as match_confidence
            FROM jurisdiction js
            JOIN jurisdictions_wikidata jw ON
                REGEXP_REPLACE(LOWER(TRIM(js.name)), 
                    ' (historic district|cdp|town|city|village|borough|municipality)$', 
                    '', 'i') = 
                REGEXP_REPLACE(LOWER(TRIM(jw.jurisdiction_name)), 
                    ' (historic district|cdp|town|city|village|borough|municipality)$', 
                    '', 'i')
                AND js.state_code = jw.state_code
                AND js.type = jw.jurisdiction_type
            WHERE NOT EXISTS (
                -- Don't duplicate if already matched by GEOID
                SELECT 1 FROM jurisdiction_crosswalk jc 
                WHERE jc.search_id = js.id AND jc.wikidata_id = jw.id
            )
            ON CONFLICT DO NOTHING
        """)
        
        count = cur.rowcount
        conn.commit()
        logger.info(f"Matched {count:,} jurisdictions by normalized name")


def build_crosswalk_by_phone(conn):
    """
    Build crosswalk using phone number matching.
    
    Match organization_location phone to jurisdiction phone.
    Normalizes phone numbers by removing non-digit characters.
    """
    logger.info("Building crosswalk by phone number...")
    
    with conn.cursor() as cur:
        # Match organization_location to jurisdiction by phone
        cur.execute("""
            INSERT INTO jurisdiction_crosswalk 
            (org_location_id, details_search_id, primary_name, state_code, 
             organization_type, jurisdiction_type, match_method, match_confidence)
            SELECT 
                ol.id as org_id,
                jd.id as details_id,
                ol.name,
                ol.state,
                ol.organization_type,
                jd.jurisdiction_type,
                'phone_exact' as match_method,
                0.85 as match_confidence
            FROM organization_location ol
            JOIN jurisdiction jd ON
                -- Normalize phone by removing all non-digits
                REGEXP_REPLACE(ol.telephone, '[^0-9]', '', 'g') = 
                REGEXP_REPLACE(jd.phone, '[^0-9]', '', 'g')
                AND ol.state = jd.state_code
            WHERE ol.telephone IS NOT NULL 
              AND ol.telephone != ''
              AND jd.phone IS NOT NULL
              AND jd.phone != ''
              AND LENGTH(REGEXP_REPLACE(ol.telephone, '[^0-9]', '', 'g')) >= 10
            ON CONFLICT DO NOTHING
        """)
        
        count = cur.rowcount
        conn.commit()
        logger.info(f"Matched {count:,} organizations to jurisdictions by phone")


def build_crosswalk_wikidata_to_details_by_city(conn):
    """
    Match jurisdictions_wikidata to jurisdiction by city+state.
    
    Handles cases where details has extra "Town" or "City" suffix.
    Example: "North Attleborough" matches "North Attleborough Town"
    """
    logger.info("Matching wikidata to details by city+state...")
    
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO jurisdiction_crosswalk 
            (wikidata_id, details_search_id, primary_name, state_code, 
             jurisdiction_type, match_method, match_confidence)
            SELECT 
                jw.id as wikidata_id,
                jd.id as details_id,
                jw.jurisdiction_name,
                jw.state_code,
                jw.jurisdiction_type,
                'city_state_normalized' as match_method,
                0.85 as match_confidence
            FROM jurisdictions_wikidata jw
            JOIN jurisdiction jd ON jw.state_code = jd.state_code
            WHERE jw.jurisdiction_type = jd.jurisdiction_type
              AND (
                  -- Exact match after removing Town/City suffix
                  LOWER(TRIM(jw.jurisdiction_name)) = 
                  LOWER(TRIM(REGEXP_REPLACE(jd.name, ' (Town|City)$', '', 'i')))
                  OR
                  -- Match after removing all non-letter characters (handles hyphens, spaces)
                  REGEXP_REPLACE(LOWER(TRIM(jw.jurisdiction_name)), '[^a-z]', '', 'g') = 
                  REGEXP_REPLACE(LOWER(TRIM(jd.name)), '[^a-z]', '', 'g')
              )
            ON CONFLICT DO NOTHING
        """)
        
        count = cur.rowcount
        conn.commit()
        logger.info(f"Matched {count:,} wikidata to details by city+state")


def build_crosswalk_by_city_proximity(conn):
    """
    Match organization_location to jurisdictions by city name + state.
    
    Uses normalized city names to handle variations like:
    - "N Attleborough" vs "North Attleborough"
    - "Attleboro" vs "Attleborough"
    """
    logger.info("Matching organizations to jurisdictions by city proximity...")
    
    with conn.cursor() as cur:
        # Match orgloc to wikidata by city+state
        cur.execute("""
            INSERT INTO jurisdiction_crosswalk 
            (org_location_id, wikidata_id, primary_name, state_code, city,
             organization_type, jurisdiction_type, match_method, match_confidence)
            SELECT 
                ol.id as org_id,
                jw.id as wiki_id,
                ol.name,
                ol.state,
                ol.city,
                ol.organization_type,
                jw.jurisdiction_type,
                'city_geographic' as match_method,
                0.75 as match_confidence
            FROM organization_location ol
            JOIN jurisdictions_wikidata jw ON ol.state = jw.state_code
            WHERE jw.jurisdiction_type = 'city'
              AND (
                  -- Normalize city names by removing punctuation and spaces
                  REGEXP_REPLACE(LOWER(TRIM(ol.city)), '[^a-z]', '', 'g') = 
                  REGEXP_REPLACE(LOWER(TRIM(jw.jurisdiction_name)), '[^a-z]', '', 'g')
              )
              AND ol.city IS NOT NULL
              AND ol.city != ''
            ON CONFLICT DO NOTHING
        """)
        
        orgloc_wiki_count = cur.rowcount
        
        # Match orgloc to details by city+state
        cur.execute("""
            INSERT INTO jurisdiction_crosswalk 
            (org_location_id, details_search_id, primary_name, state_code, city,
             organization_type, jurisdiction_type, match_method, match_confidence)
            SELECT 
                ol.id as org_id,
                jd.id as details_id,
                ol.name,
                ol.state,
                ol.city,
                ol.organization_type,
                jd.jurisdiction_type,
                'city_geographic_details' as match_method,
                0.75 as match_confidence
            FROM organization_location ol
            JOIN jurisdiction jd ON ol.state = jd.state_code
            WHERE jd.jurisdiction_type = 'city'
              AND (
                  -- Normalize city names
                  REGEXP_REPLACE(LOWER(TRIM(ol.city)), '[^a-z]', '', 'g') = 
                  REGEXP_REPLACE(LOWER(TRIM(REGEXP_REPLACE(jd.name, ' (Town|City)$', '', 'i'))), '[^a-z]', '', 'g')
              )
              AND ol.city IS NOT NULL
              AND ol.city != ''
            ON CONFLICT DO NOTHING
        """)
        
        orgloc_details_count = cur.rowcount
        
        conn.commit()
        logger.info(f"Matched {orgloc_wiki_count:,} orgloc→wikidata + {orgloc_details_count:,} orgloc→details by city")


def build_crosswalk_by_proximity(conn):
    """
    Match organizations to jurisdictions by geographic proximity.
    
    For unmatched records, if within ~1 mile (0.015 degrees) of a jurisdiction,
    create a match. Uses Haversine-style distance calculation.
    """
    logger.info("Matching stragglers by geographic proximity (within 1 mile)...")
    
    with conn.cursor() as cur:
        # Match unmatched orgloc to wikidata by proximity
        cur.execute("""
            INSERT INTO jurisdiction_crosswalk 
            (org_location_id, wikidata_id, primary_name, state_code, city,
             organization_type, jurisdiction_type, match_method, match_confidence)
            SELECT 
                ol.id as org_id,
                jw.id as wiki_id,
                ol.name,
                ol.state,
                ol.city,
                ol.organization_type,
                jw.jurisdiction_type,
                'proximity_1mile' as match_method,
                0.70 as match_confidence
            FROM organization_location ol
            CROSS JOIN LATERAL (
                SELECT 
                    jw.id,
                    jw.jurisdiction_type,
                    jw.jurisdiction_name,
                    -- Simple distance calculation in degrees (approx 1 mile = 0.015 degrees)
                    SQRT(
                        POW((jw.latitude - ol.latitude), 2) + 
                        POW((jw.longitude - ol.longitude), 2)
                    ) as distance_degrees
                FROM jurisdictions_wikidata jw
                WHERE jw.latitude IS NOT NULL 
                  AND jw.longitude IS NOT NULL
                  AND jw.state_code = ol.state
                  AND SQRT(
                      POW((jw.latitude - ol.latitude), 2) + 
                      POW((jw.longitude - ol.longitude), 2)
                  ) < 0.015  -- Approximately 1 mile
                ORDER BY distance_degrees
                LIMIT 1
            ) jw
            WHERE ol.latitude IS NOT NULL 
              AND ol.longitude IS NOT NULL
              AND NOT EXISTS (
                  -- Only match stragglers that haven't been matched yet
                  SELECT 1 FROM jurisdiction_crosswalk jc 
                  WHERE jc.org_location_id = ol.id 
                    AND jc.wikidata_id IS NOT NULL
              )
            ON CONFLICT DO NOTHING
        """)
        
        count = cur.rowcount
        conn.commit()
        logger.info(f"Matched {count:,} stragglers to jurisdictions by proximity")


def build_crosswalk_by_domain(conn):
    """
    Build crosswalk using domain matching.
    
    Match organizations/jurisdictions with same domain.
    """
    logger.info("Building crosswalk by domain...")
    
    with conn.cursor() as cur:
        # Find domain collisions (same domain across different sources)
        cur.execute("""
            WITH domain_matches AS (
                SELECT 
                    domain,
                    MAX(CASE WHEN source_table = 'organization_location' THEN source_id END) as org_id,
                    MAX(CASE WHEN source_table = 'jurisdictions_wikidata' THEN source_id END) as wiki_id,
                    MAX(CASE WHEN source_table = 'jurisdiction' THEN source_id END) as details_id,
                    MAX(jurisdiction_name) as name,
                    MAX(state_code) as state_code,
                    MAX(city) as city,
                    COUNT(DISTINCT source_table) as source_count
                FROM domain_registry
                GROUP BY domain
                HAVING COUNT(DISTINCT source_table) > 1
            )
            INSERT INTO jurisdiction_crosswalk 
            (org_location_id, wikidata_id, details_search_id, primary_name, 
             state_code, city, match_method, match_confidence)
            SELECT 
                org_id,
                wiki_id,
                details_id,
                name,
                state_code,
                city,
                'domain_exact' as match_method,
                0.95 as match_confidence
            FROM domain_matches
            ON CONFLICT DO NOTHING
        """)
        
        count = cur.rowcount
        conn.commit()
        logger.info(f"Matched {count:,} entities by domain")


def build_crosswalk_orgloc_to_search(conn):
    """
    Match organization_location to jurisdiction by name+state+type.
    
    Uses organization_location as a bridge since it has rich data (websites, addresses)
    that jurisdiction lacks.
    """
    logger.info("Matching organization_location to jurisdiction...")
    
    with conn.cursor() as cur:
        # Map organization_type to jurisdiction type
        cur.execute("""
            INSERT INTO jurisdiction_crosswalk 
            (org_location_id, search_id, primary_name, state_code, 
             organization_type, jurisdiction_type, match_method, match_confidence)
            SELECT 
                ol.id as org_id,
                js.id as search_id,
                ol.name,
                ol.state,
                ol.organization_type,
                js.type,
                'name_state_type' as match_method,
                0.85 as match_confidence
            FROM organization_location ol
            JOIN jurisdiction js ON 
                LOWER(TRIM(ol.name)) = LOWER(TRIM(js.name))
                AND ol.state = js.state_code
                AND (
                    (ol.organization_type = 'school_district' AND js.type = 'school_district') OR
                    (ol.organization_type = 'county' AND js.type = 'county') OR
                    (ol.organization_type IN ('city', 'town', 'village') AND js.type = 'city') OR
                    (ol.organization_type = 'township' AND js.type = 'township')
                )
            WHERE ol.name IS NOT NULL
            ON CONFLICT DO NOTHING
        """)
        
        count = cur.rowcount
        conn.commit()
        logger.info(f"Matched {count:,} organizations to jurisdiction")


def build_crosswalk_orgloc_to_wikidata_by_domain(conn):
    """
    Match organization_location to jurisdictions_wikidata by domain.
    
    Uses website URLs to link organizations to their jurisdiction records.
    """
    logger.info("Matching organization_location to jurisdictions_wikidata by domain...")
    
    with conn.cursor() as cur:
        cur.execute("""
            WITH org_domains AS (
                SELECT 
                    id as org_id,
                    name,
                    state,
                    city,
                    LOWER(TRIM(REGEXP_REPLACE(
                        REGEXP_REPLACE(website, '^https?://(www\.)?', ''),
                        '/.*$', ''
                    ))) as domain
                FROM organization_location
                WHERE website IS NOT NULL 
                    AND website != ''
                    AND website NOT ILIKE '%not available%'
            ),
            wiki_domains AS (
                SELECT 
                    id as wiki_id,
                    jurisdiction_name,
                    state_code,
                    LOWER(TRIM(REGEXP_REPLACE(
                        REGEXP_REPLACE(official_website, '^https?://(www\.)?', ''),
                        '/.*$', ''
                    ))) as domain
                FROM jurisdictions_wikidata
                WHERE official_website IS NOT NULL 
                    AND official_website != ''
            )
            INSERT INTO jurisdiction_crosswalk 
            (org_location_id, wikidata_id, primary_name, state_code, city,
             organization_type, jurisdiction_type, match_method, match_confidence)
            SELECT 
                od.org_id,
                wd.wiki_id,
                od.name,
                od.state,
                od.city,
                ol.organization_type,
                jw.jurisdiction_type,
                'domain_orgloc_wikidata' as match_method,
                0.90 as match_confidence
            FROM org_domains od
            JOIN wiki_domains wd ON od.domain = wd.domain
            JOIN organization_location ol ON od.org_id = ol.id
            JOIN jurisdictions_wikidata jw ON wd.wiki_id = jw.id
            WHERE od.domain IS NOT NULL AND od.domain != ''
            ON CONFLICT DO NOTHING
        """)
        
        count = cur.rowcount
        conn.commit()
        logger.info(f"Matched {count:,} organizations to wikidata by domain")


def build_crosswalk_orgloc_to_details_by_domain(conn):
    """
    Match organization_location to jurisdiction by domain.
    
    Links organizations to detailed jurisdiction records through website matching.
    """
    logger.info("Matching organization_location to jurisdiction by domain...")
    
    with conn.cursor() as cur:
        # First, check if jurisdiction has websites
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'jurisdiction' 
                AND column_name IN ('website', 'gov_url', 'official_website')
            )
        """)
        
        has_website = cur.fetchone()[0]
        
        if not has_website:
            logger.warning("jurisdiction has no website column - checking gov_domains JSONB...")
            
            # Try matching via gov_domains JSONB field
            cur.execute("""
                WITH org_domains AS (
                    SELECT 
                        id as org_id,
                        name,
                        state,
                        city,
                        LOWER(TRIM(REGEXP_REPLACE(
                            REGEXP_REPLACE(website, '^https?://(www\.)?', ''),
                            '/.*$', ''
                        ))) as domain
                    FROM organization_location
                    WHERE website IS NOT NULL 
                        AND website != ''
                        AND website NOT ILIKE '%not available%'
                )
                INSERT INTO jurisdiction_crosswalk 
                (org_location_id, details_search_id, primary_name, state_code, city,
                 organization_type, jurisdiction_type, match_method, match_confidence)
                SELECT 
                    od.org_id,
                    jd.id,
                    od.name,
                    od.state,
                    od.city,
                    ol.organization_type,
                    jd.jurisdiction_type,
                    'domain_orgloc_details_jsonb' as match_method,
                    0.80 as match_confidence
                FROM org_domains od
                JOIN jurisdiction jd ON 
                    jd.gov_domains ? od.domain
                JOIN organization_location ol ON od.org_id = ol.id
                WHERE od.domain IS NOT NULL AND od.domain != ''
                ON CONFLICT DO NOTHING
            """)
        else:
            # Direct website column matching
            cur.execute("""
                WITH org_domains AS (
                    SELECT 
                        id as org_id,
                        name,
                        state,
                        city,
                        LOWER(TRIM(REGEXP_REPLACE(
                            REGEXP_REPLACE(website, '^https?://(www\.)?', ''),
                            '/.*$', ''
                        ))) as domain
                    FROM organization_location
                    WHERE website IS NOT NULL 
                        AND website != ''
                        AND website NOT ILIKE '%not available%'
                ),
                details_domains AS (
                    SELECT 
                        id as details_id,
                        LOWER(TRIM(REGEXP_REPLACE(
                            REGEXP_REPLACE(website, '^https?://(www\.)?', ''),
                            '/.*$', ''
                        ))) as domain
                    FROM jurisdiction
                    WHERE website IS NOT NULL AND website != ''
                )
                INSERT INTO jurisdiction_crosswalk 
                (org_location_id, details_search_id, primary_name, state_code, city,
                 organization_type, jurisdiction_type, match_method, match_confidence)
                SELECT 
                    od.org_id,
                    dd.details_id,
                    od.name,
                    od.state,
                    od.city,
                    ol.organization_type,
                    jd.jurisdiction_type,
                    'domain_orgloc_details' as match_method,
                    0.90 as match_confidence
                FROM org_domains od
                JOIN details_domains dd ON od.domain = dd.domain
                JOIN organization_location ol ON od.org_id = ol.id
                JOIN jurisdiction jd ON dd.details_id = jd.id
                WHERE od.domain IS NOT NULL AND od.domain != ''
                ON CONFLICT DO NOTHING
            """)
        
        count = cur.rowcount
        conn.commit()
        logger.info(f"Matched {count:,} organizations to jurisdiction")


def build_crosswalk_by_fuzzy_name(conn, threshold: float = 0.85):
    """
    Build crosswalk using fuzzy name matching.
    
    Match jurisdictions with similar names in same state.
    Uses Levenshtein distance / fuzzy matching.
    """
    logger.info(f"Building crosswalk by fuzzy name matching (threshold={threshold})...")
    
    with conn.cursor() as cur:
        # Get unmatched organization_location
        cur.execute("""
            SELECT id, name, state, city, organization_type
            FROM organization_location
            WHERE id NOT IN (
                SELECT org_location_id FROM jurisdiction_crosswalk 
                WHERE org_location_id IS NOT NULL
            )
            AND name IS NOT NULL
            LIMIT 1000  -- Process in batches
        """)
        
        unmatched_orgs = cur.fetchall()
        logger.info(f"Found {len(unmatched_orgs)} unmatched organizations to fuzzy match")
        
        matches = []
        for org_id, org_name, state, city, org_type in unmatched_orgs:
            # Find potential matches in jurisdiction
            cur.execute("""
                SELECT id, name AS jurisdiction_name, state_code
                FROM jurisdiction
                WHERE state_code = %s
                LIMIT 100
            """, (state,))
            
            candidates = cur.fetchall()
            
            best_match = None
            best_score = 0.0
            
            for cand_id, cand_name, cand_state in candidates:
                score = fuzzy_match_score(org_name, cand_name)
                
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = (org_id, cand_id, org_name, state, city, org_type, score)
            
            if best_match:
                matches.append(best_match)
        
        if matches:
            execute_values(cur, """
                INSERT INTO jurisdiction_crosswalk 
                (org_location_id, details_search_id, primary_name, state_code, 
                 city, organization_type, match_method, match_confidence)
                VALUES %s
                ON CONFLICT DO NOTHING
            """, [(m[0], m[1], m[2], m[3], m[4], m[5], 'fuzzy_name', m[6]) for m in matches])
            
            conn.commit()
            logger.info(f"Matched {len(matches)} entities by fuzzy name")


def consolidate_to_master(conn):
    """
    Consolidate crosswalk into master_jurisdictions table.
    
    Create canonical records by aggregating all sources.
    """
    logger.info("Consolidating to master_jurisdictions...")
    
    with conn.cursor() as cur:
        cur.execute("TRUNCATE master_jurisdictions RESTART IDENTITY CASCADE")
        
        # Aggregate crosswalk data
        cur.execute("""
            WITH enriched_crosswalk AS (
                SELECT 
                    jc.*,
                    -- Get full state name from jurisdiction or use lookup
                    COALESCE(
                        js.state,
                        -- State code to name mapping
                        CASE jc.state_code
                            WHEN 'AL' THEN 'Alabama'
                            WHEN 'AK' THEN 'Alaska'
                            WHEN 'AZ' THEN 'Arizona'
                            WHEN 'AR' THEN 'Arkansas'
                            WHEN 'CA' THEN 'California'
                            WHEN 'CO' THEN 'Colorado'
                            WHEN 'CT' THEN 'Connecticut'
                            WHEN 'DE' THEN 'Delaware'
                            WHEN 'FL' THEN 'Florida'
                            WHEN 'GA' THEN 'Georgia'
                            WHEN 'HI' THEN 'Hawaii'
                            WHEN 'ID' THEN 'Idaho'
                            WHEN 'IL' THEN 'Illinois'
                            WHEN 'IN' THEN 'Indiana'
                            WHEN 'IA' THEN 'Iowa'
                            WHEN 'KS' THEN 'Kansas'
                            WHEN 'KY' THEN 'Kentucky'
                            WHEN 'LA' THEN 'Louisiana'
                            WHEN 'ME' THEN 'Maine'
                            WHEN 'MD' THEN 'Maryland'
                            WHEN 'MA' THEN 'Massachusetts'
                            WHEN 'MI' THEN 'Michigan'
                            WHEN 'MN' THEN 'Minnesota'
                            WHEN 'MS' THEN 'Mississippi'
                            WHEN 'MO' THEN 'Missouri'
                            WHEN 'MT' THEN 'Montana'
                            WHEN 'NE' THEN 'Nebraska'
                            WHEN 'NV' THEN 'Nevada'
                            WHEN 'NH' THEN 'New Hampshire'
                            WHEN 'NJ' THEN 'New Jersey'
                            WHEN 'NM' THEN 'New Mexico'
                            WHEN 'NY' THEN 'New York'
                            WHEN 'NC' THEN 'North Carolina'
                            WHEN 'ND' THEN 'North Dakota'
                            WHEN 'OH' THEN 'Ohio'
                            WHEN 'OK' THEN 'Oklahoma'
                            WHEN 'OR' THEN 'Oregon'
                            WHEN 'PA' THEN 'Pennsylvania'
                            WHEN 'RI' THEN 'Rhode Island'
                            WHEN 'SC' THEN 'South Carolina'
                            WHEN 'SD' THEN 'South Dakota'
                            WHEN 'TN' THEN 'Tennessee'
                            WHEN 'TX' THEN 'Texas'
                            WHEN 'UT' THEN 'Utah'
                            WHEN 'VT' THEN 'Vermont'
                            WHEN 'VA' THEN 'Virginia'
                            WHEN 'WA' THEN 'Washington'
                            WHEN 'WV' THEN 'West Virginia'
                            WHEN 'WI' THEN 'Wisconsin'
                            WHEN 'WY' THEN 'Wyoming'
                            WHEN 'DC' THEN 'District of Columbia'
                            WHEN 'PR' THEN 'Puerto Rico'
                            ELSE jc.state_code
                        END
                    ) as full_state_name
                FROM jurisdiction_crosswalk jc
                LEFT JOIN jurisdiction js ON jc.search_id = js.id
            )
            INSERT INTO master_jurisdictions 
            (nces_id, fips_code, geoid, canonical_name, state_code, state, 
             county, city, primary_type, source_count, data_completeness_score)
            SELECT 
                MAX(nces_id) as nces_id,
                MAX(fips_code) as fips_code,
                MAX(geoid) as geoid,
                primary_name as canonical_name,
                state_code,
                MAX(full_state_name) as state,
                MAX(county) as county,
                MAX(city) as city,
                COALESCE(jurisdiction_type, organization_type) as primary_type,
                COUNT(*) as source_count,
                CASE 
                    WHEN COUNT(*) >= 3 THEN 1.0
                    WHEN COUNT(*) = 2 THEN 0.75
                    ELSE 0.5
                END as data_completeness_score
            FROM enriched_crosswalk
            WHERE primary_name IS NOT NULL AND state_code IS NOT NULL
            GROUP BY 
                primary_name,
                state_code,
                COALESCE(jurisdiction_type, organization_type)
            ON CONFLICT (canonical_name, state_code, primary_type) DO UPDATE SET
                source_count = EXCLUDED.source_count,
                updated_at = NOW()
        """)
        
        count = cur.rowcount
        
        # Update crosswalk with master IDs
        cur.execute("""
            UPDATE jurisdiction_crosswalk jc
            SET master_jurisdiction_id = mj.id
            FROM master_jurisdictions mj
            WHERE (
                (jc.nces_id IS NOT NULL AND jc.nces_id = mj.nces_id)
                OR (jc.fips_code IS NOT NULL AND jc.fips_code = mj.fips_code)
                OR (jc.geoid IS NOT NULL AND jc.geoid = mj.geoid)
                OR (jc.primary_name = mj.canonical_name AND jc.state_code = mj.state_code)
            )
        """)
        
        conn.commit()
        logger.success(f"✅ Created {count:,} master jurisdiction records")


def generate_match_report(conn):
    """
    Generate matching statistics report.
    """
    logger.info("\n" + "="*80)
    logger.info("MASTER DATA MATCHING REPORT")
    logger.info("="*80)
    
    with conn.cursor() as cur:
        # Total counts
        cur.execute("SELECT COUNT(*) FROM organization_location")
        org_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM jurisdictions_wikidata")
        wiki_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM jurisdiction")
        search_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM jurisdiction")
        details_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM domain_registry")
        domain_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM jurisdiction_crosswalk")
        crosswalk_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM master_jurisdictions")
        master_count = cur.fetchone()[0]
        
        logger.info(f"\nSource Counts:")
        logger.info(f"  organization_location: {org_count:,}")
        logger.info(f"  jurisdictions_wikidata: {wiki_count:,}")
        logger.info(f"  jurisdiction: {search_count:,}")
        logger.info(f"  jurisdiction: {details_count:,}")
        
        logger.info(f"\nMatching Results:")
        logger.info(f"  Unique domains: {domain_count:,}")
        logger.info(f"  Crosswalk entries: {crosswalk_count:,}")
        logger.info(f"  Master jurisdictions: {master_count:,}")
        
        # Match method breakdown
        cur.execute("""
            SELECT match_method, COUNT(*), 
                   AVG(match_confidence)::DECIMAL(3,2) as avg_confidence
            FROM jurisdiction_crosswalk
            GROUP BY match_method
            ORDER BY COUNT(*) DESC
        """)
        
        logger.info(f"\nMatch Method Breakdown:")
        for method, count, conf in cur.fetchall():
            logger.info(f"  {method}: {count:,} (avg confidence: {conf})")
        
        # Coverage by organization type
        cur.execute("""
            SELECT 
                ol.organization_type,
                COUNT(*) as total,
                COUNT(jc.id) as matched,
                ROUND(100.0 * COUNT(jc.id) / COUNT(*), 2) as match_rate
            FROM organization_location ol
            LEFT JOIN jurisdiction_crosswalk jc ON ol.id = jc.org_location_id
            GROUP BY ol.organization_type
            ORDER BY total DESC
        """)
        
        logger.info(f"\nMatch Rate by Organization Type:")
        for org_type, total, matched, rate in cur.fetchall():
            logger.info(f"  {org_type}: {matched:,}/{total:,} ({rate}%)")


def main():
    """
    Execute master data management workflow.
    """
    logger.info("="*80)
    logger.info("Master Data Management: Jurisdiction Consolidation")
    logger.info("="*80)
    
    conn = get_connection()
    
    try:
        # 1. Create master tables
        create_master_tables(conn)
        
        # 2. Populate domain registry
        populate_domain_registry(conn)
        
        # 3. Build crosswalk using various matching strategies
        # ID-based matching (most reliable)
        build_crosswalk_by_nces(conn)
        build_crosswalk_by_geoid(conn)
        build_crosswalk_by_normalized_name(conn)  # Handles "Appling" vs "Appling CDP"
        
        # Phone matching (reliable unique identifier)
        build_crosswalk_by_phone(conn)  # Match by normalized phone number
        
        # City+State geographic matching
        build_crosswalk_wikidata_to_details_by_city(conn)  # Wikidata → Details by city
        build_crosswalk_by_city_proximity(conn)  # OrgLoc → Wikidata/Details by city
        
        # Geographic proximity matching (NEW - for stragglers within 1 mile)
        build_crosswalk_by_proximity(conn)  # Match unmatched records by lat/lon proximity
        
        # Domain-based matching (leveraging websites/URLs)
        build_crosswalk_by_domain(conn)  # Cross-source domain collisions
        build_crosswalk_orgloc_to_wikidata_by_domain(conn)  # Orgloc → Wikidata
        build_crosswalk_orgloc_to_details_by_domain(conn)   # Orgloc → Details
        
        # Name+Geography matching (using organizations as bridge)
        build_crosswalk_orgloc_to_search(conn)  # Orgloc → Search by name+state+type
        
        # Fuzzy matching (optional: slower, catches edge cases)
        # build_crosswalk_by_fuzzy_name(conn)
        
        # 4. Consolidate to master
        consolidate_to_master(conn)
        
        # 5. Generate report
        generate_match_report(conn)
        
        logger.success("\n✅ Master data management complete!")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
