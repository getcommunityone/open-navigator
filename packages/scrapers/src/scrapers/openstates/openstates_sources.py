"""
Open States Video Sources Integration

Open States (now part of Plural) is the most comprehensive state legislative
data aggregator in the United States.

Coverage:
- All 50 states + DC + Puerto Rico
- State legislatures with video archives
- Expanding to city councils and county boards
- Many jurisdictions host videos on YouTube/Vimeo

API: https://openstates.org/api/
Data: https://data.openstates.org/
Free tier: 50,000 requests/month (plenty for our needs)

The 'sources' field frequently contains:
- YouTube channel URLs (e.g., @CALegislature)
- Vimeo profile URLs
- Granicus video portals
- Archive.org collections
"""
import sys
from pathlib import Path

# Add project root to Python path for standalone execution
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import requests
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger
from pyspark.sql import SparkSession
from pyspark.sql.functions import lit

from config.settings import settings


OPENSTATES_API_BASE = "https://v3.openstates.org"


def get_api_key() -> Optional[str]:
    """
    Get Open States API key from settings.
    
    Sign up for free at: https://openstates.org/accounts/signup/
    """
    api_key = getattr(settings, 'openstates_api_key', None)
    
    if not api_key:
        logger.warning("⚠️  OPENSTATES_API_KEY not found in settings")
        logger.warning("   Sign up at: https://openstates.org/accounts/signup/")
        logger.warning("   Add to .env: OPENSTATES_API_KEY=your-key")
    
    return api_key


def extract_platform_from_url(url: str) -> str:
    """
    Extract platform from URL.
    """
    url_lower = url.lower()
    
    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    elif 'vimeo.com' in url_lower:
        return 'vimeo'
    elif 'granicus.com' in url_lower:
        return 'granicus'
    elif 'archive.org' in url_lower:
        return 'archive_org'
    elif 'legistar.com' in url_lower:
        return 'legistar'
    else:
        return 'other'


def get_jurisdictions_with_video_sources(api_key: str) -> List[Dict]:
    """
    Fetch all jurisdictions from Open States and extract video sources.
    
    Returns list of jurisdictions with YouTube/Vimeo/Granicus URLs.
    """
    logger.info("Fetching jurisdictions from Open States API")
    
    try:
        response = requests.get(
            f"{OPENSTATES_API_BASE}/jurisdictions",
            headers={"X-API-KEY": api_key},
            timeout=30
        )
        
        response.raise_for_status()
        
        data = response.json()
        jurisdictions = data.get('results', [])
        
        logger.info(f"✅ Retrieved {len(jurisdictions)} jurisdictions from Open States")
        
        video_sources = []
        
        for jurisdiction in jurisdictions:
            # Extract sources field
            sources = jurisdiction.get('sources', [])
            
            if not sources:
                continue
            
            for source in sources:
                url = source.get('url', '')
                
                if not url:
                    continue
                
                # Check if it's a video platform
                platform = extract_platform_from_url(url)
                
                if platform in ['youtube', 'vimeo', 'granicus', 'archive_org']:
                    video_sources.append({
                        "jurisdiction_id": jurisdiction.get('id', ''),
                        "jurisdiction_name": jurisdiction.get('name', ''),
                        "classification": jurisdiction.get('classification', ''),
                        "division_id": jurisdiction.get('division_id', ''),
                        "video_url": url,
                        "platform": platform,
                        "source": "openstates"
                    })
        
        logger.info(f"✅ Found {len(video_sources)} video sources from {len(jurisdictions)} jurisdictions")
        
        # Count by platform
        platform_counts = {}
        for source in video_sources:
            platform = source['platform']
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        logger.info("\nVideo sources by platform:")
        for platform, count in sorted(platform_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  • {platform}: {count} sources")
        
        return video_sources
    
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Failed to fetch jurisdictions from Open States: {e}")
        logger.error("   Check your API key and internet connection")
        return []


def get_legislative_sessions_with_videos(api_key: str, jurisdiction_id: str) -> List[Dict]:
    """
    Fetch legislative sessions for a jurisdiction.
    
    Many states include video_url in session metadata.
    """
    logger.info(f"Fetching legislative sessions for {jurisdiction_id}")
    
    try:
        response = requests.get(
            f"{OPENSTATES_API_BASE}/jurisdictions/{jurisdiction_id}",
            headers={"X-API-KEY": api_key},
            timeout=30
        )
        
        response.raise_for_status()
        
        data = response.json()
        sessions = data.get('legislative_sessions', [])
        
        video_sessions = []
        
        for session in sessions:
            # Check for video URLs in session metadata
            if 'video_url' in session or 'stream_url' in session:
                video_sessions.append({
                    "jurisdiction_id": jurisdiction_id,
                    "session_id": session.get('identifier', ''),
                    "session_name": session.get('name', ''),
                    "video_url": session.get('video_url') or session.get('stream_url'),
                    "source": "openstates_sessions"
                })
        
        return video_sessions
    
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to fetch sessions for {jurisdiction_id}: {e}")
        return []


def write_to_bronze_layer(
    video_sources: List[Dict],
    spark: SparkSession
) -> Dict[str, int]:
    """
    Write Open States video sources to Bronze layer.
    
    Creates table: bronze/openstates_sources
    """
    if not video_sources:
        logger.warning("No video sources to write")
        return {"total_sources": 0}
    
    # Add ingestion timestamp
    for source in video_sources:
        source['ingested_at'] = datetime.utcnow().isoformat()
    
    # Convert to DataFrame
    df = spark.createDataFrame(video_sources)
    
    # Write to Delta Lake
    output_path = f"{settings.delta_lake_path}/bronze/openstates_sources"
    
    logger.info(f"Writing Open States sources to Bronze layer: {output_path}")
    
    df.write \
        .format("delta") \
        .mode("overwrite") \
        .save(output_path)
    
    # Get stats by platform
    platform_counts = df.groupBy("platform").count().collect()
    
    logger.info("\n✅ Open States sources written to Bronze layer")
    logger.info("\nSources by platform:")
    for row in sorted(platform_counts, key=lambda r: r['count'], reverse=True):
        logger.info(f"  • {row['platform']}: {row['count']} sources")
    
    return {
        "total_sources": df.count(),
        "jurisdictions": df.select("jurisdiction_name").distinct().count(),
        "platforms": df.select("platform").distinct().count(),
        "table": "bronze/openstates_sources"
    }


def ingest_openstates_sources(spark: SparkSession) -> Dict[str, int]:
    """
    Main function: Fetch Open States video sources via API.
    
    Returns:
    - total_sources: Number of video sources extracted
    - jurisdictions: Number of jurisdictions with video sources
    - platforms: Number of video platforms found
    - table: Bronze layer table name
    """
    logger.info("=" * 60)
    logger.info("OPEN STATES VIDEO SOURCES EXTRACTION")
    logger.info("=" * 60)
    
    # Get API key
    api_key = get_api_key()
    
    if not api_key:
        logger.error("❌ Cannot proceed without Open States API key")
        logger.error("   Get one free at: https://openstates.org/accounts/signup/")
        return {"total_sources": 0, "jurisdictions": 0, "platforms": 0}
    
    # Fetch jurisdictions with video sources
    video_sources = get_jurisdictions_with_video_sources(api_key)
    
    if not video_sources:
        logger.warning("⚠️  No video sources found in Open States")
        return {"total_sources": 0, "jurisdictions": 0, "platforms": 0}
    
    # Write to Bronze layer
    stats = write_to_bronze_layer(video_sources, spark)
    
    logger.info("\n" + "=" * 60)
    logger.info(f"✅ OPEN STATES INGESTION COMPLETE")
    logger.info(f"   • Video sources: {stats['total_sources']}")
    logger.info(f"   • Jurisdictions: {stats['jurisdictions']}")
    logger.info(f"   • Platforms: {stats['platforms']}")
    logger.info(f"   • Table: {stats['table']}")
    logger.info("=" * 60)
    
    return stats


if __name__ == "__main__":
    # Test extraction
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession
    
    # Configure Spark with Delta Lake
    builder = SparkSession.builder \
        .appName("OpenStatesSourcesExtraction") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    
    # Run ingestion
    stats = ingest_openstates_sources(spark)
    
    print(f"\n✅ Extracted {stats['total_sources']} video sources from Open States")
