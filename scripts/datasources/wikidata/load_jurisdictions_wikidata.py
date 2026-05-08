#!/usr/bin/env python3
"""
Load Jurisdictions from WikiData

Queries WikiData for all cities, counties, school districts, and states,
and writes Wikidata metadata into these bronze tables:
- bronze.bronze_jurisdictions_states_wikidata
- bronze.bronze_jurisdictions_counties_wikidata
- bronze.bronze_jurisdictions_municipalities_wikidata
- bronze.bronze_jurisdictions_school_districts_wikidata

The legacy `public.jurisdictions_wikidata` table is deprecated and is no longer
created/used by this script.

Wikidata metadata includes:
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
        """Deprecated: we no longer create/use `public.jurisdictions_wikidata`."""
        return

    def _seed_wikidata_table(self, state_code: str, task: str) -> None:
        """Rebuild the per-type bronze *_wikidata table rows for one state from its base table."""
        mapping: dict[str, tuple[str, str, str]] = {
            "state": (
                "bronze.bronze_jurisdictions_states",
                "bronze.bronze_jurisdictions_states_wikidata",
                "geoid, usps, ansicode, name, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date",
            ),
            "county": (
                "bronze.bronze_jurisdictions_counties",
                "bronze.bronze_jurisdictions_counties_wikidata",
                "geoid, usps, ansicode, name, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date",
            ),
            # city task enriches municipalities
            "city": (
                "bronze.bronze_jurisdictions_municipalities",
                "bronze.bronze_jurisdictions_municipalities_wikidata",
                "geoid, usps, ansicode, name, lsad, funcstat, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date",
            ),
            "school_district": (
                "bronze.bronze_jurisdictions_school_districts",
                "bronze.bronze_jurisdictions_school_districts_wikidata",
                "geoid, usps, name, lograde, higrade, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date",
            ),
        }
        if task not in mapping:
            raise ValueError(f"Unknown seed task: {task}")

        base_table, wikidata_table, cols = mapping[task]
        cur = self.conn.cursor()
        try:
            cur.execute(f"DELETE FROM {wikidata_table} WHERE usps = %s", (state_code,))
            cur.execute(
                f"""
                INSERT INTO {wikidata_table} ({cols})
                SELECT {cols}
                FROM {base_table}
                WHERE usps = %s
                """,
                (state_code,),
            )
            self.conn.commit()
        finally:
            cur.close()

    def _apply_wikidata_updates(self, task: str, jurisdictions: List[Dict]) -> None:
        """Update the appropriate bronze *_wikidata table based on loader task."""
        if not jurisdictions:
            return

        if task == "county":
            table = "bronze.bronze_jurisdictions_counties_wikidata"
            key_field = "fips_code"
            extra_cols = {
                "wikidata_fips_code": "fips_code",
                "wikidata_geoid": "geoid",
            }
        elif task == "city":
            table = "bronze.bronze_jurisdictions_municipalities_wikidata"
            key_field = "fips_code"
            extra_cols = {
                "wikidata_fips_code": "fips_code",
                "wikidata_gnis_id": "gnis_id",
                "wikidata_geoid": "geoid",
            }
        elif task == "school_district":
            table = "bronze.bronze_jurisdictions_school_districts_wikidata"
            key_field = "nces_id"
            extra_cols = {
                "wikidata_nces_id": "nces_id",
                "wikidata_geoid": "geoid",
            }
        elif task == "state":
            table = "bronze.bronze_jurisdictions_states_wikidata"
            key_field = "fips_code"
            extra_cols = {
                "wikidata_fips_code": "fips_code",
                "wikidata_geoid": "geoid",
            }
        else:
            raise ValueError(f"Unknown update task: {task}")

        set_parts = [
            "wikidata_id = %(wikidata_id)s",
            "official_website = %(official_website)s",
            "official_image_url = %(official_image_url)s",
            "page_banner_image = %(page_banner_image)s",
            "locator_map_image = %(locator_map_image)s",
            "youtube_channel_id = %(youtube_channel_id)s",
            "youtube_channel_url = %(youtube_channel_url)s",
            "facebook_username = %(facebook_username)s",
            "facebook_url = %(facebook_url)s",
            "twitter_username = %(twitter_username)s",
            "twitter_url = %(twitter_url)s",
            "population = %(population)s",
            "area_sq_km = %(area_sq_km)s",
            "per_capita_income = %(per_capita_income)s",
            "number_of_households = %(number_of_households)s",
            "median_age = %(median_age)s",
            "time_zone = %(time_zone)s",
            "local_dialing_code = %(local_dialing_code)s",
            "google_maps_customer_id = %(google_maps_customer_id)s",
            "language_of_work_or_name = %(language_of_work_or_name)s",
            "head_of_government = %(head_of_government)s",
            "head_of_government_position = %(head_of_government_position)s",
            "head_of_government_start_time = %(head_of_government_start_time)s",
            "postal_codes = %(postal_codes)s::jsonb",
            "latitude = %(latitude)s",
            "longitude = %(longitude)s",
            "wikidata_fetched_at = CURRENT_TIMESTAMP",
            "wikidata_last_updated = CURRENT_TIMESTAMP",
        ]

        # State table has additional descriptive metadata columns
        if task == "state":
            set_parts.extend(
                [
                    "jurisdiction_label = %(jurisdiction_label)s",
                    "jurisdiction_description = %(jurisdiction_description)s",
                    "jurisdiction_aliases = %(jurisdiction_aliases)s::jsonb",
                    "native_label = %(native_label)s",
                    "nickname = %(nickname)s::jsonb",
                    "short_name = %(short_name)s::jsonb",
                    "demonym = %(demonym)s::jsonb",
                    "official_language = %(official_language)s::jsonb",
                    "motto = %(motto)s",
                    "anthem = %(anthem)s::jsonb",
                    "inception_date = %(inception_date)s",
                    "capital = %(capital)s::jsonb",
                    "iso_3166_2 = %(iso_3166_2)s",
                    "pronunciation_audio = %(pronunciation_audio)s",
                    "geoshape = %(geoshape)s",
                ]
            )

        for col, src in extra_cols.items():
            set_parts.append(f"{col} = %({src})s")

        update_sql = f"""
            UPDATE {table}
            SET {", ".join(set_parts)}
            WHERE geoid = %({key_field})s
        """

        required = {
            "wikidata_id",
            "official_website",
            "official_image_url",
            "page_banner_image",
            "locator_map_image",
            "youtube_channel_id",
            "youtube_channel_url",
            "facebook_username",
            "facebook_url",
            "twitter_username",
            "twitter_url",
            "population",
            "area_sq_km",
            "per_capita_income",
            "number_of_households",
            "median_age",
            "time_zone",
            "local_dialing_code",
            "google_maps_customer_id",
            "language_of_work_or_name",
            "head_of_government",
            "head_of_government_position",
            "head_of_government_start_time",
            "postal_codes",
            "latitude",
            "longitude",
            "fips_code",
            "gnis_id",
            "nces_id",
            "geoid",
            "jurisdiction_label",
            "jurisdiction_description",
            "jurisdiction_aliases",
            "native_label",
            "nickname",
            "short_name",
            "demonym",
            "official_language",
            "motto",
            "anthem",
            "inception_date",
            "capital",
            "iso_3166_2",
            "pronunciation_audio",
            "geoshape",
        }
        for j in jurisdictions:
            for k in required:
                j.setdefault(k, None)

        cur = self.conn.cursor()
        try:
            execute_batch(cur, update_sql, jurisdictions, page_size=200)
            self.conn.commit()
        finally:
            cur.close()
    
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
            ?postalCode ?perCapitaIncome ?timeZone ?timeZoneLabel
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
            ?postalCode ?perCapitaIncome ?timeZone ?timeZoneLabel
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
            ?headOfGov ?headOfGovLabel
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
            ?item ?itemLabel ?itemDescription ?nativeLabel
            (GROUP_CONCAT(DISTINCT ?altLabel; separator="||") AS ?altLabels)
            (GROUP_CONCAT(DISTINCT STR(?nickname); separator="||") AS ?nicknames)
            (GROUP_CONCAT(DISTINCT STR(?shortName); separator="||") AS ?shortNames)
            (GROUP_CONCAT(DISTINCT STR(?demonym); separator="||") AS ?demonyms)
            (GROUP_CONCAT(DISTINCT ?officialLanguageLabel; separator="||") AS ?officialLanguages)
            ?motto
            (GROUP_CONCAT(DISTINCT ?anthemLabel; separator="||") AS ?anthems)
            (GROUP_CONCAT(DISTINCT ?capitalLabel; separator="||") AS ?capitals)
            ?inception ?iso31662 ?pronunciationAudio ?geoshape
            ?website ?population ?area
            ?facebook ?twitter ?youtube ?fips ?image ?banner ?locatorMap
            ?dialingCode ?googleMapsCustomerId ?households ?medianAge ?languageLabel
            ?lat ?lon
            ?postalCode ?perCapitaIncome ?timeZone ?timeZoneLabel
            ?ballotpediaId ?tripadvisorId ?subreddit
            ?geonamesId
        WHERE {{
          # Direct reference to the state
          BIND(wd:{state_q_code} AS ?item)

          # Description + aliases
          OPTIONAL {{
            ?item schema:description ?itemDescription .
            FILTER(LANG(?itemDescription) = "en")
          }}
          OPTIONAL {{
            ?item skos:altLabel ?altLabel .
            FILTER(LANG(?altLabel) = "en")
          }}
          OPTIONAL {{
            ?item wdt:P1705 ?nativeLabel .
            FILTER(LANG(?nativeLabel) = "en")
          }}
          OPTIONAL {{ ?item wdt:P1448 ?nickname . }}      # official name / nickname-ish in practice
          OPTIONAL {{ ?item wdt:P2561 ?nickname . }}      # official name (native)
          OPTIONAL {{ ?item wdt:P1813 ?shortName . }}     # short name
          OPTIONAL {{ ?item wdt:P1549 ?demonym . }}       # demonym
          OPTIONAL {{
            ?item wdt:P37 ?officialLanguage .  # official language
            OPTIONAL {{
              ?officialLanguage rdfs:label ?officialLanguageLabel .
              FILTER(LANG(?officialLanguageLabel) = "en")
            }}
          }}
          OPTIONAL {{ ?item wdt:P1906 ?hogOffice . }}      # office held by head of government (often "Governor of <State>")
          OPTIONAL {{ ?item wdt:P1451 ?motto . }}         # motto
          OPTIONAL {{
            ?item wdt:P85 ?anthem .  # anthem
            OPTIONAL {{
              ?anthem rdfs:label ?anthemLabel .
              FILTER(LANG(?anthemLabel) = "en")
            }}
          }}
          OPTIONAL {{
            ?item wdt:P36 ?capital .  # capital
            OPTIONAL {{
              ?capital rdfs:label ?capitalLabel .
              FILTER(LANG(?capitalLabel) = "en")
            }}
          }}
          OPTIONAL {{ ?item wdt:P571 ?inception . }}      # inception
          OPTIONAL {{ ?item wdt:P300 ?iso31662 . }}       # ISO 3166-2 code
          OPTIONAL {{ ?item wdt:P443 ?pronunciationAudio . }} # pronunciation audio
          OPTIONAL {{ ?item wdt:P3896 ?geoshape . }}      # geoshape dataset
          
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
          
          # Additional metadata
          OPTIONAL {{ ?item wdt:P281 ?postalCode . }}
          OPTIONAL {{ ?item wdt:P3529 ?perCapitaIncome . }}
          OPTIONAL {{ ?item wdt:P421 ?timeZone . }}
          OPTIONAL {{ ?item wdt:P2390 ?ballotpediaId . }}
          OPTIONAL {{ ?item wdt:P3134 ?tripadvisorId . }}
          OPTIONAL {{ ?item wdt:P3984 ?subreddit . }}
          
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
        }}
        GROUP BY
          ?item ?itemLabel ?itemDescription ?nativeLabel
          ?motto ?inception ?iso31662 ?pronunciationAudio ?geoshape
          ?website ?population ?area ?facebook ?twitter ?youtube ?fips ?image ?banner ?locatorMap
          ?dialingCode ?googleMapsCustomerId ?households ?medianAge ?languageLabel
          ?lat ?lon ?postalCode ?perCapitaIncome ?timeZone ?timeZoneLabel
          ?ballotpediaId ?tripadvisorId ?subreddit ?geonamesId ?hogOffice
        LIMIT 1
        """
        
        logger.info(f"Querying WikiData for state: {state_name}...")
        results = await self.wikidata.execute_sparql(query)
        
        if not results:
            logger.warning(f"No WikiData entry found for {state_name}")
            return []
        
        result = results[0]
        # State labels/aliases/meta (English)
        jurisdiction_label = result.get("itemLabel") or state_name
        jurisdiction_description = result.get("itemDescription")
        aliases_en = [a for a in result.get("altLabels", "").split("||") if a] if result.get("altLabels") else None
        native_label = result.get("nativeLabel")
        nicknames = [a for a in result.get("nicknames", "").split("||") if a] if result.get("nicknames") else None
        short_names = [a for a in result.get("shortNames", "").split("||") if a] if result.get("shortNames") else None
        demonyms = [a for a in result.get("demonyms", "").split("||") if a] if result.get("demonyms") else None
        official_languages = [a for a in result.get("officialLanguages", "").split("||") if a] if result.get("officialLanguages") else None
        motto = result.get("motto")
        anthems = [a for a in result.get("anthems", "").split("||") if a] if result.get("anthems") else None
        capitals = [a for a in result.get("capitals", "").split("||") if a] if result.get("capitals") else None
        iso_3166_2 = result.get("iso31662")
        pronunciation_audio = result.get("pronunciationAudio")
        geoshape = result.get("geoshape")

        inception_date = None
        inception_raw = result.get("inception")
        if inception_raw:
            try:
                inception_date = inception_raw[:10]
            except Exception:
                inception_date = None

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
        
        # Head of government is fetched via a separate lightweight query to avoid
        # Blazegraph correlated-subquery quirks that can return unrelated leaders.
        head_of_gov = None
        head_of_gov_position = result.get("hogOfficeLabel") or f"Governor of {state_name}"
        head_start = None

        hog_query = f"""
        SELECT ?headOfGovLabel ?headStart
        WHERE {{
          wd:{state_q_code} p:P6 ?stmt .
          ?stmt ps:P6 ?headOfGov .
          OPTIONAL {{ ?stmt pq:P580 ?headStart . }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        ORDER BY DESC(?headStart)
        LIMIT 1
        """
        try:
            hog_rows = await self.wikidata.execute_sparql(hog_query)
        except Exception:
            hog_rows = []

        if hog_rows:
            hog_row = hog_rows[0]
            head_of_gov = hog_row.get("headOfGovLabel")
            # US states: head of government is the Governor.
            head_of_gov_position = f"Governor of {state_name}"
            head_start_raw = hog_row.get("headStart")
            if head_start_raw:
                try:
                    # Store as naive midnight timestamp to avoid timezone shifts when writing
                    # into a `timestamp without time zone` column.
                    head_start = datetime.fromisoformat(head_start_raw[:10])
                except Exception:
                    head_start = head_start_raw
        
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
            'jurisdiction_label': jurisdiction_label,
            'jurisdiction_description': jurisdiction_description,
            'jurisdiction_aliases': json.dumps(aliases_en) if aliases_en else None,
            'native_label': native_label,
            'nickname': json.dumps(nicknames) if nicknames else None,
            'short_name': json.dumps(short_names) if short_names else None,
            'demonym': json.dumps(demonyms) if demonyms else None,
            'official_language': json.dumps(official_languages) if official_languages else None,
            'motto': motto,
            'anthem': json.dumps(anthems) if anthems else None,
            'inception_date': inception_date,
            'capital': json.dumps(capitals) if capitals else None,
            'iso_3166_2': iso_3166_2,
            'pronunciation_audio': pronunciation_audio,
            'geoshape': geoshape,
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
        """Apply Wikidata enrichment into bronze *_wikidata tables (no public table)."""
        if not jurisdictions:
            return

        # All rows in this batch correspond to the same task (state/county/city/school_district)
        # by construction.
        jtype = jurisdictions[0].get("jurisdiction_type")
        if jtype == "county":
            task = "county"
        elif jtype == "school_district":
            task = "school_district"
        elif jtype == "state":
            task = "state"
        else:
            # city/town are stored as municipalities in bronze
            task = "city"

        self._apply_wikidata_updates(task, jurisdictions)
    
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

            # Rebuild the bronze *_wikidata base rows for this state+type, then apply updates.
            # This ensures we never end up with "all NULL" base geography columns after truncation.
            self._seed_wikidata_table(state_code, task)

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
        
        # Final summary (bronze *_wikidata tables)
        cursor = loader.conn.cursor()
        cursor.execute("""
            SELECT 'state'::text AS jurisdiction_type,
                   COUNT(*)::int AS count,
                   COUNT(*) FILTER (WHERE youtube_channel_id IS NOT NULL)::int AS with_youtube,
                   COUNT(*) FILTER (WHERE official_website IS NOT NULL)::int AS with_website
            FROM bronze.bronze_jurisdictions_states_wikidata
            UNION ALL
            SELECT 'county'::text,
                   COUNT(*)::int,
                   COUNT(*) FILTER (WHERE youtube_channel_id IS NOT NULL)::int,
                   COUNT(*) FILTER (WHERE official_website IS NOT NULL)::int
            FROM bronze.bronze_jurisdictions_counties_wikidata
            UNION ALL
            SELECT 'municipality'::text,
                   COUNT(*)::int,
                   COUNT(*) FILTER (WHERE youtube_channel_id IS NOT NULL)::int,
                   COUNT(*) FILTER (WHERE official_website IS NOT NULL)::int
            FROM bronze.bronze_jurisdictions_municipalities_wikidata
            UNION ALL
            SELECT 'school_district'::text,
                   COUNT(*)::int,
                   COUNT(*) FILTER (WHERE youtube_channel_id IS NOT NULL)::int,
                   COUNT(*) FILTER (WHERE official_website IS NOT NULL)::int
            FROM bronze.bronze_jurisdictions_school_districts_wikidata
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
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Graceful stop on Ctrl-C (avoid noisy asyncio/httpx traceback).
        logger.warning("Interrupted by user (Ctrl-C). Exiting.")
