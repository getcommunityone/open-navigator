#!/usr/bin/env python3
"""
Enrich jurisdiction with LocalView YouTube channel data

⚠️ DEPRECATED (migration 048): ALTERs/UPDATEs the pre-048 ``public.jurisdiction`` table,
now ``public.c1_jurisdiction`` (a dbt-built mart). The columns it writes (in_localview,
youtube_channels, …) were dropped in that move, so this will NOT run against the current
database and needs reworking — this enrichment now belongs in dbt (see int_youtube__events).

This script:
1. Extracts YouTube channel data from all LocalView meeting parquet files
2. Matches LocalView jurisdictions to jurisdiction
3. Adds in_localview flag
4. Enriches YouTube channel data with video counts and other metadata from LocalView
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import json
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')

# LocalView data directory
LOCALVIEW_DIR = Path('data/cache/localview')

# Development states in scope
DEV_STATES = ['AL', 'GA', 'IN', 'MA', 'WA', 'WI']

# State name to abbreviation mapping
STATE_ABBREV = {
    'Alabama': 'AL', 'Georgia': 'GA', 'Indiana': 'IN', 
    'Massachusetts': 'MA', 'Washington': 'WA', 'Wisconsin': 'WI',
    'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
    'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL',
    'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Iowa': 'IA',
    'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO',
    'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
    'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
    'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
    'Virginia': 'VA', 'West Virginia': 'WV', 'Wyoming': 'WY'
}


def extract_localview_channels():
    """Extract unique jurisdiction + YouTube channel mappings from all LocalView parquet files."""
    
    logger.info("Extracting YouTube channel data from LocalView meetings...")
    
    parquet_files = sorted(LOCALVIEW_DIR.glob('meetings.*.parquet'))
    logger.info(f"Found {len(parquet_files)} parquet files")
    
    all_channels = []
    
    for pf in parquet_files:
        logger.info(f"  Reading {pf.name}...")
        df = pd.read_parquet(pf)
        
        # Extract relevant columns
        channels_df = df[[
            'place_name', 'state_name', 'channel_id', 'channel_title',
            'vid_id', 'vid_views', 'vid_likes', 'vid_comments'
        ]].copy()
        
        # Filter to dev states only
        channels_df['state_abbrev'] = channels_df['state_name'].map(STATE_ABBREV)
        channels_df = channels_df[channels_df['state_abbrev'].isin(DEV_STATES)]
        
        # Clean place names - handle suffixes at end AND in middle
        # First remove end suffixes: "Mobile city" → "Mobile"
        channels_df['place_clean'] = channels_df['place_name'].str.replace(
            r'\s+(city|town|village|borough|CDP|County)$', '', regex=True, case=False
        ).str.strip()
        
        # Then remove any remaining "Town" or "City" in the middle (case-insensitive)
        # "Greenfield Town" → "Greenfield", "Garden City" → "Garden"
        channels_df['place_clean'] = channels_df['place_clean'].str.replace(
            r'\s+(?:town|city)\s*', ' ', regex=True, case=False
        ).str.strip()
        
        # Clean up multiple spaces
        channels_df['place_clean'] = channels_df['place_clean'].str.replace(
            r'\s+', ' ', regex=True
        ).str.strip()
        
        all_channels.append(channels_df)
    
    # Combine all data
    all_channels_df = pd.concat(all_channels, ignore_index=True)
    logger.success(f"✓ Extracted {len(all_channels_df):,} video records")
    
    # Aggregate by jurisdiction + channel
    logger.info("Aggregating channel statistics by jurisdiction...")
    
    agg_df = all_channels_df.groupby([
        'place_clean', 'state_abbrev', 'channel_id', 'channel_title'
    ]).agg({
        'vid_id': 'count',  # Video count
        'vid_views': 'sum',  # Total views
        'vid_likes': 'sum',  # Total likes
        'vid_comments': 'sum'  # Total comments
    }).reset_index()
    
    agg_df.columns = [
        'place_name', 'state', 'channel_id', 'channel_title',
        'video_count', 'total_views', 'total_likes', 'total_comments'
    ]
    
    logger.success(f"✓ Aggregated to {len(agg_df):,} unique jurisdiction+channel combinations")
    logger.info(f"  States: {sorted(agg_df['state'].unique())}")
    
    return agg_df


def add_localview_columns(conn):
    """Add in_localview flag and ensure proper schema."""
    
    logger.info("Adding/verifying LocalView columns in jurisdiction...")
    
    cursor = conn.cursor()
    
    try:
        # Add in_localview column if it doesn't exist
        cursor.execute("""
            ALTER TABLE jurisdiction 
            ADD COLUMN IF NOT EXISTS in_localview BOOLEAN DEFAULT FALSE
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jurisdiction_in_localview 
            ON jurisdiction(in_localview) 
            WHERE in_localview = TRUE
        """)
        
        conn.commit()
        logger.success("✓ LocalView columns added/verified")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"✗ Failed to add columns: {e}")
        raise
    finally:
        cursor.close()


def match_and_enrich(conn, localview_df):
    """Match LocalView data to jurisdiction and enrich."""
    
    logger.info("Matching LocalView data to jurisdiction...")
    
    cursor = conn.cursor()
    
    # Get all jurisdictions from database for the priority dev states
    cursor.execute("""
        SELECT 
            id,
            jurisdiction_id,
            name AS jurisdiction_name,
            state_code,
            website_url,
            youtube_channels
        FROM jurisdiction
        WHERE state_code IN ('AL', 'GA', 'IN', 'MA', 'WA', 'WI')
    """)
    
    db_jurisdictions = cursor.fetchall()
    logger.info(f"  Found {len(db_jurisdictions)} jurisdictions in database for priority states")
    
    # Create matching dataframe
    db_df = pd.DataFrame(db_jurisdictions, columns=[
        'id', 'jurisdiction_id', 'jurisdiction_name', 'state_code', 'website_url', 'youtube_channels'
    ])
    
    # Clean jurisdiction names for matching (same logic as LocalView cleaning)
    # First remove end suffixes
    db_df['name_clean'] = db_df['jurisdiction_name'].str.replace(
        r'\s+(city|town|village|borough|CDP|County)$', '', regex=True, case=False
    ).str.strip()
    
    # Then remove any "Town" or "City" in the middle
    db_df['name_clean'] = db_df['name_clean'].str.replace(
        r'\s+(?:town|city)\s*', ' ', regex=True, case=False
    ).str.strip()
    
    # Clean up multiple spaces and lowercase for matching
    db_df['name_clean'] = db_df['name_clean'].str.replace(
        r'\s+', ' ', regex=True
    ).str.strip().str.lower()
    
    localview_df['name_clean'] = localview_df['place_name'].str.lower()
    
    # Match on jurisdiction name + state
    matched = pd.merge(
        localview_df,
        db_df,
        left_on=['name_clean', 'state'],
        right_on=['name_clean', 'state_code'],
        how='inner'
    )
    
    logger.success(f"✓ Matched {len(matched)} LocalView channels to database jurisdictions")
    
    # Update database
    updates = []
    for _, row in matched.iterrows():
        # Parse existing youtube_channels
        existing_channels = row['youtube_channels'] if row['youtube_channels'] else []
        
        # Check if this channel already exists
        channel_exists = False
        for i, ch in enumerate(existing_channels):
            if ch.get('channel_id') == row['channel_id']:
                # Update existing channel with LocalView data
                existing_channels[i]['video_count'] = int(row['video_count'])
                existing_channels[i]['total_views'] = int(row['total_views']) if pd.notna(row['total_views']) else 0
                existing_channels[i]['in_localview'] = True
                existing_channels[i]['localview_enriched'] = datetime.now().isoformat()
                channel_exists = True
                break
        
        # If channel doesn't exist, add it
        if not channel_exists:
            new_channel = {
                'channel_id': row['channel_id'],
                'channel_title': row['channel_title'],
                'channel_url': f"https://www.youtube.com/channel/{row['channel_id']}",
                'video_count': int(row['video_count']),
                'total_views': int(row['total_views']) if pd.notna(row['total_views']) else 0,
                'discovery_method': 'localview',
                'discovered_at': datetime.now().isoformat(),
                'confidence': 1.0,
                'in_localview': True,
                'policy_score': 1  # High score for confirmed government channels
            }
            existing_channels.append(new_channel)
        
        updates.append({
            'id': row['id'],
            'youtube_channels': json.dumps(existing_channels),
            'youtube_channel_count': len(existing_channels),
            'in_localview': True
        })
    
    # Batch update
    logger.info(f"Updating {len(updates)} jurisdictions...")
    
    update_query = """
        UPDATE jurisdiction
        SET 
            youtube_channels = %(youtube_channels)s::jsonb,
            youtube_channel_count = %(youtube_channel_count)s,
            in_localview = %(in_localview)s,
            last_updated = CURRENT_TIMESTAMP
        WHERE id = %(id)s
    """
    
    try:
        execute_batch(cursor, update_query, updates, page_size=100)
        conn.commit()
        logger.success(f"✓ Updated {len(updates)} jurisdictions with LocalView data")
    except Exception as e:
        conn.rollback()
        logger.error(f"✗ Update failed: {e}")
        raise
    finally:
        cursor.close()
    
    return len(updates)


def main():
    """Main enrichment function."""
    logger.info("=" * 80)
    logger.info("LOCALVIEW ENRICHMENT → JURISDICTIONS_DETAILS_SEARCH")
    logger.info("=" * 80)
    logger.info("")
    
    # Extract LocalView channel data
    localview_df = extract_localview_channels()
    
    # Connect to database
    logger.info("Connecting to database...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.success("✓ Connected")
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return 1
    
    start_time = datetime.now()
    
    try:
        # Add LocalView columns
        add_localview_columns(conn)
        
        # Match and enrich
        updated_count = match_and_enrich(conn, localview_df)
        
        # Get final stats
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as total_in_localview,
                COUNT(DISTINCT state) as states,
                SUM(youtube_channel_count) as total_channels
            FROM jurisdiction
            WHERE in_localview = TRUE
        """)
        stats = cursor.fetchone()
        cursor.close()
        
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info("")
        logger.success("=" * 80)
        logger.success("✓ ENRICHMENT COMPLETE")
        logger.success("=" * 80)
        logger.success(f"Jurisdictions enriched: {updated_count:,}")
        logger.success(f"Total in LocalView: {stats[0]:,}")
        logger.success(f"States: {stats[1]}")
        logger.success(f"Total YouTube channels: {stats[2]:,}")
        logger.success(f"Duration: {duration:.1f} seconds")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Query: SELECT * FROM jurisdiction WHERE in_localview = TRUE LIMIT 10")
        logger.info("2. Check enriched data: SELECT jurisdiction_name, state, youtube_channels FROM jurisdiction WHERE in_localview = TRUE")
        
        return 0
        
    except Exception as e:
        logger.error(f"✗ Enrichment failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
