"""
Bulk Legislative Data Download from Plural Policy

Instead of making thousands of API calls, download complete legislative
sessions in bulk from https://open.pluralpolicy.com/data/

This is MUCH faster and has no rate limits!

Data Available:
- CSV: Bills & votes per session (https://open.pluralpolicy.com/data/session-csv/)
- JSON: Bills with full text (https://open.pluralpolicy.com/data/session-json/)
- People: Legislator data (7,300+ state legislators)
- PostgreSQL: Complete database dump (https://data.openstates.org/postgres/monthly/)

Usage:
    # Download all 2024 sessions as CSV
    python scripts/bulk_legislative_download.py --year 2024 --format csv
    
    # Download specific states as JSON
    python scripts/bulk_legislative_download.py --states AL,CA,TX --format json
    
    # Download legislator data for all states
    python scripts/bulk_legislative_download.py --legislators
    
    # Download PostgreSQL dump (monthly snapshot)
    python scripts/bulk_legislative_download.py --postgres --month 2026-04
"""

import asyncio
import argparse
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import zipfile
import gzip

import httpx
import pandas as pd
from loguru import logger


class BulkLegislativeDownloader:
    """
    Download bulk legislative data from Plural Policy / Open States.
    
    Advantages over API:
    - No rate limits (bulk downloads are encouraged!)
    - Complete session data in one download
    - Faster processing (local files)
    - Includes full bill text
    - Monthly PostgreSQL dumps for SQL analysis
    """
    
    # Base URLs
    CSV_BASE = "https://data.openstates.org"
    JSON_BASE = "https://data.openstates.org"
    POSTGRES_BASE = "https://data.openstates.org/postgres/monthly"
    POSTGRES_SCHEMA_BASE = "https://data.openstates.org/postgres/schema"
    
    # All state codes
    STATES = [
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
        'DC', 'PR'  # DC and Puerto Rico
    ]
    
    def __init__(self, cache_dir: str = "data/cache/legislation_bulk"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Session data directory structure
        self.csv_dir = self.cache_dir / "csv"
        self.json_dir = self.cache_dir / "json"
        self.postgres_dir = self.cache_dir / "postgres"
        
        for d in [self.csv_dir, self.json_dir, self.postgres_dir]:
            d.mkdir(exist_ok=True)
    
    async def list_available_sessions(self) -> List[dict]:
        """
        List all available legislative sessions.
        
        Returns:
            List of session dicts with state, year, format info
        """
        logger.info("Fetching available sessions from Plural Policy...")
        
        # The bulk data page lists sessions
        # For now, we'll generate based on states and recent years
        # TODO: Could scrape https://open.pluralpolicy.com/data/session-csv/ for exact list
        
        sessions = []
        current_year = datetime.now().year
        
        for state in self.STATES:
            for year in range(2020, current_year + 1):
                sessions.append({
                    'state': state,
                    'year': year,
                    'session_id': f"{state.lower()}-{year}",
                    'csv_available': True,  # Most states
                    'json_available': True,
                })
        
        logger.info(f"✅ Found {len(sessions)} potential sessions")
        return sessions
    
    async def download_session_csv(
        self,
        state: str,
        year: int,
        session_id: Optional[str] = None
    ) -> Optional[Path]:
        """
        Download CSV data for a legislative session.
        
        Args:
            state: Two-letter state code
            year: Session year
            session_id: Specific session identifier (auto-generated if None)
            
        Returns:
            Path to downloaded CSV file or None if failed
        """
        state = state.upper()
        session_id = session_id or f"{state.lower()}-{year}"
        
        # CSV files are typically at:
        # https://data.openstates.org/session/csv/{state}/{session_id}.csv
        url = f"{self.CSV_BASE}/session/csv/{state.lower()}/{session_id}.csv"
        
        output_file = self.csv_dir / f"{session_id}.csv"
        
        if output_file.exists():
            logger.info(f"✓ Already downloaded: {output_file.name}")
            return output_file
        
        logger.info(f"Downloading CSV: {state} {year} from {url}")
        
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            try:
                response = await client.get(url)
                
                if response.status_code == 404:
                    logger.warning(f"  Session not found: {session_id}")
                    return None
                
                response.raise_for_status()
                
                # Save to file
                output_file.write_bytes(response.content)
                logger.info(f"  ✅ Saved to {output_file.name} ({len(response.content) / 1024:.1f} KB)")
                
                return output_file
                
            except Exception as e:
                logger.error(f"  Error downloading {session_id}: {e}")
                return None
    
    async def download_session_json(
        self,
        state: str,
        year: int,
        session_id: Optional[str] = None
    ) -> Optional[Path]:
        """
        Download JSON data for a legislative session (includes full text).
        
        Args:
            state: Two-letter state code
            year: Session year
            session_id: Specific session identifier
            
        Returns:
            Path to downloaded JSON file or None if failed
        """
        state = state.upper()
        session_id = session_id or f"{state.lower()}-{year}"
        
        # JSON files are typically compressed
        url = f"{self.JSON_BASE}/session/json/{state.lower()}/{session_id}.json.zip"
        
        output_file = self.json_dir / f"{session_id}.json.zip"
        
        if output_file.exists():
            logger.info(f"✓ Already downloaded: {output_file.name}")
            return output_file
        
        logger.info(f"Downloading JSON: {state} {year} from {url}")
        
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            try:
                response = await client.get(url)
                
                if response.status_code == 404:
                    logger.warning(f"  Session not found: {session_id}")
                    return None
                
                response.raise_for_status()
                
                # Save to file
                output_file.write_bytes(response.content)
                logger.info(f"  ✅ Saved to {output_file.name} ({len(response.content) / 1024 / 1024:.1f} MB)")
                
                return output_file
                
            except Exception as e:
                logger.error(f"  Error downloading {session_id}: {e}")
                return None
    
    async def download_postgres_dump(self, month: Optional[str] = None) -> Optional[tuple[Path, Path]]:
        """
        Download PostgreSQL database dump (entire Open States database!).
        
        Downloads TWO files:
        1. Schema file: Creates all tables, indexes, constraints (~50 MB)
        2. Data file: Contains all the actual data (~10 GB)
        
        This is a LARGE download (~10 GB) but gives you the complete dataset including:
        - All 7,300+ state legislators with full details
        - All bills and votes from 2020+ across all 50 states
        - Committee memberships and assignments
        - Full text of legislation
        
        Args:
            month: Month in YYYY-MM format (default: current month)
            
        Returns:
            Tuple of (schema_file_path, data_file_path) or None if failed
        """
        if month is None:
            month = datetime.now().strftime("%Y-%m")
        
        schema_url = f"{self.POSTGRES_SCHEMA_BASE}/{month}-schema.pgdump"
        data_url = f"{self.POSTGRES_BASE}/{month}-public.pgdump"
        
        schema_file = self.postgres_dir / f"{month}-schema.pgdump"
        data_file = self.postgres_dir / f"{month}-public.pgdump"
        
        logger.info(f"Downloading OpenStates PostgreSQL dump for {month}...")
        logger.info("This requires TWO files:")
        logger.info("  1. Schema file: ~50 MB (creates tables)")
        logger.info("  2. Data file: ~10 GB (contains all data)")
        logger.info("")
        
        # Download schema file first
        logger.info("📥 Step 1/2: Downloading schema file...")
        if schema_file.exists():
            logger.info(f"  ✓ Already downloaded: {schema_file.name}")
        else:
            async with httpx.AsyncClient(timeout=600.0, follow_redirects=True) as client:
                try:
                    async with client.stream('GET', schema_url) as response:
                        if response.status_code == 404:
                            logger.error(f"Schema file not available for {month}")
                            logger.info("Try a different month or check https://data.openstates.org/postgres/schema/")
                            return None
                        
                        response.raise_for_status()
                        total_size = int(response.headers.get('content-length', 0))
                        
                        with open(schema_file, 'wb') as f:
                            downloaded = 0
                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                f.write(chunk)
                                downloaded += len(chunk)
                        
                        logger.info(f"  ✅ Schema saved: {schema_file.name} ({downloaded / 1024 / 1024:.1f} MB)")
                
                except Exception as e:
                    logger.error(f"Error downloading schema file: {e}")
                    return None
        
        # Download data file
        logger.info("\n📥 Step 2/2: Downloading data file...")
        logger.warning("This is LARGE (~10 GB) and may take a while!")
        logger.info("Database includes:")
        logger.info("  - 7,300+ state legislators")
        logger.info("  - All bills & votes (2020+)")
        logger.info("  - Committee data")
        logger.info("  - Full bill text")
        logger.info("")
        
        if data_file.exists():
            logger.info(f"  ✓ Already downloaded: {data_file.name}")
        else:
            async with httpx.AsyncClient(timeout=3600.0, follow_redirects=True) as client:
                try:
                    async with client.stream('GET', data_url) as response:
                        if response.status_code == 404:
                            logger.error(f"Data dump not available for {month}")
                            logger.info("Try a different month or check https://data.openstates.org/postgres/monthly/")
                            return None
                        
                        response.raise_for_status()
                        total_size = int(response.headers.get('content-length', 0))
                        
                        with open(data_file, 'wb') as f:
                            downloaded = 0
                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                if total_size > 0:
                                    pct = (downloaded / total_size) * 100
                                    if downloaded % (50 * 1024 * 1024) == 0:  # Log every 50MB
                                        logger.info(f"  Progress: {pct:.1f}% ({downloaded / 1024 / 1024:.1f} MB)")
                        
                        logger.info(f"  ✅ Data saved: {data_file.name} ({downloaded / 1024 / 1024:.1f} MB)")
                
                except Exception as e:
                    logger.error(f"Error downloading data file: {e}")
                    if schema_file.exists():
                        logger.info(f"Schema file is available at: {schema_file}")
                    return None
        
        logger.info("\n✅ Both files downloaded successfully!")
        logger.info(f"  Schema: {schema_file}")
        logger.info(f"  Data:   {data_file}")
        logger.info("\nNext step: Load into PostgreSQL with:")
        logger.info(f"  ./scripts/setup_openstates_db.sh")
        
        return (schema_file, data_file)
    
    async def download_legislators(
        self,
        states: Optional[List[str]] = None
    ) -> Optional[Path]:
        """
        Download legislator data from Open States/Plural Policy.
        
        NOTE: Plural Policy provides legislator data through their GraphQL API
        or the PostgreSQL dumps. There isn't a dedicated bulk CSV download for 
        just legislators, but you can:
        
        1. Use the PostgreSQL dump (includes all 7,300+ legislators)
        2. Use the Open States GraphQL API with bulk queries
        3. Extract from session JSON files (includes sponsor info)
        
        This method will download the PostgreSQL dump which includes all legislators.
        
        Args:
            states: List of state codes (not used for PostgreSQL dump)
            
        Returns:
            Path to PostgreSQL dump file
        """
        logger.info("=" * 80)
        logger.info("LEGISLATOR DATA DOWNLOAD")
        logger.info("=" * 80)
        logger.info("")
        logger.info("Legislator data is included in the PostgreSQL database dump.")
        logger.info("This includes all 7,300+ state legislators with full details:")
        logger.info("  - Names, party affiliation, district")
        logger.info("  - Contact information (email, phone, address)")
        logger.info("  - Committee memberships")
        logger.info("  - Bill sponsorships")
        logger.info("")
        
        # Download the PostgreSQL dump
        return await self.download_postgres_dump()
    
    async def download_all_states(
        self,
        year: int,
        format: str = "csv",
        states: Optional[List[str]] = None
    ) -> List[Path]:
        """
        Download data for all states (or specific states).
        
        Args:
            year: Legislative year
            format: 'csv' or 'json'
            states: List of state codes (None = all states)
            
        Returns:
            List of downloaded file paths
        """
        states = states or self.STATES
        
        logger.info(f"=" * 80)
        logger.info(f"BULK DOWNLOAD: {len(states)} states for {year} ({format.upper()})")
        logger.info(f"=" * 80)
        
        downloaded_files = []
        
        for state in states:
            if format == "csv":
                file = await self.download_session_csv(state, year)
            elif format == "json":
                file = await self.download_session_json(state, year)
            else:
                logger.error(f"Unknown format: {format}")
                continue
            
            if file:
                downloaded_files.append(file)
            
            # Small delay to be respectful
            await asyncio.sleep(0.5)
        
        logger.info(f"\n✅ Downloaded {len(downloaded_files)}/{len(states)} sessions")
        return downloaded_files
    
    def load_csv_session(self, file_path: Path) -> pd.DataFrame:
        """
        Load a session CSV file into pandas DataFrame.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            DataFrame with bill data
        """
        logger.info(f"Loading {file_path.name}...")
        df = pd.read_csv(file_path)
        logger.info(f"  ✅ Loaded {len(df)} bills")
        return df
    
    def merge_all_sessions(self, csv_files: List[Path]) -> pd.DataFrame:
        """
        Merge multiple session CSV files into one DataFrame.
        
        Args:
            csv_files: List of CSV file paths
            
        Returns:
            Combined DataFrame
        """
        logger.info(f"Merging {len(csv_files)} CSV files...")
        
        dfs = []
        for file in csv_files:
            try:
                df = pd.read_csv(file)
                # Add session info
                df['session_file'] = file.stem
                dfs.append(df)
            except Exception as e:
                logger.error(f"Error loading {file}: {e}")
        
        if not dfs:
            logger.error("No files loaded successfully")
            return pd.DataFrame()
        
        combined = pd.concat(dfs, ignore_index=True)
        logger.info(f"  ✅ Combined: {len(combined)} total bills from {len(dfs)} sessions")
        
        return combined


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Download bulk legislative data from Plural Policy"
    )
    parser.add_argument("--year", type=int, help="Legislative year to download")
    parser.add_argument(
        "--states",
        help="Comma-separated state codes (e.g., 'AL,CA,TX'). Default: all states"
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Download format (csv or json)"
    )
    parser.add_argument(
        "--postgres",
        action="store_true",
        help="Download PostgreSQL database dump instead"
    )
    parser.add_argument(
        "--legislators",
        action="store_true",
        help="Download legislator data (7,300+ state legislators)"
    )
    parser.add_argument(
        "--month",
        help="Month for PostgreSQL dump (YYYY-MM format)"
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge downloaded CSV files into single file"
    )
    
    args = parser.parse_args()
    
    downloader = BulkLegislativeDownloader()
    
    # PostgreSQL dump
    if args.postgres:
        await downloader.download_postgres_dump(args.month)
        return
    
    # Session downloads
    if not args.year:
        args.year = datetime.now().year
        logger.info(f"No year specified, using current year: {args.year}")
    
    states = args.states.split(',') if args.states else None
    
    # Download
    files = await downloader.download_all_states(
        year=args.year,
        format=args.format,
        states=states
    )
    
    # Merge if requested
    if args.merge and args.format == "csv":
        logger.info("\nMerging downloaded files...")
        combined = downloader.merge_all_sessions(files)
        
        output_file = downloader.cache_dir / f"all_states_{args.year}.csv"
        combined.to_csv(output_file, index=False)
        logger.info(f"✅ Merged file saved to {output_file}")
        logger.info(f"   Total bills: {len(combined)}")


if __name__ == "__main__":
    asyncio.run(main())
