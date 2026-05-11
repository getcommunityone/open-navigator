#!/usr/bin/env python3
"""
Scraper for U.S. Conference of Mayors election results.

Extracts mayor election data from https://www.usmayors.org/elections/election-results-2/
and updates jurisdictions_details_search with current/incoming mayor information.

Usage:
    python scrape_mayor_elections.py --states AL,GA,IN,MA,WA,WI
    python scrape_mayor_elections.py --dry-run
"""

import argparse
import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import httpx
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "database": "open_navigator",
    "user": "postgres",
    "password": "password"
}

USMAYORS_URL = "https://www.usmayors.org/elections/election-results-2/"


class USMayorsScraper:
    """Scraper for U.S. Conference of Mayors election results."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "OpenNavigator/1.0 (Civic Engagement Research; contact@communityone.org)"
            }
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def fetch_election_results(self) -> List[Dict]:
        """
        Fetch and parse mayor election results from USCM website.
        
        Returns:
            List of dicts with keys: state, city, population, election_date, mayor_name
        """
        logger.info(f"Fetching election results from {USMAYORS_URL}")
        
        try:
            response = await self.client.get(USMAYORS_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the table with election results
            # The table has rows with: State | City | Population | Date | Winner | Notes
            elections = []
            current_state = None
            
            # Find all table rows
            tables = soup.find_all('table')
            if not tables:
                logger.warning("No tables found on page")
                return []
            
            # The main table should be the first/largest one
            main_table = tables[0]
            rows = main_table.find_all('tr')
            
            for row in rows:
                cols = row.find_all('td')
                
                # Skip empty rows
                if not cols:
                    continue
                
                # Check if this is a state header row (single column with state name)
                if len(cols) == 1:
                    state_text = cols[0].get_text(strip=True)
                    if state_text and len(state_text) < 50:  # State names are short
                        current_state = state_text
                    continue
                
                # Data rows should have 5-6 columns
                if len(cols) >= 4 and current_state:
                    try:
                        # Extract data - columns are: City | Population | Date | Winner | Notes (optional)
                        city = cols[0].get_text(strip=True)
                        population_str = cols[1].get_text(strip=True).replace(',', '')
                        date_str = cols[2].get_text(strip=True)
                        mayor_name = cols[3].get_text(strip=True)
                        
                        # Skip if city or population is empty
                        if not city or not population_str:
                            continue
                        
                        # Parse population
                        try:
                            population = int(population_str)
                        except ValueError:
                            logger.debug(f"Could not parse population for {city}: {population_str}")
                            population = None
                        
                        # Parse date (format: MM/DD/YYYY)
                        election_date = None
                        if date_str and '/' in date_str:
                            try:
                                election_date = datetime.strptime(date_str, '%m/%d/%Y').date()
                            except ValueError:
                                logger.debug(f"Could not parse date for {city}: {date_str}")
                        
                        # Add to results
                        elections.append({
                            'state': current_state,
                            'city': city,
                            'population': population,
                            'election_date': election_date,
                            'mayor_name': mayor_name if mayor_name else None,
                            'source_url': USMAYORS_URL
                        })
                        
                    except Exception as e:
                        logger.debug(f"Error parsing row: {e}")
                        continue
            
            logger.info(f"Found {len(elections)} mayor election records")
            return elections
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching election results: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing election results: {e}")
            return []


def normalize_city_name(name: str) -> str:
    """Normalize city name for matching."""
    # Remove common suffixes
    name = re.sub(r'\s+(city|town|township|village|borough)$', '', name, flags=re.IGNORECASE)
    # Remove extra whitespace
    name = ' '.join(name.split())
    return name.strip()


def update_jurisdictions_with_mayor_data(
    elections: List[Dict],
    states: Optional[str] = None,
    dry_run: bool = False
) -> None:
    """
    Update jurisdictions_details_search with mayor election data.
    
    Args:
        elections: List of election records
        states: Comma-separated list of state codes to filter by
        dry_run: If True, don't commit changes to database
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Build state filter
        state_filter = ""
        if states:
            state_list = [s.strip().upper() for s in states.split(',')]
            state_filter = f"AND s.state_code IN ({','.join(repr(s) for s in state_list)})"
            logger.info(f"Filtering to states: {', '.join(state_list)}")
        
        matched = 0
        unmatched = []
        
        for election in elections:
            city = election['city']
            state = election['state']
            mayor_name = election['mayor_name']
            election_date = election['election_date']
            
            # Skip if no mayor name (election not finalized)
            if not mayor_name:
                continue
            
            # Normalize city name
            norm_city = normalize_city_name(city)
            
            # Try to match jurisdiction by city name and state
            # USCM uses full state names, we need to match by name similarity
            query = """
                SELECT d.id, s.name, s.state_code, s.state
                FROM jurisdictions_details_search d
                JOIN jurisdictions_search s ON d.jurisdiction_id = s.id
                WHERE s.type = 'city'
                  AND (
                    LOWER(s.name) = LOWER(%s)
                    OR LOWER(REPLACE(s.name, ' city', '')) = LOWER(%s)
                    OR LOWER(REPLACE(s.name, ' town', '')) = LOWER(%s)
                  )
                  AND LOWER(s.state) = LOWER(%s)
                {state_filter}
                LIMIT 1
            """.format(state_filter=state_filter)
            
            cur.execute(query, (norm_city, norm_city, norm_city, state))
            result = cur.fetchone()
            
            if result:
                matched += 1
                jurisdiction_id = result['id']
                
                logger.info(
                    f"✅ Matched: {city}, {state} -> {result['name']}, {result['state_code']} "
                    f"(Mayor: {mayor_name}, Election: {election_date})"
                )
                
                if not dry_run:
                    # Update jurisdictions_details_search with mayor info
                    update_query = """
                        UPDATE jurisdictions_details_search
                        SET 
                            current_mayor = %s,
                            mayor_election_date = %s,
                            usmayors_last_updated = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """
                    cur.execute(update_query, (mayor_name, election_date, jurisdiction_id))
            else:
                unmatched.append(f"{city}, {state}")
                logger.debug(f"❌ No match: {city}, {state}")
        
        if not dry_run:
            conn.commit()
            logger.info(f"✅ Committed {matched} mayor updates to database")
        else:
            logger.info(f"✅ DRY RUN: Would update {matched} jurisdictions")
        
        # Summary
        logger.info(f"\n{'='*60}")
        logger.info(f"SUMMARY:")
        logger.info(f"  Total elections: {len(elections)}")
        logger.info(f"  Matched: {matched}")
        logger.info(f"  Unmatched: {len(unmatched)}")
        logger.info(f"{'='*60}")
        
        if unmatched and len(unmatched) <= 20:
            logger.info("\nUnmatched cities:")
            for city in unmatched[:20]:
                logger.info(f"  - {city}")
    
    finally:
        cur.close()
        conn.close()


async def main():
    parser = argparse.ArgumentParser(
        description="Scrape mayor election data from U.S. Conference of Mayors"
    )
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated list of state codes (e.g., AL,GA,MA)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without updating database'
    )
    
    args = parser.parse_args()
    
    # Fetch election data
    async with USMayorsScraper() as scraper:
        elections = await scraper.fetch_election_results()
    
    if not elections:
        logger.error("No election data found")
        return
    
    # Update database
    update_jurisdictions_with_mayor_data(
        elections,
        states=args.states,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    asyncio.run(main())
