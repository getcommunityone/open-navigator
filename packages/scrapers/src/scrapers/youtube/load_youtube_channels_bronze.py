#!/usr/bin/env python3
"""
Load YouTube Channels to Bronze

This script builds jurisdiction → channel rows from **bronze.bronze_event_youtube**
(distinct channel per jurisdiction) and upserts into **bronze_events_channels** with
`jurisdictions` JSON (no dependency on gold ``jurisdictions_details_search``).

Features:
1. Derives channels from existing YouTube video rows in bronze
2. Auto-flags junk channels (news, entertainment, etc.) when ``--auto-flag`` is set
3. **Single database URL** — default localhost uses DB ``open_navigator``; set ``OPEN_NAVIGATOR_DATABASE_URL`` / ``DATABASE_URL`` for Neon

Validation sources (pattern / title heuristics only in this script):
1. Pattern matching — flag news, entertainment, political figures

Usage:
    python packages/scrapers/src/scrapers/youtube/load_youtube_channels_bronze.py --states AL,GA,IN,MA,MT,WA,WI

    python packages/scrapers/src/scrapers/youtube/load_youtube_channels_bronze.py --states AL,GA,IN,MA,MT,WA,WI --auto-flag
"""
import os
import sys
import json
import argparse
import asyncio
from typing import List, Dict, Optional, Set
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch
from loguru import logger
from dotenv import load_dotenv
from urllib.parse import urlparse

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))


def _reject_placeholder_dsn(label: str, url: str) -> None:
    """Fail fast when docs/examples used a literal … placeholder as hostname."""
    if not (url or "").strip():
        logger.error(f"{label}: database URL is empty.")
        sys.exit(2)
    if "\u2026" in url or "…" in url:
        logger.error(
            f"{label}: URL contains a placeholder ellipsis (…). "
            "Do not copy export lines from docs literally — use a real postgresql://… connection string, "
            "or unset BRONZE_DATABASE_URL / NEON_DATABASE_URL_DEV so .env or localhost defaults apply."
        )
        sys.exit(2)
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").strip()
        if host in ("\u2026", "…", "...", ".."):
            logger.error(f"{label}: hostname {host!r} is not valid. Fix the URL or unset the env var.")
            sys.exit(2)
    except ValueError:
        pass


def _resolve_database_url() -> str:
    """Single Neon / Postgres URL (bronze schema tables live here)."""
    load_dotenv()
    url = (
        (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip()
        or (os.getenv("NEON_DATABASE_URL_DEV") or "").strip()
        or (os.getenv("NEON_DATABASE_URL") or "").strip()
        or (os.getenv("DATABASE_URL") or "").strip()
        or (os.getenv("BRONZE_DATABASE_URL") or "").strip()
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )
    _reject_placeholder_dsn("Database URL", url)
    return url

# Junk channel patterns - ONLY obvious non-government channels
# Be conservative to avoid false positives
JUNK_PATTERNS = [
    # Major news networks (clearly not municipal government)
    'cnn', 'fox news', 'msnbc', 'nbc news', 'abc news', 'cbs news',
    
    # YouTube auto-generated channels (not real channels)
    '- topic',  # e.g., "Hamilton - Topic", "Lin-Manuel Miranda - Topic"
    
    # Music/entertainment platforms
    'vevo',  # Music videos platform
    
    # Clear entertainment shows (not government)
    'last week tonight', 'john oliver', 'daily show', 'stephen colbert',
]


class ChannelLoaderBronze:
    """Load YouTube channels into bronze_events_channels from bronze_event_youtube."""

    def __init__(self, database_url: str):
        self.conn = psycopg2.connect(database_url)

        # Ensure bronze table exists (public or default schema — same connection as reads)
        self._create_channels_table()
    
    def _create_channels_table(self):
        """Create bronze_events_channels table if it doesn't exist."""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bronze_events_channels (
                    id SERIAL PRIMARY KEY,
                    channel_id VARCHAR(50) UNIQUE NOT NULL,
                    channel_url TEXT NOT NULL,
                    channel_title VARCHAR(500),
                    channel_type VARCHAR(50),
                    subscriber_count INTEGER,
                    video_count INTEGER,
                    
                    -- Source tracking
                    in_localview BOOLEAN DEFAULT FALSE,
                    in_jurisdictions_details BOOLEAN DEFAULT FALSE,
                    on_public_website BOOLEAN DEFAULT FALSE,
                    in_wikidata BOOLEAN DEFAULT FALSE,
                    
                    -- Discovery metadata
                    discovery_method VARCHAR(100),
                    discovery_date TIMESTAMP,
                    confidence_score FLOAT,
                    
                    -- Jurisdiction associations
                    jurisdictions JSONB,
                    
                    -- Quality flags
                    is_verified BOOLEAN DEFAULT FALSE,
                    is_government BOOLEAN DEFAULT NULL,
                    flagged_as_junk BOOLEAN DEFAULT FALSE,
                    flag_reason TEXT,

                    -- About-tab featured links (see channel_about_links.py)
                    channel_external_links JSONB,
                    channel_external_links_fetched_at TIMESTAMPTZ,
                    channel_description TEXT,
                    view_count BIGINT,
                    
                    -- Metadata
                    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                );
            """)

            for alter in (
                "ALTER TABLE bronze_events_channels ADD COLUMN IF NOT EXISTS channel_external_links JSONB",
                "ALTER TABLE bronze_events_channels ADD COLUMN IF NOT EXISTS channel_external_links_fetched_at TIMESTAMPTZ",
                "ALTER TABLE bronze_events_channels ADD COLUMN IF NOT EXISTS channel_description TEXT",
                "ALTER TABLE bronze_events_channels ADD COLUMN IF NOT EXISTS view_count BIGINT",
            ):
                cursor.execute(alter + ";")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bronze_channels_channel_id ON bronze_events_channels(channel_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bronze_channels_in_localview ON bronze_events_channels(in_localview);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bronze_channels_in_wikidata ON bronze_events_channels(in_wikidata);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bronze_channels_is_government ON bronze_events_channels(is_government);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bronze_channels_flagged ON bronze_events_channels(flagged_as_junk);")
            
            self.conn.commit()
            logger.success("✓ Ensured bronze_events_channels table exists")
            
        except Exception as e:
            self.conn.rollback()
            logger.warning(f"Note: {e}")
        finally:
            cursor.close()
    
    def get_jurisdictions_channels(self, states_filter: Optional[List[str]] = None) -> List[Dict]:
        """Aggregate distinct YouTube channels per jurisdiction from bronze.bronze_event_youtube."""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)

        query = """
            WITH distinct_pairs AS (
                SELECT
                    jurisdiction_id::text AS jurisdiction_id,
                    MAX(jurisdiction_name) AS jurisdiction_name,
                    MAX(state_code) AS state_code,
                    MAX(state) AS state,
                    MAX(jurisdiction_type) AS jurisdiction_type,
                    channel_id,
                    MAX(
                        COALESCE(
                            NULLIF(BTRIM(channel_url), ''),
                            'https://www.youtube.com/channel/' || channel_id
                        )
                    ) AS channel_url,
                    MAX(NULLIF(BTRIM(channel_type), '')) AS channel_type_hint
                FROM bronze.bronze_event_youtube
                WHERE channel_id IS NOT NULL
                  AND BTRIM(channel_id) <> ''
                  AND jurisdiction_id IS NOT NULL
                  AND BTRIM(jurisdiction_id::text) <> ''
                  AND jurisdiction_name IS NOT NULL
        """
        params: list = []
        if states_filter:
            query += "              AND state_code = ANY(%s)\n"
            params.append(states_filter)
        query += """
                GROUP BY jurisdiction_id, channel_id
            )
            SELECT
                jurisdiction_id,
                MAX(jurisdiction_name) AS jurisdiction_name,
                MAX(state_code) AS state_code,
                MAX(state) AS state,
                MAX(jurisdiction_type) AS jurisdiction_type,
                jsonb_agg(
                    jsonb_build_object(
                        'channel_id', channel_id,
                        'channel_url', channel_url,
                        'channel_title', COALESCE(NULLIF(channel_type_hint, ''), ''),
                        'discovery_method', 'bronze_event_youtube'
                    )
                    ORDER BY channel_id
                ) AS youtube_channels
            FROM distinct_pairs
            GROUP BY jurisdiction_id
            ORDER BY MAX(state_code) NULLS LAST, MAX(jurisdiction_name)
        """

        cursor.execute(query, params)
        jurisdictions = cursor.fetchall()
        cursor.close()

        logger.info(
            f"Found {len(jurisdictions)} jurisdiction(s) with channels from bronze.bronze_event_youtube"
        )
        return jurisdictions
    
    def extract_channels(self, youtube_channels_json: any) -> List[Dict]:
        """Extract channel list from youtube_channels JSONB."""
        if not youtube_channels_json:
            return []
        
        channels = []
        
        if isinstance(youtube_channels_json, str):
            youtube_channels_json = json.loads(youtube_channels_json)
        
        if isinstance(youtube_channels_json, list):
            for item in youtube_channels_json:
                if isinstance(item, dict):
                    channel_id = item.get('channel_id') or item.get('channelId') or item.get('id')
                    
                    if channel_id:
                        channels.append({
                            'channel_id': channel_id,
                            'channel_title': item.get('channel_title') or item.get('title', ''),
                            'channel_url': item.get('channel_url') or f"https://www.youtube.com/channel/{channel_id}",
                            'subscriber_count': item.get('subscriber_count') or item.get('subscribers'),
                            'video_count': item.get('video_count'),
                            'confidence': item.get('confidence'),
                            'policy_score': item.get('policy_score', 0),
                            'discovery_method': item.get('discovery_method', 'bronze_event_youtube')
                        })
        
        return channels
    
    def determine_channel_type(self, channel_title: str) -> str:
        """Determine channel type from title."""
        if not channel_title:
            return 'unknown'
        
        title_lower = channel_title.lower()
        
        if any(word in title_lower for word in ['city', 'town', 'village', 'municipal']):
            return 'municipal'
        elif any(word in title_lower for word in ['county']):
            return 'county'
        elif any(word in title_lower for word in ['state', 'commonwealth']):
            return 'state'
        elif any(word in title_lower for word in ['school', 'district', 'education']):
            return 'school'
        
        return 'unknown'
    
    def is_junk_pattern(self, channel_title: str) -> tuple[bool, str]:
        """Check if channel matches junk patterns."""
        if not channel_title:
            return False, ""
        
        title_lower = channel_title.lower()
        
        for pattern in JUNK_PATTERNS:
            if pattern in title_lower:
                # Determine reason
                if any(word in title_lower for word in ['cnn', 'fox', 'msnbc', 'nbc news', 'abc news', 'cbs news']):
                    reason = 'Major news network (not municipal government)'
                elif '- topic' in title_lower:
                    reason = 'YouTube auto-generated topic channel'
                elif 'vevo' in title_lower:
                    reason = 'Music video platform'
                elif any(word in title_lower for word in ['last week tonight', 'daily show', 'john oliver', 'stephen colbert']):
                    reason = 'Entertainment/comedy show'
                else:
                    reason = f'Non-government pattern: {pattern}'
                
                return True, reason
        
        return False, ""
    
    def upsert_channel(self, channel_data: Dict):
        """Insert or update channel in bronze_events_channels."""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO bronze_events_channels (
                    channel_id, channel_url, channel_title, channel_type,
                    subscriber_count, video_count,
                    in_localview, in_jurisdictions_details, in_wikidata,
                    discovery_method, discovery_date, confidence_score,
                    jurisdictions, is_government, flagged_as_junk, flag_reason,
                    loaded_at, last_updated
                ) VALUES (
                    %(channel_id)s, %(channel_url)s, %(channel_title)s, %(channel_type)s,
                    %(subscriber_count)s, %(video_count)s,
                    %(in_localview)s, %(in_jurisdictions_details)s, %(in_wikidata)s,
                    %(discovery_method)s, CURRENT_TIMESTAMP, %(confidence)s,
                    %(jurisdictions)s::jsonb, %(is_government)s, %(flagged_as_junk)s, %(flag_reason)s,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT (channel_id) DO UPDATE SET
                    channel_title = COALESCE(EXCLUDED.channel_title, bronze_events_channels.channel_title),
                    channel_type = COALESCE(EXCLUDED.channel_type, bronze_events_channels.channel_type),
                    subscriber_count = COALESCE(EXCLUDED.subscriber_count, bronze_events_channels.subscriber_count),
                    video_count = COALESCE(EXCLUDED.video_count, bronze_events_channels.video_count),
                    in_localview = EXCLUDED.in_localview OR bronze_events_channels.in_localview,
                    in_jurisdictions_details = bronze_events_channels.in_jurisdictions_details OR EXCLUDED.in_jurisdictions_details,
                    in_wikidata = EXCLUDED.in_wikidata OR bronze_events_channels.in_wikidata,
                    confidence_score = COALESCE(EXCLUDED.confidence_score, bronze_events_channels.confidence_score),
                    jurisdictions = CASE
                        WHEN bronze_events_channels.jurisdictions IS NULL THEN EXCLUDED.jurisdictions
                        WHEN NOT bronze_events_channels.jurisdictions @> EXCLUDED.jurisdictions 
                        THEN bronze_events_channels.jurisdictions || EXCLUDED.jurisdictions
                        ELSE bronze_events_channels.jurisdictions
                    END,
                    is_government = COALESCE(EXCLUDED.is_government, bronze_events_channels.is_government),
                    flagged_as_junk = EXCLUDED.flagged_as_junk OR bronze_events_channels.flagged_as_junk,
                    flag_reason = COALESCE(EXCLUDED.flag_reason, bronze_events_channels.flag_reason),
                    last_updated = CURRENT_TIMESTAMP
            """, channel_data)
            
            self.conn.commit()
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error upserting channel {channel_data['channel_id']}: {e}")
            raise
        finally:
            cursor.close()
    
    async def load_channels(
        self,
        states_filter: Optional[List[str]] = None,
        validate: bool = False,
        auto_flag: bool = False
    ):
        """Load channels from bronze.bronze_event_youtube into bronze_events_channels."""

        logger.info("")
        logger.info("=" * 80)
        logger.info("CHANNEL LOADER (BRONZE)")
        logger.info("=" * 80)
        logger.info("Source: bronze.bronze_event_youtube (aggregated per jurisdiction)")
        logger.info(f"Target: bronze_events_channels")
        logger.info(f"States: {', '.join(states_filter) if states_filter else 'ALL'}")
        logger.info(f"Validate: {validate}")
        logger.info(f"Auto-flag: {auto_flag}")
        logger.info("")

        # Jurisdiction/channel groups from bronze video rows
        jurisdictions = self.get_jurisdictions_channels(states_filter)
        
        total_channels = 0
        loaded_channels = 0
        flagged_channels = 0
        
        for jurisdiction in jurisdictions:
            channels = self.extract_channels(jurisdiction['youtube_channels'])
            
            for channel in channels:
                total_channels += 1
                
                # Determine channel type
                channel_type = self.determine_channel_type(channel.get('channel_title', ''))
                
                # Check if junk
                is_junk, junk_reason = self.is_junk_pattern(channel.get('channel_title', ''))
                
                # Build jurisdiction association
                jurisdiction_info = {
                    'jurisdiction_id': jurisdiction['jurisdiction_id'],
                    'jurisdiction_name': jurisdiction['jurisdiction_name'],
                    'state_code': jurisdiction['state_code'],
                    'state': jurisdiction['state'],
                    'jurisdiction_type': jurisdiction['jurisdiction_type']
                }
                
                channel_data = {
                    'channel_id': channel['channel_id'],
                    'channel_url': channel['channel_url'],
                    'channel_title': channel.get('channel_title'),
                    'channel_type': channel_type,
                    'subscriber_count': channel.get('subscriber_count'),
                    'video_count': channel.get('video_count'),
                    'in_localview': False,  # Will be updated by separate process
                    'in_wikidata': False,
                    'in_jurisdictions_details': False,
                    'discovery_method': channel.get('discovery_method', 'bronze_event_youtube'),
                    'confidence': channel.get('confidence'),
                    'jurisdictions': json.dumps([jurisdiction_info]),
                    'is_government': None if not is_junk else False,
                    'flagged_as_junk': is_junk if auto_flag else False,
                    'flag_reason': junk_reason if (auto_flag and is_junk) else None
                }
                
                self.upsert_channel(channel_data)
                loaded_channels += 1
                
                if is_junk and auto_flag:
                    flagged_channels += 1
                    logger.debug(f"  Flagged: {channel['channel_title']} - {junk_reason}")
        
        logger.info("")
        logger.success(f"✓ Loaded {loaded_channels}/{total_channels} channels to bronze")
        if auto_flag:
            logger.info(f"  Flagged {flagged_channels} junk channels")
        logger.info("")
    
    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Load YouTube channels to bronze database')
    parser.add_argument('--states', type=str, help='Comma-separated state codes (e.g., AL,MA,WI)')
    parser.add_argument('--validate', action='store_true', help='Validate against WikiData')
    parser.add_argument('--auto-flag', action='store_true', help='Auto-flag junk channels')
    
    args = parser.parse_args()
    
    states_filter = args.states.split(',') if args.states else None

    url = _resolve_database_url()
    loader = ChannelLoaderBronze(url)
    
    try:
        asyncio.run(loader.load_channels(
            states_filter=states_filter,
            validate=args.validate,
            auto_flag=args.auto_flag
        ))
    finally:
        loader.close()


if __name__ == '__main__':
    main()
