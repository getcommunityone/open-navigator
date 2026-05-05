"""
LocalView Dataset Ingestion

Downloads and processes the LocalView dataset from Harvard Dataverse.
This dataset contains 1,000+ municipalities with meeting video archives.

Source: Harvard Mellon Urbanism Initiative
URL: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM

USAGE OPTIONS:
1. **API Download (Recommended)**: Set DATAVERSE_API_KEY in .env and run script
2. **Manual Download**: Download CSV files to data/cache/localview/ and run script
      
See docs/LOCALVIEW_INTEGRATION_GUIDE.md for detailed instructions.
"""
import sys
from pathlib import Path
import csv
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
import re

# Add project root to path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from pyspark.sql import SparkSession, DataFrame
    from pyspark.sql.types import StructType, StructField, StringType, IntegerType, BooleanType, TimestampType
    from pyspark.sql.functions import lit, col
    import delta
    PYSPARK_AVAILABLE = True
except ImportError:
    PYSPARK_AVAILABLE = False
    SparkSession = None
    DataFrame = None
    logger.warning("PySpark not available - install with: pip install pyspark delta-spark")

from config import settings

# Import Dataverse client for API downloads
try:
    from scripts.datasources.localview.dataverse_client import DataverseClient
    DATAVERSE_CLIENT_AVAILABLE = True
except ImportError:
    DATAVERSE_CLIENT_AVAILABLE = False
    logger.warning("Dataverse client not available - will use manual download only")


class LocalViewIngestion:
    """Ingest LocalView dataset from Harvard Dataverse."""
    
    # Expected files in cache directory (adjust if actual names differ)
    EXPECTED_FILES = {
        "municipalities": ["municipalities.csv", "municipalities.tab", "places.csv"],
        "meetings": ["meetings.csv", "meetings.tab", "events.csv"],
        "videos": ["videos.csv", "videos.tab", "recordings.csv"],
    }
    
    def __init__(self, spark: Optional[SparkSession] = None):
        """Initialize ingestion with Spark session."""
        if not PYSPARK_AVAILABLE:
            raise ImportError("PySpark required. Install with: pip install pyspark delta-spark")
        
        # Configure Spark with Delta Lake
        if spark is None:
            builder = SparkSession.builder \
                .appName("LocalViewIngestion") \
                .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
                .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
            self.spark = delta.configure_spark_with_delta_pip(builder).getOrCreate()
        else:
            self.spark = spark
        
        self.cache_dir = Path("data/cache/localview")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.bronze_path = Path(settings.BRONZE_LAYER_PATH) / "localview"
    
    def find_file(self, file_type: str) -> Optional[Path]:
        """
        Find the data file for a given type.
        
        Args:
            file_type: Type of file ("municipalities", "meetings", "videos")
            
        Returns:
            Path to file if found, None otherwise
        """
        possible_names = self.EXPECTED_FILES.get(file_type, [])
        
        for name in possible_names:
            file_path = self.cache_dir / name
            if file_path.exists():
                logger.info(f"Found {file_type} file: {file_path}")
                return file_path
        
        # List what files are actually in the directory
        existing_files = list(self.cache_dir.glob("*.*"))
        if existing_files:
            logger.warning(f"Available files in {self.cache_dir}:")
            for f in existing_files:
                logger.warning(f"  - {f.name}")
        else:
            logger.error(f"No files found in {self.cache_dir}")
            logger.error("Please download LocalView CSV files from Harvard Dataverse first.")
            logger.error("See docs/LOCALVIEW_INTEGRATION_GUIDE.md for instructions.")
        
        return None
    
    def read_csv_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Read CSV or TAB file and return as list of dictionaries.
        
        Args:
            file_path: Path to CSV or TAB file
            
        Returns:
            List of dictionaries with column names as keys
        """
        # Detect delimiter
        delimiter = '\t' if file_path.suffix == '.tab' else ','
        
        rows = []
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                rows.append(row)
        
        logger.info(f"Read {len(rows)} rows from {file_path.name}")
        return rows
    
    def detect_platform(self, url: str) -> str:
        """
        Detect video platform from URL.
        
        Args:
            url: Video or website URL
            
        Returns:
            Platform name (youtube, granicus, vimeo, archive_org, other)
        """
        if not url:
            return "unknown"
        
        url_lower = url.lower()
        
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        elif "granicus.com" in url_lower:
            return "granicus"
        elif "vimeo.com" in url_lower:
            return "vimeo"
        elif "archive.org" in url_lower:
            return "archive_org"
        elif "civicplus.com" in url_lower:
            return "civicplus"
        elif "swagit.com" in url_lower:
            return "swagit"
        elif "legistar.com" in url_lower:
            return "legistar"
        else:
            return "other"
    
    def parse_municipalities(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse municipality data into standardized format.
        
        Args:
            rows: Raw CSV rows
            
        Returns:
            Standardized municipality records
        """
        municipalities = []
        
        for row in rows:
            # Try different possible column names (adjust based on actual data)
            name = (row.get('municipality_name') or 
                   row.get('name') or 
                   row.get('municipality') or 
                   row.get('city'))
            
            state = (row.get('state') or 
                    row.get('state_code') or 
                    row.get('state_abbr'))
            
            website_url = (row.get('website_url') or 
                          row.get('url') or 
                          row.get('government_url'))
            
            meeting_page = (row.get('meeting_page_url') or 
                           row.get('meetings_url') or 
                           row.get('agenda_url'))
            
            video_archive = (row.get('video_archive_url') or 
                            row.get('videos_url') or 
                            row.get('archive_url'))
            
            population = (row.get('population') or 
                         row.get('pop') or 
                         row.get('population_2020'))
            
            if name and state:
                record = {
                    'municipality_name': name.strip(),
                    'state': state.strip().upper(),
                    'county': row.get('county', '').strip(),
                    'population': int(population) if population and population.isdigit() else None,
                    'website_url': website_url.strip() if website_url else None,
                    'meeting_page_url': meeting_page.strip() if meeting_page else None,
                    'video_archive_url': video_archive.strip() if video_archive else None,
                    'platform': self.detect_platform(video_archive or meeting_page or website_url),
                    'ingestion_timestamp': datetime.now().isoformat(),
                    'source': 'localview'
                }
                municipalities.append(record)
        
        logger.success(f"Parsed {len(municipalities)} municipalities")
        return municipalities
    
    def parse_videos(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse video data into standardized format.
        
        Args:
            rows: Raw CSV rows
            
        Returns:
            Standardized video records
        """
        videos = []
        
        for row in rows:
            # Try different possible column names
            video_url = (row.get('video_url') or 
                        row.get('url') or 
                        row.get('recording_url'))
            
            municipality = (row.get('municipality_name') or 
                           row.get('municipality') or 
                           row.get('city'))
            
            state = (row.get('state') or 
                    row.get('state_code'))
            
            meeting_date = (row.get('meeting_date') or 
                           row.get('date') or 
                           row.get('event_date'))
            
            meeting_type = (row.get('meeting_type') or 
                           row.get('type') or 
                           row.get('body'))
            
            transcript_url = (row.get('transcript_url') or 
                             row.get('transcript'))
            
            has_transcript = (row.get('transcript_available') or 
                             row.get('has_transcript') or 
                             bool(transcript_url))
            
            if video_url and municipality:
                record = {
                    'video_id': row.get('video_id') or row.get('id') or f"{municipality}_{meeting_date}",
                    'video_url': video_url.strip(),
                    'municipality_name': municipality.strip(),
                    'state': state.strip().upper() if state else None,
                    'meeting_date': meeting_date,
                    'meeting_type': meeting_type or 'Council',
                    'platform': self.detect_platform(video_url),
                    'duration_minutes': int(row.get('duration_minutes', 0)) if row.get('duration_minutes', '').isdigit() else None,
                    'has_captions': row.get('has_captions', '').lower() == 'true',
                    'has_transcript': str(has_transcript).lower() == 'true',
                    'transcript_url': transcript_url.strip() if transcript_url else None,
                    'ingestion_timestamp': datetime.now().isoformat(),
                    'source': 'localview'
                }
                videos.append(record)
        
        logger.success(f"Parsed {len(videos)} videos")
        return videos
    
    def load_municipalities(self) -> Optional[List[Dict[str, Any]]]:
        """Load municipality data from cache."""
        logger.info("Loading municipality data...")
        
        file_path = self.find_file("municipalities")
        if not file_path:
            logger.warning("Municipality file not found - will only process videos")
            return None
        
        rows = self.read_csv_file(file_path)
        return self.parse_municipalities(rows)
    
    def load_videos(self) -> Optional[List[Dict[str, Any]]]:
        """Load video data from cache."""
        logger.info("Loading video data...")
        
        file_path = self.find_file("videos")
        if not file_path:
            # Try meetings file as fallback
            file_path = self.find_file("meetings")
        
        if not file_path:
            logger.error("No video or meeting files found!")
            return None
        
        rows = self.read_csv_file(file_path)
        return self.parse_videos(rows)
    
    def write_to_bronze_layer(self, municipalities: Optional[List[Dict[str, Any]]], 
                              videos: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Write parsed data to Bronze layer.
        
        Args:
            municipalities: Municipality records
            videos: Video records
            
        Returns:
            Summary statistics
        """
        stats = {
            'municipalities_written': 0,
            'videos_written': 0,
            'platforms': {}
        }
        
        # Write municipalities
        if municipalities:
            munis_df = self.spark.createDataFrame(municipalities)
            munis_path = str(self.bronze_path / "municipalities")
            
            munis_df.write.format("delta").mode("overwrite").save(munis_path)
            stats['municipalities_written'] = len(municipalities)
            logger.success(f"✓ Written {len(municipalities)} municipalities to {munis_path}")
        
        # Write videos
        if videos:
            videos_df = self.spark.createDataFrame(videos)
            videos_path = str(self.bronze_path / "videos")
            
            videos_df.write.format("delta").mode("overwrite").save(videos_path)
            stats['videos_written'] = len(videos)
            
            # Count platforms
            platforms = {}
            for video in videos:
                platform = video['platform']
                platforms[platform] = platforms.get(platform, 0) + 1
            
            stats['platforms'] = platforms
            
            logger.success(f"✓ Written {len(videos)} videos to {videos_path}")
            logger.info("Platform distribution:")
            for platform, count in sorted(platforms.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  - {platform}: {count} videos")
        
        return stats


async def try_api_download() -> bool:
    """
    Try to download dataset using Dataverse API.
    
    Returns:
        True if successful, False otherwise
    """
    if not DATAVERSE_CLIENT_AVAILABLE:
        logger.info("Dataverse API client not available - skipping API download")
        return False
    
    # Check if API key is available
    api_key = settings.dataverse_api_key
    
    if api_key and api_key != "your_dataverse_api_key":
        logger.info("🔑 Dataverse API key found - attempting API download")
        logger.info("This may take 5-10 minutes for large datasets...")
        
        try:
            client = DataverseClient(api_key=api_key)
            result = await client.download_dataset(
                persistent_id="doi:10.7910/DVN/NJTBEM",
                output_dir=Path("data/cache/localview"),
                file_types=[".parquet", ".csv", ".tab", ".tsv"]  # Data files (parquet is primary format)
            )
            
            if result["status"] == "success" or result["status"] == "partial":
                logger.success("✓ API download completed!")
                return True
            else:
                logger.warning("⚠ API download failed - falling back to manual download")
                return False
        
        except Exception as e:
            logger.warning(f"⚠ API download failed: {e}")
            logger.info("Falling back to manual download method")
            return False
    else:
        logger.info("No Dataverse API key configured (optional)")
        logger.info("Set DATAVERSE_API_KEY in .env to enable automatic downloads")
        logger.info("Get your key at: https://dataverse.harvard.edu/loginpage.xhtml")
        return False


def main():
    """Main execution function."""
    logger.info("=" * 60)
    logger.info("LocalView Dataset Ingestion")
    logger.info("=" * 60)
    
    # Try API download first
    logger.info("\n[Step 1/2] Checking for API download option...")
    api_success = asyncio.run(try_api_download())
    
    # Check if files exist (either from API or manual download)
    cache_dir = Path("data/cache/localview")
    if not cache_dir.exists() or not list(cache_dir.glob("*.*")):
        if not api_success:
            logger.error("")
            logger.error("=" * 60)
            logger.error("❌ No files found in data/cache/localview/")
            logger.error("=" * 60)
            logger.error("")
            logger.error("OPTION 1 - API Download (Recommended):")
            logger.error("  1. Get free API key: https://dataverse.harvard.edu/loginpage.xhtml")
            logger.error("  2. Add to .env: DATAVERSE_API_KEY=your_key")
            logger.error("  3. Re-run this script")
            logger.error("")
            logger.error("OPTION 2 - Manual Download:")
            logger.error("  1. Visit: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM")
            logger.error("  2. Download CSV/TAB files")
            logger.error("  3. Save to: data/cache/localview/")
            logger.error("  4. Re-run this script")
            logger.error("")
            logger.error("See docs/LOCALVIEW_INTEGRATION_GUIDE.md for detailed instructions.")
            logger.error("")
            return 1
    
    # Initialize ingestion
    logger.info("\n[Step 2/2] Processing downloaded files...")
    ingestion = LocalViewIngestion()
    
    # Load data
    municipalities = ingestion.load_municipalities()
    videos = ingestion.load_videos()
    
    if not municipalities and not videos:
        logger.error("❌ No data could be loaded!")
        logger.error("Check that CSV files are in the correct format.")
        return 1
    
    # Write to Bronze layer
    stats = ingestion.write_to_bronze_layer(municipalities, videos)
    
    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.success("✓ LocalView ingestion complete!")
    logger.info("=" * 60)
    logger.info(f"Municipalities: {stats['municipalities_written']}")
    logger.info(f"Videos: {stats['videos_written']}")
    if stats['platforms']:
        logger.info("\nTop platforms:")
        for platform, count in sorted(stats['platforms'].items(), key=lambda x: x[1], reverse=True)[:5]:
            logger.info(f"  {platform}: {count} videos")
    logger.info("")
    
    return 0


if __name__ == "__main__":
    exit(main())
