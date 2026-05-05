#!/usr/bin/env python3
"""
OpenStates Document Downloader

Downloads bill documents and versions from the local PostgreSQL OpenStates database.
Supports incremental reruns and recovery from failures.

Directory Structure:
    /mnt/d/openstates_documents/  (or configurable base path)
    ├── versions/
    │   ├── AL/
    │   │   ├── 2025/
    │   │   │   ├── www.legislature.state.al.us_...pdf
    │   │   │   └── ...
    │   │   └── 2026/
    │   ├── CA/
    │   │   ├── 2025/
    │   │   └── 2026/
    │   └── ...
    ├── documents/
    │   ├── MA/
    │   │   ├── 2025/
    │   │   │   ├── malegislature.gov_...pdf
    │   │   │   └── ...
    │   │   └── 2026/
    │   └── ...
    └── download_log.json

Database: PostgreSQL OpenStates data at localhost:5433
Total Documents: ~4.5 million (3.5M versions + 1M documents)

Usage:
    # Download everything
    python download_documents.py

    # Custom database connection
    python download_documents.py --db-url "postgresql://user:pass@localhost:5433/openstates"

    # Custom base directory
    python download_documents.py --base-dir /mnt/d/openstates_docs

    # Download only specific years
    python download_documents.py --years 2024,2025

    # Download only documents (not versions)
    python download_documents.py --type documents

    # Limit number of files to download
    python download_documents.py --limit 1000

    # Resume interrupted download
    python download_documents.py --resume

    # Dry run
    python download_documents.py --dry-run
"""

import argparse
import json
import psycopg2
import requests
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from loguru import logger
import time
from tqdm import tqdm
from urllib.parse import urlparse


class OpenStatesDocumentDownloader:
    """Download OpenStates documents from PostgreSQL database"""
    
    def __init__(
        self,
        base_dir: Path,
        db_url: str = "postgresql://postgres:password@localhost:5433/openstates",
        resume: bool = False
    ):
        """
        Initialize OpenStates document downloader
        
        Args:
            base_dir: Base directory for downloads
            db_url: PostgreSQL connection URL
            resume: Resume interrupted downloads
        """
        self.base_dir = Path(base_dir)
        self.versions_dir = self.base_dir / "versions"
        self.documents_dir = self.base_dir / "documents"
        self.log_file = self.base_dir / "download_log.json"
        self.db_url = db_url
        self.resume = resume
        
        # Create directories
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir.mkdir(exist_ok=True)
        self.documents_dir.mkdir(exist_ok=True)
        
        # Load download log
        self.download_log = self._load_log()
        
        # Session for HTTP requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (OpenStates Document Downloader/1.0)'
        })
        
        # Database connection
        self.conn = None
    
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
            'stats': {
                'versions': {'downloaded': 0, 'failed': 0, 'skipped': 0},
                'documents': {'downloaded': 0, 'failed': 0, 'skipped': 0}
            }
        }
    
    def _save_log(self):
        """Save download log"""
        self.download_log['last_updated'] = datetime.now().isoformat()
        with open(self.log_file, 'w') as f:
            json.dump(self.download_log, f, indent=2)
    
    def _connect_db(self):
        """Connect to PostgreSQL database"""
        if not self.conn or self.conn.closed:
            logger.info(f"🔌 Connecting to database...")
            self.conn = psycopg2.connect(self.db_url)
    
    def _close_db(self):
        """Close database connection"""
        if self.conn and not self.conn.closed:
            self.conn.close()
    
    def _sanitize_filename(self, text: str) -> str:
        """
        Convert text to safe filename in snake_case
        
        Args:
            text: Text to sanitize
        
        Returns:
            Safe filename string
        """
        # Remove/replace unsafe characters
        text = str(text).lower()
        # Replace spaces and special chars with underscores
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s-]+', '_', text)
        # Remove leading/trailing underscores
        text = text.strip('_')
        # Limit length
        if len(text) > 200:
            text = text[:200]
        return text or 'unknown'
    
    def _url_to_filename(self, url: str) -> str:
        """
        Convert URL to safe filename
        
        Removes http://, https://, and converts special characters to underscores
        to create a unique filename based on the URL.
        
        Args:
            url: Document URL
        
        Returns:
            Safe filename string (without extension)
        """
        # Remove protocol
        filename = url.replace('https://', '').replace('http://', '')
        
        # Remove trailing slashes
        filename = filename.rstrip('/')
        
        # Replace special characters with underscores
        # Keep alphanumeric, dots, and hyphens
        filename = re.sub(r'[^\w\.-]', '_', filename)
        
        # Replace multiple underscores with single
        filename = re.sub(r'_+', '_', filename)
        
        # Remove leading/trailing underscores
        filename = filename.strip('_')
        
        # Limit length (leave room for extension)
        if len(filename) > 200:
            # Keep start and end of URL for uniqueness
            filename = filename[:100] + '_' + filename[-99:]
        
        return filename or 'document'
    
    def _get_file_extension(self, url: str, media_type: Optional[str]) -> str:
        """
        Determine file extension from URL or media type
        
        Args:
            url: Document URL
            media_type: MIME type
        
        Returns:
            File extension with dot (e.g., '.pdf')
        """
        # Try to get from URL first
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Common extensions
        for ext in ['.pdf', '.html', '.htm', '.doc', '.docx', '.txt', '.xml']:
            if path.endswith(ext):
                return ext
        
        # Try media type
        if media_type:
            media_map = {
                'application/pdf': '.pdf',
                'text/html': '.html',
                'text/plain': '.txt',
                'application/msword': '.doc',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
                'application/xml': '.xml',
                'text/xml': '.xml',
            }
            return media_map.get(media_type.lower(), '.pdf')
        
        # Default to PDF (most common for legislative documents)
        return '.pdf'
    
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
    
    def _download_file(
        self,
        url: str,
        dest_path: Path,
        description: str,
        doc_type: str
    ) -> bool:
        """
        Download a single file
        
        Args:
            url: URL to download
            dest_path: Destination file path
            description: Description for progress bar
            doc_type: 'versions' or 'documents' for stats tracking
        
        Returns:
            True if successful, False otherwise
        """
        if self._is_downloaded(url, dest_path):
            self.download_log['stats'][doc_type]['skipped'] += 1
            return True
        
        try:
            # Download with timeout
            response = self.session.get(url, stream=True, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            # Create parent directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get total size
            total_size = int(response.headers.get('content-length', 0))
            
            # Download
            with open(dest_path, 'wb') as f:
                if total_size > 0:
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
                else:
                    # No content-length header
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            
            # Log success
            file_size = dest_path.stat().st_size
            self.download_log['completed_files'][url] = {
                'path': str(dest_path),
                'size': file_size,
                'downloaded_at': datetime.now().isoformat(),
            }
            self.download_log['stats'][doc_type]['downloaded'] += 1
            
            # Save log periodically (every 100 downloads)
            if self.download_log['stats'][doc_type]['downloaded'] % 100 == 0:
                self._save_log()
            
            return True
            
        except requests.exceptions.HTTPError as e:
            # Handle 403/404 as "not available"
            if e.response.status_code in [403, 404]:
                self.download_log['failed_files'][url] = {
                    'error': f"HTTP {e.response.status_code}: Not available",
                    'failed_at': datetime.now().isoformat(),
                }
                self.download_log['stats'][doc_type]['failed'] += 1
                return False
            else:
                logger.warning(f"⚠️  HTTP {e.response.status_code} for {url[:60]}...")
                self.download_log['failed_files'][url] = {
                    'error': str(e),
                    'failed_at': datetime.now().isoformat(),
                }
                self.download_log['stats'][doc_type]['failed'] += 1
                return False
                
        except Exception as e:
            logger.debug(f"Failed: {url[:60]}... - {e}")
            self.download_log['failed_files'][url] = {
                'error': str(e),
                'failed_at': datetime.now().isoformat(),
            }
            self.download_log['stats'][doc_type]['failed'] += 1
            return False
    
    def download_bill_versions(
        self,
        years: Optional[List[int]] = None,
        states: Optional[List[str]] = None,
        limit: Optional[int] = None,
        dry_run: bool = False
    ) -> Tuple[int, int, int]:
        """
        Download bill version documents
        
        Args:
            years: Optional list of years to download
            states: Optional list of state codes (e.g., ['CA', 'TX']) to download
            limit: Optional limit on number of files
            dry_run: If True, only show what would be downloaded
        
        Returns:
            Tuple of (successful, skipped, failed) counts
        """
        self._connect_db()
        cur = self.conn.cursor()
        
        # Build query
        query = """
            SELECT 
                bv.id,
                bv.note,
                bl.url,
                bl.media_type,
                b.identifier as bill_id,
                EXTRACT(YEAR FROM b.created_at)::int as year,
                ls.jurisdiction_id,
                SUBSTRING(ls.jurisdiction_id FROM 'ocd-jurisdiction/country:us/state:([a-z]{2})') as state
            FROM opencivicdata_billversion bv
            JOIN opencivicdata_billversionlink bl ON bl.version_id = bv.id
            JOIN opencivicdata_bill b ON bv.bill_id = b.id
            JOIN opencivicdata_legislativesession ls ON b.legislative_session_id = ls.id
            WHERE bl.url IS NOT NULL
        """
        
        params = []
        if years:
            query += " AND EXTRACT(YEAR FROM b.created_at) = ANY(%s)"
            params.append(years)
        
        if states:
            query += " AND SUBSTRING(ls.jurisdiction_id FROM 'ocd-jurisdiction/country:us/state:([a-z]{2})') = ANY(%s)"
            params.append([s.lower() for s in states])
        
        query += " ORDER BY state, year DESC, b.identifier"
        
        if limit:
            query += f" LIMIT {limit}"
        
        logger.info(f"📥 Querying bill versions from database...")
        cur.execute(query, params)
        
        results = cur.fetchall()
        total = len(results)
        
        logger.info(f"📊 Found {total:,} bill version documents")
        
        if dry_run:
            logger.info("🔍 DRY RUN - Sample documents that would be downloaded:")
            for row in results[:10]:
                version_id, note, url, media_type, bill_id, year, jurisdiction_id, state = row
                state_code = (state or 'unknown').upper()
                filename = self._url_to_filename(url)
                ext = self._get_file_extension(url, media_type)
                # Avoid double extensions
                if not filename.lower().endswith(ext.lower()):
                    filename = f"{filename}{ext}"
                print(f"  {state_code}/{year}/{filename}")
            if total > 10:
                print(f"  ... and {total - 10:,} more")
            return 0, 0, 0
        
        # Download files
        successful = 0
        failed = 0
        skipped = 0
        
        logger.info(f"⬇️  Downloading {total:,} bill versions...")
        
        for i, row in enumerate(results, 1):
            version_id, note, url, media_type, bill_id, year, jurisdiction_id, state = row
            
            # Create filename from URL to avoid overlaps across states
            filename = self._url_to_filename(url)
            ext = self._get_file_extension(url, media_type)
            
            # Avoid double extensions if URL already contains extension
            if not filename.lower().endswith(ext.lower()):
                filename = f"{filename}{ext}"
            
            # Create state/year directory structure
            state_code = (state or 'unknown').upper()
            state_dir = self.versions_dir / state_code / str(year)
            dest_path = state_dir / filename
            
            # Check if already downloaded
            if self._is_downloaded(url, dest_path):
                skipped += 1
                if i % 1000 == 0:
                    logger.info(f"  Progress: {i:,}/{total:,} ({i/total*100:.1f}%) - ✅ {successful:,} | ⏭️ {skipped:,} | ❌ {failed:,}")
                continue
            
            # Download
            description = f"[{i}/{total}] {bill_id} ({year})"
            success = self._download_file(url, dest_path, description, 'versions')
            
            if success:
                successful += 1
            else:
                failed += 1
            
            # Progress update every 1000 files
            if i % 1000 == 0:
                logger.info(f"  Progress: {i:,}/{total:,} ({i/total*100:.1f}%) - ✅ {successful:,} | ⏭️ {skipped:,} | ❌ {failed:,}")
                self._save_log()
            
            # No rate limiting - download as fast as possible
            # time.sleep(0.1)  # Removed for speed
        
        # Final save
        self._save_log()
        
        cur.close()
        return successful, skipped, failed
    
    def download_bill_documents(
        self,
        years: Optional[List[int]] = None,
        states: Optional[List[str]] = None,
        limit: Optional[int] = None,
        dry_run: bool = False
    ) -> Tuple[int, int, int]:
        """
        Download bill documents (fiscal notes, committee statements, etc.)
        
        Args:
            years: Optional list of years to download
            states: Optional list of state codes (e.g., ['CA', 'TX']) to download
            limit: Optional limit on number of files
            dry_run: If True, only show what would be downloaded
        
        Returns:
            Tuple of (successful, skipped, failed) counts
        """
        self._connect_db()
        cur = self.conn.cursor()
        
        # Build query
        query = """
            SELECT 
                bd.id,
                bd.note,
                bdl.url,
                bdl.media_type,
                b.identifier as bill_id,
                EXTRACT(YEAR FROM b.created_at)::int as year,
                ls.jurisdiction_id,
                SUBSTRING(ls.jurisdiction_id FROM 'ocd-jurisdiction/country:us/state:([a-z]{2})') as state
            FROM opencivicdata_billdocument bd
            JOIN opencivicdata_billdocumentlink bdl ON bdl.document_id = bd.id
            JOIN opencivicdata_bill b ON bd.bill_id = b.id
            JOIN opencivicdata_legislativesession ls ON b.legislative_session_id = ls.id
            WHERE bdl.url IS NOT NULL
        """
        
        params = []
        if years:
            query += " AND EXTRACT(YEAR FROM b.created_at) = ANY(%s)"
            params.append(years)
        
        if states:
            query += " AND SUBSTRING(ls.jurisdiction_id FROM 'ocd-jurisdiction/country:us/state:([a-z]{2})') = ANY(%s)"
            params.append([s.lower() for s in states])
        
        query += " ORDER BY state, year DESC, b.identifier"
        
        if limit:
            query += f" LIMIT {limit}"
        
        logger.info(f"📥 Querying bill documents from database...")
        cur.execute(query, params)
        
        results = cur.fetchall()
        total = len(results)
        
        logger.info(f"📊 Found {total:,} bill documents")
        
        if dry_run:
            logger.info("🔍 DRY RUN - Sample documents that would be downloaded:")
            for row in results[:10]:
                doc_id, note, url, media_type, bill_id, year, jurisdiction_id, state = row
                state_code = (state or 'unknown').upper()
                filename = self._url_to_filename(url)
                ext = self._get_file_extension(url, media_type)
                # Avoid double extensions
                if not filename.lower().endswith(ext.lower()):
                    filename = f"{filename}{ext}"
                print(f"  {state_code}/{year}/{filename}")
            if total > 10:
                print(f"  ... and {total - 10:,} more")
            return 0, 0, 0
        
        # Download files
        successful = 0
        failed = 0
        skipped = 0
        
        logger.info(f"⬇️  Downloading {total:,} bill documents...")
        
        for i, row in enumerate(results, 1):
            doc_id, note, url, media_type, bill_id, year, jurisdiction_id, state = row
            
            # Create filename from URL to avoid overlaps across states
            filename = self._url_to_filename(url)
            ext = self._get_file_extension(url, media_type)
            
            # Avoid double extensions if URL already contains extension
            if not filename.lower().endswith(ext.lower()):
                filename = f"{filename}{ext}"
            
            # Create state/year directory structure
            state_code = (state or 'unknown').upper()
            state_dir = self.documents_dir / state_code / str(year)
            dest_path = state_dir / filename
            
            # Check if already downloaded
            if self._is_downloaded(url, dest_path):
                skipped += 1
                if i % 1000 == 0:
                    logger.info(f"  Progress: {i:,}/{total:,} ({i/total*100:.1f}%) - ✅ {successful:,} | ⏭️ {skipped:,} | ❌ {failed:,}")
                continue
            
            # Download
            description = f"[{i}/{total}] {bill_id} ({year})"
            success = self._download_file(url, dest_path, description, 'documents')
            
            if success:
                successful += 1
            else:
                failed += 1
            
            # Progress update every 1000 files
            if i % 1000 == 0:
                logger.info(f"  Progress: {i:,}/{total:,} ({i/total*100:.1f}%) - ✅ {successful:,} | ⏭️ {skipped:,} | ❌ {failed:,}")
                self._save_log()
            
            # No rate limiting - download as fast as possible
            # time.sleep(0.1)  # Removed for speed
        
        # Final save
        self._save_log()
        
        cur.close()
        return successful, skipped, failed


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Download OpenStates documents from PostgreSQL database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download everything
  python download_documents.py

  # Download only 2024-2025 documents
  python download_documents.py --years 2024,2025

  # Download only bill documents (not versions)
  python download_documents.py --type documents

  # Download limited number for testing
  python download_documents.py --limit 100 --dry-run

  # Resume interrupted download
  python download_documents.py --resume

  # Custom database and directory
  python download_documents.py --db-url "postgresql://user:pass@host:port/db" --base-dir /mnt/d/docs
        """
    )
    
    parser.add_argument(
        '--base-dir',
        type=str,
        default='/mnt/d/openstates_documents',
        help='Base directory for downloads (default: /mnt/d/openstates_documents)'
    )
    
    parser.add_argument(
        '--db-url',
        type=str,
        default='postgresql://postgres:password@localhost:5433/openstates',
        help='PostgreSQL connection URL'
    )
    
    parser.add_argument(
        '--type',
        type=str,
        choices=['all', 'versions', 'documents'],
        default='all',
        help='Which document type to download (default: all)'
    )
    
    parser.add_argument(
        '--years',
        type=str,
        help='Comma-separated list of years (e.g., 2024,2025)'
    )
    
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated list of state codes (e.g., CA,TX,NY) to download specific states only'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of files to download (useful for testing)'
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
    
    # Parse years
    years = None
    if args.years:
        years = [int(y.strip()) for y in args.years.split(',')]
    
    # Parse states
    states = None
    if args.states:
        states = [s.strip().upper() for s in args.states.split(',')]
    
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Create downloader
    downloader = OpenStatesDocumentDownloader(
        base_dir=Path(args.base_dir),
        db_url=args.db_url,
        resume=args.resume
    )
    
    logger.info("📄 OpenStates Document Downloader")
    logger.info(f"📁 Base directory: {args.base_dir}")
    logger.info(f"🔌 Database: {args.db_url.split('@')[1] if '@' in args.db_url else args.db_url}")
    logger.info("")
    
    # Download based on type
    total_successful = 0
    total_skipped = 0
    total_failed = 0
    
    try:
        if args.type in ['all', 'versions']:
            logger.info("=" * 60)
            logger.info("📥 Downloading Bill Versions")
            logger.info("=" * 60)
            s, sk, f = downloader.download_bill_versions(
                years=years,
                states=states,
                limit=args.limit,
                dry_run=args.dry_run
            )
            total_successful += s
            total_skipped += sk
            total_failed += f
        
        if args.type in ['all', 'documents']:
            logger.info("\n" + "=" * 60)
            logger.info("📥 Downloading Bill Documents")
            logger.info("=" * 60)
            s, sk, f = downloader.download_bill_documents(
                years=years,
                states=states,
                limit=args.limit,
                dry_run=args.dry_run
            )
            total_successful += s
            total_skipped += sk
            total_failed += f
        
        # Summary
        if not args.dry_run:
            logger.info("\n" + "=" * 60)
            logger.info("📊 Download Summary:")
            logger.info(f"  ✅ Successful: {total_successful:,}")
            logger.info(f"  ⏭️  Skipped: {total_skipped:,}")
            logger.info(f"  ❌ Failed: {total_failed:,}")
            logger.info(f"  📁 Base directory: {args.base_dir}")
            logger.info("=" * 60)
    
    finally:
        # Close database connection
        downloader._close_db()


if __name__ == '__main__':
    main()
