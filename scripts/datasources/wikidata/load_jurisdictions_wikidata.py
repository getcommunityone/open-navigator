#!/usr/bin/env python3
"""
Load Jurisdictions from WikiData

Queries WikiData for all cities, counties, school districts, and states,
populating a jurisdictions_wikidata table with official data including:
- Official websites
- YouTube channels
- Social media (Facebook, Twitter)
- Population
- Geographic coordinates

This serves as a validation source for channel quality and provides
authoritative jurisdiction metadata.

Usage:
    # Load all dev states
    python scripts/datasources/wikidata/load_jurisdictions_wikidata.py --states AL,GA,IN,MA,WA,WI
    
    # Load specific state
    python scripts/datasources/wikidata/load_jurisdictions_wikidata.py --states AL
    
    # Load all jurisdiction types
    python scripts/datasources/wikidata/load_jurisdictions_wikidata.py --states AL --types city,county,school_district,state
"""
import os
import sys
import argparse
import asyncio
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_batch
from loguru import logger
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from scripts.datasources.wikidata.wikidata_integration import WikidataQuery

load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')

# State mapping - includes WikiData Q-codes, FIPS codes, and county types
STATE_MAP = {
    "AL": {"name": "Alabama", "q_code": "Q173", "fips": "01", "county_type": "Q13410400"},
    "GA": {"name": "Georgia", "q_code": "Q1428", "fips": "13", "county_type": "Q13410428"},
    "IN": {"name": "Indiana", "q_code": "Q1415", "fips": "18", "county_type": "Q13414760"},
    "MA": {"name": "Massachusetts", "q_code": "Q771", "fips": "25", "county_type": "Q13410485"},
    "WA": {"name": "Washington", "q_code": "Q1223", "fips": "53", "county_type": "Q13415369"},  # Fixed: was Q13414759
    "WI": {"name": "Wisconsin", "q_code": "Q1537", "fips": "55", "county_type": "Q13414761"}
}

# WikiData Q-codes for jurisdiction types
JURISDICTION_TYPES = {
    "city": "Q515",  # City
    "town": "Q3957",  # Town/Municipality
    "county": "Q47168",  # County of the United States
    "school_district": "Q1455778",  # School district
    "state": "Q35657"  # State of the United States
}


class CheckpointManager:
    """Persist completed (state, type) pairs so interrupted runs can resume."""

    def __init__(self, checkpoint_file: str):
        self.path = Path(checkpoint_file)
        self._completed: set = set()
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self._completed = {tuple(x) for x in data.get("completed", [])}
                logger.info(f"Resuming from checkpoint: {len(self._completed)} tasks already done")
            except Exception:
                self._completed = set()

    def is_done(self, state: str, jtype: str) -> bool:
        return (state, jtype) in self._completed

    def mark_done(self, state: str, jtype: str):
        self._completed.add((state, jtype))
        self._save()

    def _save(self):
        self.path.write_text(json.dumps({
            "completed": [list(x) for x in self._completed],
            "last_updated": datetime.utcnow().isoformat(),
        }, indent=2))


class JurisdictionsWikiDataLoader:
    """Load jurisdiction data from WikiData into PostgreSQL."""
    
    def __init__(self, database_url: str):
        self.conn = psycopg2.connect(database_url)
        self.wikidata = WikidataQuery()
        
        # Create table
        self._create_table()
    
    def _create_table(self):
        """Create jurisdictions_wikidata table."""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jurisdictions_wikidata (
                    id SERIAL PRIMARY KEY,
                    
                    -- Identifiers
                    wikidata_id VARCHAR(20) UNIQUE NOT NULL,
                    jurisdiction_id VARCHAR(50),  -- Link to jurisdictions_details_search
                    jurisdiction_id_type VARCHAR(50),
                    jurisdiction_name VARCHAR(200) NOT NULL,
                    state_code VARCHAR(2) NOT NULL,
                    state VARCHAR(50) NOT NULL,
                    jurisdiction_type VARCHAR(50) NOT NULL,  -- city, county, school_district, state
                    
                    -- Official links
                    official_website TEXT,
                    official_image_url TEXT,
                    locator_map_image TEXT,
                    page_banner_image TEXT,
                    youtube_channel_id VARCHAR(50),
                    youtube_channel_url TEXT,
                    facebook_username VARCHAR(100),
                    facebook_url TEXT,
                    twitter_username VARCHAR(100),
                    twitter_url TEXT,
                    
                    -- Demographics
                    population INTEGER,
                    area_sq_km FLOAT,
                    per_capita_income INTEGER,
                    number_of_households DOUBLE PRECISION,
                    median_age DOUBLE PRECISION,
                    
                    -- Geographic
                    latitude FLOAT,
                    longitude FLOAT,

                    -- Standard identifiers for joins
                    fips_code VARCHAR(20),
                    gnis_id VARCHAR(20),
                    nces_id VARCHAR(20),
                    geonames_id VARCHAR(20),
                    geoid VARCHAR(20),

                    -- Additional metadata
                    head_of_government VARCHAR(255),
                    head_of_government_position VARCHAR(255),
                    head_of_government_start_time TIMESTAMP,
                    postal_codes JSONB,
                    local_dialing_code VARCHAR(50),
                    google_maps_customer_id VARCHAR(50),
                    language_of_work_or_name VARCHAR(100),
                    time_zone VARCHAR(255),
                    ballotpedia_id VARCHAR(255),
                    tripadvisor_id VARCHAR(255),
                    subreddit VARCHAR(255),
                    
                    -- Metadata
                    confidence_score FLOAT DEFAULT 1.0,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                );
            """)

            # Backward-compatible adds for existing tables created with older schema
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS jurisdiction_id_type VARCHAR(50);")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS official_image_url TEXT;")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS locator_map_image TEXT;")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS page_banner_image TEXT;")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS per_capita_income INTEGER;")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS number_of_households DOUBLE PRECISION;")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS median_age DOUBLE PRECISION;")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS fips_code VARCHAR(20);")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS gnis_id VARCHAR(20);")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS nces_id VARCHAR(20);")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS geonames_id VARCHAR(20);")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS geoid VARCHAR(20);")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS head_of_government VARCHAR(255);")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS head_of_government_position VARCHAR(255);")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS head_of_government_start_time TIMESTAMP;")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS postal_codes JSONB;")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS local_dialing_code VARCHAR(50);")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS google_maps_customer_id VARCHAR(50);")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS language_of_work_or_name VARCHAR(100);")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS time_zone VARCHAR(255);")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS ballotpedia_id VARCHAR(255);")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS tripadvisor_id VARCHAR(255);")
            cursor.execute("ALTER TABLE jurisdictions_wikidata ADD COLUMN IF NOT EXISTS subreddit VARCHAR(255);")
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wikidata_state ON jurisdictions_wikidata(state_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wikidata_type ON jurisdictions_wikidata(jurisdiction_type);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wikidata_youtube ON jurisdictions_wikidata(youtube_channel_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wikidata_jurisdiction_id ON jurisdictions_wikidata(jurisdiction_id);")
            
            self.conn.commit()
            logger.success("✓ Created jurisdictions_wikidata table")
            
        except Exception as e:
            self.conn.rollback()
            logger.warning(f"Table creation note: {e}")
        finally:
            cursor.close()
    
    async def query_all_jurisdictions_in_state(self, state_code: str, types: List[str]) -> List[Dict]:
        """Query WikiData for all jurisdiction types in a state using optimized two-pronged approach."""
        state_info = STATE_MAP.get(state_code)
        if not state_info:
            logger.error(f"Unknown state code: {state_code}")
            return []
        
        state_name = state_info["name"]
        state_q_code = state_info["q_code"]
        
        # Build type filters
        city_types = []
        county_types = []
        school_types = []
        
        if 'city' in types or 'town' in types:
            city_types = [JURISDICTION_TYPES['city'], JURISDICTION_TYPES['town']]
        
        if 'county' in types:
            county_types = [JURISDICTION_TYPES['county']]
        
        if 'school_district' in types:
            school_types = [JURISDICTION_TYPES['school_district']]
        
        all_jurisdictions = []
        
        # Query cities/towns separately with optimized approach
        if city_types:
            city_jurisdictions = await self._query_cities_in_state(state_code, state_q_code, state_name)
            all_jurisdictions.extend(city_jurisdictions)
        
        # Query counties separately
        if county_types:
            county_jurisdictions = await self._query_counties_in_state(state_code, state_q_code, state_name)
            all_jurisdictions.extend(county_jurisdictions)
        
        # Query school districts separately
        if school_types:
            school_jurisdictions = await self._query_schools_in_state(state_code, state_q_code, state_name)
            all_jurisdictions.extend(school_jurisdictions)
        
        logger.success(f"✓ Found {len(all_jurisdictions)} jurisdictions in {state_name}")
        return all_jurisdictions
    
    async def _query_cities_in_state(self, state_code: str, state_q_code: str, state_name: str) -> List[Dict]:
        """Query cities/towns/settlements in a state.

        Wikidata does not consistently model US municipalities strictly as `instance of city (Q515)`.
        This query broadens to common settlement/municipality types and constrains to US places
        that have at least one of (FIPS place code, GNIS ID) so results are joinable downstream.
        """
        query = f"""
        SELECT DISTINCT 
            ?item ?itemLabel ?website ?population ?area
            ?facebook ?twitter ?youtube ?fips ?gnis ?nces ?image ?banner ?locatorMap
            ?dialingCode ?googleMapsCustomerId ?households ?medianAge ?languageLabel
            ?lat ?lon
            ?headOfGov ?headOfGovLabel ?positionLabel
            ?headStart ?postalCode ?perCapitaIncome ?timeZone ?timeZoneLabel
            ?ballotpediaId ?tripadvisorId ?subreddit
            ?geonamesId
        WHERE {{
          # Enumerate types explicitly; direct wdt:P31 is much faster than
          # wdt:P31/wdt:P279* (full subclass traversal).
          VALUES ?placeType {{
            wd:Q515       # city
            wd:Q3957      # town
            wd:Q15284     # municipality
            wd:Q486972    # human settlement
            wd:Q493522    # census-designated place
            wd:Q1115575   # city with county status
            wd:Q1549591   # big city
            wd:Q15222645  # unincorporated community
            wd:Q2989398   # populated place in the United States
            wd:Q1426695   # township (United States)
          }}
          ?item wdt:P31 ?placeType .

          # Within state (transitive - includes places in counties)
          ?item wdt:P131+ wd:{state_q_code} .

          # United States
          ?item wdt:P17 wd:Q30 .
          
          OPTIONAL {{ ?item wdt:P856 ?website . }}
          OPTIONAL {{ ?item wdt:P1082 ?population . }}
          OPTIONAL {{ ?item wdt:P2046 ?area . }}
          OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
          OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
          OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
          OPTIONAL {{ ?item wdt:P882 ?fips . }}
          OPTIONAL {{ ?item wdt:P590 ?gnis . }}
          OPTIONAL {{ ?item wdt:P6545 ?nces . }}
          OPTIONAL {{ ?item wdt:P18 ?image . }}
          OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}
          OPTIONAL {{ ?item wdt:P948 ?banner . }}
          OPTIONAL {{ ?item wdt:P1566 ?geonamesId . }}
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLatitude ?lat . }}
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLongitude ?lon . }}
          OPTIONAL {{ ?item wdt:P473 ?dialingCode . }}
          OPTIONAL {{ ?item wdt:P3749 ?googleMapsCustomerId . }}
          OPTIONAL {{ ?item wdt:P1538 ?households . }}
          OPTIONAL {{ ?item wdt:P1310 ?medianAge . }}
          OPTIONAL {{ ?item wdt:P407 ?language . }}

          # Require at least one joinable identifier
          FILTER(BOUND(?fips) || BOUND(?gnis))
          
          # Head of government
          OPTIONAL {{ 
            {{
              SELECT ?headOfGov ?headStart WHERE {{
                ?item p:P6 ?headStmt .
                ?headStmt ps:P6 ?headOfGov .
                OPTIONAL {{ ?headStmt pq:P580 ?headStart . }}
                FILTER(BOUND(?headStart))
              }}
              ORDER BY DESC(?headStart)
              LIMIT 1
            }}
            OPTIONAL {{ ?headOfGov wdt:P39 ?position . }}
          }}
          
          # Additional metadata
          OPTIONAL {{ ?item wdt:P281 ?postalCode . }}
          OPTIONAL {{ ?item wdt:P3529 ?perCapitaIncome . }}
          OPTIONAL {{ ?item wdt:P421 ?timeZone . }}
          OPTIONAL {{ ?item wdt:P2390 ?ballotpediaId . }}
          OPTIONAL {{ ?item wdt:P3134 ?tripadvisorId . }}
          OPTIONAL {{ ?item wdt:P3984 ?subreddit . }}
          
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 2000
        """
        
        logger.info(f"Querying WikiData for cities in {state_name}...")
        try:
            results = await self.wikidata.execute_sparql(query)
        except Exception as e:
            logger.warning(f"City query failed: {e}")
            results = []
        
        jurisdictions = self._parse_jurisdiction_results(results, state_code, state_name, 'city')
        logger.info(f"  Found {len(jurisdictions)} cities")
        return jurisdictions
    
    async def _query_counties_in_state(self, state_code: str, state_q_code: str, state_name: str) -> List[Dict]:
        """Query counties using state-specific AND generic county types to catch all counties."""
        state_info = STATE_MAP.get(state_code)
        if not state_info or not state_info.get("county_type"):
            logger.warning(f"No county type defined for {state_name}")
            return []
        
        county_type_q = state_info["county_type"]
        
        query = f"""
        SELECT DISTINCT 
            ?item ?itemLabel ?website ?population ?area
            ?facebook ?twitter ?youtube ?fips ?gnis ?nces ?image ?banner ?locatorMap
            ?dialingCode ?googleMapsCustomerId ?households ?medianAge ?languageLabel
            ?lat ?lon
            ?headOfGov ?headOfGovLabel ?positionLabel
            ?headStart ?postalCode ?perCapitaIncome ?timeZone ?timeZoneLabel
            ?ballotpediaId ?tripadvisorId ?subreddit
            ?geonamesId
        WHERE {{
          # County must be instance of generic or state-specific county type
          VALUES ?countyType {{ wd:{county_type_q} wd:Q47168 }}
          ?item wdt:P31 ?countyType .
          
          # Must be located in this state
          ?item wdt:P131+ wd:{state_q_code} .
          
          OPTIONAL {{ ?item wdt:P856 ?website . }}
          OPTIONAL {{ ?item wdt:P1082 ?population . }}
          OPTIONAL {{ ?item wdt:P2046 ?area . }}
          OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
          OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
          OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
          OPTIONAL {{ ?item wdt:P882 ?fips . }}
          OPTIONAL {{ ?item wdt:P590 ?gnis . }}
          OPTIONAL {{ ?item wdt:P6545 ?nces . }}
          OPTIONAL {{ ?item wdt:P18 ?image . }}
          OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}
          OPTIONAL {{ ?item wdt:P948 ?banner . }}
          OPTIONAL {{ ?item wdt:P1566 ?geonamesId . }}
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLatitude ?lat . }}
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLongitude ?lon . }}
          OPTIONAL {{ ?item wdt:P473 ?dialingCode . }}
          OPTIONAL {{ ?item wdt:P3749 ?googleMapsCustomerId . }}
          OPTIONAL {{ ?item wdt:P1538 ?households . }}
          OPTIONAL {{ ?item wdt:P1310 ?medianAge . }}
          OPTIONAL {{ ?item wdt:P407 ?language . }}
          
          # Head of government
          OPTIONAL {{ 
            {{
              SELECT ?headOfGov ?headStart WHERE {{
                ?item p:P6 ?headStmt .
                ?headStmt ps:P6 ?headOfGov .
                OPTIONAL {{ ?headStmt pq:P580 ?headStart . }}
                FILTER(BOUND(?headStart))
              }}
              ORDER BY DESC(?headStart)
              LIMIT 1
            }}
            OPTIONAL {{ ?headOfGov wdt:P39 ?position . }}
          }}
          
          # Additional metadata
          OPTIONAL {{ ?item wdt:P281 ?postalCode . }}
          OPTIONAL {{ ?item wdt:P3529 ?perCapitaIncome . }}
          OPTIONAL {{ ?item wdt:P421 ?timeZone . }}
          OPTIONAL {{ ?item wdt:P2390 ?ballotpediaId . }}
          OPTIONAL {{ ?item wdt:P3134 ?tripadvisorId . }}
          OPTIONAL {{ ?item wdt:P3984 ?subreddit . }}
          
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
        }}
        LIMIT 500
        """
        
        logger.info(f"Querying WikiData for counties in {state_name}...")
        results = await self.wikidata.execute_sparql(query)
        
        jurisdictions = self._parse_jurisdiction_results(results, state_code, state_name, 'county')
        logger.info(f"  Found {len(jurisdictions)} counties")
        return jurisdictions
    
    async def _query_schools_in_state(self, state_code: str, state_q_code: str, state_name: str) -> List[Dict]:
        """Query school districts - use transitive since they can be nested."""
        query = f"""
        SELECT DISTINCT 
            ?item ?itemLabel ?website ?population ?area
            ?facebook ?twitter ?youtube ?fips ?gnis ?nces ?image ?banner ?locatorMap
            ?dialingCode ?googleMapsCustomerId ?households ?medianAge ?languageLabel
            ?lat ?lon
            ?headOfGov ?headOfGovLabel ?positionLabel
            ?headStart ?postalCode ?perCapitaIncome ?timeZone ?timeZoneLabel
            ?ballotpediaId ?tripadvisorId ?subreddit
            ?geonamesId
        WHERE {{
          ?item wdt:P31 wd:Q1455778 .  # School district
          ?item wdt:P131+ wd:{state_q_code} .
          
          OPTIONAL {{ ?item wdt:P856 ?website . }}
          OPTIONAL {{ ?item wdt:P1082 ?population . }}
          OPTIONAL {{ ?item wdt:P2046 ?area . }}
          OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
          OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
          OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
          OPTIONAL {{ ?item wdt:P882 ?fips . }}
          OPTIONAL {{ ?item wdt:P590 ?gnis . }}
          OPTIONAL {{ ?item wdt:P6545 ?nces . }}
          OPTIONAL {{ ?item wdt:P18 ?image . }}
          OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}
          OPTIONAL {{ ?item wdt:P948 ?banner . }}
          OPTIONAL {{ ?item wdt:P1566 ?geonamesId . }}
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLatitude ?lat . }}
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLongitude ?lon . }}
          OPTIONAL {{ ?item wdt:P473 ?dialingCode . }}
          OPTIONAL {{ ?item wdt:P3749 ?googleMapsCustomerId . }}
          OPTIONAL {{ ?item wdt:P1538 ?households . }}
          OPTIONAL {{ ?item wdt:P1310 ?medianAge . }}
          OPTIONAL {{ ?item wdt:P407 ?language . }}
          
          # Head of government/superintendent
          OPTIONAL {{ 
            {{
              SELECT ?headOfGov ?headStart WHERE {{
                ?item p:P6 ?headStmt .
                ?headStmt ps:P6 ?headOfGov .
                OPTIONAL {{ ?headStmt pq:P580 ?headStart . }}
                FILTER(BOUND(?headStart))
              }}
              ORDER BY DESC(?headStart)
              LIMIT 1
            }}
            OPTIONAL {{ ?headOfGov wdt:P39 ?position . }}
          }}
          
          # Additional metadata
          OPTIONAL {{ ?item wdt:P281 ?postalCode . }}
          OPTIONAL {{ ?item wdt:P3529 ?perCapitaIncome . }}
          OPTIONAL {{ ?item wdt:P421 ?timeZone . }}
          OPTIONAL {{ ?item wdt:P2390 ?ballotpediaId . }}
          OPTIONAL {{ ?item wdt:P3134 ?tripadvisorId . }}
          OPTIONAL {{ ?item wdt:P3984 ?subreddit . }}
          
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
        }}
        LIMIT 500
        """
        
        logger.info(f"Querying WikiData for school districts in {state_name}...")
        results = await self.wikidata.execute_sparql(query)
        
        jurisdictions = self._parse_jurisdiction_results(results, state_code, state_name, 'school_district')
        logger.info(f"  Found {len(jurisdictions)} school districts")
        return jurisdictions
    
    def _parse_jurisdiction_results(self, results: List[Dict], state_code: str, state_name: str, jurisdiction_type: str) -> List[Dict]:
        """Parse SPARQL results into jurisdiction records."""
        def _safe_float(v: Optional[str]) -> Optional[float]:
            if v is None:
                return None
            try:
                return float(v)
            except Exception:
                return None

        jurisdictions = []
        for result in results:
            wikidata_id = result.get("item", "").split("/")[-1]
            youtube_channel_id = result.get("youtube")
            
            # Extract US government IDs
            fips_code = result.get("fips")
            gnis_id = result.get("gnis")
            nces_id = result.get("nces")
            geonames_id = result.get("geonamesId")
            
            # Extract official image URL
            image_url = result.get("image")
            locator_map_url = result.get("locatorMap")
            banner_url = result.get("banner")
            
            # Build jurisdiction_id and jurisdiction_id_type to match our database format
            jurisdiction_id = None
            jurisdiction_id_type = None
            geoid = None
            
            if jurisdiction_type == 'county' and fips_code:
                # Format: county_{FIPS} (e.g., county_01001)
                jurisdiction_id = f"county_{fips_code}"
                jurisdiction_id_type = 'county_fips'
                # GEOID for counties is the 5-digit FIPS code (state + county)
                geoid = fips_code
            elif jurisdiction_type == 'school_district' and nces_id:
                # Format: school_{NCES} (e.g., school_0100001)
                jurisdiction_id = f"school_{nces_id}"
                jurisdiction_id_type = 'nces_id'
                # GEOID for school districts is the NCES ID
                geoid = nces_id
            elif fips_code:
                # City with FIPS place code
                geoid = fips_code
            
            if gnis_id and not jurisdiction_id:
                # Format: {GNIS_ID} (e.g., 173056)
                jurisdiction_id = gnis_id
                jurisdiction_id_type = 'gnis_id'
            
            # Extract head of government info
            head_of_gov = result.get("headOfGovLabel")
            head_of_gov_position = result.get("positionLabel")
            head_start = result.get("headStart")
            
            # Extract postal codes (can be multiple in WikiData)
            postal_code = result.get("postalCode")
            postal_codes = json.dumps([postal_code]) if postal_code else None
            
            # Extract additional metadata
            per_capita_income = int(result.get("perCapitaIncome")) if result.get("perCapitaIncome") else None
            time_zone = result.get("timeZoneLabel") or result.get("timeZone")
            ballotpedia_id = result.get("ballotpediaId")
            tripadvisor_id = result.get("tripadvisorId")
            subreddit = result.get("subreddit")
            dialing_code = result.get("dialingCode")
            google_maps_customer_id = result.get("googleMapsCustomerId")
            number_of_households = _safe_float(result.get("households"))
            median_age = _safe_float(result.get("medianAge"))
            language_of_work_or_name = result.get("languageLabel")
            
            jurisdictions.append({
                'wikidata_id': wikidata_id,
                'jurisdiction_id': jurisdiction_id,
                'jurisdiction_id_type': jurisdiction_id_type,
                'jurisdiction_name': result.get("itemLabel", ""),
                'state_code': state_code,
                'state': state_name,
                'jurisdiction_type': jurisdiction_type,
                'official_website': result.get("website"),
                'official_image_url': image_url,
                'page_banner_image': banner_url,
                'youtube_channel_id': youtube_channel_id,
                'youtube_channel_url': f"https://www.youtube.com/channel/{youtube_channel_id}" if youtube_channel_id else None,
                'facebook_username': result.get("facebook"),
                'facebook_url': f"https://www.facebook.com/{result.get('facebook')}" if result.get('facebook') else None,
                'twitter_username': result.get("twitter"),
                'twitter_url': f"https://twitter.com/{result.get('twitter')}" if result.get('twitter') else None,
                'population': int(result.get("population")) if result.get("population") else None,
                'area_sq_km': float(result.get("area")) if result.get("area") else None,
                'number_of_households': number_of_households,
                'median_age': median_age,
                'latitude': float(result.get("lat")) if result.get("lat") else None,
                'longitude': float(result.get("lon")) if result.get("lon") else None,
                'fips_code': fips_code,
                'gnis_id': gnis_id,
                'nces_id': nces_id,
                'geonames_id': geonames_id,
                'geoid': geoid,
                'locator_map_image': locator_map_url,
                'head_of_government': head_of_gov,
                'head_of_government_position': head_of_gov_position,
                'head_of_government_start_time': head_start,
                'postal_codes': postal_codes,
                'per_capita_income': per_capita_income,
                'local_dialing_code': dialing_code,
                'google_maps_customer_id': google_maps_customer_id,
                'language_of_work_or_name': language_of_work_or_name,
                'time_zone': time_zone,
                'ballotpedia_id': ballotpedia_id,
                'tripadvisor_id': tripadvisor_id,
                'subreddit': subreddit,
            })
        
        return jurisdictions
    
    async def query_state_info(self, state_code: str) -> List[Dict]:
        """Query WikiData for state government info."""
        state_info = STATE_MAP.get(state_code)
        if not state_info:
            return []
        
        state_name = state_info["name"]
        state_q_code = state_info["q_code"]
        
        query = f"""
        SELECT DISTINCT 
            ?item ?itemLabel ?website ?population ?area
            ?facebook ?twitter ?youtube ?fips ?image ?banner ?locatorMap
            ?dialingCode ?googleMapsCustomerId ?households ?medianAge ?languageLabel
            ?lat ?lon
            ?headOfGov ?headOfGovLabel ?positionLabel
            ?headStart ?postalCode ?perCapitaIncome ?timeZone ?timeZoneLabel
            ?ballotpediaId ?tripadvisorId ?subreddit
            ?geonamesId
        WHERE {{
          # Direct reference to the state
          BIND(wd:{state_q_code} AS ?item)
          
          OPTIONAL {{ ?item wdt:P856 ?website . }}
          OPTIONAL {{ ?item wdt:P1082 ?population . }}
          OPTIONAL {{ ?item wdt:P2046 ?area . }}
          OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
          OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
          OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
          OPTIONAL {{ ?item wdt:P882 ?fips . }}    # FIPS code
          OPTIONAL {{ ?item wdt:P18 ?image . }}    # Official image
          OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}  # Locator map image
          OPTIONAL {{ ?item wdt:P948 ?banner . }}
          OPTIONAL {{ ?item wdt:P1566 ?geonamesId . }} # GeoNames ID
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLatitude ?lat . }}
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLongitude ?lon . }}
          OPTIONAL {{ ?item wdt:P473 ?dialingCode . }}
          OPTIONAL {{ ?item wdt:P3749 ?googleMapsCustomerId . }}
          OPTIONAL {{ ?item wdt:P1538 ?households . }}
          OPTIONAL {{ ?item wdt:P1310 ?medianAge . }}
          OPTIONAL {{ ?item wdt:P407 ?language . }}
          
          # Head of government (Governor)
          OPTIONAL {{ 
            {{
              SELECT ?headOfGov ?headStart WHERE {{
                ?item p:P6 ?headStmt .
                ?headStmt ps:P6 ?headOfGov .
                OPTIONAL {{ ?headStmt pq:P580 ?headStart . }}
                # Restrict to governors (Wikidata can contain erroneous/alternate P6 statements)
                ?headOfGov wdt:P39 ?posHeld .
                ?posHeld wdt:P31/wdt:P279* wd:Q132176 .  # governor

                FILTER(BOUND(?headStart))
                FILTER(YEAR(?headStart) < 3000)
              }}
              ORDER BY DESC(?headStart)
              LIMIT 1
            }}
            OPTIONAL {{ ?headOfGov wdt:P39 ?position . }}
          }}
          
          # Additional metadata
          OPTIONAL {{ ?item wdt:P281 ?postalCode . }}
          OPTIONAL {{ ?item wdt:P3529 ?perCapitaIncome . }}
          OPTIONAL {{ ?item wdt:P421 ?timeZone . }}
          OPTIONAL {{ ?item wdt:P2390 ?ballotpediaId . }}
          OPTIONAL {{ ?item wdt:P3134 ?tripadvisorId . }}
          OPTIONAL {{ ?item wdt:P3984 ?subreddit . }}
          
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
        }}
        """
        
        logger.info(f"Querying WikiData for state: {state_name}...")
        results = await self.wikidata.execute_sparql(query)
        
        if not results:
            logger.warning(f"No WikiData entry found for {state_name}")
            return []
        
        result = results[0]
        youtube_channel_id = result.get("youtube")
        image_url = result.get("image")
        locator_map_url = result.get("locatorMap")
        banner_url = result.get("banner")
        geonames_id = result.get("geonamesId")
        
        # Use hardcoded FIPS code from STATE_MAP (WikiData doesn't have state FIPS codes)
        fips_code = state_info["fips"]
        
        # State jurisdiction_id: state_{FIPS} (e.g., state_01 for Alabama)
        jurisdiction_id = f"state_{fips_code}"
        jurisdiction_id_type = 'state_fips'
        
        # Extract head of government info (Governor)
        head_of_gov = result.get("headOfGovLabel")
        head_of_gov_position = result.get("positionLabel")
        head_start = result.get("headStart")
        
        # Extract postal codes (can be multiple)
        postal_code = result.get("postalCode")
        postal_codes = json.dumps([postal_code]) if postal_code else None
        
        # Extract additional metadata
        per_capita_income = int(result.get("perCapitaIncome")) if result.get("perCapitaIncome") else None
        time_zone = result.get("timeZoneLabel") or result.get("timeZone")
        ballotpedia_id = result.get("ballotpediaId")
        tripadvisor_id = result.get("tripadvisorId")
        subreddit = result.get("subreddit")
        dialing_code = result.get("dialingCode")
        google_maps_customer_id = result.get("googleMapsCustomerId")
        try:
            number_of_households = float(result.get("households")) if result.get("households") else None
        except Exception:
            number_of_households = None
        try:
            median_age = float(result.get("medianAge")) if result.get("medianAge") else None
        except Exception:
            median_age = None
        language_of_work_or_name = result.get("languageLabel")
        
        return [{
            'wikidata_id': state_q_code,
            'jurisdiction_id': jurisdiction_id,
            'jurisdiction_id_type': jurisdiction_id_type,
            'jurisdiction_name': state_name,
            'state_code': state_code,
            'state': state_name,
            'jurisdiction_type': 'state',
            'official_website': result.get("website"),
            'official_image_url': image_url,
            'page_banner_image': banner_url,
            'youtube_channel_id': youtube_channel_id,
            'youtube_channel_url': f"https://www.youtube.com/channel/{youtube_channel_id}" if youtube_channel_id else None,
            'facebook_username': result.get("facebook"),
            'facebook_url': f"https://www.facebook.com/{result.get('facebook')}" if result.get('facebook') else None,
            'twitter_username': result.get("twitter"),
            'twitter_url': f"https://twitter.com/{result.get('twitter')}" if result.get('twitter') else None,
            'population': int(result.get("population")) if result.get("population") else None,
            'area_sq_km': float(result.get("area")) if result.get("area") else None,
            'latitude': float(result.get("lat")) if result.get("lat") else None,
            'longitude': float(result.get("lon")) if result.get("lon") else None,
            'fips_code': fips_code,
            'gnis_id': None,
            'nces_id': None,
            'geonames_id': geonames_id,
            'geoid': fips_code,  # For states, GEOID is the 2-digit FIPS code
            'locator_map_image': locator_map_url,
            'head_of_government': head_of_gov,
            'head_of_government_position': head_of_gov_position,
            'head_of_government_start_time': head_start,
            'postal_codes': postal_codes,
            'per_capita_income': per_capita_income,
            'number_of_households': number_of_households,
            'median_age': median_age,
            'local_dialing_code': dialing_code,
            'google_maps_customer_id': google_maps_customer_id,
            'language_of_work_or_name': language_of_work_or_name,
            'time_zone': time_zone,
            'ballotpedia_id': ballotpedia_id,
            'tripadvisor_id': tripadvisor_id,
            'subreddit': subreddit,
        }]
    
    def insert_jurisdictions(self, jurisdictions: List[Dict]):
        """Insert jurisdictions into database."""
        if not jurisdictions:
            return
        
        cursor = self.conn.cursor()
        
        insert_query = """
            INSERT INTO jurisdictions_wikidata (
                wikidata_id, jurisdiction_id, jurisdiction_id_type, jurisdiction_name, state_code, state, jurisdiction_type,
                official_website, official_image_url, locator_map_image, page_banner_image,
                youtube_channel_id, youtube_channel_url,
                facebook_username, facebook_url, twitter_username, twitter_url,
                population, area_sq_km, per_capita_income, number_of_households, median_age, latitude, longitude,
                fips_code, gnis_id, nces_id, geonames_id, geoid,
                head_of_government, head_of_government_position, head_of_government_start_time,
                postal_codes, local_dialing_code, google_maps_customer_id, language_of_work_or_name, time_zone,
                ballotpedia_id, tripadvisor_id, subreddit,
                confidence_score, fetched_at
            ) VALUES (
                %(wikidata_id)s, %(jurisdiction_id)s, %(jurisdiction_id_type)s, %(jurisdiction_name)s, %(state_code)s, %(state)s, %(jurisdiction_type)s,
                %(official_website)s, %(official_image_url)s, %(locator_map_image)s, %(page_banner_image)s,
                %(youtube_channel_id)s, %(youtube_channel_url)s,
                %(facebook_username)s, %(facebook_url)s, %(twitter_username)s, %(twitter_url)s,
                %(population)s, %(area_sq_km)s, %(per_capita_income)s, %(number_of_households)s, %(median_age)s, %(latitude)s, %(longitude)s,
                %(fips_code)s, %(gnis_id)s, %(nces_id)s, %(geonames_id)s, %(geoid)s,
                %(head_of_government)s, %(head_of_government_position)s, %(head_of_government_start_time)s,
                %(postal_codes)s::jsonb, %(local_dialing_code)s, %(google_maps_customer_id)s, %(language_of_work_or_name)s, %(time_zone)s,
                %(ballotpedia_id)s, %(tripadvisor_id)s, %(subreddit)s,
                1.0, CURRENT_TIMESTAMP
            )
            ON CONFLICT (wikidata_id) DO UPDATE SET
                jurisdiction_id = COALESCE(EXCLUDED.jurisdiction_id, jurisdictions_wikidata.jurisdiction_id),
                jurisdiction_id_type = COALESCE(EXCLUDED.jurisdiction_id_type, jurisdictions_wikidata.jurisdiction_id_type),
                official_website = COALESCE(EXCLUDED.official_website, jurisdictions_wikidata.official_website),
                official_image_url = COALESCE(EXCLUDED.official_image_url, jurisdictions_wikidata.official_image_url),
                locator_map_image = COALESCE(EXCLUDED.locator_map_image, jurisdictions_wikidata.locator_map_image),
                page_banner_image = COALESCE(EXCLUDED.page_banner_image, jurisdictions_wikidata.page_banner_image),
                youtube_channel_id = COALESCE(EXCLUDED.youtube_channel_id, jurisdictions_wikidata.youtube_channel_id),
                youtube_channel_url = COALESCE(EXCLUDED.youtube_channel_url, jurisdictions_wikidata.youtube_channel_url),
                facebook_username = COALESCE(EXCLUDED.facebook_username, jurisdictions_wikidata.facebook_username),
                facebook_url = COALESCE(EXCLUDED.facebook_url, jurisdictions_wikidata.facebook_url),
                twitter_username = COALESCE(EXCLUDED.twitter_username, jurisdictions_wikidata.twitter_username),
                twitter_url = COALESCE(EXCLUDED.twitter_url, jurisdictions_wikidata.twitter_url),
                population = COALESCE(EXCLUDED.population, jurisdictions_wikidata.population),
                area_sq_km = COALESCE(EXCLUDED.area_sq_km, jurisdictions_wikidata.area_sq_km),
                per_capita_income = COALESCE(EXCLUDED.per_capita_income, jurisdictions_wikidata.per_capita_income),
                number_of_households = COALESCE(EXCLUDED.number_of_households, jurisdictions_wikidata.number_of_households),
                median_age = COALESCE(EXCLUDED.median_age, jurisdictions_wikidata.median_age),
                latitude = COALESCE(EXCLUDED.latitude, jurisdictions_wikidata.latitude),
                longitude = COALESCE(EXCLUDED.longitude, jurisdictions_wikidata.longitude),
                fips_code = COALESCE(EXCLUDED.fips_code, jurisdictions_wikidata.fips_code),
                gnis_id = COALESCE(EXCLUDED.gnis_id, jurisdictions_wikidata.gnis_id),
                nces_id = COALESCE(EXCLUDED.nces_id, jurisdictions_wikidata.nces_id),
                geonames_id = COALESCE(EXCLUDED.geonames_id, jurisdictions_wikidata.geonames_id),
                geoid = COALESCE(EXCLUDED.geoid, jurisdictions_wikidata.geoid),
                head_of_government = COALESCE(EXCLUDED.head_of_government, jurisdictions_wikidata.head_of_government),
                head_of_government_position = COALESCE(EXCLUDED.head_of_government_position, jurisdictions_wikidata.head_of_government_position),
                head_of_government_start_time = COALESCE(EXCLUDED.head_of_government_start_time, jurisdictions_wikidata.head_of_government_start_time),
                postal_codes = COALESCE(EXCLUDED.postal_codes, jurisdictions_wikidata.postal_codes),
                local_dialing_code = COALESCE(EXCLUDED.local_dialing_code, jurisdictions_wikidata.local_dialing_code),
                google_maps_customer_id = COALESCE(EXCLUDED.google_maps_customer_id, jurisdictions_wikidata.google_maps_customer_id),
                language_of_work_or_name = COALESCE(EXCLUDED.language_of_work_or_name, jurisdictions_wikidata.language_of_work_or_name),
                time_zone = COALESCE(EXCLUDED.time_zone, jurisdictions_wikidata.time_zone),
                ballotpedia_id = COALESCE(EXCLUDED.ballotpedia_id, jurisdictions_wikidata.ballotpedia_id),
                tripadvisor_id = COALESCE(EXCLUDED.tripadvisor_id, jurisdictions_wikidata.tripadvisor_id),
                subreddit = COALESCE(EXCLUDED.subreddit, jurisdictions_wikidata.subreddit),
                last_updated = CURRENT_TIMESTAMP
        """
        
        try:
            execute_batch(cursor, insert_query, jurisdictions, page_size=100)
            self.conn.commit()
            logger.success(f"✓ Inserted {len(jurisdictions)} jurisdictions")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error inserting jurisdictions: {e}")
            raise
        finally:
            cursor.close()
    
    async def load_state(self, state_code: str, types: List[str], checkpoint: Optional['CheckpointManager'] = None):
        """Load all jurisdiction types for a state."""
        state_info = STATE_MAP.get(state_code, {})
        state_name = state_info.get('name', state_code)
        state_q_code = state_info.get('q_code', '')

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"LOADING WIKIDATA FOR {state_name}")
        logger.info("=" * 80)

        all_jurisdictions = []

        # Determine ordered sub-queries, merging city/town into one task
        query_tasks = []
        if 'state' in types:
            query_tasks.append('state')
        if 'city' in types or 'town' in types:
            query_tasks.append('city')
        if 'county' in types:
            query_tasks.append('county')
        if 'school_district' in types:
            query_tasks.append('school_district')

        for task in query_tasks:
            if checkpoint and checkpoint.is_done(state_code, task):
                logger.info(f"  Skipping {task} for {state_code} (already completed)")
                continue

            if task == 'state':
                results = await self.query_state_info(state_code)
            elif task == 'city':
                results = await self._query_cities_in_state(state_code, state_q_code, state_name)
            elif task == 'county':
                results = await self._query_counties_in_state(state_code, state_q_code, state_name)
            elif task == 'school_district':
                results = await self._query_schools_in_state(state_code, state_q_code, state_name)
            else:
                continue

            all_jurisdictions.extend(results)
            if results:
                self.insert_jurisdictions(results)
            if checkpoint:
                checkpoint.mark_done(state_code, task)

        with_youtube = sum(1 for j in all_jurisdictions if j.get('youtube_channel_id'))
        with_website = sum(1 for j in all_jurisdictions if j.get('official_website'))

        logger.info("")
        logger.success(f"✓ Loaded {len(all_jurisdictions)} jurisdictions for {state_code}")
        logger.info(f"  With YouTube channels: {with_youtube}")
        logger.info(f"  With official websites: {with_website}")
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Load jurisdictions from WikiData')
    
    parser.add_argument(
        '--states',
        type=str,
        required=True,
        help='Comma-separated list of state codes (e.g., AL,MA,WI)'
    )
    
    parser.add_argument(
        '--types',
        type=str,
        default='city,county,state',
        help='Comma-separated jurisdiction types (default: city,county,state)'
    )

    parser.add_argument(
        '--checkpoint-file',
        type=str,
        default='.wikidata_checkpoint.json',
        help='Checkpoint file for resume support (default: .wikidata_checkpoint.json)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Ignore existing checkpoint and re-fetch everything'
    )

    args = parser.parse_args()

    # Parse states and types
    states = [s.strip().upper() for s in args.states.split(',')]
    types = [t.strip().lower() for t in args.types.split(',')]

    checkpoint = None if args.force else CheckpointManager(args.checkpoint_file)

    # Load data
    loader = JurisdictionsWikiDataLoader(DATABASE_URL)
    
    try:
        for state in states:
            await loader.load_state(state, types, checkpoint)
        
        # Final summary
        cursor = loader.conn.cursor()
        cursor.execute("""
            SELECT 
                jurisdiction_type,
                COUNT(*) as count,
                COUNT(*) FILTER (WHERE youtube_channel_id IS NOT NULL) as with_youtube,
                COUNT(*) FILTER (WHERE official_website IS NOT NULL) as with_website
            FROM jurisdictions_wikidata
            GROUP BY jurisdiction_type
            ORDER BY count DESC
        """)
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("FINAL SUMMARY")
        logger.info("=" * 80)
        
        for row in cursor.fetchall():
            jtype, count, youtube, website = row
            logger.info(f"{jtype:15s}: {count:4d} total, {youtube:3d} with YouTube, {website:3d} with website")
        
        cursor.close()
        
    finally:
        loader.close()


if __name__ == '__main__':
    asyncio.run(main())
