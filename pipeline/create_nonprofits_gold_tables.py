"""
Nonprofit Discovery and Gold Table Creation Pipeline

This script:
1. Discovers nonprofit organizations using free APIs (ProPublica, IRS, Every.org)
2. Enriches nonprofit data with financial and program information
3. Creates curated gold tables for analysis and dashboards

Gold Tables Created:
1. nonprofits_organizations - Basic info (name, EIN, NTEE, location)
2. nonprofits_financials - Revenue, assets, expenses from 990 forms
3. nonprofits_programs - Services and programs offered
4. nonprofits_locations - Geographic service areas

Data Sources:
- ProPublica Nonprofit Explorer API (IRS Form 990 data)
- IRS Tax Exempt Organization Search
- Every.org Charity API
- Findhelp.org (Aunt Bertha)

Input: API calls to free nonprofit data sources
Output: data/gold/nonprofits_*.parquet
"""

import pandas as pd
import requests
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import time
from loguru import logger
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from scripts.utils.calendar_year_util import calendar_year_label
from scripts.datasources.irs.nonprofit_discovery import NonprofitDiscovery
from scripts.discovery.irs_bmf_ingestion import IRSBMFIngestion


class NonprofitGoldTableCreator:
    """Discover nonprofits and create curated gold tables"""
    
    def __init__(
        self,
        cache_dir: str = "data/cache/nonprofits",
        bronze_dir: str = "data/bronze/nonprofits",
        gold_dir: str = "data/gold"
    ):
        self.cache_dir = Path(cache_dir)
        self.bronze_dir = Path(bronze_dir)
        self.gold_dir = Path(gold_dir)
        
        # Create directories
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.bronze_dir.mkdir(parents=True, exist_ok=True)
        self.gold_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize discovery modules
        self.discovery = NonprofitDiscovery(cache_dir=str(self.cache_dir))
        self.irs = IRSBMFIngestion(cache_dir=str(self.cache_dir.parent / "irs_bmf"))
        
        logger.info(f"Cache directory: {self.cache_dir}")
        logger.info(f"Bronze directory: {self.bronze_dir}")
        logger.info(f"Gold directory: {self.gold_dir}")
    
    def discover_nonprofits_from_irs(
        self,
        states: Optional[List[str]] = None,
        ntee_codes: Optional[List[str]] = None,
        download_all: bool = False
    ) -> pd.DataFrame:
        """
        Discover ALL nonprofits from IRS EO-BMF bulk data (1.9M+ organizations)
        
        This is MUCH faster and more complete than API-based discovery!
        
        Args:
            states: List of state codes to download (None = all states via regional files)
            ntee_codes: Optional NTEE codes to filter (None = all nonprofits)
            download_all: If True, download all 4 regional files (~1.9M orgs)
        
        Returns:
            DataFrame with nonprofit data
        """
        logger.info("=" * 60)
        logger.info("IRS EO-BMF BULK DATA DOWNLOAD")
        logger.info("=" * 60)
        
        if download_all:
            # Download all 4 regional files (~1.9M+ organizations)
            logger.info("Downloading ALL U.S. nonprofits from IRS (4 regional files)...")
            df = self.irs.download_all_regions()
        elif states:
            # Download specific states
            logger.info(f"Downloading {len(states)} states from IRS...")
            df = self.irs.download_states(states)
        else:
            raise ValueError("Must specify either states or download_all=True")
        
        # Filter by NTEE codes if specified
        if ntee_codes and len(ntee_codes) > 0:
            df = self.irs.filter_by_ntee(df, ntee_codes)
        
        # Convert to ProPublica-compatible format
        standardized = self.irs.standardize_to_propublica_format(df)
        
        logger.success(f"IRS data ready: {len(standardized):,} organizations")
        return standardized
    
    def discover_nonprofits_by_state(
        self,
        states: List[str],
        ntee_codes: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Discover nonprofits across multiple states
        
        Args:
            states: List of 2-letter state codes (e.g., ["AL", "MI", "NY"])
            ntee_codes: Optional list of NTEE codes to filter (e.g., ["E", "P", "K"])
                       Use empty list [] to get ALL nonprofits without filtering
                       Use None for default community service codes (E, P, K, L, S, W)
        
        Returns:
            DataFrame with discovered nonprofit data
        """
        logger.info(f"Discovering nonprofits in {len(states)} states...")
        
        all_nonprofits = []
        successful_requests = 0
        failed_requests = 0
        skipped_requests = 0
        
        # Handle NTEE code filtering options
        if ntee_codes is None:
            # Default NTEE codes (focus on community services)
            ntee_codes = [
                "E",   # Health
                "P",   # Human Services
                "K",   # Food, Agriculture
                "L",   # Housing
                "S",   # Community Improvement
                "W",   # Public Affairs
            ]
            logger.info(f"Using default NTEE codes: {', '.join(ntee_codes)}")
        elif len(ntee_codes) == 0:
            # Empty list means get ALL nonprofits (no NTEE filtering)
            ntee_codes = [None]  # Will search once per state without NTEE filter
            logger.info("Searching for ALL nonprofits (no NTEE filtering)")
        
        total_requests = len(states) * len(ntee_codes)
        current_request = 0
        
        for state in states:
            logger.info(f"Processing state: {state}")
            
            for ntee_code in ntee_codes:
                current_request += 1
                
                if ntee_code is None:
                    logger.info(f"  - Searching ALL nonprofits (no NTEE filter) ({current_request}/{total_requests})")
                else:
                    logger.info(f"  - Searching NTEE code: {ntee_code} ({current_request}/{total_requests})")
                
                # Search ProPublica API
                nonprofits = self.discovery.search_propublica(
                    state=state,
                    ntee_code=ntee_code
                )
                
                if nonprofits:
                    logger.success(f"    ✅ Found {len(nonprofits)} organizations")
                    all_nonprofits.extend(nonprofits)
                    successful_requests += 1
                elif nonprofits is not None and len(nonprofits) == 0:
                    # API succeeded but returned no results
                    logger.info(f"    ⚠️  No organizations found")
                    skipped_requests += 1
                else:
                    # API failed
                    logger.warning(f"    ❌ API request failed (continuing...)")
                    failed_requests += 1
                
                # Rate limiting
                time.sleep(1.0)
        
        # Summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("DISCOVERY SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total requests: {total_requests}")
        logger.info(f"Successful: {successful_requests} ({successful_requests/total_requests*100:.1f}%)")
        logger.info(f"No results: {skipped_requests}")
        logger.info(f"Failed: {failed_requests}")
        logger.info(f"Total nonprofits discovered: {len(all_nonprofits)}")
        logger.info("=" * 60)
        logger.info("")
        
        if not all_nonprofits:
            logger.error("No nonprofits discovered! All API requests failed or returned no results.")
            logger.info("This could be due to:")
            logger.info("  1. ProPublica API server issues (500 errors)")
            logger.info("  2. Network connectivity problems")
            logger.info("  3. No nonprofits in specified states/NTEE codes")
            logger.info("")
            logger.info("Suggestions:")
            logger.info("  - Try again later (API may be experiencing issues)")
            logger.info("  - Try different states: --states AL CA TX NY")
            logger.info("  - Check if cached data exists and use --skip-discovery")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(all_nonprofits)
        
        # Remove duplicates by EIN
        if 'ein' in df.columns:
            original_count = len(df)
            df = df.drop_duplicates(subset=['ein'], keep='first')
            logger.info(f"Removed {original_count - len(df)} duplicates")
        
        logger.success(f"Total unique nonprofits discovered: {len(df):,}")
        
        # Save to bronze layer
        bronze_path = self.bronze_dir / "discovered_nonprofits.parquet"
        df.to_parquet(bronze_path, index=False)
        logger.info(f"Saved to bronze layer: {bronze_path}")
        
        return df
    
    def create_nonprofits_organizations(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create nonprofits_organizations gold table
        
        Columns: ein, organization_name, ntee_code, city, state, zip_code,
                 tax_period, ruling_date, subsection_code
        """
        logger.info("Creating nonprofits_organizations gold table...")
        
        org_data = []
        
        for _, row in df.iterrows():
            org_data.append({
                'ein': row.get('ein'),
                'organization_name': row.get('name') or row.get('organization_name'),
                'ntee_code': row.get('ntee_code'),
                'ntee_description': row.get('ntee_description'),
                'city': row.get('city'),
                'state': row.get('state'),
                'zip_code': row.get('zipcode') or row.get('zip_code'),
                'tax_period': row.get('tax_period'),
                'ruling_date': row.get('ruling_date'),
                'subsection_code': row.get('subsection_code'),
                'website': row.get('website'),
                'mission': row.get('mission'),
            })
        
        org_df = pd.DataFrame(org_data)
        
        # Save to parquet
        output_path = self.gold_dir / "nonprofits_organizations.parquet"
        org_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(org_df):,} records")
        
        return org_df
    
    def create_nonprofits_financials(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create nonprofits_financials gold table
        
        Financial data from IRS Form 990
        """
        logger.info("Creating nonprofits_financials gold table...")
        
        financial_data = []
        
        for _, row in df.iterrows():
            financial_data.append({
                'ein': row.get('ein'),
                'organization_name': row.get('name') or row.get('organization_name'),
                'tax_year': calendar_year_label(row.get('tax_period')),
                'total_revenue': row.get('revenue_amount'),
                'total_assets': row.get('asset_amount'),
                'total_expenses': row.get('income_amount'),  # Often mislabeled in APIs
                'filing_type': row.get('filing_type'),
                'asset_code': row.get('asset_code'),
                'income_code': row.get('income_code'),
            })
        
        financial_df = pd.DataFrame(financial_data)
        
        # Save to parquet
        output_path = self.gold_dir / "nonprofits_financials.parquet"
        financial_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(financial_df):,} records")
        
        return financial_df
    
    def create_nonprofits_programs(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create nonprofits_programs gold table
        
        Programs and services offered by nonprofits
        """
        logger.info("Creating nonprofits_programs gold table...")
        
        program_data = []
        
        # Map NTEE codes to program categories
        ntee_program_mapping = {
            'E': 'Health Services',
            'P': 'Human Services',
            'K': 'Food & Agriculture',
            'L': 'Housing & Shelter',
            'S': 'Community Development',
            'W': 'Public Affairs',
            'B': 'Education',
            'A': 'Arts & Culture',
            'C': 'Environment',
            'D': 'Animal Welfare',
        }
        
        for _, row in df.iterrows():
            ntee_code = str(row.get('ntee_code', ''))[:1]  # First letter
            program_category = ntee_program_mapping.get(ntee_code, 'Other')
            
            program_data.append({
                'ein': row.get('ein'),
                'organization_name': row.get('name') or row.get('organization_name'),
                'ntee_code': row.get('ntee_code'),
                'program_category': program_category,
                'ntee_description': row.get('ntee_description'),
                'mission': row.get('mission'),
            })
        
        program_df = pd.DataFrame(program_data)
        
        # Save to parquet
        output_path = self.gold_dir / "nonprofits_programs.parquet"
        program_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(program_df):,} records")
        
        return program_df
    
    def create_nonprofits_locations(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create nonprofits_locations gold table
        
        Geographic location and service areas
        """
        logger.info("Creating nonprofits_locations gold table...")
        
        location_data = []
        
        for _, row in df.iterrows():
            location_data.append({
                'ein': row.get('ein'),
                'organization_name': row.get('name') or row.get('organization_name'),
                'address': row.get('street_address') or row.get('address'),
                'city': row.get('city'),
                'state': row.get('state'),
                'zip_code': row.get('zipcode') or row.get('zip_code'),
                'county': row.get('county'),
                'latitude': row.get('latitude'),
                'longitude': row.get('longitude'),
            })
        
        location_df = pd.DataFrame(location_data)
        
        # Save to parquet
        output_path = self.gold_dir / "nonprofits_locations.parquet"
        location_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(location_df):,} records")
        
        return location_df
    
    def create_nonprofits_fundraisers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create nonprofits_fundraisers gold table
        
        Fundraising campaigns and donation info from Every.org enrichment
        """
        logger.info("Creating nonprofits_fundraisers gold table...")
        
        fundraiser_data = []
        
        for _, row in df.iterrows():
            # Only include if has Every.org data
            if pd.notna(row.get('profile_url')) or pd.notna(row.get('is_disbursable')):
                fundraiser_data.append({
                    'ein': row.get('ein'),
                    'organization_name': row.get('name') or row.get('organization_name'),
                    'everyorg_slug': row.get('primary_slug'),
                    'profile_url': row.get('profile_url'),
                    'is_disbursable': row.get('is_disbursable'),
                    'causes': row.get('causes'),
                    'logo_url': row.get('logo_url'),
                    'cover_image_url': row.get('cover_image_url'),
                })
        
        fundraiser_df = pd.DataFrame(fundraiser_data)
        
        # Save to parquet
        output_path = self.gold_dir / "nonprofits_fundraisers.parquet"
        fundraiser_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(fundraiser_df):,} records")
        
        return fundraiser_df
    
    def create_all_gold_tables(
        self,
        states: Optional[List[str]] = None,
        ntee_codes: Optional[List[str]] = None,
        skip_discovery: bool = False,
        use_irs_data: bool = False,
        download_all_irs: bool = False
    ):
        """
        Main pipeline: Discover nonprofits and create all gold tables
        
        Args:
            states: List of state codes to search (default: ["AL", "MI"])
            ntee_codes: NTEE codes to filter (None=default, []=all nonprofits)
            skip_discovery: If True, load from existing bronze data instead of API
            use_irs_data: If True, download from IRS EO-BMF instead of ProPublica API
            download_all_irs: If True with use_irs_data, download ALL 1.9M+ nonprofits
        """
        logger.info("=" * 60)
        logger.info("NONPROFIT DISCOVERY AND GOLD TABLE CREATION")
        logger.info("=" * 60)
        
        # Default states
        if states is None:
            states = ["AL", "MI"]  # Alabama and Michigan as examples
        
        # Step 1: Discover or load nonprofit data
        if skip_discovery:
            logger.info("Skipping discovery, loading from bronze layer...")
            bronze_path = self.bronze_dir / "discovered_nonprofits.parquet"
            if bronze_path.exists():
                df = pd.read_parquet(bronze_path)
                logger.info(f"Loaded {len(df):,} nonprofits from bronze layer")
            else:
                logger.error("No bronze data found! Run with skip_discovery=False first.")
                return
        elif use_irs_data:
            # Use IRS EO-BMF bulk data (RECOMMENDED - gets ALL nonprofits!)
            logger.info("Using IRS EO-BMF bulk data source...")
            df = self.discover_nonprofits_from_irs(
                states=states if not download_all_irs else None,
                ntee_codes=ntee_codes,
                download_all=download_all_irs
            )
        else:
            # Use ProPublica API (limited to 25 results per request)
            logger.info("Using ProPublica API...")
            df = self.discover_nonprofits_by_state(states, ntee_codes)
        
        if df.empty:
            logger.error("No nonprofit data available. Exiting.")
            return
        
        # Step 2: Create all gold tables
        self.create_nonprofits_organizations(df)
        self.create_nonprofits_financials(df)
        self.create_nonprofits_programs(df)
        self.create_nonprofits_locations(df)
        self.create_nonprofits_fundraisers(df)
        
        logger.success("=" * 60)
        logger.success("ALL NONPROFIT GOLD TABLES CREATED!")
        logger.success("=" * 60)
        
        # Show summary
        gold_files = list(self.gold_dir.glob("nonprofits_*.parquet"))
        logger.info(f"\nCreated {len(gold_files)} gold tables:")
        for file in sorted(gold_files):
            df_check = pd.read_parquet(file)
            logger.info(f"  - {file.name}: {len(df_check):,} records")


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Discover nonprofits and create gold tables")
    parser.add_argument(
        "--states",
        nargs="+",
        default=["AL", "MI"],
        help="State codes to search (e.g., AL MI NY)"
    )
    parser.add_argument(
        "--skip-discovery",
        action="store_true",
        help="Skip API discovery, use existing bronze data"
    )
    
    args = parser.parse_args()
    
    creator = NonprofitGoldTableCreator()
    creator.create_all_gold_tables(
        states=args.states,
        skip_discovery=args.skip_discovery
    )


if __name__ == "__main__":
    main()
