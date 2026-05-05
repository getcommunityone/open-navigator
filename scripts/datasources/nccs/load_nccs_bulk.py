#!/usr/bin/env python3
"""
NCCS (National Center for Charitable Statistics) → Bronze Table Loader

Downloads Unified BMF (Business Master File) data from the National Center for Charitable Statistics
and loads it into the bronze_organizations_nonprofits_nccs table.

This provides historical nonprofit data (1989-2025) with one row per organization,
enriched with additional metadata not available in raw IRS files.

Directory Structure:
    /mnt/d/nccs_data/  (or configurable base path)
    ├── unified-bmf/
    │   ├── v1.2/
    │   │   ├── full/
    │   │   │   └── UNIFIED_BMF_V1.2.csv
    │   │   └── by-state/
    │   │       ├── AL.csv
    │   │       ├── CA.csv
    │   │       └── ...

Data Sources:
    - Unified BMF: Historical data (1989-2025) with one row per organization

Website: https://urbaninstitute.github.io/nccs/catalogs/catalog-bmf.html

Usage:
    # Download and load to bronze
    python load_nccs_bulk.py

    # Custom base directory
    python load_nccs_bulk.py --base-dir /mnt/d/nccs_data

    # Download specific states only
    python load_nccs_bulk.py --states CA,NY,TX
"""

import argparse
import json
import requests
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from loguru import logger
import time
from tqdm import tqdm
from bs4 import BeautifulSoup
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


class NCCSBulkDownloader:
    """Download and organize NCCS BMF data files"""
    
    BASE_URL = "https://nccsdata.s3.us-east-1.amazonaws.com"
    CATALOG_URL = "https://urbaninstitute.github.io/nccs/catalogs/catalog-bmf.html"
    
    # US States and Territories
    STATES = {
        'AK': 'Alaska', 'AL': 'Alabama', 'AR': 'Arkansas', 'AS': 'American Samoa',
        'AZ': 'Arizona', 'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut',
        'DC': 'District of Columbia', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
        'GU': 'Guam', 'HI': 'Hawaii', 'IA': 'Iowa', 'ID': 'Idaho', 'IL': 'Illinois',
        'IN': 'Indiana', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana',
        'MA': 'Massachusetts', 'MD': 'Maryland', 'ME': 'Maine', 'MI': 'Michigan',
        'MN': 'Minnesota', 'MO': 'Missouri', 'MP': 'Northern Mariana Islands',
        'MS': 'Mississippi', 'MT': 'Montana', 'NC': 'North Carolina', 'ND': 'North Dakota',
        'NE': 'Nebraska', 'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico',
        'NV': 'Nevada', 'NY': 'New York', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon',
        'PA': 'Pennsylvania', 'PR': 'Puerto Rico', 'RI': 'Rhode Island', 'SC': 'South Carolina',
        'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
        'VA': 'Virginia', 'VI': 'U.S. Virgin Islands', 'VT': 'Vermont', 'WA': 'Washington',
        'WI': 'Wisconsin', 'WV': 'West Virginia', 'WY': 'Wyoming', 'ZZ': 'Unmapped'
    }
    
    # Transformed BMF available months (June 2023 - Jan 2026)
    TRANSFORMED_MONTHS = [
        '2023_06', '2023_07', '2023_08', '2023_09', '2023_10', '2023_11', '2023_12',
        '2024_01', '2024_02', '2024_03', '2024_04', '2024_05', '2024_06', '2024_07',
        '2024_08', '2024_09', '2024_10', '2024_11', '2024_12',
        '2025_01', '2025_02', '2025_03', '2025_04', '2025_05', '2025_06', '2025_07',
        '2025_08', '2025_09', '2025_10', '2025_11', '2025_12',
        '2026_01'
    ]
    
    # Raw BMF available months (June 2023 - Jan 2026)
    RAW_MONTHS = [
        '2023-06', '2023-07', '2023-08', '2023-09', '2023-10', '2023-11', '2023-12',
        '2024-01', '2024-02', '2024-03', '2024-04', '2024-05', '2024-06', '2024-07',
        '2024-08', '2024-09', '2024-10', '2024-11', '2024-12',
        '2025-01', '2025-02', '2025-03', '2025-04', '2025-05', '2025-06', '2025-07',
        '2025-08', '2025-09', '2025-10', '2025-11', '2025-12',
        '2026-01'
    ]
    
    def __init__(self, base_dir: Path, resume: bool = False):
        """
        Initialize NCCS bulk downloader
        
        Args:
            base_dir: Base directory for downloads (e.g., /mnt/d/nccs_data/)
            resume: Resume interrupted downloads
        """
        self.base_dir = Path(base_dir)
        self.unified_dir = self.base_dir / "unified-bmf" / "v1.2"
        self.transformed_dir = self.base_dir / "transformed-bmf"
        self.raw_dir = self.base_dir / "raw-bmf"
        self.log_file = self.base_dir / "download_log.json"
        self.resume = resume
        
        # Create directories
        self.base_dir.mkdir(parents=True, exist_ok=True)
        (self.unified_dir / "full").mkdir(parents=True, exist_ok=True)
        (self.unified_dir / "by-state").mkdir(parents=True, exist_ok=True)
        (self.unified_dir / "data-dictionary").mkdir(parents=True, exist_ok=True)
        self.transformed_dir.mkdir(exist_ok=True)
        self.raw_dir.mkdir(exist_ok=True)
        
        # Load download log
        self.download_log = self._load_log()
        
        # Session for HTTP requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (NCCS Bulk Downloader/1.0)'
        })
    
    def _load_log(self) -> Dict:
        """Load download log"""
        if self.log_file.exists():
            with open(self.log_file) as f:
                return json.load(f)
        return {
            'started': datetime.now().isoformat(),
            'last_updated': None,
            'completed_files': {},
            'failed_files': {},
        }
    
    def _save_log(self):
        """Save download log"""
        self.download_log['last_updated'] = datetime.now().isoformat()
        with open(self.log_file, 'w') as f:
            json.dump(self.download_log, f, indent=2)
    
    def _discover_state_files(self) -> Dict[str, Tuple[str, str]]:
        """
        Scrape the NCCS catalog page to discover actual state file URLs
        
        Returns:
            Dict mapping state codes to (url, state_name) tuples
        """
        logger.info("🔍 Discovering state file URLs from catalog page...")
        
        try:
            response = self.session.get(self.CATALOG_URL, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            state_files = {}
            
            # Find all download buttons (class="button")
            # They're in table rows with state names in adjacent cells
            for link in soup.find_all('a', class_='button'):
                href = link.get('href', '')
                
                # Look for Unified BMF state files (pattern: {STATE_CODE}_BMF_V*.csv)
                if '/bmf/unified/' in href and '_BMF_' in href and href.endswith('.csv'):
                    # Extract state code from filename (e.g., AL_BMF_V1.1.csv -> AL)
                    filename = href.split('/')[-1]
                    state_code = filename.split('_')[0].upper()
                    
                    # Find the state name in the same table row
                    row = link.find_parent('tr')
                    if row:
                        cells = row.find_all('td')
                        # Usually: [DOWNLOAD button, file size, state name]
                        if len(cells) >= 3:
                            state_name = cells[2].get_text(strip=True)
                        else:
                            # Fallback to state code lookup
                            state_name = self.STATES.get(state_code, state_code)
                    else:
                        state_name = self.STATES.get(state_code, state_code)
                    
                    # Ensure URL is absolute
                    if not href.startswith('http'):
                        href = f"https:{href}" if href.startswith('//') else f"https://nccsdata.s3.amazonaws.com{href}"
                    
                    state_files[state_code] = (href, state_name)
            
            logger.info(f"✅ Discovered {len(state_files)} state files from catalog")
            
            # Debug: show a few examples
            if state_files:
                examples = list(state_files.items())[:3]
                for code, (url, name) in examples:
                    logger.debug(f"   {code} ({name}): {url}")
            
            return state_files
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to scrape catalog page: {e}")
            logger.info("   Falling back to constructed URLs...")
            return {}
    
    def _is_downloaded(self, url: str, dest_path: Path) -> bool:
        """Check if file is already downloaded (always checks, not just in resume mode)"""
        # Always skip if file exists and has reasonable size (> 1KB)
        if dest_path.exists() and dest_path.stat().st_size > 1024:
            return True
        
        return False
    
    def _download_file(self, url: str, dest_path: Path, description: str) -> bool:
        """
        Download a single file with progress bar
        
        Args:
            url: URL to download
            dest_path: Destination file path
            description: Description for progress bar
        
        Returns:
            True if successful, False otherwise
        """
        if self._is_downloaded(url, dest_path):
            logger.info(f"⏭️  Skipping (already downloaded): {dest_path.name}")
            return True
        
        try:
            # Get file size
            response = self.session.head(url, allow_redirects=True, timeout=30)
            total_size = int(response.headers.get('content-length', 0))
            
            # Download with progress bar
            response = self.session.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(dest_path, 'wb') as f:
                with tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    desc=description,
                    leave=False
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            
            # Log success
            self.download_log['completed_files'][url] = {
                'path': str(dest_path),
                'size': dest_path.stat().st_size,
                'downloaded_at': datetime.now().isoformat(),
            }
            self._save_log()
            
            logger.success(f"✅ Downloaded: {dest_path.name} ({total_size:,} bytes)")
            return True
            
        except requests.exceptions.HTTPError as e:
            # Handle 403/404 as "file not available" rather than fatal error
            if e.response.status_code in [403, 404]:
                logger.warning(f"⚠️  File not available (skipping): {dest_path.name}")
                self.download_log['failed_files'][url] = {
                    'error': f"HTTP {e.response.status_code}: File not available on server",
                    'failed_at': datetime.now().isoformat(),
                }
                self._save_log()
                return False
            else:
                logger.error(f"❌ Failed to download {url}: {e}")
                self.download_log['failed_files'][url] = {
                    'error': str(e),
                    'failed_at': datetime.now().isoformat(),
                }
                self._save_log()
                return False
        except Exception as e:
            logger.error(f"❌ Failed to download {url}: {e}")
            self.download_log['failed_files'][url] = {
                'error': str(e),
                'failed_at': datetime.now().isoformat(),
            }
            self._save_log()
            return False
    
    def download_unified_bmf(
        self,
        states: Optional[List[str]] = None,
        download_full: bool = True,
        dry_run: bool = False
    ):
        """
        Download Unified BMF files
        
        Args:
            states: Optional list of state codes (e.g., ['CA', 'NY'])
            download_full: Also download full unified BMF file
            dry_run: If True, only show what would be downloaded
        """
        files_to_download = []
        
        # Data dictionary (always download)
        dict_url = f"{self.BASE_URL}/harmonized/harmonized_data_dictionary.xlsx"
        dict_path = self.unified_dir / "data-dictionary" / "harmonized_data_dictionary.xlsx"
        files_to_download.append({
            'url': dict_url,
            'path': dict_path,
            'description': 'Data Dictionary',
            'type': 'dictionary'
        })
        
        # Full unified BMF
        if download_full:
            full_url = f"{self.BASE_URL}/bmf/unified/v1.2/UNIFIED_BMF_V1.2.csv"
            full_path = self.unified_dir / "full" / "UNIFIED_BMF_V1.2.csv"
            files_to_download.append({
                'url': full_url,
                'path': full_path,
                'description': 'Full Unified BMF',
                'type': 'full'
            })
        
        # State files - discover actual URLs from catalog page
        discovered_states = self._discover_state_files()
        
        states_to_download = states if states else list(self.STATES.keys())
        if not states and discovered_states:
            # If downloading all states and we successfully discovered URLs,
            # include any additional states (like 'ZZ' Unmapped) that were found
            for state_code in discovered_states.keys():
                if state_code not in states_to_download and state_code == 'ZZ':
                    states_to_download.append(state_code)
        
        for state_code in states_to_download:
            # Try to use discovered URL first
            if state_code in discovered_states:
                state_url, state_name = discovered_states[state_code]
            elif state_code in self.STATES:
                # Fall back to constructed URL if not discovered
                state_name = self.STATES[state_code].replace(' ', '%20')
                state_url = f"{self.BASE_URL}/bmf/unified/v1.2/{state_name}.csv"
                state_name = self.STATES[state_code]
            else:
                logger.warning(f"⚠️  Unknown state code: {state_code}")
                continue
            
            state_path = self.unified_dir / "by-state" / f"{state_code}.csv"
            
            files_to_download.append({
                'url': state_url,
                'path': state_path,
                'description': f"Unified BMF - {state_name}",
                'type': 'state',
                'state': state_code
            })
        
        logger.info(f"📥 Unified BMF: {len(files_to_download)} files")
        
        if dry_run:
            logger.info("🔍 DRY RUN - Files that would be downloaded:")
            for f in files_to_download:
                type_str = f['type']
                if f['type'] == 'state':
                    type_str = f"{f['state']} ({self.STATES[f['state']]})"
                print(f"  {type_str:30} | {f['path'].name}")
            return 0, 0, 0, 0
        
        # Download files
        successful = 0
        failed = 0
        skipped = 0
        not_available = 0
        
        for i, file_info in enumerate(files_to_download, 1):
            logger.info(f"\n[{i}/{len(files_to_download)}] {file_info['description']}")
            
            if self._is_downloaded(file_info['url'], file_info['path']):
                skipped += 1
                continue
            
            success = self._download_file(
                file_info['url'],
                file_info['path'],
                file_info['description']
            )
            
            if success:
                successful += 1
            else:
                # Check if it's a 403/404 (not available) vs other error
                if file_info['url'] in self.download_log['failed_files']:
                    error = self.download_log['failed_files'][file_info['url']].get('error', '')
                    if 'not available' in error.lower() or '403' in error or '404' in error:
                        not_available += 1
                    else:
                        failed += 1
                else:
                    failed += 1
            
            # Rate limiting
            time.sleep(0.5)
        
        return successful, skipped, failed, not_available
    
    def download_transformed_bmf(
        self,
        months: Optional[List[str]] = None,
        dry_run: bool = False
    ):
        """
        Download Transformed BMF files (monthly cleaned data)
        
        Args:
            months: Optional list of months (e.g., ['2025_12', '2026_01'])
            dry_run: If True, only show what would be downloaded
        """
        files_to_download = []
        
        months_to_download = months if months else self.TRANSFORMED_MONTHS
        
        for month in months_to_download:
            if month not in self.TRANSFORMED_MONTHS:
                logger.warning(f"⚠️  Invalid month: {month}")
                continue
            
            # Data file
            data_url = f"{self.BASE_URL}/processed/bmf/{month}/bmf_{month}_processed.csv"
            data_path = self.transformed_dir / month / f"bmf_{month}_processed.csv"
            
            # Dictionary file
            dict_url = f"{self.BASE_URL}/processed/bmf/{month}/bmf_{month}_data_dictionary.csv"
            dict_path = self.transformed_dir / month / f"bmf_{month}_data_dictionary.csv"
            
            files_to_download.extend([
                {
                    'url': data_url,
                    'path': data_path,
                    'description': f"Transformed BMF {month}",
                    'type': 'data',
                    'month': month
                },
                {
                    'url': dict_url,
                    'path': dict_path,
                    'description': f"Data Dictionary {month}",
                    'type': 'dictionary',
                    'month': month
                }
            ])
        
        logger.info(f"📥 Transformed BMF: {len(files_to_download)} files")
        
        if dry_run:
            logger.info("🔍 DRY RUN - Files that would be downloaded:")
            for f in files_to_download:
                print(f"  {f['month']:10} | {f['type']:10} | {f['path'].name}")
            return 0, 0, 0, 0
        
        # Download files
        successful = 0
        failed = 0
        skipped = 0
        not_available = 0
        
        for i, file_info in enumerate(files_to_download, 1):
            logger.info(f"\n[{i}/{len(files_to_download)}] {file_info['description']}")
            
            if self._is_downloaded(file_info['url'], file_info['path']):
                skipped += 1
                continue
            
            success = self._download_file(
                file_info['url'],
                file_info['path'],
                file_info['description']
            )
            
            if success:
                successful += 1
            else:
                # Check if it's a 403/404 (not available) vs other error
                if file_info['url'] in self.download_log['failed_files']:
                    error = self.download_log['failed_files'][file_info['url']].get('error', '')
                    if 'not available' in error.lower() or '403' in error or '404' in error:
                        not_available += 1
                    else:
                        failed += 1
                else:
                    failed += 1
            
            # Rate limiting
            time.sleep(0.5)
        
        return successful, skipped, failed, not_available
    
    def download_raw_bmf(
        self,
        months: Optional[List[str]] = None,
        dry_run: bool = False
    ):
        """
        Download Raw BMF archives (unmodified IRS files)
        
        Args:
            months: Optional list of months (e.g., ['2025-12', '2026-01'])
            dry_run: If True, only show what would be downloaded
        """
        files_to_download = []
        
        months_to_download = months if months else self.RAW_MONTHS
        
        for month in months_to_download:
            if month not in self.RAW_MONTHS:
                logger.warning(f"⚠️  Invalid month: {month}")
                continue
            
            raw_url = f"{self.BASE_URL}/raw/bmf/{month}-BMF.csv"
            raw_path = self.raw_dir / f"{month}-BMF.csv"
            
            files_to_download.append({
                'url': raw_url,
                'path': raw_path,
                'description': f"Raw BMF {month}",
                'type': 'raw',
                'month': month
            })
        
        logger.info(f"📥 Raw BMF: {len(files_to_download)} files")
        
        if dry_run:
            logger.info("🔍 DRY RUN - Files that would be downloaded:")
            for f in files_to_download:
                print(f"  {f['month']:10} | {f['path'].name}")
            return 0, 0, 0, 0
        
        # Download files
        successful = 0
        failed = 0
        skipped = 0
        not_available = 0
        
        for i, file_info in enumerate(files_to_download, 1):
            logger.info(f"\n[{i}/{len(files_to_download)}] {file_info['description']}")
            
            if self._is_downloaded(file_info['url'], file_info['path']):
                skipped += 1
                continue
            
            success = self._download_file(
                file_info['url'],
                file_info['path'],
                file_info['description']
            )
            
            if success:
                successful += 1
            else:
                # Check if it's a 403/404 (not available) vs other error
                if file_info['url'] in self.download_log['failed_files']:
                    error = self.download_log['failed_files'][file_info['url']].get('error', '')
                    if 'not available' in error.lower() or '403' in error or '404' in error:
                        not_available += 1
                    else:
                        failed += 1
                else:
                    failed += 1
            
            # Rate limiting
            time.sleep(0.5)
        
        return successful, skipped, failed, not_available


def create_bronze_tables(cursor):
    """Create bronze_organizations_nonprofits_nccs tables (current + history)"""
    
    # Create history table (ALL records with composite key)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bronze_organizations_nonprofits_nccs_history (
            id SERIAL PRIMARY KEY,
            ein2 VARCHAR(20),  -- Alternative EIN format
            ein VARCHAR(20) NOT NULL,
            ntee_irs VARCHAR(20),  -- IRS NTEE code
            ntee_nccs VARCHAR(20),  -- NCCS NTEE code  
            nteev2 VARCHAR(20),  -- NTEE version 2
            nccs_level_1 VARCHAR(100),  -- Top-level category
            nccs_level_2 VARCHAR(100),  -- Mid-level category
            nccs_level_3 VARCHAR(100),  -- Detailed category
            f990_org_addr_city VARCHAR(100),
            f990_org_addr_state VARCHAR(2),
            f990_org_addr_zip VARCHAR(20),
            f990_org_addr_street VARCHAR(255),
            census_cbsa_fips VARCHAR(20),  -- Core-Based Statistical Area FIPS
            census_cbsa_name VARCHAR(200),  -- CBSA name (metro/micro area)
            census_block_fips VARCHAR(20),  -- Census block FIPS
            census_urban_area VARCHAR(200),  -- Urban area name
            census_state_abbr VARCHAR(2),  -- Census state abbreviation
            census_county_name VARCHAR(100),  -- County name
            org_addr_full TEXT,  -- Full address string
            org_addr_match VARCHAR(200),  -- Address match quality (can be full address)
            latitude DOUBLE PRECISION,  -- Geocoded latitude
            longitude DOUBLE PRECISION,  -- Geocoded longitude
            geocoder_score DOUBLE PRECISION,  -- Geocoding confidence score
            geocoder_match VARCHAR(100),  -- Geocoding match quality
            bmf_subsection_code VARCHAR(20),
            bmf_status_code VARCHAR(20),
            bmf_pf_filing_req_code VARCHAR(20),
            bmf_organization_code VARCHAR(20),
            bmf_income_code VARCHAR(20),
            bmf_group_exempt_num VARCHAR(20),
            bmf_foundation_code VARCHAR(20),
            bmf_filing_req_code VARCHAR(20),
            bmf_deductibility_code VARCHAR(20),
            bmf_classification_code VARCHAR(20),
            bmf_asset_code VARCHAR(20),
            bmf_affiliation_code VARCHAR(20),
            org_ruling_date VARCHAR(20),  -- YYYYMMDD
            org_fiscal_year INTEGER,
            org_ruling_year INTEGER,
            org_year_first INTEGER,  -- First year in BMF
            org_year_last INTEGER,  -- Last year in BMF (used for versioning)
            org_year_count INTEGER,  -- Number of years in BMF
            org_pers_ico TEXT,  -- In care of person
            org_name_sec TEXT,  -- Secondary name
            org_name_current TEXT,  -- Current organization name
            org_fiscal_period VARCHAR(20),  -- YYYYMM
            f990_total_revenue_recent BIGINT,
            f990_total_income_recent BIGINT,
            f990_total_assets_recent BIGINT,
            f990_total_expenses_recent BIGINT,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Composite unique key: EIN + year (allows multiple versions per org)
            UNIQUE(ein, org_year_last)
        );
        
        -- Indexes for history table
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_hist_ein ON bronze_organizations_nonprofits_nccs_history(ein);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_hist_year ON bronze_organizations_nonprofits_nccs_history(org_year_last);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_hist_state ON bronze_organizations_nonprofits_nccs_history(f990_org_addr_state);
    """)
    logger.success("✅ Created bronze_organizations_nonprofits_nccs_history table")
    
    # Create current table (most recent records only)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bronze_organizations_nonprofits_nccs (
            id SERIAL PRIMARY KEY,
            ein2 VARCHAR(20),  -- Alternative EIN format
            ein VARCHAR(20) NOT NULL,
            ntee_irs VARCHAR(20),  -- IRS NTEE code
            ntee_nccs VARCHAR(20),  -- NCCS NTEE code  
            nteev2 VARCHAR(20),  -- NTEE version 2
            nccs_level_1 VARCHAR(100),  -- Top-level category
            nccs_level_2 VARCHAR(100),  -- Mid-level category
            nccs_level_3 VARCHAR(100),  -- Detailed category
            f990_org_addr_city VARCHAR(100),
            f990_org_addr_state VARCHAR(2),
            f990_org_addr_zip VARCHAR(20),
            f990_org_addr_street VARCHAR(255),
            census_cbsa_fips VARCHAR(20),  -- Core-Based Statistical Area FIPS
            census_cbsa_name VARCHAR(200),  -- CBSA name (metro/micro area)
            census_block_fips VARCHAR(20),  -- Census block FIPS
            census_urban_area VARCHAR(200),  -- Urban area name
            census_state_abbr VARCHAR(2),  -- Census state abbreviation
            census_county_name VARCHAR(100),  -- County name
            org_addr_full TEXT,  -- Full address string
            org_addr_match VARCHAR(200),  -- Address match quality (can be full address)
            latitude DOUBLE PRECISION,  -- Geocoded latitude
            longitude DOUBLE PRECISION,  -- Geocoded longitude
            geocoder_score DOUBLE PRECISION,  -- Geocoding confidence score
            geocoder_match VARCHAR(100),  -- Geocoding match quality
            bmf_subsection_code VARCHAR(20),
            bmf_status_code VARCHAR(20),
            bmf_pf_filing_req_code VARCHAR(20),
            bmf_organization_code VARCHAR(20),
            bmf_income_code VARCHAR(20),
            bmf_group_exempt_num VARCHAR(20),
            bmf_foundation_code VARCHAR(20),
            bmf_filing_req_code VARCHAR(20),
            bmf_deductibility_code VARCHAR(20),
            bmf_classification_code VARCHAR(20),
            bmf_asset_code VARCHAR(20),
            bmf_affiliation_code VARCHAR(20),
            org_ruling_date VARCHAR(20),  -- YYYYMMDD
            org_fiscal_year INTEGER,
            org_ruling_year INTEGER,
            org_year_first INTEGER,  -- First year in BMF
            org_year_last INTEGER,  -- Last year in BMF
            org_year_count INTEGER,  -- Number of years in BMF
            org_pers_ico TEXT,  -- In care of person
            org_name_sec TEXT,  -- Secondary name
            org_name_current TEXT,  -- Current organization name
            org_fiscal_period VARCHAR(20),  -- YYYYMM
            f990_total_revenue_recent BIGINT,
            f990_total_income_recent BIGINT,
            f990_total_assets_recent BIGINT,
            f990_total_expenses_recent BIGINT,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            UNIQUE(ein)
        );
        
        -- Indexes for current table (more comprehensive since it's the main query table)
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_state ON bronze_organizations_nonprofits_nccs(f990_org_addr_state);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_city ON bronze_organizations_nonprofits_nccs(f990_org_addr_city, f990_org_addr_state);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_ntee ON bronze_organizations_nonprofits_nccs(ntee_nccs);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_ntee_irs ON bronze_organizations_nonprofits_nccs(ntee_irs);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_level1 ON bronze_organizations_nonprofits_nccs(nccs_level_1);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_county ON bronze_organizations_nonprofits_nccs(census_county_name, census_state_abbr);
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_name ON bronze_organizations_nonprofits_nccs USING gin(to_tsvector('english', org_name_current));
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_lat ON bronze_organizations_nonprofits_nccs(latitude) WHERE latitude IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_bronze_nccs_lon ON bronze_organizations_nonprofits_nccs(longitude) WHERE longitude IS NOT NULL;
    """)
    logger.success("✅ Created bronze_organizations_nonprofits_nccs table (current only)")


def load_to_bronze(file_path: Path, db_url: str = "postgresql://postgres:password@localhost:5433/open_navigator_bronze"):
    """
    Load NCCS Unified BMF data into bronze tables (history + current)
    
    Args:
        file_path: Path to NCCS CSV file
        db_url: PostgreSQL connection string
    """
    logger.info(f"💾 Loading NCCS data from: {file_path}")
    
    # Read CSV in chunks to handle large file
    chunk_size = 50000
    logger.info(f"  Reading CSV in chunks of {chunk_size:,} rows...")
    
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    try:
        # Create tables
        create_bronze_tables(cursor)
        conn.commit()
        
        # Process file in chunks
        chunks_processed = 0
        total_rows = 0
        total_history_rows = 0
        total_current_rows = 0
        
        # Use on_bad_lines='skip' to handle malformed CSV rows
        # Note: The NCCS CSV file may have an incomplete last line
        try:
            for chunk in pd.read_csv(file_path, chunksize=chunk_size, dtype=str, low_memory=False, on_bad_lines='skip'):
            chunks_processed += 1
            chunk_rows = len(chunk)
            total_rows += chunk_rows
            
            logger.info(f"  Processing chunk {chunks_processed}: {chunk_rows:,} rows (total: {total_rows:,})")
            
            # Lowercase column names to match Python convention
            chunk.columns = chunk.columns.str.lower()
            
            # Convert numeric columns
            numeric_cols = ['org_fiscal_year', 'org_ruling_year', 'org_year_first', 'org_year_last', 'org_year_count',
                          'f990_total_revenue_recent', 'f990_total_income_recent', 'f990_total_assets_recent', 'f990_total_expenses_recent']
            for col in numeric_cols:
                if col in chunk.columns:
                    chunk[col] = pd.to_numeric(chunk[col], errors='coerce')
            
            # Convert float columns
            float_cols = ['latitude', 'longitude', 'geocoder_score']
            for col in float_cols:
                if col in chunk.columns:
                    chunk[col] = pd.to_numeric(chunk[col], errors='coerce')
            
            # Fill NaN with None for proper NULL handling
            chunk_clean = chunk.where(pd.notna(chunk), None)
            
            # === 1. Insert ALL records into HISTORY table (dedupe on composite key: ein + org_year_last) ===
            chunk_history = chunk_clean.copy()
            if 'ein' in chunk_history.columns and 'org_year_last' in chunk_history.columns:
                chunk_hist_orig = len(chunk_history)
                # Deduplicate on composite key (ein, org_year_last)
                chunk_history = chunk_history.drop_duplicates(subset=['ein', 'org_year_last'], keep='first')
                dups_removed = chunk_hist_orig - len(chunk_history)
                if dups_removed > 0:
                    logger.info(f"  📚 Removed {dups_removed:,} duplicate (ein, year) pairs in history")
            
            insert_history_query = """
                INSERT INTO bronze_organizations_nonprofits_nccs_history (
                    ein2, ein, ntee_irs, ntee_nccs, nteev2, nccs_level_1, nccs_level_2, nccs_level_3,
                    f990_org_addr_city, f990_org_addr_state, f990_org_addr_zip, f990_org_addr_street,
                    census_cbsa_fips, census_cbsa_name, census_block_fips, census_urban_area,
                    census_state_abbr, census_county_name, org_addr_full, org_addr_match,
                    latitude, longitude, geocoder_score, geocoder_match,
                    bmf_subsection_code, bmf_status_code, bmf_pf_filing_req_code, bmf_organization_code,
                    bmf_income_code, bmf_group_exempt_num, bmf_foundation_code, bmf_filing_req_code,
                    bmf_deductibility_code, bmf_classification_code, bmf_asset_code, bmf_affiliation_code,
                    org_ruling_date, org_fiscal_year, org_ruling_year, org_year_first, org_year_last,
                    org_year_count, org_pers_ico, org_name_sec, org_name_current, org_fiscal_period,
                    f990_total_revenue_recent, f990_total_income_recent, f990_total_assets_recent, f990_total_expenses_recent
                ) VALUES %s
                ON CONFLICT (ein, org_year_last) DO UPDATE SET
                    org_name_current = EXCLUDED.org_name_current,
                    f990_total_revenue_recent = EXCLUDED.f990_total_revenue_recent,
                    f990_total_assets_recent = EXCLUDED.f990_total_assets_recent,
                    loaded_at = CURRENT_TIMESTAMP
            """
            
            # Convert ALL records (after deduplication) to insert into history
            history_records = []
            for row in chunk_history.to_dict('records'):
                def safe_get(key):
                    val = row.get(key)
                    if pd.isna(val):
                        return None
                    return val
                
                history_records.append((
                    safe_get('ein2'), safe_get('ein'), safe_get('ntee_irs'), safe_get('ntee_nccs'), safe_get('nteev2'),
                    safe_get('nccs_level_1'), safe_get('nccs_level_2'), safe_get('nccs_level_3'),
                    safe_get('f990_org_addr_city'), safe_get('f990_org_addr_state'), safe_get('f990_org_addr_zip'), safe_get('f990_org_addr_street'),
                    safe_get('census_cbsa_fips'), safe_get('census_cbsa_name'), safe_get('census_block_fips'), safe_get('census_urban_area'),
                    safe_get('census_state_abbr'), safe_get('census_county_name'), safe_get('org_addr_full'), safe_get('org_addr_match'),
                    safe_get('latitude'), safe_get('longitude'), safe_get('geocoder_score'), safe_get('geocoder_match'),
                    safe_get('bmf_subsection_code'), safe_get('bmf_status_code'), safe_get('bmf_pf_filing_req_code'), safe_get('bmf_organization_code'),
                    safe_get('bmf_income_code'), safe_get('bmf_group_exempt_num'), safe_get('bmf_foundation_code'), safe_get('bmf_filing_req_code'),
                    safe_get('bmf_deductibility_code'), safe_get('bmf_classification_code'), safe_get('bmf_asset_code'), safe_get('bmf_affiliation_code'),
                    safe_get('org_ruling_date'), safe_get('org_fiscal_year'), safe_get('org_ruling_year'), safe_get('org_year_first'), safe_get('org_year_last'),
                    safe_get('org_year_count'), safe_get('org_pers_ico'), safe_get('org_name_sec'), safe_get('org_name_current'), safe_get('org_fiscal_period'),
                    safe_get('f990_total_revenue_recent'), safe_get('f990_total_income_recent'), safe_get('f990_total_assets_recent'), safe_get('f990_total_expenses_recent'),
                ))
            
            # Insert into history table
            execute_values(cursor, insert_history_query, history_records, page_size=1000)
            conn.commit()
            total_history_rows += len(history_records)
            logger.info(f"  📚 Inserted {len(history_records):,} records to history table")
            
            # === 2. Deduplicate and insert into CURRENT table (most recent only) ===
            chunk_current = chunk_clean.copy()
            if 'ein' in chunk_current.columns:
                chunk_orig_size = len(chunk_current)
                chunk_current = chunk_current.sort_values('org_year_last', ascending=False, na_position='last')
                chunk_current = chunk_current.drop_duplicates(subset=['ein'], keep='first')
                duplicates_removed = chunk_orig_size - len(chunk_current)
                if duplicates_removed > 0:
                    logger.info(f"  🔄 Keeping {len(chunk_current):,} most recent records (removed {duplicates_removed:,} older versions)")
            
            insert_current_query = """
                INSERT INTO bronze_organizations_nonprofits_nccs (
                    ein2, ein, ntee_irs, ntee_nccs, nteev2, nccs_level_1, nccs_level_2, nccs_level_3,
                    f990_org_addr_city, f990_org_addr_state, f990_org_addr_zip, f990_org_addr_street,
                    census_cbsa_fips, census_cbsa_name, census_block_fips, census_urban_area,
                    census_state_abbr, census_county_name, org_addr_full, org_addr_match,
                    latitude, longitude, geocoder_score, geocoder_match,
                    bmf_subsection_code, bmf_status_code, bmf_pf_filing_req_code, bmf_organization_code,
                    bmf_income_code, bmf_group_exempt_num, bmf_foundation_code, bmf_filing_req_code,
                    bmf_deductibility_code, bmf_classification_code, bmf_asset_code, bmf_affiliation_code,
                    org_ruling_date, org_fiscal_year, org_ruling_year, org_year_first, org_year_last,
                    org_year_count, org_pers_ico, org_name_sec, org_name_current, org_fiscal_period,
                    f990_total_revenue_recent, f990_total_income_recent, f990_total_assets_recent, f990_total_expenses_recent
                ) VALUES %s
                ON CONFLICT (ein) DO UPDATE SET
                    org_name_current = EXCLUDED.org_name_current,
                    f990_org_addr_city = EXCLUDED.f990_org_addr_city,
                    f990_org_addr_state = EXCLUDED.f990_org_addr_state,
                    ntee_nccs = EXCLUDED.ntee_nccs,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    f990_total_revenue_recent = EXCLUDED.f990_total_revenue_recent,
                    f990_total_assets_recent = EXCLUDED.f990_total_assets_recent,
                    org_year_last = EXCLUDED.org_year_last,
                    loaded_at = CURRENT_TIMESTAMP
            """
            
            # Convert deduplicated records
            current_records = []
            for row in chunk_current.to_dict('records'):
                def safe_get(key):
                    val = row.get(key)
                    if pd.isna(val):
                        return None
                    return val
                
                current_records.append((
                    safe_get('ein2'), safe_get('ein'), safe_get('ntee_irs'), safe_get('ntee_nccs'), safe_get('nteev2'),
                    safe_get('nccs_level_1'), safe_get('nccs_level_2'), safe_get('nccs_level_3'),
                    safe_get('f990_org_addr_city'), safe_get('f990_org_addr_state'), safe_get('f990_org_addr_zip'), safe_get('f990_org_addr_street'),
                    safe_get('census_cbsa_fips'), safe_get('census_cbsa_name'), safe_get('census_block_fips'), safe_get('census_urban_area'),
                    safe_get('census_state_abbr'), safe_get('census_county_name'), safe_get('org_addr_full'), safe_get('org_addr_match'),
                    safe_get('latitude'), safe_get('longitude'), safe_get('geocoder_score'), safe_get('geocoder_match'),
                    safe_get('bmf_subsection_code'), safe_get('bmf_status_code'), safe_get('bmf_pf_filing_req_code'), safe_get('bmf_organization_code'),
                    safe_get('bmf_income_code'), safe_get('bmf_group_exempt_num'), safe_get('bmf_foundation_code'), safe_get('bmf_filing_req_code'),
                    safe_get('bmf_deductibility_code'), safe_get('bmf_classification_code'), safe_get('bmf_asset_code'), safe_get('bmf_affiliation_code'),
                    safe_get('org_ruling_date'), safe_get('org_fiscal_year'), safe_get('org_ruling_year'), safe_get('org_year_first'), safe_get('org_year_last'),
                    safe_get('org_year_count'), safe_get('org_pers_ico'), safe_get('org_name_sec'), safe_get('org_name_current'), safe_get('org_fiscal_period'),
                    safe_get('f990_total_revenue_recent'), safe_get('f990_total_income_recent'), safe_get('f990_total_assets_recent'), safe_get('f990_total_expenses_recent'),
                ))
            
            # Insert into current table
            execute_values(cursor, insert_current_query, current_records, page_size=1000)
            conn.commit()
            total_current_rows += len(current_records)
            
            logger.success(f"  ✅ Chunk {chunks_processed} complete: {len(current_records):,} current, {len(history_records):,} history")
        
        except pd.errors.ParserError as e:
            # Handle malformed CSV (e.g., incomplete last line)
            logger.warning(f"⚠️  CSV parsing ended due to malformed data: {e}")
            logger.info(f"  This is likely an incomplete last line in the CSV file")
            logger.info(f"  Continuing with successfully loaded data...")
        
        logger.success(f"🎉 Load complete!")
        logger.info(f"  📊 Total rows processed: {total_rows:,}")
        logger.info(f"  📚 History table: {total_history_rows:,} records (all versions)")
        logger.info(f"  🎯 Current table: {total_current_rows:,} records (most recent only)")
        
    except Exception as e:
        logger.error(f"❌ Error loading to bronze: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Download NCCS BMF data files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download everything to /mnt/d/nccs_data/
  python bulk_download_nccs.py

  # Download to custom directory
  python bulk_download_nccs.py --base-dir /path/to/directory

  # Download only Unified BMF
  python bulk_download_nccs.py --dataset unified

  # Download specific states only
  python bulk_download_nccs.py --dataset unified --states CA,NY,TX

  # Download only recent transformed BMF
  python bulk_download_nccs.py --dataset transformed --months 2025_12,2026_01

  # Resume interrupted download
  python bulk_download_nccs.py --resume

  # Dry run
  python bulk_download_nccs.py --dry-run
        """
    )
    
    parser.add_argument(
        '--base-dir',
        type=str,
        default='/mnt/d/nccs_data',
        help='Base directory for downloads (default: /mnt/d/nccs_data)'
    )
    
    parser.add_argument(
        '--dataset',
        type=str,
        choices=['all', 'unified', 'transformed', 'raw'],
        default='all',
        help='Which dataset to download (default: all)'
    )
    
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated list of state codes for Unified BMF (e.g., CA,NY,TX)'
    )
    
    parser.add_argument(
        '--months',
        type=str,
        help='Comma-separated list of months for Transformed/Raw BMF (e.g., 2025_12,2026_01)'
    )
    
    parser.add_argument(
        '--no-full',
        action='store_true',
        help='Skip downloading full Unified BMF file (only download state files)'
    )
    
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume interrupted download'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be downloaded without actually downloading'
    )
    
    parser.add_argument(
        '--skip-load',
        action='store_true',
        help='Download only, skip loading to database'
    )
    
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='Skip download phase, only load existing files to database'
    )
    
    args = parser.parse_args()
    
    # Parse states
    states = args.states.split(',') if args.states else None
    
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    logger.info("=" * 60)
    logger.info("NCCS Unified BMF → Bronze Table Loader")
    logger.info("=" * 60)
    logger.info(f"📁 Base directory: {args.base_dir}")
    logger.info("")
    
    # Create downloader
    downloader = NCCSBulkDownloader(
        base_dir=Path(args.base_dir),
        resume=args.resume
    )
    
    # Download Unified BMF (unless skip-download flag is set)
    if args.skip_download:
        logger.info("⏭️  Skipping download phase (--skip-download flag)")
        s, sk, f, na = 0, 0, 0, 0
    else:
        logger.info("📥 Downloading Unified BMF data...")
        s, sk, f, na = downloader.download_unified_bmf(
            states=states,
            download_full=(states is None),  # Only download full file if no states specified
            dry_run=False
        )
        
        logger.info(f"\n✅ Download complete: {s} successful, {sk} skipped, {f} failed")
    
    if args.skip_load:
        logger.info("⏭️  Skipping database load (--skip-load flag)")
        return
    
    # Load to bronze
    if states:
        # Load state files
        logger.info(f"\n💾 Loading {len(states)} state file(s) to bronze...")
        for state in states:
            file_path = Path(args.base_dir) / "unified-bmf" / "v1.2" / "by-state" / f"{state}.csv"
            if file_path.exists():
                load_to_bronze(file_path)
            else:
                logger.warning(f"⚠️  File not found: {file_path}")
    else:
        # Load full file
        file_path = Path(args.base_dir) / "unified-bmf" / "v1.2" / "full" / "UNIFIED_BMF_V1.2.csv"
        if file_path.exists():
            load_to_bronze(file_path)
        else:
            logger.error(f"❌ Full file not found: {file_path}")
    
    logger.info("=" * 60)
    logger.success("✅ NCCS data loaded to bronze!")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
