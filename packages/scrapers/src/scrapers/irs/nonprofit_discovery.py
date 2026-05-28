"""
Nonprofit Discovery Module
Automated discovery and enrichment of nonprofits and churches using free APIs

Data Sources:
1. ProPublica Nonprofit Explorer API - Financial data, EIN, NTEE codes
2. IRS Tax Exempt Organization Search - Official tax-exempt status
3. Every.org Charity API - Mission statements, logos
4. Findhelp.org (Aunt Bertha) - Local services directory
5. 211 Directory - Regional social services
"""

import requests
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
import json
import time
from datetime import datetime
from loguru import logger


class NonprofitDiscovery:
    """Discover and enrich nonprofit data from multiple free sources"""
    
    def __init__(self, cache_dir: str = "data/cache/nonprofits"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Rate limiting
        self.last_request_time = {}
        self.min_request_interval = 1.0  # seconds between requests
    
    def _rate_limit(self, source: str):
        """Rate limiting to be respectful to free APIs"""
        if source in self.last_request_time:
            elapsed = time.time() - self.last_request_time[source]
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)
        self.last_request_time[source] = time.time()
    
    # =========================================================================
    # 1. ProPublica Nonprofit Explorer API
    # =========================================================================
    
    def search_propublica(
        self, 
        state: str = "AL",
        ntee_code: Optional[str] = None,
        city: Optional[str] = None
    ) -> List[Dict]:
        """
        Search ProPublica Nonprofit Explorer API
        
        API Docs: https://projects.propublica.org/nonprofits/api
        
        NOTE: NTEE filtering is done CLIENT-SIDE due to ProPublica API bug
              that causes 500 errors when using ntee[id] parameter.
        
        Args:
            state: 2-letter state code (e.g., "AL")
            ntee_code: NTEE major group (e.g., "E" for health) - filtered client-side
            city: City name (e.g., "Tuscaloosa")
        
        Returns:
            List of nonprofit records (filtered by NTEE if specified)
        """
        cache_file = self.cache_dir / f"propublica_{state}_{ntee_code or 'all'}_{city or 'all'}.json"
        
        # Check cache
        if cache_file.exists():
            logger.info(f"Using cached ProPublica data from {cache_file}")
            with open(cache_file) as f:
                return json.load(f)
        
        base_url = "https://projects.propublica.org/nonprofits/api/v2/search.json"
        
        # Build params - NOTE: Excluding ntee[id] due to API 500 error bug
        params = {
            "state[id]": state,
        }
        
        if city:
            params["q"] = city
        
        self._rate_limit("propublica")
        
        # Retry logic for API failures
        max_retries = 3
        retry_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Searching ProPublica API: state={state}, city={city} (attempt {attempt + 1}/{max_retries})")
                if ntee_code:
                    logger.info(f"  → Will filter for NTEE code '{ntee_code}' client-side after retrieval")
                    
                response = requests.get(base_url, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                organizations = data.get("organizations", [])
                
                logger.success(f"Retrieved {len(organizations)} organizations from ProPublica")
                
                # Parse results
                nonprofits = []
                for org in organizations:
                    org_ntee = org.get("ntee_code", "")
                    
                    # CLIENT-SIDE NTEE FILTERING (workaround for API bug)
                    if ntee_code and org_ntee:
                        # Check if org's NTEE code starts with requested code
                        if not org_ntee.startswith(ntee_code):
                            continue  # Skip this org, doesn't match filter
                    
                    nonprofit = {
                        "source": "propublica",
                        "ein": org.get("ein"),
                        "name": org.get("name"),
                        "city": org.get("city"),
                        "state": org.get("state"),
                        "ntee_code": org_ntee,
                        "subsection_code": org.get("subsection_code"),
                        "classification_codes": org.get("classification_codes", ""),
                        "ruling_date": org.get("ruling_date"),
                        "deductibility_code": org.get("deductibility_code"),
                        "foundation_code": org.get("foundation_code"),
                        "organization_code": org.get("organization_code"),
                        "exempt_organization_status_code": org.get("exempt_organization_status_code"),
                        "tax_period": org.get("tax_period"),
                        "asset_cd": org.get("asset_cd"),
                        "income_cd": org.get("income_cd"),
                        "filing_requirement_code": org.get("filing_requirement_code"),
                        "pf_filing_requirement_code": org.get("pf_filing_requirement_code"),
                        "accounting_period": org.get("accounting_period"),
                        "asset_amount": org.get("asset_amount"),
                        "income_amount": org.get("income_amount"),
                        "revenue_amount": org.get("revenue_amount"),
                        "ntee_description": self._get_ntee_description(org_ntee)
                    }
                    nonprofits.append(nonprofit)
                
                if ntee_code:
                    logger.success(f"Filtered to {len(nonprofits)} organizations matching NTEE code '{ntee_code}'")
                else:
                    logger.success(f"Returning all {len(nonprofits)} organizations")
                
                # Cache results
                with open(cache_file, 'w') as f:
                    json.dump(nonprofits, f, indent=2)
                
                return nonprofits
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 500:
                    # Server error - retry with backoff
                    if attempt < max_retries - 1:
                        logger.warning(f"ProPublica API returned 500 error, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        logger.error(f"ProPublica API failed after {max_retries} attempts: {e}")
                        logger.warning(f"Skipping state={state}, city={city} - API unavailable")
                        return []
                else:
                    # Other HTTP errors
                    logger.error(f"ProPublica API HTTP error: {e}")
                    return []
                    
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    logger.warning(f"Request timeout, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(f"ProPublica API timeout after {max_retries} attempts")
                    return []
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"ProPublica API request failed: {e}")
                return []
        
        # Should not reach here, but just in case
        return []
    
    def get_propublica_org_details(self, ein: str) -> Optional[Dict]:
        """
        Get detailed information about a specific organization
        
        Args:
            ein: Employer Identification Number (9 digits)
        
        Returns:
            Detailed organization data including filings
        """
        cache_file = self.cache_dir / f"propublica_org_{ein}.json"
        
        if cache_file.exists():
            logger.info(f"Using cached org details for EIN {ein}")
            with open(cache_file) as f:
                return json.load(f)
        
        base_url = f"https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"
        
        self._rate_limit("propublica")
        
        try:
            logger.info(f"Fetching org details for EIN {ein}")
            response = requests.get(base_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            org = data.get("organization", {})
            
            details = {
                "source": "propublica",
                "ein": ein,
                "name": org.get("name"),
                "city": org.get("city"),
                "state": org.get("state"),
                "zipcode": org.get("zipcode"),
                "ntee_code": org.get("ntee_code"),
                "ntee_description": self._get_ntee_description(org.get("ntee_code")),
                "subsection_code": org.get("subsection_code"),
                "filings": []
            }
            
            # Get recent filings
            for filing in data.get("filings_with_data", [])[:5]:  # Last 5 filings
                filing_data = {
                    "tax_period": filing.get("tax_prd_yr"),
                    "total_revenue": filing.get("totrevenue"),
                    "total_expenses": filing.get("totfuncexpns"),
                    "total_assets": filing.get("totassetsend"),
                    "total_liabilities": filing.get("totliabend"),
                    "net_assets": filing.get("totnetassetend"),
                    "contributions": filing.get("totcntrbgfts"),
                    "program_service_revenue": filing.get("totprgmrevnue"),
                    "pdf_url": filing.get("pdf_url")
                }
                details["filings"].append(filing_data)
            
            # Cache results
            with open(cache_file, 'w') as f:
                json.dump(details, f, indent=2)
            
            return details
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch org details for EIN {ein}: {e}")
            return None
    
    # =========================================================================
    # 2. Every.org Charity API
    # =========================================================================
    
    def search_everyorg(
        self,
        location: str = "Tuscaloosa, AL",
        causes: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Search Every.org for nonprofits by location and cause
        
        API Docs: https://www.every.org/nonprofit-api
        
        Args:
            location: City, State format
            causes: List of causes (e.g., ["health", "education"])
        
        Returns:
            List of nonprofits with mission statements and logos
        """
        cache_file = self.cache_dir / f"everyorg_{location.replace(' ', '_').replace(',', '')}_{'-'.join(causes or ['all'])}.json"
        
        if cache_file.exists():
            logger.info(f"Using cached Every.org data from {cache_file}")
            with open(cache_file) as f:
                return json.load(f)
        
        # Note: Every.org API requires authentication
        # For now, we'll use their public browse endpoint
        base_url = "https://www.every.org/api/nonprofits/search"
        
        params = {
            "location": location,
            "take": 100
        }
        
        if causes:
            params["causes"] = ",".join(causes)
        
        self._rate_limit("everyorg")
        
        try:
            logger.info(f"Searching Every.org: location={location}, causes={causes}")
            response = requests.get(base_url, params=params, timeout=30)
            
            # Every.org may require API key - handle gracefully
            if response.status_code == 401:
                logger.warning("Every.org API requires authentication - skipping")
                return []
            
            response.raise_for_status()
            data = response.json()
            
            nonprofits = []
            for org in data.get("nonprofits", []):
                nonprofit = {
                    "source": "everyorg",
                    "ein": org.get("ein"),
                    "name": org.get("name"),
                    "slug": org.get("slug"),
                    "description": org.get("description"),
                    "mission": org.get("mission"),
                    "logo_url": org.get("logoUrl"),
                    "cover_image_url": org.get("coverImageUrl"),
                    "location": org.get("location"),
                    "website_url": org.get("websiteUrl"),
                    "ntee_code": org.get("nteeCode"),
                    "ntee_description": self._get_ntee_description(org.get("nteeCode")),
                    "causes": org.get("causes", [])
                }
                nonprofits.append(nonprofit)
            
            logger.success(f"Found {len(nonprofits)} organizations from Every.org")
            
            # Cache results
            with open(cache_file, 'w') as f:
                json.dump(nonprofits, f, indent=2)
            
            return nonprofits
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Every.org API request failed (may require auth): {e}")
            return []
    
    # =========================================================================
    # 3. Findhelp.org (Aunt Bertha) Scraper
    # =========================================================================
    
    def search_findhelp(
        self,
        location: str = "Tuscaloosa, AL",
        keyword: str = "dental"
    ) -> List[Dict]:
        """
        Scrape Findhelp.org for local service providers
        
        Note: This uses their public search page. For production, consider
        requesting API access from Findhelp.org
        
        Args:
            location: City, State
            keyword: Service keyword (e.g., "dental", "health", "food")
        
        Returns:
            List of service providers
        """
        cache_file = self.cache_dir / f"findhelp_{location.replace(' ', '_').replace(',', '')}_{keyword}.json"
        
        if cache_file.exists():
            logger.info(f"Using cached Findhelp data from {cache_file}")
            with open(cache_file) as f:
                return json.load(f)
        
        # Findhelp.org search URL
        base_url = "https://www.findhelp.org/search"
        
        params = {
            "query": keyword,
            "location": location
        }
        
        self._rate_limit("findhelp")
        
        try:
            logger.info(f"Searching Findhelp.org: location={location}, keyword={keyword}")
            
            # This would require HTML parsing - simplified version
            # In production, use BeautifulSoup or Playwright for full scraping
            
            # Placeholder for now
            logger.warning("Findhelp.org scraping requires HTML parsing - implement with BeautifulSoup")
            
            return []
            
        except Exception as e:
            logger.error(f"Findhelp.org scraping failed: {e}")
            return []
    
    # =========================================================================
    # 4. 211 Directory Search
    # =========================================================================
    
    def search_211(
        self,
        state: str = "AL",
        county: str = "Tuscaloosa",
        keyword: str = "dental"
    ) -> List[Dict]:
        """
        Search 211 directory for local social services
        
        Note: Each state/region has different 211 systems. This targets
        Alabama's 211 system.
        
        Args:
            state: State code
            county: County name
            keyword: Service keyword
        
        Returns:
            List of service providers
        """
        cache_file = self.cache_dir / f"211_{state}_{county}_{keyword}.json"
        
        if cache_file.exists():
            logger.info(f"Using cached 211 data from {cache_file}")
            with open(cache_file) as f:
                return json.load(f)
        
        # Alabama 211 URL
        # Note: Different states use different 211 systems
        base_url = "https://www.211connects.org"
        
        logger.info(f"Searching 211: state={state}, county={county}, keyword={keyword}")
        
        # This would require state-specific scraping
        logger.warning("211 directory scraping requires state-specific implementation")
        
        return []
    
    # =========================================================================
    # Helper Functions
    # =========================================================================
    
    def _get_ntee_description(self, ntee_code: Optional[str]) -> str:
        """Get human-readable description for NTEE code"""
        if not ntee_code:
            return "Unknown"
        
        ntee_map = {
            "E": "Health - General and Rehabilitative",
            "E20": "Hospitals and Related Primary Medical Care Facilities",
            "E30": "Ambulatory Health Center, Community Clinic",
            "E32": "School-Based Health Care",
            "E40": "Reproductive Health Care",
            "E50": "Rehabilitative Medical Services",
            "E80": "Health - General and Rehabilitative N.E.C.",
            "F": "Mental Health, Crisis Intervention",
            "K": "Food, Agriculture, and Nutrition",
            "K30": "Food Service, Free Food Distribution Programs",
            "K34": "Congregate Meals",
            "N": "Recreation, Sports, Leisure, Athletics",
            "O": "Youth Development",
            "O50": "Youth Development Programs, Other",
            "P": "Human Services - Multipurpose and Other",
            "X": "Religion Related, Spiritual Development",
            "X20": "Christian",
            "W": "Public, Society Benefit - Multipurpose and Other"
        }
        
        # Try exact match first
        if ntee_code in ntee_map:
            return ntee_map[ntee_code]
        
        # Try major group (first letter)
        if ntee_code[0] in ntee_map:
            return ntee_map[ntee_code[0]]
        
        return f"NTEE {ntee_code}"
    
    def merge_nonprofit_data(
        self,
        propublica_orgs: List[Dict],
        everyorg_orgs: List[Dict]
    ) -> List[Dict]:
        """
        Merge nonprofit data from multiple sources by EIN
        
        Args:
            propublica_orgs: Orgs from ProPublica API
            everyorg_orgs: Orgs from Every.org API
        
        Returns:
            Merged list with enriched data
        """
        merged = {}
        
        # Add ProPublica data (financial backbone)
        for org in propublica_orgs:
            ein = org.get("ein")
            if ein:
                merged[ein] = org
        
        # Enrich with Every.org data (mission, logo)
        for org in everyorg_orgs:
            ein = org.get("ein")
            if ein and ein in merged:
                # Add Every.org fields to existing record
                merged[ein].update({
                    "mission": org.get("mission") or merged[ein].get("mission"),
                    "description": org.get("description"),
                    "logo_url": org.get("logo_url"),
                    "website_url": org.get("website_url"),
                    "causes": org.get("causes", [])
                })
            elif ein:
                # New org not in ProPublica data
                merged[ein] = org
        
        logger.success(f"Merged {len(merged)} unique nonprofits")
        
        return list(merged.values())
    
    def export_to_frontend(
        self,
        nonprofits: List[Dict],
        output_file: str = "frontend/policy-dashboards/src/data/tuscaloosa_nonprofits.json"
    ):
        """
        Export nonprofit data in frontend-compatible format
        
        Args:
            nonprofits: List of nonprofit records
            output_file: Path to output JSON file
        """
        frontend_data = []
        
        for org in nonprofits:
            # Get most recent financial data
            revenue = org.get("revenue_amount") or org.get("income_amount", 0)
            
            # Estimate impact (this would come from services data in production)
            estimated_impact = self._estimate_impact(org)
            
            frontend_org = {
                "name": org.get("name"),
                "ein": org.get("ein"),
                "ntee_code": org.get("ntee_code"),
                "ntee_description": org.get("ntee_description", ""),
                "mission": org.get("mission") or org.get("description", ""),
                "services": self._extract_services(org),
                "annual_budget": revenue,
                **estimated_impact,
                "contact": {
                    "website": org.get("website_url", ""),
                    "email": "",  # Not typically in public APIs
                    "phone": ""   # Would need scraping
                },
                "logo_url": org.get("logo_url"),
                "volunteer_opportunities": True,  # Default assumption
                "accepting_board_members": False  # Would need manual verification
            }
            
            frontend_data.append(frontend_org)
        
        # Save to file
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(frontend_data, f, indent=2)
        
        logger.success(f"Exported {len(frontend_data)} nonprofits to {output_file}")
    
    def _extract_services(self, org: Dict) -> List[str]:
        """Extract services from org description/mission"""
        # This is a placeholder - real version would use NLP
        services = []
        
        description = (org.get("description") or org.get("mission") or "").lower()
        
        service_keywords = {
            "dental": "Dental care and screenings",
            "food": "Food assistance and nutrition programs",
            "health": "Healthcare services",
            "mental": "Mental health services",
            "youth": "Youth development programs",
            "education": "Educational programs"
        }
        
        for keyword, service in service_keywords.items():
            if keyword in description:
                services.append(service)
        
        return services or ["Community services"]
    
    def _estimate_impact(self, org: Dict) -> Dict:
        """Estimate impact metrics based on revenue"""
        revenue = org.get("revenue_amount") or org.get("income_amount", 0)
        
        # Rough estimates based on nonprofit sector averages
        # This would be replaced with actual reported data
        if revenue:
            return {
                "students_served": int(revenue / 50) if "school" in org.get("ntee_description", "").lower() else 0,
                "families_served": int(revenue / 200),
                "youth_served": int(revenue / 100) if "youth" in org.get("ntee_description", "").lower() else 0
            }
        
        return {
            "students_served": 0,
            "families_served": 0,
            "youth_served": 0
        }


def discover_tuscaloosa_nonprofits(
    ntee_codes: List[str] = ["E", "E32", "E40", "K", "O", "X"]
) -> List[Dict]:
    """
    Run complete nonprofit discovery for Tuscaloosa, AL
    
    Args:
        ntee_codes: List of NTEE codes to search for
    
    Returns:
        Merged list of nonprofits
    """
    discovery = NonprofitDiscovery()
    
    all_nonprofits = []
    
    # Search ProPublica for each NTEE code
    for ntee in ntee_codes:
        logger.info(f"Searching for NTEE code {ntee}...")
        
        orgs = discovery.search_propublica(
            state="AL",
            city="Tuscaloosa",
            ntee_code=ntee
        )
        
        all_nonprofits.extend(orgs)
        
        # Be respectful to API
        time.sleep(1)
    
    # Try Every.org (may require auth)
    everyorg_orgs = discovery.search_everyorg(
        location="Tuscaloosa, AL",
        causes=["health", "education", "youth"]
    )
    
    # Merge data sources
    merged = discovery.merge_nonprofit_data(all_nonprofits, everyorg_orgs)
    
    # Enrich top organizations with detailed data
    for org in merged[:20]:  # Top 20 by revenue
        ein = org.get("ein")
        if ein:
            details = discovery.get_propublica_org_details(ein)
            if details:
                org.update(details)
            time.sleep(1)  # Rate limiting
    
    # Export to frontend
    discovery.export_to_frontend(merged)
    
    return merged


if __name__ == "__main__":
    logger.info("Starting Tuscaloosa nonprofit discovery...")
    
    nonprofits = discover_tuscaloosa_nonprofits()
    
    logger.success(f"✓ Discovered {len(nonprofits)} nonprofits in Tuscaloosa")
    
    # Print summary
    print("\n" + "="*60)
    print("TUSCALOOSA NONPROFIT SUMMARY")
    print("="*60)
    
    by_ntee = {}
    for org in nonprofits:
        ntee = org.get("ntee_code", "Unknown")
        if ntee not in by_ntee:
            by_ntee[ntee] = []
        by_ntee[ntee].append(org)
    
    for ntee, orgs in sorted(by_ntee.items(), key=lambda x: len(x[1]), reverse=True):
        desc = NonprofitDiscovery()._get_ntee_description(ntee)
        print(f"\n{ntee} - {desc}: {len(orgs)} organizations")
        for org in orgs[:3]:  # Top 3
            revenue = org.get("revenue_amount", 0)
            print(f"  • {org['name']}: ${revenue:,}/year")
