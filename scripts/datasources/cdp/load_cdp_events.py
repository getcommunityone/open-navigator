#!/usr/bin/env python3
"""
Load Council Data Project (CDP) Events to Bronze

Fetches meeting events, sessions, and transcripts from CDP instances
and loads them into bronze_events_search and bronze_events_text_ai tables.

CDP Documentation: https://councildataproject.github.io/cdp-data/

Usage:
    python load_cdp_events.py --instance seattle --start-date 2024-01-01
    python load_cdp_events.py --instance portland --start-date 2023-01-01 --store-transcripts
"""

import os
import sys
import argparse
import pandas as pd
from datetime import datetime
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
DATABASE_URL = f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator'

# CDP Instance Mapping
CDP_INSTANCES = {
    'seattle': 'Seattle',
    'portland': 'Portland', 
    'boston': 'Boston',
    'denver': 'Denver',
    'king-county': 'KingCounty',
    'alameda': 'Alameda',
    'oakland': 'Oakland',
    'charlotte': 'Charlotte',
    'san-jose': 'SanJose',
}

# Jurisdiction mapping for CDP instances
JURISDICTION_MAPPING = {
    'seattle': {'city': 'Seattle', 'state_code': 'WA', 'state': 'Washington', 'type': 'city'},
    'portland': {'city': 'Portland', 'state_code': 'OR', 'state': 'Oregon', 'type': 'city'},
    'boston': {'city': 'Boston', 'state_code': 'MA', 'state': 'Massachusetts', 'type': 'city'},
    'denver': {'city': 'Denver', 'state_code': 'CO', 'state': 'Colorado', 'type': 'city'},
    'king-county': {'city': None, 'county': 'King', 'state_code': 'WA', 'state': 'Washington', 'type': 'county'},
    'alameda': {'city': None, 'county': 'Alameda', 'state_code': 'CA', 'state': 'California', 'type': 'county'},
    'oakland': {'city': 'Oakland', 'state_code': 'CA', 'state': 'California', 'type': 'city'},
    'charlotte': {'city': 'Charlotte', 'state_code': 'NC', 'state': 'North Carolina', 'type': 'city'},
    'san-jose': {'city': 'San José', 'state_code': 'CA', 'state': 'California', 'type': 'city'},
}


def install_cdp_data():
    """Install cdp-data package if not already installed."""
    try:
        import cdp_data
        logger.info("✅ cdp-data package already installed")
    except ImportError:
        logger.info("📦 Installing cdp-data package...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "cdp-data"])
        logger.info("✅ cdp-data installed successfully")


def load_sessions_from_cdp(instance_slug: str, start_datetime: str, store_transcripts: bool = False):
    """
    Load session data from a CDP instance.
    
    Args:
        instance_slug: CDP instance name (e.g., 'seattle', 'portland')
        start_datetime: Start date in YYYY-MM-DD format
        store_transcripts: Whether to download and store transcripts
    
    Returns:
        DataFrame with session data
    """
    from cdp_data import CDPInstances, datasets
    
    # Get the CDP instance class attribute
    instance_name = CDP_INSTANCES.get(instance_slug)
    if not instance_name:
        raise ValueError(f"Unknown CDP instance: {instance_slug}. Available: {list(CDP_INSTANCES.keys())}")
    
    cdp_instance = getattr(CDPInstances, instance_name)
    
    logger.info(f"📥 Fetching sessions from CDP instance: {instance_slug} (starting {start_datetime})")
    
    try:
        # Fetch session dataset
        ds = datasets.get_session_dataset(
            infrastructure_slug=cdp_instance,
            start_datetime=start_datetime,
            store_transcript=store_transcripts,
            store_transcript_as_csv=store_transcripts,
            replace_py_objects=True,  # Replace Python objects with IDs for storage
        )
        
        logger.info(f"✅ Fetched {len(ds)} sessions from {instance_slug}")
        return ds
        
    except Exception as e:
        logger.error(f"❌ Error fetching sessions from {instance_slug}: {e}")
        raise


def transform_to_bronze_events(sessions_df: pd.DataFrame, instance_slug: str) -> pd.DataFrame:
    """
    Transform CDP session data to bronze_events_search schema.
    
    Args:
        sessions_df: DataFrame from CDP get_session_dataset()
        instance_slug: CDP instance name for jurisdiction mapping
    
    Returns:
        DataFrame matching bronze_events_search schema
    """
    jurisdiction = JURISDICTION_MAPPING[instance_slug]
    
    # Map CDP fields to our bronze schema
    bronze_df = pd.DataFrame({
        # Core event fields
        'event_datetime': pd.to_datetime(sessions_df.get('session_datetime')),
        'title': sessions_df.get('event_minutes_item', {}).apply(lambda x: x.get('name') if isinstance(x, dict) else None),
        'description': sessions_df.get('event_minutes_item', {}).apply(lambda x: x.get('description') if isinstance(x, dict) else None),
        
        # CDP-compatible fields
        'body_name': sessions_df.get('body', {}).apply(lambda x: x.get('name') if isinstance(x, dict) else 'City Council'),
        'body_description': sessions_df.get('body', {}).apply(lambda x: x.get('description') if isinstance(x, dict) else None),
        'agenda_url': sessions_df.get('event', {}).apply(lambda x: x.get('agenda_uri') if isinstance(x, dict) else None),
        'minutes_url': sessions_df.get('event', {}).apply(lambda x: x.get('minutes_uri') if isinstance(x, dict) else None),
        'external_source_id': sessions_df.get('id'),  # CDP session ID
        
        # Video/session fields
        'video_url': sessions_df.get('video_uri'),
        'session_content_hash': sessions_df.get('session_content_hash'),
        
        # Jurisdiction fields
        'jurisdiction_name': jurisdiction['city'] or jurisdiction.get('county'),
        'jurisdiction_type': jurisdiction['type'],
        'city': jurisdiction.get('city'),
        'county': jurisdiction.get('county'),
        'state_code': jurisdiction['state_code'],
        'state': jurisdiction['state'],
        
        # Source tracking
        'source': 'cdp',
        'source_url': f'https://councildataproject.org/{instance_slug}',
        'ingestion_timestamp': datetime.now(),
    })
    
    # Clean up NaN values
    bronze_df = bronze_df.where(pd.notnull(bronze_df), None)
    
    return bronze_df


def transform_to_bronze_transcripts(sessions_df: pd.DataFrame, instance_slug: str) -> pd.DataFrame:
    """
    Transform CDP transcript data to bronze_events_text_ai schema.
    
    Args:
        sessions_df: DataFrame from CDP with transcript data
        instance_slug: CDP instance name
    
    Returns:
        DataFrame matching bronze_events_text_ai schema
    """
    # Filter sessions that have transcripts
    has_transcript = sessions_df['transcript_file_id'].notna()
    transcript_df = sessions_df[has_transcript].copy()
    
    if len(transcript_df) == 0:
        logger.warning(f"⚠️  No transcripts found for {instance_slug}")
        return pd.DataFrame()
    
    # Map to bronze_events_text_ai schema
    bronze_transcripts = pd.DataFrame({
        'video_id': transcript_df['video_uri'].str.extract(r'([^/]+)$')[0],  # Extract video ID from URI
        'event_id': transcript_df['event'].apply(lambda x: x.get('id') if isinstance(x, dict) else None),
        'raw_text': None,  # Transcripts stored separately as JSON/CSV files
        'transcript_path': transcript_df['transcript_file_id'],  # Path to transcript file
        'ai_model': 'cdp',  # CDP's transcript generator
        'transcript_quality': transcript_df.get('transcript_confidence', 0.95),
        'language': 'en',
        'processed_at': datetime.now(),
        'source': 'cdp',
    })
    
    return bronze_transcripts


def load_to_database(df: pd.DataFrame, table_name: str, schema: str = 'bronze'):
    """
    Load DataFrame to PostgreSQL bronze table.
    
    Args:
        df: DataFrame to load
        table_name: Target table name
        schema: Database schema (default: bronze)
    """
    if df.empty:
        logger.warning(f"⚠️  No data to load into {schema}.{table_name}")
        return
    
    engine = create_engine(DATABASE_URL)
    
    try:
        # Load to database
        df.to_sql(
            table_name,
            engine,
            schema=schema,
            if_exists='append',
            index=False,
            method='multi',
            chunksize=1000
        )
        
        logger.info(f"✅ Loaded {len(df)} rows to {schema}.{table_name}")
        
    except Exception as e:
        logger.error(f"❌ Error loading to {schema}.{table_name}: {e}")
        raise
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description='Load Council Data Project (CDP) events to bronze tables'
    )
    parser.add_argument(
        '--instance',
        required=True,
        choices=list(CDP_INSTANCES.keys()),
        help='CDP instance to fetch data from'
    )
    parser.add_argument(
        '--start-date',
        required=True,
        help='Start date in YYYY-MM-DD format'
    )
    parser.add_argument(
        '--store-transcripts',
        action='store_true',
        help='Download and store transcript files'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be loaded without actually loading'
    )
    
    args = parser.parse_args()
    
    # Install cdp-data package
    install_cdp_data()
    
    # Load sessions from CDP
    sessions_df = load_sessions_from_cdp(
        args.instance,
        args.start_date,
        args.store_transcripts
    )
    
    # Transform to bronze schemas
    bronze_events = transform_to_bronze_events(sessions_df, args.instance)
    logger.info(f"📊 Transformed {len(bronze_events)} events")
    
    if args.store_transcripts:
        bronze_transcripts = transform_to_bronze_transcripts(sessions_df, args.instance)
        logger.info(f"📊 Transformed {len(bronze_transcripts)} transcripts")
    
    # Load to database (unless dry run)
    if args.dry_run:
        logger.info("🔍 DRY RUN - Would load:")
        logger.info(f"   {len(bronze_events)} events to bronze.bronze_events_search")
        if args.store_transcripts:
            logger.info(f"   {len(bronze_transcripts)} transcripts to bronze.bronze_events_text_ai")
        logger.info("\nSample event data:")
        print(bronze_events.head())
    else:
        load_to_database(bronze_events, 'bronze_events_search', 'bronze')
        
        if args.store_transcripts and not bronze_transcripts.empty:
            load_to_database(bronze_transcripts, 'bronze_events_text_ai', 'bronze')
        
        logger.info("✅ CDP data loaded successfully!")


if __name__ == '__main__':
    main()
