"""
Dataverse API Client

Production-ready client for Harvard Dataverse following IQSS best practices.
Based on official API documentation: https://guides.dataverse.org/en/latest/api/index.html

Features:
- API token authentication
- Rate limiting with exponential backoff
- Checksum verification
- Version-aware caching
- Comprehensive error handling
- Pagination support
- Retry logic

Source: https://github.com/IQSS/dataverse
"""
import sys
from pathlib import Path
import hashlib
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger
import json

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import httpx
except ImportError:
    logger.error("httpx required. Install with: pip install httpx")
    httpx = None

from config import settings


class DataverseAPIError(Exception):
    """Custom exception for Dataverse API errors."""
    pass


class DataverseClient:
    """
    Official Dataverse API client following IQSS best practices.
    
    Usage:
        client = DataverseClient(api_key="your-key")
        metadata = await client.get_dataset_metadata("doi:10.7910/DVN/NJTBEM")
        result = await client.download_dataset("doi:10.7910/DVN/NJTBEM")
    """
    
    # API endpoints
    DATASET_ENDPOINT = "/api/datasets/:persistentId/"
    FILE_DOWNLOAD_ENDPOINT = "/api/access/datafile/{file_id}"
    SEARCH_ENDPOINT = "/api/search"
    
    # Rate limiting (requests per minute)
    DEFAULT_RATE_LIMIT = 100
    RATE_LIMIT_PERIOD = 60  # seconds
    
    def __init__(
        self,
        base_url: str = "https://dataverse.harvard.edu",
        api_key: Optional[str] = None,
        timeout: int = 120,
        max_retries: int = 3,
        cache_enabled: bool = True
    ):
        """
        Initialize Dataverse client.
        
        Args:
            base_url: Dataverse instance URL (default: Harvard Dataverse)
            api_key: API token for authentication (optional but recommended)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
            cache_enabled: Enable version-aware file caching
        """
        if not httpx:
            raise ImportError("httpx required. Install with: pip install httpx")
        
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or settings.dataverse_api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_enabled = cache_enabled
        
        # Cache directory
        self.cache_dir = Path("data/cache/dataverse")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Metadata cache
        self.metadata_cache_dir = self.cache_dir / "metadata"
        self.metadata_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Rate limiting state
        self._request_times: List[datetime] = []
        
        if self.api_key:
            logger.info("Dataverse client initialized with API key")
        else:
            logger.warning("Dataverse client initialized without API key (rate limits may apply)")
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers for API requests.
        
        Returns:
            Headers dictionary with API key if available
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "OralHealthPolicyPulse/1.0 (Civic Tech Research)"
        }
        
        if self.api_key:
            headers["X-Dataverse-key"] = self.api_key
        
        return headers
    
    async def _rate_limit_wait(self):
        """
        Implement client-side rate limiting.
        
        Enforces maximum requests per minute to avoid 429 errors.
        """
        now = datetime.now()
        
        # Remove requests older than the rate limit period
        self._request_times = [
            t for t in self._request_times 
            if (now - t).total_seconds() < self.RATE_LIMIT_PERIOD
        ]
        
        # Check if we've hit the limit
        if len(self._request_times) >= self.DEFAULT_RATE_LIMIT:
            oldest = min(self._request_times)
            wait_time = self.RATE_LIMIT_PERIOD - (now - oldest).total_seconds()
            
            if wait_time > 0:
                logger.warning(f"Rate limit reached. Waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
        
        # Record this request
        self._request_times.append(now)
    
    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """
        Make HTTP request with retry logic and exponential backoff.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            **kwargs: Additional arguments for httpx.request()
        
        Returns:
            HTTP response
        
        Raises:
            DataverseAPIError: If all retry attempts fail
        """
        await self._rate_limit_wait()
        
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.request(method, url, **kwargs)
                    
                    # Handle specific status codes
                    if response.status_code == 200:
                        return response
                    
                    elif response.status_code == 401:
                        raise DataverseAPIError(
                            "Unauthorized: API key required or invalid. "
                            "Sign up at https://dataverse.harvard.edu/loginpage.xhtml"
                        )
                    
                    elif response.status_code == 404:
                        raise DataverseAPIError(f"Not found: {url}")
                    
                    elif response.status_code == 429:
                        # Rate limited by server
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning(f"Server rate limit hit. Retrying after {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    
                    elif response.status_code >= 500:
                        # Server error - retry with backoff
                        if attempt < self.max_retries - 1:
                            wait_time = 2 ** attempt
                            logger.warning(f"Server error {response.status_code}. Retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            raise DataverseAPIError(f"Server error: HTTP {response.status_code}")
                    
                    else:
                        raise DataverseAPIError(
                            f"API error: HTTP {response.status_code} - {response.text}"
                        )
                
                except httpx.TimeoutException:
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"Request timeout. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise DataverseAPIError("Request timed out after all retry attempts")
                
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"Request failed: {e}. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise DataverseAPIError(f"Request failed: {e}")
        
        raise DataverseAPIError("All retry attempts exhausted")
    
    def _get_cached_metadata_path(self, persistent_id: str, version: str) -> Path:
        """Get path to cached metadata file."""
        safe_id = persistent_id.replace(":", "_").replace("/", "_")
        return self.metadata_cache_dir / f"{safe_id}_{version}.json"
    
    async def get_dataset_metadata(
        self,
        persistent_id: str,
        version: str = ":latest",
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get dataset metadata from Dataverse.
        
        Args:
            persistent_id: DOI or handle (e.g., "doi:10.7910/DVN/NJTBEM")
            version: Dataset version (":latest", ":draft", or specific version number)
            use_cache: Use cached metadata if available (for :latest version only)
        
        Returns:
            Dataset metadata dictionary or None if not found
        
        Example:
            metadata = await client.get_dataset_metadata("doi:10.7910/DVN/NJTBEM")
            files = metadata["data"]["latestVersion"]["files"]
        """
        # Check cache
        if use_cache and self.cache_enabled and version == ":latest":
            cache_file = self._get_cached_metadata_path(persistent_id, version)
            if cache_file.exists():
                # Check if cache is recent (less than 1 day old)
                cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
                if cache_age < timedelta(days=1):
                    logger.info(f"Using cached metadata (age: {cache_age.total_seconds() / 3600:.1f}h)")
                    with open(cache_file, 'r') as f:
                        return json.load(f)
        
        # Fetch from API
        url = f"{self.base_url}{self.DATASET_ENDPOINT}"
        params = {
            "persistentId": persistent_id,
        }
        
        # Add version if not :latest
        if version != ":latest":
            params["version"] = version
        
        logger.info(f"Fetching metadata for {persistent_id} (version: {version})")
        
        try:
            response = await self._request_with_retry(
                "GET",
                url,
                params=params,
                headers=self._get_headers()
            )
            
            metadata = response.json()
            
            # Cache the metadata
            if self.cache_enabled and version == ":latest":
                cache_file = self._get_cached_metadata_path(persistent_id, version)
                with open(cache_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                logger.debug(f"Cached metadata to {cache_file}")
            
            return metadata
        
        except DataverseAPIError as e:
            logger.error(f"Failed to fetch metadata: {e}")
            return None
    
    def _verify_checksum(self, content: bytes, expected_md5: Optional[str]) -> bool:
        """
        Verify file checksum.
        
        Args:
            content: File content bytes
            expected_md5: Expected MD5 checksum
        
        Returns:
            True if checksum matches or no checksum provided
        """
        if not expected_md5:
            logger.warning("No checksum provided - skipping verification")
            return True
        
        actual_md5 = hashlib.md5(content).hexdigest()
        
        if actual_md5.lower() == expected_md5.lower():
            logger.debug(f"✓ Checksum verified: {actual_md5}")
            return True
        else:
            logger.error(f"✗ Checksum mismatch! Expected: {expected_md5}, Got: {actual_md5}")
            return False
    
    async def download_file(
        self,
        file_id: int,
        output_path: Path,
        expected_checksum: Optional[str] = None,
        verify_checksum: bool = True
    ) -> bool:
        """
        Download a file from Dataverse with checksum verification.
        
        Args:
            file_id: Dataverse file ID
            output_path: Where to save the file
            expected_checksum: Expected MD5 checksum (if known)
            verify_checksum: Whether to verify checksum
        
        Returns:
            True if download successful and checksum valid
        
        Example:
            success = await client.download_file(
                file_id=123456,
                output_path=Path("data/municipalities.csv"),
                expected_checksum="abc123..."
            )
        """
        url = f"{self.base_url}{self.FILE_DOWNLOAD_ENDPOINT.format(file_id=file_id)}"
        
        logger.info(f"Downloading file {file_id} to {output_path.name}")
        
        try:
            response = await self._request_with_retry(
                "GET",
                url,
                headers=self._get_headers()
            )
            
            # Verify checksum if requested
            if verify_checksum and expected_checksum:
                if not self._verify_checksum(response.content, expected_checksum):
                    logger.error("Checksum verification failed - file may be corrupted")
                    return False
            
            # Save file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)
            
            file_size_mb = len(response.content) / (1024 * 1024)
            logger.success(f"✓ Downloaded {output_path.name} ({file_size_mb:.2f} MB)")
            
            return True
        
        except DataverseAPIError as e:
            logger.error(f"Download failed: {e}")
            return False
    
    async def download_dataset(
        self,
        persistent_id: str,
        output_dir: Optional[Path] = None,
        file_types: Optional[List[str]] = None,
        verify_checksums: bool = True
    ) -> Dict[str, Any]:
        """
        Download all files (or filtered subset) from a dataset.
        
        Args:
            persistent_id: Dataset DOI (e.g., "doi:10.7910/DVN/NJTBEM")
            output_dir: Where to save files (defaults to cache_dir/dataset_name)
            file_types: List of file extensions to download (e.g., [".csv", ".tab"])
                       If None, downloads all files
            verify_checksums: Whether to verify MD5 checksums
        
        Returns:
            Summary dictionary with download statistics
        
        Example:
            result = await client.download_dataset(
                "doi:10.7910/DVN/NJTBEM",
                file_types=[".csv", ".tab"]
            )
            print(f"Downloaded {result['downloaded']} files to {result['output_dir']}")
        """
        # Set output directory
        if output_dir is None:
            safe_id = persistent_id.replace(":", "_").replace("/", "_")
            output_dir = self.cache_dir / safe_id
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get metadata
        logger.info(f"Fetching dataset metadata for {persistent_id}")
        metadata = await self.get_dataset_metadata(persistent_id)
        
        if not metadata:
            return {
                "status": "error",
                "message": "Failed to fetch dataset metadata",
                "downloaded": 0,
                "failed": 0,
                "files": []
            }
        
        # Extract file list
        try:
            files = metadata["data"]["latestVersion"]["files"]
            logger.info(f"Found {len(files)} files in dataset")
        except KeyError:
            logger.error("Invalid metadata structure - cannot find files list")
            return {
                "status": "error",
                "message": "Invalid metadata structure",
                "downloaded": 0,
                "failed": 0,
                "files": []
            }
        
        # Filter by file type if specified
        if file_types:
            original_count = len(files)
            files = [
                f for f in files
                if any(f["dataFile"]["filename"].lower().endswith(ext.lower()) for ext in file_types)
            ]
            logger.info(f"Filtered to {len(files)} files matching {file_types} (from {original_count} total)")
        
        # Download each file
        downloaded = []
        failed = []
        
        for i, file_info in enumerate(files, 1):
            try:
                file_id = file_info["dataFile"]["id"]
                filename = file_info["dataFile"]["filename"]
                checksum = file_info["dataFile"].get("md5")
                
                output_path = output_dir / filename
                
                logger.info(f"[{i}/{len(files)}] Downloading {filename}...")
                
                success = await self.download_file(
                    file_id,
                    output_path,
                    expected_checksum=checksum,
                    verify_checksum=verify_checksums
                )
                
                if success:
                    downloaded.append(str(output_path))
                else:
                    failed.append(filename)
            
            except Exception as e:
                logger.error(f"Error downloading {filename}: {e}")
                failed.append(filename)
        
        # Summary
        status = "success" if not failed else ("partial" if downloaded else "error")
        
        logger.info("")
        logger.info("=" * 60)
        if status == "success":
            logger.success(f"✓ Successfully downloaded all {len(downloaded)} files")
        elif status == "partial":
            logger.warning(f"⚠ Downloaded {len(downloaded)} files, {len(failed)} failed")
        else:
            logger.error(f"✗ All downloads failed")
        logger.info("=" * 60)
        
        return {
            "status": status,
            "downloaded": len(downloaded),
            "failed": len(failed),
            "failed_files": failed,
            "files": downloaded,
            "output_dir": str(output_dir)
        }
    
    async def search_datasets(
        self,
        query: str,
        type: str = "dataset",
        per_page: int = 10,
        start: int = 0
    ) -> Dict[str, Any]:
        """
        Search for datasets in Dataverse.
        
        Args:
            query: Search query string
            type: Type of results ("dataset", "datafile", "all")
            per_page: Number of results per page
            start: Starting offset for pagination
        
        Returns:
            Search results dictionary
        
        Example:
            results = await client.search_datasets("municipal meetings")
            for item in results["data"]["items"]:
                print(item["name"], item["global_id"])
        """
        url = f"{self.base_url}{self.SEARCH_ENDPOINT}"
        params = {
            "q": query,
            "type": type,
            "per_page": per_page,
            "start": start
        }
        
        try:
            response = await self._request_with_retry(
                "GET",
                url,
                params=params,
                headers=self._get_headers()
            )
            
            return response.json()
        
        except DataverseAPIError as e:
            logger.error(f"Search failed: {e}")
            return {"status": "error", "message": str(e)}


# Convenience functions for common operations

async def download_localview_dataset(
    api_key: Optional[str] = None,
    output_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Download the LocalView dataset from Harvard Dataverse.
    
    This is the largest known database of municipal meeting videos.
    
    Args:
        api_key: Optional Dataverse API key (recommended)
        output_dir: Where to save files (defaults to data/cache/dataverse/localview)
    
    Returns:
        Download summary dictionary
    
    Example:
        result = await download_localview_dataset()
        print(f"Downloaded {result['downloaded']} files")
    """
    client = DataverseClient(api_key=api_key)
    
    logger.info("=" * 60)
    logger.info("LocalView Dataset Download")
    logger.info("=" * 60)
    
    result = await client.download_dataset(
        persistent_id="doi:10.7910/DVN/NJTBEM",
        output_dir=output_dir or Path("data/cache/localview"),
        file_types=[".csv", ".tab", ".tsv"]  # Only download data files
    )
    
    return result


# CLI for testing
async def main():
    """Test the Dataverse client."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Dataverse API Client")
    parser.add_argument("--api-key", help="Dataverse API key")
    parser.add_argument("--dataset", default="doi:10.7910/DVN/NJTBEM", help="Dataset DOI")
    parser.add_argument("--output", help="Output directory")
    parser.add_argument("--metadata-only", action="store_true", help="Only fetch metadata")
    
    args = parser.parse_args()
    
    client = DataverseClient(api_key=args.api_key)
    
    if args.metadata_only:
        # Just fetch metadata
        metadata = await client.get_dataset_metadata(args.dataset)
        if metadata:
            print(json.dumps(metadata, indent=2))
    else:
        # Download full dataset
        output_dir = Path(args.output) if args.output else None
        result = await client.download_dataset(args.dataset, output_dir)
        
        print("\nDownload Summary:")
        print(f"Status: {result['status']}")
        print(f"Downloaded: {result['downloaded']} files")
        print(f"Failed: {result['failed']} files")
        print(f"Output: {result['output_dir']}")


if __name__ == "__main__":
    asyncio.run(main())
