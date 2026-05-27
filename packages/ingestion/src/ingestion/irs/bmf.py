"""
IRS Business Master File (EO-BMF) Ingestion → Bronze Table

Downloads and loads the complete IRS Exempt Organizations Business Master File
into the bronze_organizations_nonprofits_irs table.

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
import psycopg2
from psycopg2.extras import execute_values

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


def create_bronze_table(cursor):
    """Create bronze.bronze_organizations_nonprofits_irs table"""
    cursor.execute("""
        CREATE SCHEMA IF NOT EXISTS bronze;
        CREATE TABLE IF NOT EXISTS bronze.bronze_organizations_nonprofits_irs (
            id SERIAL PRIMARY KEY,
            ein VARCHAR(20) NOT NULL,
            name TEXT,
            ico VARCHAR(100),
            street VARCHAR(255),
            city VARCHAR(100),
            state_code VARCHAR(2),
            zip_code VARCHAR(20),
            group_exemption VARCHAR(20),
            subsection VARCHAR(20),
            affiliation VARCHAR(20),
            classification VARCHAR(20),
            ruling VARCHAR(20),
            deductibility VARCHAR(50),
            foundation VARCHAR(20),
            activity VARCHAR(200),
            organization VARCHAR(20),
            status VARCHAR(20),
            tax_period VARCHAR(20),
            asset_cd VARCHAR(20),
            income_cd VARCHAR(20),
            filing_req_cd VARCHAR(20),
            pf_filing_req_cd VARCHAR(20),
            acct_pd VARCHAR(20),
            asset_amt BIGINT,
            income_amt BIGINT,
            revenue_amt BIGINT,
            ntee_cd VARCHAR(20),
            sort_name VARCHAR(255),
            country VARCHAR(20),
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(ein)
        );

        CREATE INDEX IF NOT EXISTS idx_bronze_irs_state ON bronze.bronze_organizations_nonprofits_irs(state_code);
        CREATE INDEX IF NOT EXISTS idx_bronze_irs_city  ON bronze.bronze_organizations_nonprofits_irs(city, state_code);
        CREATE INDEX IF NOT EXISTS idx_bronze_irs_ntee  ON bronze.bronze_organizations_nonprofits_irs(ntee_cd);
        CREATE INDEX IF NOT EXISTS idx_bronze_irs_name  ON bronze.bronze_organizations_nonprofits_irs USING gin(to_tsvector('english', name));
    """)
    logger.success("✅ Created bronze.bronze_organizations_nonprofits_irs table")


def load_to_bronze(df: pd.DataFrame, db_url: str = None):
    """
    Load IRS BMF data into bronze table
    
    Args:
        df: DataFrame with IRS BMF data
        db_url: PostgreSQL connection string
    """
    import os
    if db_url is None:
        password = os.getenv("POSTGRES_PASSWORD", "password")
        db_url = f"postgresql://postgres:{password}@localhost:5433/open_navigator"

    logger.info(f"💾 Loading {len(df):,} organizations to bronze.bronze_organizations_nonprofits_irs...")

    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    try:
        # Create table
        create_bronze_table(cursor)
        conn.commit()
        
        # Prepare data for insertion - FAST vectorized approach
        logger.info("  Converting numeric columns...")
        
        # Convert numeric columns in place (much faster than row-by-row)
        numeric_cols = ['asset_amt', 'income_amt', 'revenue_amt']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                # Convert to Int64 (nullable integer) to handle NaN properly
                df[col] = df[col].astype('Int64')
        
        # Fill NaN with None for proper NULL handling in PostgreSQL
        df_clean = df.where(pd.notna(df), None)
        
        # Batch insert query
        insert_query = """
            INSERT INTO bronze.bronze_organizations_nonprofits_irs (
                ein, name, ico, street, city, state_code, zip_code,
                group_exemption, subsection, affiliation, classification,
                ruling, deductibility, foundation, activity, organization,
                status, tax_period, asset_cd, income_cd, filing_req_cd,
                pf_filing_req_cd, acct_pd, asset_amt, income_amt, revenue_amt,
                ntee_cd, sort_name, country
            ) VALUES %s
            ON CONFLICT (ein) DO UPDATE SET
                name = EXCLUDED.name,
                city = EXCLUDED.city,
                state_code = EXCLUDED.state_code,
                ntee_cd = EXCLUDED.ntee_cd,
                asset_amt = EXCLUDED.asset_amt,
                income_amt = EXCLUDED.income_amt,
                revenue_amt = EXCLUDED.revenue_amt,
                loaded_at = CURRENT_TIMESTAMP
        """
        
        # Process in batches to avoid memory issues with large datasets
        batch_size = 50000
        total_rows = len(df_clean)
        num_batches = (total_rows + batch_size - 1) // batch_size
        
        logger.info(f"  Inserting {total_rows:,} records in {num_batches} batches of {batch_size:,}...")
        
        for batch_num in range(num_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_rows)
            
            logger.info(f"  Batch {batch_num + 1}/{num_batches}: rows {start_idx:,} to {end_idx:,}")
            
            # Get batch slice
            batch_df = df_clean.iloc[start_idx:end_idx]
            logger.info(f"  Sliced {len(batch_df)} rows for batch")
            
            # Convert batch to records
            logger.info(f"  Converting batch to records...")
            records = []
            for row in batch_df.to_dict('records'):
                # Convert pandas NA to None
                def safe_get(key):
                    val = row.get(key)
                    if pd.isna(val):
                        return None
                    return val
                
                records.append((
                    safe_get('ein'),
                    safe_get('name'),
                    safe_get('ico'),
                    safe_get('street'),
                    safe_get('city'),
                    safe_get('state'),
                    safe_get('zip'),
                    safe_get('group'),
                    safe_get('subsection'),
                    safe_get('affiliation'),
                    safe_get('classification'),
                    safe_get('ruling'),
                    safe_get('deductibility'),
                    safe_get('foundation'),
                    safe_get('activity'),
                    safe_get('organization'),
                    safe_get('status'),
                    safe_get('tax_period'),
                    safe_get('asset_cd'),
                    safe_get('income_cd'),
                    safe_get('filing_req_cd'),
                    safe_get('pf_filing_req_cd'),
                    safe_get('acct_pd'),
                    safe_get('asset_amt'),
                    safe_get('income_amt'),
                    safe_get('revenue_amt'),
                    safe_get('ntee_cd'),
                    safe_get('sort_name'),
                    safe_get('country'),
                ))
            
            logger.info(f"  Converted {len(records)} records, preparing to insert...")
            
            # Insert batch
            try:
                logger.info(f"  Executing INSERT for batch {batch_num + 1}...")
                execute_values(cursor, insert_query, records, page_size=1000)
                logger.info(f"  INSERT completed, committing...")
                conn.commit()
                logger.success(f"  ✅ Batch {batch_num + 1}/{num_batches} inserted ({len(records):,} records)")
            except Exception as e:
                logger.error(f"  ❌ Batch {batch_num + 1} failed: {e}")
                logger.error(f"  Exception type: {type(e).__name__}")
                logger.error(f"  Sample record from batch: {records[0] if records else 'None'}")
                import traceback
                logger.error(f"  Traceback:\n{traceback.format_exc()}")
                conn.rollback()
                raise
        
        logger.success(f"✅ All batches completed!")
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM bronze.bronze_organizations_nonprofits_irs")
        total = cursor.fetchone()[0]
        logger.success(f"✅ Loaded successfully! Total in bronze: {total:,}")
        
        # Show sample stats
        cursor.execute("""
            SELECT state_code, COUNT(*) as count
            FROM bronze.bronze_organizations_nonprofits_irs
            GROUP BY state_code
            ORDER BY count DESC
            LIMIT 10
        """)
        logger.info("📊 Top 10 states by organization count:")
        for state, count in cursor.fetchall():
            logger.info(f"   {state}: {count:,}")
        
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("IRS Business Master File → Bronze Table Loader")
    logger.info("=" * 60)
    
    # Initialize ingestion client
    ingestion = IRSBMFIngestion()
    
    # Download all regions (fastest - 4 files instead of 50+ states)
    logger.info("📥 Downloading all IRS regions (1.9M+ organizations)...")
    df = ingestion.download_all_regions(force_refresh=False)
    
    logger.info(f"📋 Downloaded {len(df):,} organizations")
    logger.info(f"📋 Columns: {list(df.columns)}")
    
    # Load to bronze table
    load_to_bronze(df)
    
    logger.info("=" * 60)
    logger.success("✅ IRS BMF data loaded to bronze!")
    logger.info("=" * 60)
