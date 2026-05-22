#!/usr/bin/env python3
"""
Load and Validate YouTube Channels

This script loads channels from jurisdiction into events_channels_search,
validates them against multiple sources, and flags junk channels.

Features:
1. Enriches jurisdiction with Wikidata population and metadata
2. Matches LocalView events to YouTube channels
3. Validates channels against WikiData
4. Auto-flags junk channels (news, entertainment, etc.)

Validation sources:
1. LocalView dataset - channels with historical meeting data
2. WikiData - official government YouTube channels
3. Pattern matching - flag news, entertainment, political figures

Usage:
    # Load all channels (enriches with Wikidata automatically)
    python scripts/datasources/youtube/load_channels.py --states AL,GA,IN,MA,MT,WA,WI
    
    # Load and validate
    python scripts/datasources/youtube/load_channels.py --states AL,GA,IN,MA,MT,WA,WI --validate
    
    # Auto-flag junk channels
    python scripts/datasources/youtube/load_channels.py --states AL,GA,IN,MA,MT,WA,WI --auto-flag
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

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from scripts.datasources.wikidata.wikidata_integration import WikidataQuery

load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')

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


class ChannelLoader:
    """Load and validate YouTube channels."""
    
    def __init__(self, database_url: str):
        self.conn = psycopg2.connect(database_url)
        self.wikidata = WikidataQuery()
        
        # Ensure tables exist
        self._create_channels_table()
    
    def _create_channels_table(self):
        """Create events_channels_search table if it doesn't exist."""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events_channels_search (
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
                    
                    -- Metadata
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_video_check TIMESTAMP,
                    notes TEXT
                );
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channels_channel_id ON events_channels_search(channel_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channels_in_localview ON events_channels_search(in_localview);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channels_in_wikidata ON events_channels_search(in_wikidata);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channels_is_government ON events_channels_search(is_government);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channels_flagged ON events_channels_search(flagged_as_junk);")
            
            self.conn.commit()
            logger.success("✓ Ensured events_channels_search table exists")
            
        except Exception as e:
            self.conn.rollback()
            logger.warning(f"Note: {e}")
        finally:
            cursor.close()
    
    def get_jurisdictions_channels(self, states_filter: Optional[List[str]] = None) -> List[Dict]:
        """Get all channels from jurisdiction."""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                jurisdiction_id,
                name AS jurisdiction_name,
                state_code,
                state,
                type AS jurisdiction_type,
                youtube_channels
            FROM jurisdiction
            WHERE youtube_channel_count > 0
                AND youtube_channels IS NOT NULL
        """
        
        params = []
        if states_filter:
            query += " AND state_code = ANY(%s)"
            params.append(states_filter)
        
        query += " ORDER BY state_code, jurisdiction_name"
        
        cursor.execute(query, params)
        jurisdictions = cursor.fetchall()
        cursor.close()
        
        logger.info(f"Found {len(jurisdictions)} jurisdictions with YouTube channels")
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
                            'discovery_method': item.get('discovery_method', 'jurisdictions_details')
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
    
    def check_in_localview(self, channel_id: str) -> bool:
        """Check if channel exists in LocalView data."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM event 
                WHERE channel_id = %s AND source = 'localview'
            )
        """, (channel_id,))
        
        exists = cursor.fetchone()[0]
        cursor.close()
        
        return exists
    
    def enrich_from_wikidata(self, states_filter: Optional[List[str]] = None):
        """Enrich jurisdiction with population and metadata from jurisdictions_wikidata.
        
        Handles naming variations:
        - Exact match first
        - Then tries removing " County", " city", " town" suffixes
        
        Updates:
        - population
        - per_capita_income
        - time_zone
        - ballotpedia_id
        - tripadvisor_id
        - subreddit
        - postal_codes
        - official_image_url
        - head_of_government
        """
        cursor = self.conn.cursor()
        
        try:
            logger.info("  Enriching jurisdiction from Wikidata...")
            
            # Build state filter
            state_filter_sql = ""
            params = []
            if states_filter:
                state_filter_sql = "AND d.state_code = ANY(%s)"
                params.append(states_filter)
            
            # Strategy 1: Exact match
            query1 = f"""
                UPDATE jurisdiction d
                SET 
                    population = w.population,
                    per_capita_income = w.per_capita_income,
                    time_zone = w.time_zone,
                    ballotpedia_id = w.ballotpedia_id,
                    tripadvisor_id = w.tripadvisor_id,
                    subreddit = w.subreddit,
                    postal_codes = w.postal_codes,
                    official_image_url = w.official_image_url,
                    head_of_government = w.head_of_government,
                    last_updated = CURRENT_TIMESTAMP
                FROM jurisdictions_wikidata w
                WHERE d.name = w.jurisdiction_name
                  AND d.state_code = w.state_code
                  {state_filter_sql}
                  AND w.population IS NOT NULL;
            """
            
            cursor.execute(query1, params)
            exact_matches = cursor.rowcount
            self.conn.commit()
            logger.info(f"    Exact name matches: {exact_matches}")
            
            # Strategy 2: Match with county suffix (wikidata has "King County", details has "King")
            query2 = f"""
                UPDATE jurisdiction d
                SET 
                    population = COALESCE(d.population, w.population),
                    per_capita_income = COALESCE(d.per_capita_income, w.per_capita_income),
                    time_zone = COALESCE(d.time_zone, w.time_zone),
                    ballotpedia_id = COALESCE(d.ballotpedia_id, w.ballotpedia_id),
                    tripadvisor_id = COALESCE(d.tripadvisor_id, w.tripadvisor_id),
                    subreddit = COALESCE(d.subreddit, w.subreddit),
                    postal_codes = COALESCE(d.postal_codes, w.postal_codes),
                    official_image_url = COALESCE(d.official_image_url, w.official_image_url),
                    head_of_government = COALESCE(d.head_of_government, w.head_of_government),
                    last_updated = CURRENT_TIMESTAMP
                FROM jurisdictions_wikidata w
                WHERE d.name || ' County' = w.jurisdiction_name
                  AND d.state_code = w.state_code
                  AND d.type = 'county'
                  {state_filter_sql}
                  AND w.population IS NOT NULL;
            """
            
            cursor.execute(query2, params)
            county_matches = cursor.rowcount
            self.conn.commit()
            logger.info(f"    County suffix matches: {county_matches}")
            
            # Strategy 3: Match cities with variations (less common but handle "City of X" vs "X")
            query3 = f"""
                UPDATE jurisdiction d
                SET 
                    population = COALESCE(d.population, w.population),
                    per_capita_income = COALESCE(d.per_capita_income, w.per_capita_income),
                    time_zone = COALESCE(d.time_zone, w.time_zone),
                    ballotpedia_id = COALESCE(d.ballotpedia_id, w.ballotpedia_id),
                    tripadvisor_id = COALESCE(d.tripadvisor_id, w.tripadvisor_id),
                    subreddit = COALESCE(d.subreddit, w.subreddit),
                    postal_codes = COALESCE(d.postal_codes, w.postal_codes),
                    official_image_url = COALESCE(d.official_image_url, w.official_image_url),
                    head_of_government = COALESCE(d.head_of_government, w.head_of_government),
                    last_updated = CURRENT_TIMESTAMP
                FROM jurisdictions_wikidata w
                WHERE (
                    ('City of ' || d.name = w.jurisdiction_name) OR
                    (d.name = REPLACE(w.jurisdiction_name, 'City of ', ''))
                  )
                  AND d.state_code = w.state_code
                  AND d.type = 'city'
                  {state_filter_sql}
                  AND w.population IS NOT NULL;
            """
            
            cursor.execute(query3, params)
            city_matches = cursor.rowcount
            self.conn.commit()
            logger.info(f"    City variation matches: {city_matches}")
            
            total_enriched = exact_matches + county_matches + city_matches
            logger.success(f"✓ Enriched {total_enriched} jurisdictions with Wikidata population and metadata")
            
            # Show enrichment stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE population IS NOT NULL AND population > 0) as has_population,
                    COUNT(*) FILTER (WHERE per_capita_income IS NOT NULL) as has_income,
                    COUNT(*) FILTER (WHERE ballotpedia_id IS NOT NULL) as has_ballotpedia
                FROM jurisdiction
                WHERE state_code = ANY(%s);
            """, (states_filter,) if states_filter else (None,))
            
            stats = cursor.fetchone()
            if stats and states_filter:
                logger.info(f"  Jurisdictions with population: {stats[1]}/{stats[0]} ({stats[1]*100//stats[0] if stats[0] > 0 else 0}%)")
                logger.info(f"  Jurisdictions with income data: {stats[2]}/{stats[0]}")
                logger.info(f"  Jurisdictions with Ballotpedia: {stats[3]}/{stats[0]}")
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error enriching from Wikidata: {e}")
            raise
        finally:
            cursor.close()
    
    def update_localview_from_events(self):
        """Update in_localview flag for all channels based on event.
        
        Any channel that has at least one event with source='localview' will be
        marked as in_localview=TRUE.
        
        Steps:
        1. Match localview events to YouTube events by video_url
        2. Update channel_id in localview events
        3. Mark channels as in_localview
        """
        cursor = self.conn.cursor()
        
        try:
            # Step 1: Update channel_id for localview events by matching video URLs
            logger.info("  Step 1: Matching localview events to YouTube channels...")
            
            cursor.execute("""
                UPDATE event e1
                SET channel_id = e2.channel_id,
                    last_updated = CURRENT_TIMESTAMP
                FROM event e2
                WHERE e1.source = 'localview'
                  AND e1.channel_id IS NULL
                  AND e1.video_url IS NOT NULL
                  AND e2.source = 'youtube'
                  AND e2.channel_id IS NOT NULL
                  AND e1.video_url = e2.video_url;
            """)
            
            matched_count = cursor.rowcount
            self.conn.commit()
            logger.info(f"    Matched {matched_count} localview events to channels via video URL")
            
            # Step 2: Update in_localview for channels that have localview events
            logger.info("  Step 2: Marking channels with localview events...")
            
            cursor.execute("""
                UPDATE events_channels_search
                SET in_localview = TRUE,
                    last_updated = CURRENT_TIMESTAMP
                WHERE channel_id IN (
                    SELECT DISTINCT channel_id
                    FROM event
                    WHERE source = 'localview'
                      AND channel_id IS NOT NULL
                )
                AND (in_localview = FALSE OR in_localview IS NULL);
            """)
            
            updated_count = cursor.rowcount
            self.conn.commit()
            
            logger.success(f"✓ Updated {updated_count} channels to in_localview=TRUE based on events")
            
            # Show summary
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT c.channel_id) as total_localview_channels,
                    COUNT(DISTINCT e.event_id) as localview_events_linked
                FROM events_channels_search c
                INNER JOIN event e ON c.channel_id = e.channel_id
                WHERE c.in_localview = TRUE
                  AND e.source = 'localview';
            """)
            stats = cursor.fetchone()
            
            logger.info(f"  Total channels marked in_localview: {stats[0] if stats else 0}")
            logger.info(f"  Total localview events linked: {stats[1] if stats else 0}")
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error updating localview flags: {e}")
            raise
        finally:
            cursor.close()
    
    async def check_in_wikidata(self, jurisdiction_name: str, state_code: str, channel_id: str) -> bool:
        """Check if channel exists in WikiData for this jurisdiction."""
        try:
            # Query WikiData for jurisdiction info
            info = await self.wikidata.get_jurisdiction_info(jurisdiction_name, state_code, 'city')
            
            if info and info.get('youtube_channel_id'):
                wikidata_channel_id = info['youtube_channel_id']
                return wikidata_channel_id == channel_id
            
            return False
            
        except Exception as e:
            logger.debug(f"WikiData check failed for {jurisdiction_name}: {e}")
            return False
    
    def upsert_channel(self, channel_data: Dict):
        """Insert or update channel in events_channels_search."""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO events_channels_search (
                    channel_id, channel_url, channel_title, channel_type,
                    subscriber_count, video_count,
                    in_localview, in_jurisdictions_details, in_wikidata,
                    discovery_method, discovery_date, confidence_score,
                    jurisdictions, is_government, flagged_as_junk, flag_reason,
                    last_updated
                ) VALUES (
                    %(channel_id)s, %(channel_url)s, %(channel_title)s, %(channel_type)s,
                    %(subscriber_count)s, %(video_count)s,
                    %(in_localview)s, TRUE, %(in_wikidata)s,
                    %(discovery_method)s, CURRENT_TIMESTAMP, %(confidence)s,
                    %(jurisdictions)s::jsonb, %(is_government)s, %(flagged_as_junk)s, %(flag_reason)s,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (channel_id) DO UPDATE SET
                    channel_title = COALESCE(EXCLUDED.channel_title, events_channels_search.channel_title),
                    channel_type = COALESCE(EXCLUDED.channel_type, events_channels_search.channel_type),
                    subscriber_count = COALESCE(EXCLUDED.subscriber_count, events_channels_search.subscriber_count),
                    video_count = COALESCE(EXCLUDED.video_count, events_channels_search.video_count),
                    in_localview = EXCLUDED.in_localview OR events_channels_search.in_localview,
                    in_jurisdictions_details = TRUE,
                    in_wikidata = EXCLUDED.in_wikidata OR events_channels_search.in_wikidata,
                    confidence_score = COALESCE(EXCLUDED.confidence_score, events_channels_search.confidence_score),
                    jurisdictions = CASE
                        WHEN events_channels_search.jurisdictions IS NULL THEN EXCLUDED.jurisdictions
                        WHEN NOT events_channels_search.jurisdictions @> EXCLUDED.jurisdictions 
                        THEN events_channels_search.jurisdictions || EXCLUDED.jurisdictions
                        ELSE events_channels_search.jurisdictions
                    END,
                    is_government = COALESCE(EXCLUDED.is_government, events_channels_search.is_government),
                    flagged_as_junk = EXCLUDED.flagged_as_junk OR events_channels_search.flagged_as_junk,
                    flag_reason = COALESCE(EXCLUDED.flag_reason, events_channels_search.flag_reason),
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
        """Load channels from jurisdiction."""
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("CHANNEL LOADER")
        logger.info("=" * 80)
        logger.info(f"States: {', '.join(states_filter) if states_filter else 'ALL'}")
        logger.info(f"Validate: {validate}")
        logger.info(f"Auto-flag junk: {auto_flag}")
        logger.info("")
        
        # First, enrich jurisdiction with Wikidata
        logger.info("Enriching jurisdiction from Wikidata...")
        self.enrich_from_wikidata(states_filter)
        logger.info("")
        
        # Update in_localview based on existing events
        logger.info("Updating in_localview flags from event...")
        self.update_localview_from_events()
        logger.info("")
        
        # Get jurisdictions
        jurisdictions = self.get_jurisdictions_channels(states_filter)
        
        total_channels = 0
        flagged_channels = 0
        validated_channels = 0
        
        for idx, jurisdiction in enumerate(jurisdictions, 1):
            jurisdiction_id = jurisdiction['jurisdiction_id']
            jurisdiction_name = jurisdiction['jurisdiction_name']
            state_code = jurisdiction['state_code']
            state = jurisdiction['state']
            jurisdiction_type = jurisdiction['jurisdiction_type']
            
            logger.info(f"[{idx}/{len(jurisdictions)}] {jurisdiction_name}, {state_code}")
            
            # Extract channels
            channels = self.extract_channels(jurisdiction['youtube_channels'])
            logger.info(f"  Found {len(channels)} channel(s)")
            
            for channel in channels:
                channel_id = channel['channel_id']
                channel_title = channel['channel_title']
                
                # Determine channel type
                channel_type = self.determine_channel_type(channel_title)
                
                # Check for junk patterns
                is_junk, junk_reason = self.is_junk_pattern(channel_title)
                
                # Check in LocalView
                in_localview = self.check_in_localview(channel_id)
                
                # Check in WikiData (if validating)
                in_wikidata = False
                if validate:
                    in_wikidata = await self.check_in_wikidata(jurisdiction_name, state_code, channel_id)
                    if in_wikidata:
                        validated_channels += 1
                        logger.info(f"    ✓ {channel_title} - VALIDATED in WikiData")
                
                # Determine is_government
                is_government = None
                if in_wikidata or in_localview:
                    is_government = True
                elif is_junk:
                    is_government = False
                
                # Flag as junk if auto-flagging
                flagged = False
                flag_reason = None
                if auto_flag and is_junk:
                    flagged = True
                    flag_reason = junk_reason
                    flagged_channels += 1
                    logger.warning(f"    ✗ {channel_title} - FLAGGED: {junk_reason}")
                
                # Prepare jurisdiction data
                jurisdiction_data = {
                    'jurisdiction_id': jurisdiction_id,
                    'jurisdiction_name': jurisdiction_name,
                    'state_code': state_code,
                    'state': state
                }
                
                # Upsert channel
                channel_data = {
                    'channel_id': channel_id,
                    'channel_url': channel['channel_url'],
                    'channel_title': channel_title,
                    'channel_type': channel_type,
                    'subscriber_count': channel.get('subscriber_count'),
                    'video_count': channel.get('video_count'),
                    'in_localview': in_localview,
                    'in_wikidata': in_wikidata,
                    'discovery_method': channel.get('discovery_method'),
                    'confidence': channel.get('confidence'),
                    'jurisdictions': json.dumps([jurisdiction_data]),
                    'is_government': is_government,
                    'flagged_as_junk': flagged,
                    'flag_reason': flag_reason
                }
                
                self.upsert_channel(channel_data)
                total_channels += 1
        
        # Final statistics
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE in_localview) as in_localview,
                COUNT(*) FILTER (WHERE in_wikidata) as in_wikidata,
                COUNT(*) FILTER (WHERE flagged_as_junk) as flagged,
                COUNT(*) FILTER (WHERE is_government = TRUE) as confirmed_govt,
                COUNT(*) FILTER (WHERE channel_type = 'municipal') as municipal,
                COUNT(*) FILTER (WHERE channel_type = 'county') as county,
                COUNT(*) FILTER (WHERE channel_type = 'school') as school,
                COUNT(*) FILTER (WHERE channel_type = 'unknown') as unknown
            FROM events_channels_search
        """)
        stats = cursor.fetchone()
        cursor.close()
        
        logger.info("")
        logger.success("=" * 80)
        logger.success("LOADING COMPLETE")
        logger.success("=" * 80)
        logger.success(f"Channels processed: {total_channels}")
        logger.success(f"Channels flagged as junk: {flagged_channels}")
        if validate:
            logger.success(f"Channels validated in WikiData: {validated_channels}")
        logger.info("")
        logger.info("Database statistics:")
        logger.info(f"  Total channels: {stats['total']}")
        logger.info(f"  In LocalView: {stats['in_localview']}")
        logger.info(f"  In WikiData: {stats['in_wikidata']}")
        logger.info(f"  Flagged as junk: {stats['flagged']}")
        logger.info(f"  Confirmed government: {stats['confirmed_govt']}")
        logger.info("")
        logger.info("By channel type:")
        logger.info(f"  Municipal: {stats['municipal']}")
        logger.info(f"  County: {stats['county']}")
        logger.info(f"  School: {stats['school']}")
        logger.info(f"  Unknown: {stats['unknown']}")
        logger.info("")
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Load and validate YouTube channels')
    
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated list of state codes (e.g., AL,MA,WI)'
    )
    
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate channels against WikiData (slower but more accurate)'
    )
    
    parser.add_argument(
        '--auto-flag',
        action='store_true',
        help='Automatically flag junk channels (news, entertainment, etc.)'
    )
    
    args = parser.parse_args()
    
    # Parse states
    states_filter = None
    if args.states:
        states_filter = [s.strip().upper() for s in args.states.split(',')]
    
    # Load channels
    loader = ChannelLoader(DATABASE_URL)
    
    try:
        await loader.load_channels(
            states_filter=states_filter,
            validate=args.validate,
            auto_flag=args.auto_flag
        )
    finally:
        loader.close()


if __name__ == '__main__':
    asyncio.run(main())
