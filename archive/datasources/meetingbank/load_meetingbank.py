"""
MeetingBank Dataset Integration

MeetingBank is an academic benchmark dataset containing 1,366 city council meetings
from 6 major U.S. cities (Alameda, Boston, Denver, King County, Long Beach, Seattle).

Dataset Citation (REQUIRED):
    Yebowen Hu, Tim Ganter, Hanieh Deilamsalehy, Franck Dernoncourt, Hassan Foroosh, Fei Liu.
    "MeetingBank: A Benchmark Dataset for Meeting Summarization"
    In Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL),
    July 2023, Toronto, Canada.
    
    BibTeX:
    @inproceedings{hu-etal-2023-meetingbank,
        title = "MeetingBank: A Benchmark Dataset for Meeting Summarization",
        author = "Yebowen Hu and Tim Ganter and Hanieh Deilamsalehy and 
                  Franck Dernoncourt and Hassan Foroosh and Fei Liu",
        booktitle = "Proceedings of the 61st Annual Meeting of the Association for 
                     Computational Linguistics (ACL)",
        month = July,
        year = "2023",
        address = "Toronto, Canada",
        publisher = "Association for Computational Linguistics",
    }

Resources:
- Paper: https://arxiv.org/abs/2305.17529
- HuggingFace: https://huggingface.co/datasets/huuuyeah/meetingbank
- Zenodo: https://zenodo.org/record/7989108

What you get:
- 1,366 meetings with full transcripts (avg 28k tokens)
- Human-written summaries (ground truth for evaluation)
- Machine-generated summaries (from 6 systems)
- PDF meeting minutes & agendas
- 3,579 hours of video
- 6,892 segment-level summarization instances
"""
import sys
from pathlib import Path

# Add project root to Python path for standalone execution
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from datasets import load_dataset
from pyspark.sql import SparkSession
from pyspark.sql.functions import lit
from datetime import datetime
from typing import Dict, List
from loguru import logger

from config.settings import settings


# Cities covered in MeetingBank
MEETINGBANK_CITIES = {
    "alameda": {"name": "Alameda", "state": "CA"},
    "boston": {"name": "Boston", "state": "MA"},
    "denver": {"name": "Denver", "state": "CO"},
    "kingcounty": {"name": "King County", "state": "WA"},
    "longbeach": {"name": "Long Beach", "state": "CA"},
    "seattle": {"name": "Seattle", "state": "WA"}
}


def extract_city_from_id(meeting_id: str) -> Dict[str, str]:
    """
    Extract city name and state from MeetingBank meeting ID.
    
    Example IDs:
    - alameda_2019_01_15
    - boston_2020_03_04
    """
    parts = meeting_id.split('_')
    if len(parts) >= 1:
        city_key = parts[0].lower()
        if city_key in MEETINGBANK_CITIES:
            return MEETINGBANK_CITIES[city_key]
    
    return {"name": "Unknown", "state": "Unknown"}


def load_meetingbank_dataset() -> dict:
    """
    Download MeetingBank dataset from HuggingFace.
    
    Returns dict with train/validation/test splits.
    """
    logger.info("Downloading MeetingBank dataset from HuggingFace")
    logger.info("This may take a few minutes on first download...")
    
    try:
        # Download from HuggingFace (cached after first download)
        meetingbank = load_dataset("huuuyeah/meetingbank")
        
        total_meetings = sum(len(meetingbank[split]) for split in meetingbank.keys())
        
        logger.info(f"✅ Downloaded MeetingBank:")
        logger.info(f"  • Train: {len(meetingbank['train'])} meetings")
        logger.info(f"  • Validation: {len(meetingbank['validation'])} meetings")
        logger.info(f"  • Test: {len(meetingbank['test'])} meetings")
        logger.info(f"  • Total: {total_meetings} meetings")
        
        return meetingbank
    
    except Exception as e:
        logger.error(f"Failed to download MeetingBank: {e}")
        logger.error("Make sure you have 'datasets' installed: pip install datasets")
        raise


def extract_video_urls_from_instance(instance: dict) -> Dict[str, str]:
    """
    Extract YouTube/Vimeo URLs from MeetingBank's 'urls' dictionary.
    
    MeetingBank stores video URLs in multiple formats:
    - urls['youtube_id'] -> https://www.youtube.com/watch?v=ID
    - urls['vimeo_id'] -> https://vimeo.com/ID
    - urls['archive_url'] -> https://archive.org/details/...
    - video_url field -> Direct URL
    """
    urls_dict = instance.get('urls', {})
    video_urls = {}
    
    # Extract YouTube URL
    if 'youtube_id' in urls_dict and urls_dict['youtube_id']:
        video_urls['youtube_url'] = f"https://www.youtube.com/watch?v={urls_dict['youtube_id']}"
    
    # Extract Vimeo URL
    if 'vimeo_id' in urls_dict and urls_dict['vimeo_id']:
        video_urls['vimeo_url'] = f"https://vimeo.com/{urls_dict['vimeo_id']}"
    
    # Extract Archive.org URL
    if 'archive_url' in urls_dict and urls_dict['archive_url']:
        video_urls['archive_url'] = urls_dict['archive_url']
    
    # Fallback to top-level video_url field
    if not video_urls and instance.get('video_url'):
        video_urls['video_url'] = instance['video_url']
    
    return video_urls


def parse_meetingbank_to_dataframe(
    meetingbank: dict,
    spark: SparkSession
) -> "pyspark.sql.DataFrame":
    """
    Parse MeetingBank dataset into PySpark DataFrame.
    
    Extracts:
    - Meeting ID
    - City name and state
    - Full transcript
    - Human summary (ground truth)
    - Source URL (if available)
    - Video URLs (YouTube, Vimeo, Archive.org)
    - Metadata
    """
    logger.info("Parsing MeetingBank meetings to DataFrame")
    
    meetings = []
    
    for split in ['train', 'validation', 'test']:
        logger.info(f"Processing {split} split...")
        
        for instance in meetingbank[split]:
            # Extract city info from meeting ID
            city_info = extract_city_from_id(instance['id'])
            
            # Extract video URLs from urls dictionary
            video_urls = extract_video_urls_from_instance(instance)
            
            # Parse meeting data
            meeting = {
                "meeting_id": instance['id'],
                "jurisdiction_name": city_info['name'],
                "state_code": city_info['state'],
                "transcript": instance.get('transcript', ''),
                "summary_human": instance.get('summary', ''),
                "date": instance.get('date', ''),
                "split": split,
                
                # Metadata
                "has_transcript": bool(instance.get('transcript')),
                "has_summary": bool(instance.get('summary')),
                "transcript_length": len(instance.get('transcript', '')),
                "summary_length": len(instance.get('summary', '')),
                
                # Video URLs (NEW - extracts from urls dictionary)
                "youtube_url": video_urls.get('youtube_url', ''),
                "vimeo_url": video_urls.get('vimeo_url', ''),
                "archive_url": video_urls.get('archive_url', ''),
                
                # Additional fields from MeetingBank
                "source_url": instance.get('url', ''),
                "video_url": video_urls.get('video_url', instance.get('video_url', '')),
                "agenda_url": instance.get('agenda_url', ''),
                "minutes_url": instance.get('minutes_url', ''),
                
                # Source tracking
                "source": "meetingbank",
                "source_dataset": "huggingface:huuuyeah/meetingbank",
                "ingested_at": datetime.utcnow().isoformat()
            }
            
            meetings.append(meeting)
    
    # Convert to PySpark DataFrame
    df = spark.createDataFrame(meetings)
    
    logger.info(f"✅ Parsed {len(meetings)} meetings into DataFrame")
    
    return df


def write_to_bronze_layer(
    df: "pyspark.sql.DataFrame",
    spark: SparkSession
) -> Dict[str, int]:
    """
    Write MeetingBank meetings to Bronze layer.
    
    Creates table: bronze/meetingbank_meetings
    """
    from delta import DeltaTable
    
    output_path = f"{settings.delta_lake_path}/bronze/meetingbank_meetings"
    
    logger.info(f"Writing MeetingBank data to Bronze layer: {output_path}")
    
    # Write to Delta Lake
    df.write \
        .format("delta") \
        .mode("overwrite") \
        .save(output_path)
    
    # Get stats by city
    city_counts = df.groupBy("jurisdiction_name").count().collect()
    
    logger.info("✅ MeetingBank data written to Bronze layer")
    logger.info("\nMeetings by city:")
    for row in city_counts:
        logger.info(f"  • {row['jurisdiction_name']}: {row['count']} meetings")
    
    return {
        "total_meetings": df.count(),
        "cities": df.select("jurisdiction_name").distinct().count(),
        "table": "bronze/meetingbank_meetings"
    }


def extract_meetingbank_urls(
    df: "pyspark.sql.DataFrame",
    spark: SparkSession
) -> Dict[str, int]:
    """
    Extract unique URLs from MeetingBank for URL discovery.
    
    Creates table: bronze/meetingbank_urls
    
    Includes YouTube, Vimeo, Archive.org video URLs from urls dictionary.
    """
    logger.info("Extracting URLs from MeetingBank meetings")
    
    # Collect all URLs
    urls = []
    
    for row in df.collect():
        # Add source URLs
        if row.source_url:
            urls.append({
                "url": row.source_url,
                "url_type": "meeting_source",
                "jurisdiction_name": row.jurisdiction_name,
                "state_code": row.state_code,
                "source": "meetingbank"
            })
        
        # Add YouTube URLs (from urls dictionary)
        if row.youtube_url:
            urls.append({
                "url": row.youtube_url,
                "url_type": "video_youtube",
                "jurisdiction_name": row.jurisdiction_name,
                "state_code": row.state_code,
                "source": "meetingbank"
            })
        
        # Add Vimeo URLs (from urls dictionary)
        if row.vimeo_url:
            urls.append({
                "url": row.vimeo_url,
                "url_type": "video_vimeo",
                "jurisdiction_name": row.jurisdiction_name,
                "state_code": row.state_code,
                "source": "meetingbank"
            })
        
        # Add Archive.org URLs (from urls dictionary)
        if row.archive_url:
            urls.append({
                "url": row.archive_url,
                "url_type": "video_archive",
                "jurisdiction_name": row.jurisdiction_name,
                "state_code": row.state_code,
                "source": "meetingbank"
            })
        
        # Add generic video URLs
        if row.video_url and row.video_url not in [row.youtube_url, row.vimeo_url, row.archive_url]:
            urls.append({
                "url": row.video_url,
                "url_type": "video",
                "jurisdiction_name": row.jurisdiction_name,
                "state_code": row.state_code,
                "source": "meetingbank"
            })
        
        # Add agenda URLs
        if row.agenda_url:
            urls.append({
                "url": row.agenda_url,
                "url_type": "agenda",
                "jurisdiction_name": row.jurisdiction_name,
                "state_code": row.state_code,
                "source": "meetingbank"
            })
        
        # Add minutes URLs
        if row.minutes_url:
            urls.append({
                "url": row.minutes_url,
                "url_type": "minutes",
                "jurisdiction_name": row.jurisdiction_name,
                "state_code": row.state_code,
                "source": "meetingbank"
            })
    
    if not urls:
        logger.warning("⚠️  No URLs found in MeetingBank dataset")
        return {"total_urls": 0}
    
    # Deduplicate URLs
    unique_urls = {url['url']: url for url in urls}.values()
    
    logger.info(f"✅ Found {len(unique_urls)} unique URLs from MeetingBank")
    
    # Count by URL type
    url_types = {}
    for url in unique_urls:
        url_type = url['url_type']
        url_types[url_type] = url_types.get(url_type, 0) + 1
    
    logger.info("\nURLs by type:")
    for url_type, count in sorted(url_types.items()):
        logger.info(f"  • {url_type}: {count} URLs")
    
    # Convert to DataFrame
    urls_df = spark.createDataFrame(list(unique_urls))
    urls_df = urls_df.withColumn("ingested_at", lit(datetime.utcnow().isoformat()))
    
    # Write to Bronze layer
    output_path = f"{settings.delta_lake_path}/bronze/meetingbank_urls"
    urls_df.write \
        .format("delta") \
        .mode("overwrite") \
        .save(output_path)
    
    logger.info(f"✅ Extracted {len(unique_urls)} unique URLs")
    
    return {
        "total_urls": len(unique_urls),
        "table": "bronze/meetingbank_urls"
    }


def ingest_meetingbank(spark: SparkSession = None) -> dict:
    """
    Main function: Download and ingest MeetingBank dataset.
    
    Steps:
    1. Download from HuggingFace
    2. Parse to DataFrame
    3. Write to Bronze layer
    4. Extract URLs
    
    Returns summary statistics.
    """
    from delta import configure_spark_with_delta_pip
    
    if spark is None:
        logger.info("Creating Spark session")
        builder = SparkSession.builder \
            .appName("MeetingBankIngestion") \
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
            .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        spark = configure_spark_with_delta_pip(builder).getOrCreate()
    
    logger.info("=" * 80)
    logger.info("MEETINGBANK DATASET INGESTION")
    logger.info("=" * 80)
    
    # Step 1: Download from HuggingFace
    meetingbank = load_meetingbank_dataset()
    
    # Step 2: Parse to DataFrame
    df = parse_meetingbank_to_dataframe(meetingbank, spark)
    
    # Step 3: Write to Bronze layer
    bronze_result = write_to_bronze_layer(df, spark)
    
    # Step 4: Extract URLs
    url_result = extract_meetingbank_urls(df, spark)
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("MEETINGBANK INGESTION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Meetings ingested: {bronze_result['total_meetings']}")
    logger.info(f"Cities covered: {bronze_result['cities']}")
    logger.info(f"URLs extracted: {url_result['total_urls']}")
    logger.info("\nBronze tables created:")
    logger.info(f"  • {bronze_result['table']}")
    logger.info(f"  • {url_result['table']}")
    
    return {
        "status": "complete",
        "meetings": bronze_result['total_meetings'],
        "cities": bronze_result['cities'],
        "urls": url_result['total_urls'],
        "tables": [bronze_result['table'], url_result['table']]
    }


if __name__ == "__main__":
    print("🏛️ MeetingBank Dataset Ingestion")
    print("=" * 80)
    print("\nMeetingBank is an academic benchmark dataset containing 1,366 city council")
    print("meetings from 6 major U.S. cities with full transcripts and human summaries.")
    print("\nCities covered:")
    for city_info in MEETINGBANK_CITIES.values():
        print(f"  • {city_info['name']}, {city_info['state']}")
    print("\n" + "=" * 80)
    print("\nStarting ingestion...\n")
    
    try:
        result = ingest_meetingbank()
        
        print("\n✅ SUCCESS!")
        print(f"\nIngested {result['meetings']} meetings from {result['cities']} cities")
        print(f"Extracted {result['urls']} URLs")
        
        print("\nNext steps:")
        print("  1. Run keyword detection on transcripts")
        print("  2. Test AI summarization against human summaries")
        print("  3. Extract oral health policy mentions")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nMake sure you have 'datasets' installed:")
        print("  pip install datasets")
