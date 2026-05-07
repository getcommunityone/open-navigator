#!/usr/bin/env python3
"""
NCCS (National Center for Charitable Statistics) Bulk Downloader

Downloads Unified BMF (Business Master File), Transformed BMF, and Raw BMF data
from the National Center for Charitable Statistics.

Directory Structure:
    data/cache/nccs/  (or configurable base path)
    ├── unified-bmf/
    │   └── v1.2/
    │       ├── full/
    │       │   └── UNIFIED_BMF_V1.2.csv
    │       ├── by-state/
    │       │   ├── AL.csv
    │       │   └── ...
    │       └── data-dictionary/
    ├── transformed-bmf/
    │   └── {YYYY_MM}/
    └── raw-bmf/

Website: https://urbaninstitute.github.io/nccs/catalogs/catalog-bmf.html

Usage:
    # Download everything
    python download_nccs_bulk.py

    # Custom base directory
    python download_nccs_bulk.py --base-dir /mnt/d/nccs_data

    # Download specific states only
    python download_nccs_bulk.py --dataset unified --states CA,NY,TX

    # Dry run
    python download_nccs_bulk.py --dry-run
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

    TRANSFORMED_MONTHS = [
        '2023_06', '2023_07', '2023_08', '2023_09', '2023_10', '2023_11', '2023_12',
        '2024_01', '2024_02', '2024_03', '2024_04', '2024_05', '2024_06', '2024_07',
        '2024_08', '2024_09', '2024_10', '2024_11', '2024_12',
        '2025_01', '2025_02', '2025_03', '2025_04', '2025_05', '2025_06', '2025_07',
        '2025_08', '2025_09', '2025_10', '2025_11', '2025_12',
        '2026_01'
    ]

    RAW_MONTHS = [
        '2023-06', '2023-07', '2023-08', '2023-09', '2023-10', '2023-11', '2023-12',
        '2024-01', '2024-02', '2024-03', '2024-04', '2024-05', '2024-06', '2024-07',
        '2024-08', '2024-09', '2024-10', '2024-11', '2024-12',
        '2025-01', '2025-02', '2025-03', '2025-04', '2025-05', '2025-06', '2025-07',
        '2025-08', '2025-09', '2025-10', '2025-11', '2025-12',
        '2026-01'
    ]

    def __init__(self, base_dir: Path, resume: bool = False):
        self.base_dir = Path(base_dir)
        self.unified_dir = self.base_dir / "unified-bmf" / "v1.2"
        self.transformed_dir = self.base_dir / "transformed-bmf"
        self.raw_dir = self.base_dir / "raw-bmf"
        self.log_file = self.base_dir / "download_log.json"
        self.resume = resume

        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise SystemExit(
                f"Cannot create base directory '{self.base_dir}': {e}\n"
                f"Pass a writable path with --base-dir (e.g. --base-dir ~/nccs_data)"
            ) from None
        (self.unified_dir / "full").mkdir(parents=True, exist_ok=True)
        (self.unified_dir / "by-state").mkdir(parents=True, exist_ok=True)
        (self.unified_dir / "data-dictionary").mkdir(parents=True, exist_ok=True)
        self.transformed_dir.mkdir(exist_ok=True)
        self.raw_dir.mkdir(exist_ok=True)

        self.download_log = self._load_log()

        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (NCCS Bulk Downloader/1.0)'})

    def _load_log(self) -> Dict:
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
        self.download_log['last_updated'] = datetime.now().isoformat()
        with open(self.log_file, 'w') as f:
            json.dump(self.download_log, f, indent=2)

    def _discover_state_files(self) -> Dict[str, Tuple[str, str]]:
        """Scrape the NCCS catalog page to discover actual state file URLs."""
        logger.info("Discovering state file URLs from catalog page...")

        try:
            response = self.session.get(self.CATALOG_URL, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            state_files = {}

            for link in soup.find_all('a', class_='button'):
                href = link.get('href', '')

                if '/bmf/unified/' in href and '_BMF_' in href and href.endswith('.csv'):
                    filename = href.split('/')[-1]
                    state_code = filename.split('_')[0].upper()

                    row = link.find_parent('tr')
                    if row:
                        cells = row.find_all('td')
                        if len(cells) >= 3:
                            state_name = cells[2].get_text(strip=True)
                        else:
                            state_name = self.STATES.get(state_code, state_code)
                    else:
                        state_name = self.STATES.get(state_code, state_code)

                    if not href.startswith('http'):
                        href = f"https:{href}" if href.startswith('//') else f"https://nccsdata.s3.amazonaws.com{href}"

                    state_files[state_code] = (href, state_name)

            logger.info(f"Discovered {len(state_files)} state files from catalog")

            if state_files:
                for code, (url, name) in list(state_files.items())[:3]:
                    logger.debug(f"   {code} ({name}): {url}")

            return state_files

        except Exception as e:
            logger.warning(f"Failed to scrape catalog page: {e}")
            logger.info("Falling back to constructed URLs...")
            return {}

    def _is_downloaded(self, url: str, dest_path: Path) -> bool:
        return dest_path.exists() and dest_path.stat().st_size > 1024

    def _download_file(self, url: str, dest_path: Path, description: str) -> bool:
        if self._is_downloaded(url, dest_path):
            logger.info(f"Skipping (already downloaded): {dest_path.name}")
            return True

        try:
            response = self.session.head(url, allow_redirects=True, timeout=30)
            total_size = int(response.headers.get('content-length', 0))

            response = self.session.get(url, stream=True, timeout=60)
            response.raise_for_status()

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            with open(dest_path, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True, desc=description, leave=False) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))

            self.download_log['completed_files'][url] = {
                'path': str(dest_path),
                'size': dest_path.stat().st_size,
                'downloaded_at': datetime.now().isoformat(),
            }
            self._save_log()

            logger.success(f"Downloaded: {dest_path.name} ({total_size:,} bytes)")
            return True

        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [403, 404]:
                logger.warning(f"File not available (skipping): {dest_path.name}")
                self.download_log['failed_files'][url] = {
                    'error': f"HTTP {e.response.status_code}: File not available on server",
                    'failed_at': datetime.now().isoformat(),
                }
            else:
                logger.error(f"Failed to download {url}: {e}")
                self.download_log['failed_files'][url] = {
                    'error': str(e),
                    'failed_at': datetime.now().isoformat(),
                }
            self._save_log()
            return False
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            self.download_log['failed_files'][url] = {
                'error': str(e),
                'failed_at': datetime.now().isoformat(),
            }
            self._save_log()
            return False

    def _run_downloads(self, files_to_download: List[Dict], dry_run: bool) -> Tuple[int, int, int, int]:
        """Execute a list of download specs, returning (successful, skipped, failed, not_available)."""
        if dry_run:
            for f in files_to_download:
                print(f"  {f['description']:40} | {f['path'].name}")
            return 0, 0, 0, 0

        successful = skipped = failed = not_available = 0

        for i, file_info in enumerate(files_to_download, 1):
            logger.info(f"\n[{i}/{len(files_to_download)}] {file_info['description']}")

            if self._is_downloaded(file_info['url'], file_info['path']):
                skipped += 1
                continue

            success = self._download_file(file_info['url'], file_info['path'], file_info['description'])

            if success:
                successful += 1
            else:
                error = self.download_log['failed_files'].get(file_info['url'], {}).get('error', '')
                if 'not available' in error.lower() or '403' in error or '404' in error:
                    not_available += 1
                else:
                    failed += 1

            time.sleep(0.5)

        return successful, skipped, failed, not_available

    def download_unified_bmf(
        self,
        states: Optional[List[str]] = None,
        download_full: bool = True,
        dry_run: bool = False
    ) -> Tuple[int, int, int, int]:
        files_to_download = []

        dict_url = f"{self.BASE_URL}/harmonized/harmonized_data_dictionary.xlsx"
        dict_path = self.unified_dir / "data-dictionary" / "harmonized_data_dictionary.xlsx"
        files_to_download.append({'url': dict_url, 'path': dict_path, 'description': 'Data Dictionary'})

        if download_full:
            full_url = f"{self.BASE_URL}/bmf/unified/v1.2/UNIFIED_BMF_V1.2.csv"
            full_path = self.unified_dir / "full" / "UNIFIED_BMF_V1.2.csv"
            files_to_download.append({'url': full_url, 'path': full_path, 'description': 'Full Unified BMF'})

        discovered_states = self._discover_state_files()
        states_to_download = states if states else list(self.STATES.keys())

        if not states and discovered_states:
            for state_code in discovered_states:
                if state_code not in states_to_download and state_code == 'ZZ':
                    states_to_download.append(state_code)

        for state_code in states_to_download:
            if state_code in discovered_states:
                state_url, state_name = discovered_states[state_code]
            elif state_code in self.STATES:
                state_name_enc = self.STATES[state_code].replace(' ', '%20')
                state_url = f"{self.BASE_URL}/bmf/unified/v1.2/{state_name_enc}.csv"
                state_name = self.STATES[state_code]
            else:
                logger.warning(f"Unknown state code: {state_code}")
                continue

            state_path = self.unified_dir / "by-state" / f"{state_code}.csv"
            files_to_download.append({
                'url': state_url,
                'path': state_path,
                'description': f"Unified BMF - {state_name} ({state_code})",
            })

        logger.info(f"Unified BMF: {len(files_to_download)} files to process")
        return self._run_downloads(files_to_download, dry_run)

    def download_transformed_bmf(
        self,
        months: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> Tuple[int, int, int, int]:
        files_to_download = []

        for month in (months or self.TRANSFORMED_MONTHS):
            if month not in self.TRANSFORMED_MONTHS:
                logger.warning(f"Invalid month: {month}")
                continue

            files_to_download.extend([
                {
                    'url': f"{self.BASE_URL}/processed/bmf/{month}/bmf_{month}_processed.csv",
                    'path': self.transformed_dir / month / f"bmf_{month}_processed.csv",
                    'description': f"Transformed BMF {month}",
                },
                {
                    'url': f"{self.BASE_URL}/processed/bmf/{month}/bmf_{month}_data_dictionary.csv",
                    'path': self.transformed_dir / month / f"bmf_{month}_data_dictionary.csv",
                    'description': f"Data Dictionary {month}",
                },
            ])

        logger.info(f"Transformed BMF: {len(files_to_download)} files to process")
        return self._run_downloads(files_to_download, dry_run)

    def download_raw_bmf(
        self,
        months: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> Tuple[int, int, int, int]:
        files_to_download = []

        for month in (months or self.RAW_MONTHS):
            if month not in self.RAW_MONTHS:
                logger.warning(f"Invalid month: {month}")
                continue

            files_to_download.append({
                'url': f"{self.BASE_URL}/raw/bmf/{month}-BMF.csv",
                'path': self.raw_dir / f"{month}-BMF.csv",
                'description': f"Raw BMF {month}",
            })

        logger.info(f"Raw BMF: {len(files_to_download)} files to process")
        return self._run_downloads(files_to_download, dry_run)


def main():
    parser = argparse.ArgumentParser(
        description='Download NCCS BMF data files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python download_nccs_bulk.py
  python download_nccs_bulk.py --base-dir /mnt/d/nccs_data
  python download_nccs_bulk.py --dataset unified
  python download_nccs_bulk.py --dataset unified --states CA,NY,TX
  python download_nccs_bulk.py --dataset transformed --months 2025_12,2026_01
  python download_nccs_bulk.py --resume
  python download_nccs_bulk.py --dry-run
        """
    )

    parser.add_argument('--base-dir', type=str, default='data/cache/nccs',
                        help='Base directory for downloads (default: data/cache/nccs)')
    parser.add_argument('--dataset', type=str, choices=['all', 'unified', 'transformed', 'raw'], default='all',
                        help='Which dataset to download (default: all)')
    parser.add_argument('--states', type=str,
                        help='Comma-separated state codes for Unified BMF (e.g., CA,NY,TX)')
    parser.add_argument('--months', type=str,
                        help='Comma-separated months for Transformed/Raw BMF (e.g., 2025_12,2026_01)')
    parser.add_argument('--no-full', action='store_true',
                        help='Skip full Unified BMF file (only download state files)')
    parser.add_argument('--resume', action='store_true', help='Resume interrupted download')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be downloaded without downloading')

    args = parser.parse_args()

    states = args.states.split(',') if args.states else None
    months = args.months.split(',') if args.months else None

    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )

    logger.info("=" * 60)
    logger.info("NCCS Bulk Downloader")
    logger.info("=" * 60)
    logger.info(f"Base directory: {args.base_dir}")

    downloader = NCCSBulkDownloader(base_dir=Path(args.base_dir), resume=args.resume)

    totals = {'successful': 0, 'skipped': 0, 'failed': 0, 'not_available': 0}

    def accumulate(result):
        s, sk, f, na = result
        totals['successful'] += s
        totals['skipped'] += sk
        totals['failed'] += f
        totals['not_available'] += na

    if args.dataset in ('all', 'unified'):
        accumulate(downloader.download_unified_bmf(
            states=states,
            download_full=not args.no_full and states is None,
            dry_run=args.dry_run,
        ))

    if args.dataset in ('all', 'transformed'):
        accumulate(downloader.download_transformed_bmf(months=months, dry_run=args.dry_run))

    if args.dataset in ('all', 'raw'):
        accumulate(downloader.download_raw_bmf(months=months, dry_run=args.dry_run))

    logger.info("=" * 60)
    logger.info(
        f"Done: {totals['successful']} downloaded, {totals['skipped']} skipped, "
        f"{totals['failed']} failed, {totals['not_available']} not available"
    )
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
