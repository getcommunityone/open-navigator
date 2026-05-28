#!/usr/bin/env python3
"""
FEC Bulk Data Unzipper (High-Performance Edition)

Unzips all FEC bulk data files downloaded by load_fec_bulk.py
from data/cache/fec_data/bulk-downloads/ to data/cache/fec_data/unzipped/

Supports multiple extraction methods for maximum speed:
- Python zipfile (default, portable)
- 7-Zip (2-3x faster if installed)
- Parallel processing (4-8x faster with multiple workers)

Directory Structure:
    data/cache/fec_data/
    ├── bulk-downloads/          # Original ZIP files (source)
    │   ├── candidate-master/
    │   │   ├── 1980/cn80.zip
    │   │   └── 2024/cn24.zip
    │   ├── contributions-by-individuals/
    │   │   └── 2024/indiv24.zip
    │   └── ...
    └── unzipped/                # Unzipped CSV files (destination)
        ├── candidate-master/
        │   ├── 1980/
        │   │   ├── cn80.txt
        │   │   ├── cn_header_file.csv
        │   │   └── ...
        │   └── 2024/
        │       ├── cn24.txt
        │       └── ...
        ├── contributions-by-individuals/
        │   └── 2024/
        │       ├── indiv24.txt
        │       ├── indiv_header_file.csv
        │       └── ...
        └── ...

Usage:
    # Quick start: Unzip only the latest 2 years with 8 workers (RECOMMENDED)
    python unzip_fec_data.py --latest 2 --workers 8 
    # Fast: Use 8 parallel workers (4-8x faster)
    python unzip_fec_data.py --workers 8 
    # Fastest: Use 7-Zip with 8 workers (10-15x faster if 7z installed)
    python unzip_fec_data.py --method 7z --workers 8 
    # Default (single-threaded Python)
    python unzip_fec_data.py 
    # Specific category only
    python unzip_fec_data.py --category candidate-master --workers 4

    # Specific years only
    python unzip_fec_data.py --years 2020,2022,2024 --workers 4
    
    # Latest 5 years only
    python unzip_fec_data.py --latest 5 --workers 8

    # Resume interrupted extraction
    python unzip_fec_data.py --resume --workers 8

    # Dry run (show what would be unzipped)
    python unzip_fec_data.py --dry-run

    # Remove ZIP files after successful extraction (saves 50% disk space)
    python unzip_fec_data.py --remove-zips --workers 8
"""

import argparse
import json
import zipfile
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
from loguru import logger
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial


def _unzip_worker(args: Tuple[Path, Path, bool, Path, bool, bool, str]) -> Tuple[bool, Path, Path, int]:
    """
    Worker function for parallel unzipping (must be at module level for pickling)
    
    Args:
        args: Tuple of (zip_path, dest_dir, dry_run, base_dir, use_7z, remove_zips, method)
    
    Returns:
        Tuple of (success, zip_path, dest_dir, file_count)
    """
    zip_path, dest_dir, dry_run, base_dir, use_7z, remove_zips, method = args
    
    if dry_run:
        return True, zip_path, dest_dir, 0
    
    try:
        # Create destination directory
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract using chosen method
        if use_7z:
            # Use 7-Zip
            result = subprocess.run(
                ['7z', 'x', str(zip_path), f'-o{dest_dir}', '-y'],
                capture_output=True,
                text=True,
                check=True
            )
            file_list = [str(f.relative_to(dest_dir)) for f in dest_dir.rglob('*') if f.is_file()]
        else:
            # Use Python zipfile
            with zipfile.ZipFile(zip_path, 'r') as zf:
                file_list = zf.namelist()
                zf.extractall(dest_dir)
        
        file_count = len(file_list)
        
        # Remove ZIP file if requested
        removed = False
        if remove_zips:
            zip_path.unlink()
            removed = True
        
        return True, zip_path, dest_dir, file_count
        
    except Exception as e:
        return False, zip_path, dest_dir, 0


class FECBulkUnzipper:
    """Unzip FEC bulk data files with parallel processing and 7-Zip support"""
    
    def __init__(
        self, 
        base_dir: Path, 
        resume: bool = False,
        remove_zips: bool = False,
        method: str = 'python',
        workers: int = 1
    ):
        """
        Initialize FEC bulk unzipper
        
        Args:
            base_dir: Base directory containing bulk-downloads/ (default: data/cache/fec_data/)
            resume: Skip already unzipped files
            remove_zips: Remove ZIP files after successful extraction
            method: Extraction method ('python', '7z', or 'auto')
            workers: Number of parallel workers (1 = single-threaded)
        """
        self.base_dir = Path(base_dir)
        self.bulk_dir = self.base_dir / "bulk-downloads"
        self.unzipped_dir = self.base_dir / "unzipped"
        self.log_file = self.base_dir / "unzip_log.json"
        self.resume = resume
        self.remove_zips = remove_zips
        self.method = method
        self.workers = workers
        
        # Validate source directory exists
        if not self.bulk_dir.exists():
            logger.error(f"❌ Source directory not found: {self.bulk_dir}")
            logger.info("💡 Run load_fec_bulk.py first to download FEC data")
            sys.exit(1)
        
        # Create destination directory
        self.unzipped_dir.mkdir(parents=True, exist_ok=True)
        
        # Detect extraction method
        self.use_7z = self._detect_extraction_method()
        
        # Load unzip log
        self.unzip_log = self._load_log()
        
        # Statistics
        self.stats = {
            'total_zips': 0,
            'unzipped': 0,
            'skipped': 0,
            'failed': 0,
            'removed': 0,
        }
    
    def _detect_extraction_method(self) -> bool:
        """Detect if 7-Zip is available and choose best method"""
        if self.method == 'python':
            logger.info("📦 Using Python zipfile (portable)")
            return False
        
        if self.method == '7z':
            if shutil.which('7z'):
                logger.info("⚡ Using 7-Zip (2-3x faster)")
                return True
            else:
                logger.warning("⚠️  7z not found, falling back to Python zipfile")
                logger.info("💡 Install with: sudo apt-get install p7zip-full")
                return False
        
        if self.method == 'auto':
            if shutil.which('7z'):
                logger.info("⚡ Using 7-Zip (auto-detected, 2-3x faster)")
                return True
            else:
                logger.info("📦 Using Python zipfile (7z not found)")
                return False
        
        logger.warning(f"⚠️  Unknown method '{self.method}', using Python zipfile")
        return False
        
        # Load unzip log
        self.unzip_log = self._load_log()
        
        # Statistics
        self.stats = {
            'total_zips': 0,
            'unzipped': 0,
            'skipped': 0,
            'failed': 0,
            'removed': 0,
        }
    
    def _load_log(self) -> Dict:
        """Load unzip log"""
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
        """Save unzip log"""
        self.unzip_log['last_updated'] = datetime.now().isoformat()
        with open(self.log_file, 'w') as f:
            json.dump(self.unzip_log, f, indent=2)
    
    def _is_unzipped(self, zip_path: Path, dest_dir: Path) -> bool:
        """Check if ZIP file is already unzipped"""
        if not self.resume:
            return False
        
        # Check if in completed log
        zip_key = str(zip_path.relative_to(self.base_dir))
        if zip_key in self.unzip_log['completed_files']:
            unzip_info = self.unzip_log['completed_files'][zip_key]
            
            # Verify destination directory exists and has files
            if dest_dir.exists() and any(dest_dir.iterdir()):
                # Check if all expected files exist
                expected_files = unzip_info.get('extracted_files', [])
                if expected_files:
                    all_exist = all(
                        (dest_dir / f).exists() 
                        for f in expected_files
                    )
                    if all_exist:
                        return True
        
        return False
    
    def _unzip_with_python(self, zip_path: Path, dest_dir: Path) -> Tuple[bool, List[str]]:
        """Unzip using Python's zipfile module"""
        with zipfile.ZipFile(zip_path, 'r') as zf:
            file_list = zf.namelist()
            zf.extractall(dest_dir)
        return True, file_list
    
    def _unzip_with_7z(self, zip_path: Path, dest_dir: Path) -> Tuple[bool, List[str]]:
        """Unzip using 7-Zip (2-3x faster)"""
        try:
            # Run 7z extract command
            result = subprocess.run(
                ['7z', 'x', str(zip_path), f'-o{dest_dir}', '-y'],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Get list of extracted files from dest_dir
            file_list = [
                str(f.relative_to(dest_dir)) 
                for f in dest_dir.rglob('*') 
                if f.is_file()
            ]
            
            return True, file_list
            
        except subprocess.CalledProcessError as e:
            logger.error(f"7z extraction failed: {e.stderr}")
            return False, []
    
    def _unzip_file(
        self, 
        zip_path: Path, 
        dest_dir: Path,
        dry_run: bool = False
    ) -> bool:
        """
        Unzip a single file
        
        Args:
            zip_path: Path to ZIP file
            dest_dir: Destination directory
            dry_run: If True, don't actually unzip
        
        Returns:
            True if successful, False otherwise
        """
        zip_key = str(zip_path.relative_to(self.base_dir))
        
        # Check if already unzipped
        if self._is_unzipped(zip_path, dest_dir):
            self.stats['skipped'] += 1
            return True
        
        if dry_run:
            logger.info(f"🔍 Would unzip: {zip_path} → {dest_dir}")
            return True
        
        try:
            # Create destination directory
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract using chosen method
            if self.use_7z:
                success, file_list = self._unzip_with_7z(zip_path, dest_dir)
            else:
                success, file_list = self._unzip_with_python(zip_path, dest_dir)
            
            if not success:
                self.stats['failed'] += 1
                return False
            
            # Log success
            self.unzip_log['completed_files'][zip_key] = {
                'zip_path': str(zip_path),
                'dest_dir': str(dest_dir),
                'extracted_files': file_list[:100],  # Limit log size
                'file_count': len(file_list),
                'unzipped_at': datetime.now().isoformat(),
            }
            
            self.stats['unzipped'] += 1
            
            # Remove ZIP file if requested
            if self.remove_zips:
                zip_path.unlink()
                self.stats['removed'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to unzip {zip_path.name}: {e}")
            self.unzip_log['failed_files'][zip_key] = {
                'error': str(e),
                'failed_at': datetime.now().isoformat(),
            }
            self.stats['failed'] += 1
            return False
    
    def find_zip_files(
        self,
        categories: Optional[Set[str]] = None,
        years: Optional[Set[str]] = None
    ) -> List[Path]:
        """
        Find all ZIP files in bulk-downloads directory
        
        Args:
            categories: Optional set of categories to filter (e.g., {'candidate-master'})
            years: Optional set of years to filter (e.g., {'2020', '2022', '2024'})
        
        Returns:
            List of ZIP file paths
        """
        zip_files = []
        
        # Recursively find all .zip files
        for zip_path in self.bulk_dir.rglob("*.zip"):
            # Filter by category
            if categories:
                # Get category from path (e.g., bulk-downloads/candidate-master/2024/cn24.zip)
                relative_path = zip_path.relative_to(self.bulk_dir)
                category = relative_path.parts[0] if len(relative_path.parts) > 0 else None
                
                if category not in categories:
                    continue
            
            # Filter by year
            if years:
                # Get year from path (e.g., bulk-downloads/candidate-master/2024/cn24.zip)
                relative_path = zip_path.relative_to(self.bulk_dir)
                year = relative_path.parts[1] if len(relative_path.parts) > 1 else None
                
                if year not in years:
                    continue
            
            zip_files.append(zip_path)
        
        return sorted(zip_files)
    
    def unzip_all(
        self,
        categories: Optional[Set[str]] = None,
        years: Optional[Set[str]] = None,
        dry_run: bool = False
    ):
        """
        Unzip all FEC bulk data files (with optional parallel processing)
        
        Args:
            categories: Optional set of categories to filter
            years: Optional set of years to filter
            dry_run: If True, don't actually unzip
        """
        logger.info("=" * 70)
        logger.info("FEC BULK DATA UNZIPPER (HIGH-PERFORMANCE EDITION)")
        logger.info("=" * 70)
        logger.info(f"📂 Source: {self.bulk_dir}")
        logger.info(f"📁 Destination: {self.unzipped_dir}")
        logger.info(f"⚙️  Method: {'7-Zip' if self.use_7z else 'Python zipfile'}")
        logger.info(f"👷 Workers: {self.workers} {'(parallel)' if self.workers > 1 else '(single-threaded)'}")
        if categories:
            logger.info(f"📋 Categories: {', '.join(sorted(categories))}")
        if years:
            logger.info(f"📅 Years: {', '.join(sorted(years))}")
        if dry_run:
            logger.warning("🔍 DRY RUN MODE - No files will be unzipped")
        logger.info("")
        
        # Find all ZIP files
        zip_files = self.find_zip_files(categories=categories, years=years)
        self.stats['total_zips'] = len(zip_files)
        
        if not zip_files:
            logger.warning("⚠️  No ZIP files found")
            return
        
        logger.info(f"Found {len(zip_files)} ZIP files")
        logger.info("")
        
        # Prepare unzip tasks
        tasks = []
        for zip_path in zip_files:
            relative_path = zip_path.relative_to(self.bulk_dir)
            dest_dir = self.unzipped_dir / relative_path.parent / zip_path.stem
            tasks.append((zip_path, dest_dir, dry_run))
        
        # Execute unzipping (parallel or sequential)
        if self.workers > 1 and not dry_run:
            logger.info(f"🚀 Starting parallel extraction with {self.workers} workers")
            self._unzip_parallel(tasks)
        else:
            logger.info(f"📦 Starting sequential extraction")
            for zip_path, dest_dir, dry_run in tqdm(tasks, desc="Unzipping", unit="file"):
                self._unzip_file(zip_path, dest_dir, dry_run)
                
                # Save log periodically
                if not dry_run and self.stats['unzipped'] % 10 == 0:
                    self._save_log()
        
        # Save final log
        if not dry_run:
            self._save_log()
        
        # Print summary
        logger.info("")
        logger.info("=" * 70)
        logger.info("SUMMARY")
        logger.info("=" * 70)
        logger.info(f"📊 Total ZIP files: {self.stats['total_zips']}")
        logger.info(f"✅ Unzipped: {self.stats['unzipped']}")
        logger.info(f"⏭️  Skipped: {self.stats['skipped']}")
        logger.info(f"❌ Failed: {self.stats['failed']}")
        if self.remove_zips:
            logger.info(f"🗑️  Removed: {self.stats['removed']}")
        logger.info("")
        
        if self.stats['failed'] > 0:
            logger.warning("⚠️  Some files failed to unzip. Check unzip_log.json for details.")
    
    def _unzip_parallel(self, tasks: List[Tuple[Path, Path, bool]]):
        """Unzip files in parallel using ProcessPoolExecutor"""
        # Prepare tasks with all necessary args for module-level worker
        worker_tasks = [
            (zip_path, dest_dir, dry_run, self.base_dir, self.use_7z, self.remove_zips, self.method)
            for zip_path, dest_dir, dry_run in tasks
        ]
        
        with ProcessPoolExecutor(max_workers=self.workers) as executor:
            # Submit all tasks
            futures = {executor.submit(_unzip_worker, task): task[0] for task in worker_tasks}
            
            # Track progress with tqdm
            with tqdm(total=len(futures), desc="Unzipping (parallel)", unit="file") as pbar:
                for future in as_completed(futures):
                    zip_path = futures[future]
                    try:
                        success, zip_path_result, dest_dir, file_count = future.result()
                        if success:
                            self.stats['unzipped'] += 1
                            
                            # Log to unzip_log
                            zip_key = str(zip_path_result.relative_to(self.base_dir))
                            self.unzip_log['completed_files'][zip_key] = {
                                'zip_path': str(zip_path_result),
                                'dest_dir': str(dest_dir),
                                'file_count': file_count,
                                'unzipped_at': datetime.now().isoformat(),
                            }
                            
                            if self.remove_zips:
                                self.stats['removed'] += 1
                        else:
                            self.stats['failed'] += 1
                            logger.error(f"❌ Failed to unzip {zip_path.name}")
                            
                            # Log failure
                            zip_key = str(zip_path_result.relative_to(self.base_dir))
                            self.unzip_log['failed_files'][zip_key] = {
                                'error': 'Extraction failed',
                                'failed_at': datetime.now().isoformat(),
                            }
                    except Exception as e:
                        logger.error(f"❌ Worker exception for {zip_path.name}: {e}")
                        self.stats['failed'] += 1
                    
                    pbar.update(1)
                    
                    # Save log periodically
                    if self.stats['unzipped'] % 10 == 0:
                        self._save_log()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Unzip FEC bulk data files (High-Performance Edition)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    from fec_paths import default_fec_data_dir

    parser.add_argument(
        '--base-dir',
        type=Path,
        default=None,
        help=f'Base directory containing bulk-downloads/ (default: {default_fec_data_dir()})'
    )
    
    parser.add_argument(
        '--category',
        type=str,
        help='Specific category to unzip (e.g., candidate-master, contributions-by-individuals)'
    )
    
    parser.add_argument(
        '--years',
        type=str,
        help='Comma-separated list of years to unzip (e.g., 2020,2022,2024)'
    )
    
    parser.add_argument(
        '--latest',
        type=int,
        help='Only unzip the latest N years (e.g., --latest 2 for most recent 2 years)'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=1,
        help='Number of parallel workers (default: 1, recommend: 4-8 for best performance)'
    )
    
    parser.add_argument(
        '--method',
        type=str,
        default='auto',
        choices=['python', '7z', 'auto'],
        help='Extraction method: python (portable), 7z (2-3x faster), auto (use 7z if available)'
    )
    
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Skip already unzipped files'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be unzipped without actually unzipping'
    )
    
    parser.add_argument(
        '--remove-zips',
        action='store_true',
        help='Remove ZIP files after successful extraction (saves 50%% disk space)'
    )
    
    args = parser.parse_args()
    if args.base_dir is None:
        args.base_dir = default_fec_data_dir()

    # Parse categories and years
    categories = {args.category} if args.category else None
    years = set(args.years.split(',')) if args.years else None
    
    # Handle --latest option (auto-determine latest N years)
    if args.latest:
        if args.years:
            logger.error("❌ Cannot use both --years and --latest options together")
            sys.exit(1)
        
        # Find all available years in the bulk-downloads directory
        base_dir = Path(args.base_dir)
        bulk_dir = base_dir / "bulk-downloads"
        
        if not bulk_dir.exists():
            logger.error(f"❌ Bulk downloads directory not found: {bulk_dir}")
            sys.exit(1)
        
        # Scan for all year directories
        available_years = set()
        for category_dir in bulk_dir.iterdir():
            if category_dir.is_dir():
                for year_dir in category_dir.iterdir():
                    if year_dir.is_dir() and year_dir.name.isdigit():
                        available_years.add(year_dir.name)
        
        if not available_years:
            logger.error("❌ No year directories found in bulk-downloads")
            sys.exit(1)
        
        # Get latest N years
        sorted_years = sorted(available_years, reverse=True)
        latest_years = sorted_years[:args.latest]
        years = set(latest_years)
        
        logger.info(f"📅 Auto-selected latest {args.latest} years: {', '.join(sorted(latest_years, reverse=True))}")
        logger.info("")
    
    # Auto-detect optimal worker count if requested
    if args.workers == 0:
        args.workers = max(1, cpu_count() - 1)
        logger.info(f"Auto-detected {args.workers} workers (CPU count: {cpu_count()})")
    
    # Create unzipper
    unzipper = FECBulkUnzipper(
        base_dir=args.base_dir,
        resume=args.resume,
        remove_zips=args.remove_zips,
        method=args.method,
        workers=args.workers
    )
    
    # Unzip all files
    unzipper.unzip_all(
        categories=categories,
        years=years,
        dry_run=args.dry_run
    )


if __name__ == '__main__':
    main()
