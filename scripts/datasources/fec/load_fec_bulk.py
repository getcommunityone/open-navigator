#!/usr/bin/env python3
"""
FEC Bulk Data Downloader

Downloads all bulk data files from https://www.fec.gov/data/browse-data/?tab=bulk-data
and organizes them in a directory structure matching the FEC website.

Directory Structure (organized by FEC page categories):
    D:/fec_data/  (or configurable base path)
    ├── bulk-downloads/
    │   ├── candidate-master/
    │   │   ├── 1980/cn80.zip
    │   │   └── 2024/cn24.zip
    │   ├── all-candidates/
    │   │   ├── 1980/weball80.zip
    │   │   └── 2024/weball24.zip
    │   ├── house-senate-campaigns/
    │   │   └── 2024/
    │   │       ├── webk24.zip
    │   │       └── webl24.zip
    │   ├── committee-master/
    │   │   └── 2024/cm24.zip
    │   ├── pac-summary/
    │   │   └── 2024/pas224.zip
    │   ├── contributions-by-individuals/
    │   │   └── 2024/indiv24.zip
    │   ├── candidate-committee-linkages/
    │   │   └── 2024/ccl24.zip
    │   ├── committee-to-committee/
    │   │   └── 2024/oth24.zip
    │   ├── operating-expenditures/
    │   │   └── 2024/oppexp24.zip
    │   ├── summary-reports/
    │   │   └── 2024/
    │   │       ├── candidate_summary_2024.csv
    │   │       ├── independent_expenditure_2024.csv
    │   │       └── ...
    │   ├── headers/
    │   │   ├── cm_header_file.csv
    │   │   └── ...
    │   └── special-files/
    │       ├── lobbyist.csv
    │       └── ...
    └── download_log.json

File Types:
    - cm: Committee Master
    - cn: Candidate Master
    - ccl: Candidate-Committee Linkages
    - indiv: Individual Contributions
    - pas2: PAC Summary
    - oth: Other Transactions
    - oppexp: Operating Expenditures
    - weball: All Candidates
    - webk: Current House/Senate Campaigns
    - webl: Current House/Senate Campaigns

Usage:
    # Download everything (default: D:/fec_data/)
    python bulk_download_fec.py

    # Custom base directory
    python bulk_download_fec.py --base-dir /mnt/d/fec_data

    # Specific years only
    python bulk_download_fec.py --years 2020,2022,2024

    # Specific file types only
    python bulk_download_fec.py --types indiv,cn,cm

    # Resume interrupted download
    python bulk_download_fec.py --resume

    # Dry run (show what would be downloaded)
    python bulk_download_fec.py --dry-run
"""

import argparse
import json
import requests
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
from loguru import logger
import time
from bs4 import BeautifulSoup
from tqdm import tqdm


class FECBulkDownloader:
    """Download and organize FEC bulk data files"""
    
    BASE_URL = "https://www.fec.gov"
    BULK_DATA_URL = f"{BASE_URL}/data/browse-data/?tab=bulk-data"
    
    # FEC Page Categories (matching website organization)
    FILE_CATEGORIES = {
        'cn': 'candidate-master',
        'weball': 'all-candidates',
        'webk': 'house-senate-campaigns',
        'webl': 'house-senate-campaigns',
        'cm': 'committee-master',
        'pas2': 'pac-summary',
        'indiv': 'contributions-by-individuals',
        'ccl': 'candidate-committee-linkages',
        'oth': 'committee-to-committee',
        'oppexp': 'operating-expenditures',
    }
    
    # CSV file patterns (by year)
    CSV_FILE_PATTERNS = [
        'candidate_summary',
        'committee_summary',
        'independent_expenditure',
        'CommunicationCosts',
        'ElectioneeringComm',
        'Form1Filer',
        'Form2Filer',
        'leadership',
    ]
    
    # Header files (one-time downloads)
    HEADER_FILES = [
        'cm_header_file.csv',
        'cn_header_file.csv',
        'ccl_header_file.csv',
        'indiv_header_file.csv',
        'pas2_header_file.csv',
        'oth_header_file.csv',
        'oppexp_header_file.csv',
    ]
    
    # Other special files
    SPECIAL_FILES = [
        'lobbyist.csv',
        'lobbyist_bundle.csv',
        'FalseFictitiousFilings.csv',
        'Contributions_by_3Zip.csv',
        'Contributions_by_Size.csv',
    ]
    
    def __init__(self, base_dir: Path, resume: bool = False):
        """
        Initialize FEC bulk downloader
        
        Args:
            base_dir: Base directory for downloads (e.g., D:/fec_data/)
            resume: Resume interrupted downloads
        """
        self.base_dir = Path(base_dir)
        self.bulk_dir = self.base_dir / "bulk-downloads"
        self.headers_dir = self.bulk_dir / "headers"
        self.log_file = self.base_dir / "download_log.json"
        self.resume = resume
        
        # Create directories
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.bulk_dir.mkdir(exist_ok=True)
        self.headers_dir.mkdir(exist_ok=True)
        
        # Load download log
        self.download_log = self._load_log()
        
        # Session for HTTP requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (FEC Bulk Downloader/1.0)'
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
            
        except Exception as e:
            logger.error(f"❌ Failed to download {url}: {e}")
            self.download_log['failed_files'][url] = {
                'error': str(e),
                'failed_at': datetime.now().isoformat(),
            }
            self._save_log()
            return False
    
    def discover_files(self) -> List[Dict[str, str]]:
        """
        Discover all available files from FEC bulk data page
        
        Returns:
            List of dicts with 'url', 'path', 'type', 'year'
        """
        logger.info("🔍 Discovering available files from FEC website...")
        
        try:
            response = self.session.get(self.BULK_DATA_URL, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            files = []
            
            # Find all download links
            for link in soup.find_all('a', href=True):
                href = link['href']
                
                # Only process bulk-downloads links
                if '/files/bulk-downloads/' not in href:
                    continue
                
                url = f"{self.BASE_URL}{href}" if href.startswith('/') else href
                filename = href.split('/')[-1]
                
                # Parse file info
                file_info = self._parse_file_info(href, filename)
                if file_info:
                    files.append(file_info)
            
            logger.info(f"📊 Found {len(files)} files to download")
            return files
            
        except Exception as e:
            logger.error(f"❌ Failed to discover files: {e}")
            return []
    
    def _parse_file_info(self, href: str, filename: str) -> Optional[Dict]:
        """Parse file information from href"""
        parts = href.split('/')
        
        # Extract year from path
        year = None
        for part in parts:
            if part.isdigit() and len(part) == 4:
                year = part
                break
        
        # Determine file type and category
        file_type = 'other'
        category = 'other'
        
        if filename in self.HEADER_FILES:
            file_type = 'header'
            category = 'headers'
            dest_path = self.bulk_dir / 'headers' / filename
        elif filename in self.SPECIAL_FILES:
            file_type = 'special'
            category = 'special-files'
            dest_path = self.bulk_dir / 'special-files' / filename
        elif year:
            # Determine category based on file prefix
            for prefix, cat in self.FILE_CATEGORIES.items():
                if filename.startswith(prefix):
                    file_type = prefix
                    category = cat
                    break
            
            # Check CSV patterns
            for csv_pattern in self.CSV_FILE_PATTERNS:
                if csv_pattern in filename:
                    file_type = csv_pattern
                    category = 'summary-reports'
                    break
            
            # Organize by category, then year
            dest_path = self.bulk_dir / category / year / filename
        else:
            dest_path = self.bulk_dir / 'other' / filename
        
        url = f"{self.BASE_URL}{href}" if href.startswith('/') else href
        
        return {
            'url': url,
            'path': dest_path,
            'filename': filename,
            'type': file_type,
            'category': category,
            'year': year,
        }
    
    def download_all(
        self,
        years: Optional[List[str]] = None,
        file_types: Optional[List[str]] = None,
        dry_run: bool = False
    ):
        """
        Download all files
        
        Args:
            years: Optional list of years to download (e.g., ['2020', '2022'])
            file_types: Optional list of file types (e.g., ['indiv', 'cm'])
            dry_run: If True, only show what would be downloaded
        """
        files = self.discover_files()
        
        # Filter by years
        if years:
            files = [f for f in files if f['year'] in years or f['year'] is None]
        
        # Filter by file types
        if file_types:
            files = [f for f in files if f['type'] in file_types or f['type'] in ['header', 'special']]
        
        logger.info(f"📥 Preparing to download {len(files)} files")
        
        if dry_run:
            logger.info("🔍 DRY RUN - Files that would be downloaded:")
            for f in files:
                print(f"  {f['year'] or 'N/A':>4} | {f['category']:30} | {f['filename']}")
            return
        
        # Download files
        successful = 0
        failed = 0
        skipped = 0
        
        for i, file_info in enumerate(files, 1):
            logger.info(f"\n[{i}/{len(files)}] {file_info['filename']}")
            
            if self._is_downloaded(file_info['url'], file_info['path']):
                skipped += 1
                continue
            
            success = self._download_file(
                file_info['url'],
                file_info['path'],
                f"{file_info['category']} - {file_info['year'] or 'N/A'}"
            )
            
            if success:
                successful += 1
            else:
                failed += 1
            
            # Rate limiting
            time.sleep(0.5)
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("📊 Download Summary:")
        logger.info(f"  ✅ Successful: {successful}")
        logger.info(f"  ⏭️  Skipped: {skipped}")
        logger.info(f"  ❌ Failed: {failed}")
        logger.info(f"  📁 Base directory: {self.base_dir}")
        logger.info("="*60)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Download FEC bulk data files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download everything to D:/fec_data/
  python bulk_download_fec.py

  # Download to custom directory
  python bulk_download_fec.py --base-dir /mnt/d/fec_data

  # Download specific years only
  python bulk_download_fec.py --years 2020,2022,2024

  # Download specific file types only
  python bulk_download_fec.py --types indiv,cn,cm

  # Resume interrupted download
  python bulk_download_fec.py --resume

  # Dry run (show what would be downloaded)
  python bulk_download_fec.py --dry-run
        """
    )
    
    parser.add_argument(
        '--base-dir',
        type=str,
        default='D:/fec_data',
        help='Base directory for downloads (default: D:/fec_data)'
    )
    
    parser.add_argument(
        '--years',
        type=str,
        help='Comma-separated list of years to download (e.g., 2020,2022,2024)'
    )
    
    parser.add_argument(
        '--types',
        type=str,
        help='Comma-separated list of file types (e.g., indiv,cm,cn)'
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
    
    # Parse years and types
    years = args.years.split(',') if args.years else None
    file_types = args.types.split(',') if args.types else None
    
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Create downloader and run
    downloader = FECBulkDownloader(
        base_dir=Path(args.base_dir),
        resume=args.resume
    )
    
    downloader.download_all(
        years=years,
        file_types=file_types,
        dry_run=args.dry_run
    )


if __name__ == '__main__':
    main()
