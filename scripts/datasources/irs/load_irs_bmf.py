"""
IRS Business Master File (EO-BMF) Ingestion

Downloads and processes the complete IRS Exempt Organizations Business Master File.
This provides ALL 1.9M+ tax-exempt organizations in the United States.

Data Source: https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf

Key Features:
- Complete coverage of all U.S. tax-exempt organizations
- Updated monthly by the IRS
- Includes NTEE codes, financial data, subsection classification
- Available by state or region (4 regional files)
- CSV format, ~1.9M+ records total

Author: Open Navigator
License: MIT
"""

import requests
import pandas as pd
from pathlib import Path
from loguru import logger
from typing import List, Optional, Dict
import time
from io import StringIO
from datetime import datetime

class IRSBMFIngestion:
    """
    Download and process IRS Business Master File data
    """
    
    # IRS EO-BMF file URLs
    BASE_URL = "https://www.irs.gov/pub/irs-soi"
    
    # Regional files (fastest download - 4 files vs 50+ state files)
    REGIONAL_FILES = {
        "region1": f"{BASE_URL}/eo1.csv",  # Northeast
        "region2": f"{BASE_URL}/eo2.csv",  # Mid-Atlantic & Great Lakes
        "region3": f"{BASE_URL}/eo3.csv",  # Gulf Coast & Pacific
        "region4": f"{BASE_URL}/eo4.csv",  # All other
    }
    
    # State-specific files (2-letter state codes)
    STATE_CODES = [
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
        "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
        "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
        "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
        "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
    ]
    
    def __init__(self, cache_dir: str = "data/cache/irs_bmf"):
        """
        Initialize IRS BMF ingestion client
        
        Args:
            cache_dir: Directory to cache downloaded files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"IRS BMF cache directory: {self.cache_dir}")
    
    def download_regional_file(self, region: str, force_refresh: bool = False) -> pd.DataFrame:
        """
        Download a regional EO-BMF file
        
        Args:
            region: Region name (region1, region2, region3, region4)
            force_refresh: If True, re-download even if cached
            
        Returns:
            DataFrame with nonprofit data
        """
        if region not in self.REGIONAL_FILES:
            raise ValueError(f"Invalid region: {region}. Must be one of {list(self.REGIONAL_FILES.keys())}")
        
        url = self.REGIONAL_FILES[region]
        cache_file = self.cache_dir / f"{region}.parquet"
        
        # Return cached data if available
        if cache_file.exists() and not force_refresh:
            logger.info(f"Loading {region} from cache: {cache_file}")
            return pd.read_parquet(cache_file)
        
        # Download from IRS
        logger.info(f"Downloading {region} from IRS: {url}")
        logger.info("This may take a few minutes on first download...")
        
        try:
            response = requests.get(url, timeout=300)  # 5 minute timeout
            response.raise_for_status()
            
            # Parse CSV
            df = pd.read_csv(StringIO(response.text), dtype=str)
            logger.success(f"Downloaded {len(df):,} organizations from {region}")
            
            # Standardize column names (IRS uses uppercase)
            df.columns = df.columns.str.lower()
            
            # Cache to parquet for fast future loading
            df.to_parquet(cache_file, index=False)
            logger.info(f"Cached to: {cache_file}")
            
            return df
            
        except requests.RequestException as e:
            logger.error(f"Failed to download {region}: {e}")
            raise
    
    def download_state_file(self, state: str, force_refresh: bool = False) -> pd.DataFrame:
        """
        Download state-specific EO-BMF file
        
        Args:
            state: 2-letter state code (e.g., "AL", "CA")
            force_refresh: If True, re-download even if cached
            
        Returns:
            DataFrame with nonprofit data for that state
        """
        state = state.upper()
        if state not in self.STATE_CODES:
            raise ValueError(f"Invalid state: {state}. Must be 2-letter state code.")
        
        url = f"{self.BASE_URL}/eo_{state.lower()}.csv"
        cache_file = self.cache_dir / f"state_{state}.parquet"
        
        # Return cached data if available
        if cache_file.exists() and not force_refresh:
            logger.info(f"Loading {state} from cache: {cache_file}")
            return pd.read_parquet(cache_file)
        
        # Download from IRS
        logger.info(f"Downloading {state} from IRS: {url}")
        
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            # Parse CSV
            df = pd.read_csv(StringIO(response.text), dtype=str)
            logger.success(f"Downloaded {len(df):,} organizations from {state}")
            
            # Standardize column names
            df.columns = df.columns.str.lower()
            
            # Cache to parquet
            df.to_parquet(cache_file, index=False)
            logger.info(f"Cached to: {cache_file}")
            
            return df
            
        except requests.RequestException as e:
            logger.error(f"Failed to download {state}: {e}")
            raise
    
    def download_all_regions(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Download ALL regional files and combine (fastest way to get all 1.9M+ orgs)
        
        Args:
            force_refresh: If True, re-download even if cached
            
        Returns:
            Combined DataFrame with all U.S. nonprofits
        """
        logger.info("=" * 60)
        logger.info("DOWNLOADING ALL IRS EO-BMF DATA (1.9M+ organizations)")
        logger.info("=" * 60)
        
        all_data = []
        
        for region in self.REGIONAL_FILES.keys():
            df = self.download_regional_file(region, force_refresh)
            all_data.append(df)
            time.sleep(1)  # Be nice to IRS servers
        
        # Combine all regions
        combined = pd.concat(all_data, ignore_index=True)
        logger.success(f"Combined total: {len(combined):,} organizations")
        
        # Cache combined dataset
        combined_file = self.cache_dir / "all_regions_combined.parquet"
        combined.to_parquet(combined_file, index=False)
        logger.info(f"Cached combined dataset to: {combined_file}")
        
        return combined
    
    def download_states(self, states: List[str], force_refresh: bool = False) -> pd.DataFrame:
        """
        Download multiple state files and combine
        
        Args:
            states: List of 2-letter state codes
            force_refresh: If True, re-download even if cached
            
        Returns:
            Combined DataFrame
        """
        all_data = []
        
        for state in states:
            df = self.download_state_file(state, force_refresh)
            all_data.append(df)
            time.sleep(0.5)  # Rate limiting
        
        combined = pd.concat(all_data, ignore_index=True)
        logger.success(f"Combined {len(states)} states: {len(combined):,} organizations")
        
        return combined
    
    def filter_by_ntee(self, df: pd.DataFrame, ntee_codes: List[str]) -> pd.DataFrame:
        """
        Filter organizations by NTEE code prefix
        
        Args:
            df: DataFrame with 'ntee_cd' column
            ntee_codes: List of NTEE code prefixes (e.g., ["E", "P", "K"])
            
        Returns:
            Filtered DataFrame
        """
        if 'ntee_cd' not in df.columns:
            logger.warning("No 'ntee_cd' column found in data")
            return df
        
        # Filter to rows where NTEE code starts with any of the prefixes
        mask = df['ntee_cd'].fillna('').str.upper().str.startswith(tuple(ntee_codes))
        filtered = df[mask].copy()
        
        logger.info(f"Filtered {len(df):,} → {len(filtered):,} organizations by NTEE codes: {ntee_codes}")
        return filtered
    
    def filter_by_state(self, df: pd.DataFrame, states: List[str]) -> pd.DataFrame:
        """
        Filter organizations by state
        
        Args:
            df: DataFrame with 'state' column
            states: List of 2-letter state codes
            
        Returns:
            Filtered DataFrame
        """
        if 'state' not in df.columns:
            logger.warning("No 'state' column found in data")
            return df
        
        states_upper = [s.upper() for s in states]
        filtered = df[df['state'].str.upper().isin(states_upper)].copy()
        
        logger.info(f"Filtered {len(df):,} → {len(filtered):,} organizations by states: {states}")
        return filtered
    
    def standardize_to_propublica_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert IRS EO-BMF format to match ProPublica API schema
        
        This allows seamless integration with existing nonprofit pipeline.
        
        Returns:
            DataFrame with ProPublica-compatible schema
        """
        logger.info("Converting IRS EO-BMF to ProPublica-compatible format...")
        
        # Map IRS columns to ProPublica schema
        standardized = pd.DataFrame({
            'ein': df.get('ein', ''),
            'name': df.get('name', ''),
            'city': df.get('city', ''),
            'state': df.get('state', ''),
            'ntee_code': df.get('ntee_cd', ''),
            'subsection_code': df.get('subsection', ''),  # e.g., "03" = 501(c)(3)
            'street_address': df.get('street', ''),
            'zip_code': df.get('zip', ''),
            'asset_amount': pd.to_numeric(df.get('asset_amt', 0), errors='coerce').fillna(0),
            'income_amount': pd.to_numeric(df.get('income_amt', 0), errors='coerce').fillna(0),
            'ruling_date': df.get('ruling', ''),
            'deductibility_status': df.get('deductibility', ''),
            'foundation_code': df.get('foundation', ''),
            'activity_codes': df.get('activity', ''),
            'organization_code': df.get('organization', ''),
            'exempt_org_status_code': df.get('status', ''),
            'tax_period': df.get('tax_period', ''),
            'sort_name': df.get('sort_name', ''),
            'data_source': 'IRS_EO_BMF',
            'irs_last_updated': datetime.utcnow().isoformat()
        })
        
        logger.success(f"Standardized {len(standardized):,} organizations")
        return standardized


def demo_download_state():
    """Demo: Download single state (Alabama)"""
    logger.info("=== DEMO: Download Alabama nonprofits ===")
    
    irs = IRSBMFIngestion()
    df = irs.download_state_file("AL")
    
    print(f"\nDownloaded {len(df):,} Alabama nonprofits")
    print(f"Columns: {list(df.columns)}")
    print("\nSample data:")
    print(df.head())
    
    # Filter to health organizations
    if 'ntee_cd' in df.columns:
        health = irs.filter_by_ntee(df, ["E"])
        print(f"\nHealth organizations (NTEE E): {len(health):,}")


def demo_download_all():
    """Demo: Download ALL 1.9M+ nonprofits"""
    logger.info("=== DEMO: Download ALL U.S. nonprofits ===")
    
    irs = IRSBMFIngestion()
    df = irs.download_all_regions()
    
    print(f"\nTotal nonprofits: {len(df):,}")
    print(f"Columns: {list(df.columns)}")
    
    # Show breakdown by NTEE category
    if 'ntee_cd' in df.columns:
        print("\nTop 10 NTEE categories:")
        ntee_counts = df['ntee_cd'].fillna('Unknown').str[0].value_counts().head(10)
        print(ntee_counts)
    
    # Convert to ProPublica format
    standardized = irs.standardize_to_propublica_format(df)
    print("\nStandardized to ProPublica format:")
    print(standardized.head())


if __name__ == "__main__":
    # Run demo (single state is faster for testing)
    demo_download_state()
    
    # Uncomment to download ALL 1.9M+ orgs (takes ~5-10 minutes)
    # demo_download_all()
