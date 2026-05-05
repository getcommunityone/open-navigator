#!/usr/bin/env python3
"""
NCCS (National Center for Charitable Statistics) Bulk Data Downloader

Downloads Unified BMF (Business Master File) data and data dictionaries from the
National Center for Charitable Statistics at the Urban Institute.

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
    │   └── data-dictionary/
    │       └── harmonized_data_dictionary.xlsx
    ├── transformed-bmf/
    │   ├── 2026-01/
    │   │   ├── bmf_2026_01_processed.csv
    │   │   └── bmf_2026_01_data_dictionary.csv
    │   └── ...
    ├── raw-bmf/
    │   ├── 2026-01-BMF.csv
    │   └── ...
    └── download_log.json

Data Sources:
    - Unified BMF: Historical data (1989-2025) with one row per organization
    - Transformed BMF: Monthly cleaned/validated IRS releases (June 2023-present)
    - Raw BMF: Unmodified monthly IRS files (June 2023-present)

Website: https://urbaninstitute.github.io/nccs/catalogs/catalog-bmf.html

Usage:
    # Download everything
    python bulk_download_nccs.py

    # Custom base directory
    python bulk_download_nccs.py --base-dir /mnt/d/nccs_data

    # Download only Unified BMF
    python bulk_download_nccs.py --dataset unified

    # Download specific states only
    python bulk_download_nccs.py --states CA,NY,TX

    # Resume interrupted download
    python bulk_download_nccs.py --resume

    # Dry run
    python bulk_download_nccs.py --dry-run
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
        """Check if file is already downloaded"""
        if not self.resume:
            return False
        
        if not dest_path.exists():
            return False
        
        # Check if in completed log
        if url in self.download_log['completed_files']:
            file_info = self.download_log['completed_files'][url]
            if dest_path.stat().st_size == file_info.get('size', 0):
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
    
    args = parser.parse_args()
    
    # Parse states and months
    states = args.states.split(',') if args.states else None
    months_transformed = args.months.split(',') if args.months and args.dataset in ['all', 'transformed'] else None
    months_raw = [m.replace('_', '-') for m in args.months.split(',')] if args.months and args.dataset in ['all', 'raw'] else None
    
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Create downloader
    downloader = NCCSBulkDownloader(
        base_dir=Path(args.base_dir),
        resume=args.resume
    )
    
    # Download datasets
    total_successful = 0
    total_skipped = 0
    total_failed = 0
    total_not_available = 0
    
    logger.info("📊 NCCS BMF Data Downloader")
    logger.info(f"📁 Base directory: {args.base_dir}")
    logger.info("")
    
    if args.dataset in ['all', 'unified']:
        logger.info("=" * 60)
        logger.info("📥 Downloading Unified BMF")
        logger.info("=" * 60)
        s, sk, f, na = downloader.download_unified_bmf(
            states=states,
            download_full=not args.no_full,
            dry_run=args.dry_run
        )
        total_successful += s
        total_skipped += sk
        total_failed += f
        total_not_available += na
    
    if args.dataset in ['all', 'transformed']:
        logger.info("\n" + "=" * 60)
        logger.info("📥 Downloading Transformed BMF")
        logger.info("=" * 60)
        s, sk, f, na = downloader.download_transformed_bmf(
            months=months_transformed,
            dry_run=args.dry_run
        )
        total_successful += s
        total_skipped += sk
        total_failed += f
        total_not_available += na
    
    if args.dataset in ['all', 'raw']:
        logger.info("\n" + "=" * 60)
        logger.info("📥 Downloading Raw BMF")
        logger.info("=" * 60)
        s, sk, f, na = downloader.download_raw_bmf(
            months=months_raw,
            dry_run=args.dry_run
        )
        total_successful += s
        total_skipped += sk
        total_failed += f
        total_not_available += na
    
    # Summary
    if not args.dry_run:
        logger.info("\n" + "=" * 60)
        logger.info("📊 Download Summary:")
        logger.info(f"  ✅ Successful: {total_successful}")
        logger.info(f"  ⏭️  Skipped: {total_skipped}")
        if total_not_available > 0:
            logger.info(f"  ⚠️  Not available on server: {total_not_available}")
        if total_failed > 0:
            logger.info(f"  ❌ Failed: {total_failed}")
        logger.info(f"  📁 Base directory: {args.base_dir}")
        logger.info("=" * 60)


if __name__ == '__main__':
    main()
