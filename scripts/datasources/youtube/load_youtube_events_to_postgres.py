#!/usr/bin/env python3
"""
Load YouTube Events to bronze.bronze_events_youtube

This script:
1. Reads YouTube channels from bronze.bronze_events_youtube (existing videos with channel data)
2. For each channel, fetches new videos using YouTube API or yt-dlp fallback
3. Fetches video transcripts (captions/subtitles) from YouTube
4. Incrementally adds/updates events in bronze.bronze_events_youtube table (bronze layer)
5. Stores video transcripts in bronze.bronze_events_text_ai table (bronze layer)
6. Links events to jurisdictions via jurisdiction_id

Usage:
    # Process all jurisdictions with YouTube channels
    python scripts/datasources/youtube/load_youtube_events_to_postgres.py
    
    # Process specific states only
    python scripts/datasources/youtube/load_youtube_events_to_postgres.py --states AL,MA,WI

    # One jurisdiction (Northport) — refresh 2026 live streams into bronze
    python scripts/datasources/youtube/load_youtube_events_to_postgres.py \\
        --jurisdiction-id municipality_0155200 --days 200 --max-videos 80 --skip-transcripts
    
    # Process only new videos (published in last N days)
    python scripts/datasources/youtube/load_youtube_events_to_postgres.py --days 30
    
    # Limit videos per channel
    python scripts/datasources/youtube/load_youtube_events_to_postgres.py --max-videos 10
    
    # Skip transcript fetching (faster)
    python scripts/datasources/youtube/load_youtube_events_to_postgres.py --skip-transcripts
    
    # Fetch text transcripts only (no VTT downloads, faster and cleaner)
    python scripts/datasources/youtube/load_youtube_events_to_postgres.py --text-transcripts-only
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
import argparse
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch, RealDictCursor
from loguru import logger
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled, 
    NoTranscriptFound, 
    VideoUnavailable,
    IpBlocked
)
import yt_dlp

# Import YouTube scraper (handles API and yt-dlp fallback)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'localview'))
from scrape_youtube_channels import MunicipalYouTubeScraper

from scripts.datasources.youtube.channel_about_links import (
    ensure_bronze_events_channels_link_columns,
)
from scripts.gemini.transcript_cache_paths import resolve_meeting_event_date

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')


class YouTubeEventsLoader:
    """Load YouTube videos from jurisdictions into bronze.bronze_events_youtube table."""
    
    def __init__(
        self,
        database_url: str,
        youtube_api_key: Optional[str] = None,
        max_videos_per_channel: int = 200,
        min_duration_seconds: int = 120,
        days_lookback: Optional[int] = None,
        fetch_transcripts: bool = True,
        force_full_fetch: bool = False,
        transcript_delay: float = 2.0,
        use_ytdlp_fallback: bool = True,
        cookies_file: Optional[str] = None,
        proxy_url: Optional[str] = None,
        ensure_schema_setup: bool = True,
    ):
        # Sanitize database URL to fix common connection issues (Neon channel_binding)
        self.database_url = self._sanitize_database_url(database_url)
        self.youtube_api_key = youtube_api_key
        self.max_videos = max_videos_per_channel
        self.min_duration_seconds = max(0, int(min_duration_seconds or 0))
        self.days_lookback = days_lookback
        self.fetch_transcripts = fetch_transcripts
        self.force_full_fetch = force_full_fetch
        self.transcript_delay = transcript_delay  # Delay between transcript fetches (seconds)
        self.use_ytdlp_fallback = use_ytdlp_fallback  # Whether to fall back to yt-dlp when youtube_transcript_api fails
        self.cookies_file = cookies_file  # Path to cookies.txt file for authenticated requests
        self.proxy_url = proxy_url  # Proxy URL to bypass IP blocks
        
        # Initialize YouTube scraper with cookies/proxy support
        self.scraper = MunicipalYouTubeScraper(
            api_key=youtube_api_key,
            cookies_file=cookies_file,
            proxy_url=proxy_url
        )
        
        # Connect to database
        self.conn = psycopg2.connect(self.database_url)
        
        # Ensure tables and columns exist (optional for tight backfill loops).
        if ensure_schema_setup:
            self._add_jurisdiction_id_column()
            self._create_bronze_events_text_ai_table()
            self._create_bronze_events_channels_table()
            ensure_bronze_events_channels_link_columns(self.conn)
    
    def _sanitize_database_url(self, url: str) -> str:
        """Sanitize database URL to fix common connection issues.
        
        Fixes:
        - Neon's channel_binding=require parameter (causes psycopg2 errors)
        - Quoted parameter values
        - Whitespace and newlines in URL
        """
        # Strip leading/trailing whitespace from entire URL
        url = url.strip()
        
        # Remove newlines and extra whitespace within the URL
        url = re.sub(r'\s+', ' ', url).replace('\n', '').replace('\r', '')
        
        # Fix channel_binding parameter (common issue with Neon/cloud PostgreSQL)
        # psycopg2 doesn't support channel_binding=require, change to prefer or remove
        if 'channel_binding=' in url:
            # First, remove any quotes and whitespace around the value
            url = re.sub(r'channel_binding=\s*["\']?\s*(require|prefer)\s*["\']?\s*', r'channel_binding=prefer', url)
            # Catch any remaining quoted values (with potential whitespace inside)
            url = re.sub(r'channel_binding=\s*["\']([^"\'\'\&\s]+)\s*["\']', r'channel_binding=\1', url)
        
        # Also fix sslmode if it has quotes or whitespace
        if 'sslmode=' in url:
            url = re.sub(r'sslmode=\s*["\']([^"\'\'\&\s]+)\s*["\']', r'sslmode=\1', url)
        
        return url
    
    def _add_jurisdiction_id_column(self):
        """Add jurisdiction_id and channel_id columns to event if they don't exist."""
        cursor = self.conn.cursor()
        
        try:
            # Add jurisdiction_id column
            cursor.execute("""
                ALTER TABLE event 
                ADD COLUMN IF NOT EXISTS jurisdiction_id VARCHAR(50);
            """)
            
            # Add channel_id column for per-channel tracking
            cursor.execute("""
                ALTER TABLE event 
                ADD COLUMN IF NOT EXISTS channel_id VARCHAR(50);
            """)
            
            # Add YouTube metrics columns
            cursor.execute("""
                ALTER TABLE event
                ADD COLUMN IF NOT EXISTS view_count INTEGER;
            """)
            
            cursor.execute("""
                ALTER TABLE event
                ADD COLUMN IF NOT EXISTS duration_minutes INTEGER;
            """)
            
            cursor.execute("""
                ALTER TABLE event
                ADD COLUMN IF NOT EXISTS like_count INTEGER;
            """)
            
            # Add language column
            cursor.execute("""
                ALTER TABLE event
                ADD COLUMN IF NOT EXISTS language VARCHAR(10);
            """)
            
            # Add channel_type column
            cursor.execute("""
                ALTER TABLE event
                ADD COLUMN IF NOT EXISTS channel_type VARCHAR(50);
            """)
            
            # Add location_description column
            cursor.execute("""
                ALTER TABLE event
                ADD COLUMN IF NOT EXISTS location_description TEXT;
            """)
            
            # Add channel_url column
            cursor.execute("""
                ALTER TABLE event
                ADD COLUMN IF NOT EXISTS channel_url TEXT;
            """)
            
            # Create index for jurisdiction_id
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_jurisdiction_id 
                ON event(jurisdiction_id);
            """)
            
            # Create index for channel_id
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_channel_id 
                ON event(channel_id);
            """)
            
            # Add unique constraint on video_url to prevent duplicates
            cursor.execute("""
                DO $$ 
                BEGIN
                    ALTER TABLE event 
                    ADD CONSTRAINT unique_video_url 
                    UNIQUE (video_url);
                EXCEPTION
                    WHEN duplicate_object OR duplicate_table THEN NULL;
                END $$;
            """)
            
            # Add foreign key constraint (optional - helps data integrity)
            cursor.execute("""
                DO $$ 
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = 'jurisdiction'
                    )
                    AND EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'jurisdiction'
                          AND column_name = 'jurisdiction_id'
                    ) THEN
                        IF EXISTS (
                            SELECT 1
                            FROM pg_constraint c
                            JOIN pg_class t ON t.oid = c.conrelid
                            JOIN pg_namespace n ON n.oid = t.relnamespace
                            JOIN unnest(c.conkey) WITH ORDINALITY AS cols(attnum, ord) ON TRUE
                            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = cols.attnum
                            WHERE n.nspname = 'public'
                              AND t.relname = 'jurisdiction'
                              AND c.contype IN ('p', 'u')
                            GROUP BY c.oid
                                                        HAVING array_agg(a.attname::text ORDER BY cols.ord) = ARRAY['jurisdiction_id']
                        ) THEN
                            ALTER TABLE event 
                            ADD CONSTRAINT fk_events_jurisdiction
                            FOREIGN KEY (jurisdiction_id) 
                            REFERENCES jurisdiction(jurisdiction_id)
                            ON DELETE SET NULL;
                        END IF;
                    END IF;
                EXCEPTION
                    WHEN duplicate_object OR duplicate_table THEN NULL;
                END $$;
            """)
            
            self.conn.commit()
            logger.success("✓ Ensured jurisdiction_id, channel_id, metrics, language, location, and channel_url columns exist")
            
        except Exception as e:
            self.conn.rollback()
            logger.warning(f"Note: {e}")
        finally:
            cursor.close()
    
    def _create_bronze_events_text_ai_table(self):
        """Create bronze.bronze_events_text_ai table if it doesn't exist."""
        cursor = self.conn.cursor()
        
        try:
            # Create bronze schema if it doesn't exist
            cursor.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
            
            # Create table matching migration 004 schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bronze.bronze_events_text_ai (
                    id SERIAL PRIMARY KEY,
                    event_id INTEGER,
                    video_id VARCHAR(20) NOT NULL,
                    raw_text TEXT,
                    segments JSONB,
                    language VARCHAR(10),
                    is_auto_generated BOOLEAN DEFAULT FALSE,
                    transcript_source VARCHAR(50),
                    ai_model VARCHAR(100),
                    ai_extraction_version VARCHAR(20),
                    has_transcript BOOLEAN DEFAULT FALSE,
                    transcript_quality VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_bronze_events_text_ai_event_id 
                ON bronze.bronze_events_text_ai(event_id);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_bronze_events_text_ai_video_id 
                ON bronze.bronze_events_text_ai(video_id);
            """)
            
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_bronze_events_text_video_id_unique 
                ON bronze.bronze_events_text_ai(video_id);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_bronze_events_text_source 
                ON bronze.bronze_events_text_ai(transcript_source);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_bronze_events_text_quality 
                ON bronze.bronze_events_text_ai(has_transcript, transcript_quality);
            """)
            
            # Full-text search index on raw_text
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_bronze_events_text_search_gin 
                ON bronze.bronze_events_text_ai USING GIN (to_tsvector('english', COALESCE(raw_text, '')));
            """)
            
            self.conn.commit()
            logger.success("✓ Ensured bronze.bronze_events_text_ai table exists")
            
        except Exception as e:
            self.conn.rollback()
            logger.warning(f"Note: {e}")
        finally:
            cursor.close()
    
    def _create_bronze_events_channels_table(self):
        """Create bronze.bronze_events_channels table if it doesn't exist."""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bronze.bronze_events_channels (
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

                    -- About-tab featured links (parsed from public /about HTML)
                    channel_external_links JSONB,
                    channel_external_links_fetched_at TIMESTAMPTZ,
                    channel_description TEXT,
                    view_count BIGINT,
                    
                    -- Metadata
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_video_check TIMESTAMP,
                    notes TEXT
                );
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_channels_channel_id 
                ON bronze.bronze_events_channels(channel_id);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_channels_in_localview 
                ON bronze.bronze_events_channels(in_localview);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_channels_is_government 
                ON bronze.bronze_events_channels(is_government);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_channels_flagged 
                ON bronze.bronze_events_channels(flagged_as_junk);
            """)
            
            self.conn.commit()
            logger.success("✓ Ensured bronze.bronze_events_channels table exists")
            
        except Exception as e:
            self.conn.rollback()
            logger.warning(f"Note: {e}")
        finally:
            cursor.close()
    
    def upsert_channel(
        self,
        channel_id: str,
        channel_url: str,
        channel_title: str,
        channel_type: str,
        jurisdiction_id: str,
        jurisdiction_name: str,
        state_code: str,
        discovery_method: str = 'jurisdictions_details',
        confidence_score: float = None
    ):
        """Upsert channel information into bronze.bronze_events_channels."""
        cursor = self.conn.cursor()
        
        try:
            # bronze_events_localview has no channel_id; link LocalView rows (datasource_id = video_id)
            # to a channel via int_localview_youtube_video_channels (dbt) or bronze_events_youtube.
            in_localview = False
            for probe_sql, probe_params in (
                (
                    """
                    SELECT EXISTS(
                        SELECT 1
                        FROM bronze.bronze_events_localview lv
                        INNER JOIN intermediate.int_localview_youtube_video_channels m
                            ON m.video_id = lv.datasource_id
                        WHERE lv.datasource = 'localview'
                          AND m.channel_id = %s
                    )
                    """,
                    (channel_id,),
                ),
                (
                    """
                    SELECT EXISTS(
                        SELECT 1
                        FROM bronze.bronze_events_localview lv
                        INNER JOIN bronze.bronze_events_youtube y
                            ON y.video_id = lv.datasource_id
                        WHERE lv.datasource = 'localview'
                          AND y.channel_id = %s
                    )
                    """,
                    (channel_id,),
                ),
            ):
                try:
                    cursor.execute(probe_sql, probe_params)
                    if cursor.fetchone()[0]:
                        in_localview = True
                        break
                except Exception as exc:
                    logger.debug("LocalView channel probe skipped: {}", exc)
            
            # Prepare jurisdiction data
            jurisdiction_data = {
                'jurisdiction_id': jurisdiction_id,
                'jurisdiction_name': jurisdiction_name,
                'state_code': state_code
            }
            
            cursor.execute("""
                INSERT INTO bronze.bronze_events_channels (
                    channel_id, channel_url, channel_title, channel_type,
                    in_localview, in_jurisdictions_details,
                    discovery_method, discovery_date, confidence_score,
                    jurisdictions, last_updated
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, TRUE,
                    %s, CURRENT_TIMESTAMP, %s,
                    %s::jsonb, CURRENT_TIMESTAMP
                )
                ON CONFLICT (channel_id) DO UPDATE SET
                    channel_title = COALESCE(EXCLUDED.channel_title, bronze.bronze_events_channels.channel_title),
                    channel_type = COALESCE(EXCLUDED.channel_type, bronze.bronze_events_channels.channel_type),
                    in_localview = EXCLUDED.in_localview OR bronze.bronze_events_channels.in_localview,
                    in_jurisdictions_details = TRUE,
                    discovery_method = COALESCE(EXCLUDED.discovery_method, bronze.bronze_events_channels.discovery_method),
                    confidence_score = COALESCE(EXCLUDED.confidence_score, bronze.bronze_events_channels.confidence_score),
                    jurisdictions = CASE
                        WHEN bronze.bronze_events_channels.jurisdictions IS NULL THEN %s::jsonb
                        WHEN NOT bronze.bronze_events_channels.jurisdictions @> %s::jsonb 
                        THEN bronze.bronze_events_channels.jurisdictions || %s::jsonb
                        ELSE bronze.bronze_events_channels.jurisdictions
                    END,
                    last_updated = CURRENT_TIMESTAMP
            """, (
                channel_id, channel_url, channel_title, channel_type,
                in_localview,
                discovery_method, confidence_score,
                json.dumps([jurisdiction_data]),
                json.dumps([jurisdiction_data]),
                json.dumps([jurisdiction_data]),
                json.dumps([jurisdiction_data])
            ))
            
            self.conn.commit()
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error upserting channel {channel_id}: {e}")
        finally:
            cursor.close()
    
    def get_jurisdictions_with_youtube(
        self,
        states_filter: Optional[List[str]] = None,
        jurisdiction_id: Optional[str] = None,
    ) -> List[Dict]:
        """Get jurisdictions that have YouTube channels.

        Primary source: ``intermediate.int_events_channels`` joined to
        ``intermediate.int_jurisdictions`` (broader channel coverage).
        Fallback: ``bronze.bronze_events_youtube`` when intermediate models are
        unavailable or empty.
        """
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Preferred source for full reruns: channel registry resolved by dbt.
            query_int = """
                SELECT
                    j.jurisdiction_id,
                    j.name AS jurisdiction_name,
                    j.state_code,
                    j.state,
                    j.jurisdiction_type,
                    jsonb_agg(
                        DISTINCT jsonb_build_object(
                            'channel_id', ec.channel_id,
                            'channel_url', COALESCE(NULLIF(BTRIM(ec.channel_url), ''), 'https://www.youtube.com/channel/' || ec.channel_id),
                            'channel_title', COALESCE(NULLIF(BTRIM(ec.channel_title), ''), j.name),
                            'channel_type', COALESCE(NULLIF(BTRIM(ec.channel_type), ''), 'unknown')
                        )
                    ) AS youtube_channels,
                    COUNT(DISTINCT ec.channel_id) AS youtube_channel_count
                FROM intermediate.int_events_channels ec
                INNER JOIN intermediate.int_jurisdictions j
                    ON j.jurisdiction_id = ec.jurisdiction_id
                WHERE ec.channel_id IS NOT NULL
                  AND BTRIM(ec.channel_id) <> ''
                  AND ec.jurisdiction_id IS NOT NULL
                  AND BTRIM(ec.jurisdiction_id::text) <> ''
                  AND COALESCE(ec.flagged_as_junk, FALSE) = FALSE
                  AND COALESCE(ec.is_government, TRUE) = TRUE
            """

            params_int: list[Any] = []
            if states_filter:
                query_int += " AND j.state_code = ANY(%s)"
                params_int.append(states_filter)
            if jurisdiction_id:
                query_int += " AND j.jurisdiction_id = %s"
                params_int.append(jurisdiction_id.strip())

            query_int += """
                GROUP BY j.jurisdiction_id, j.name, j.state_code, j.state, j.jurisdiction_type
                HAVING COUNT(DISTINCT ec.channel_id) > 0
                ORDER BY youtube_channel_count DESC, jurisdiction_name
            """

            cursor.execute(query_int, params_int)
            jurisdictions = cursor.fetchall()
            if jurisdictions:
                logger.info(
                    f"Found {len(jurisdictions)} jurisdictions with YouTube channels (source=intermediate.int_events_channels)"
                )
                return jurisdictions
            logger.warning("No channel mappings in intermediate.int_events_channels; falling back to bronze.bronze_events_youtube")

        except Exception as exc:
            logger.warning(f"Intermediate channel source unavailable, falling back to bronze: {exc}")

        # Fallback source: existing bronze video rows.
        query = """
            SELECT
                COALESCE(jurisdiction_id, 'unknown') as jurisdiction_id,
                jurisdiction_name,
                state_code,
                state,
                jurisdiction_type,
                jsonb_agg(
                    DISTINCT jsonb_build_object(
                        'channel_id', channel_id,
                        'channel_url', channel_url,
                        'channel_title', jurisdiction_name
                    )
                ) as youtube_channels,
                COUNT(DISTINCT channel_id) as youtube_channel_count
            FROM bronze.bronze_events_youtube
            WHERE channel_id IS NOT NULL
              AND jurisdiction_name IS NOT NULL
        """

        params = []
        if states_filter:
            query += " AND state_code = ANY(%s)"
            params.append(states_filter)
        if jurisdiction_id:
            query += " AND jurisdiction_id = %s"
            params.append(jurisdiction_id.strip())

        query += """
            GROUP BY jurisdiction_id, jurisdiction_name, state_code, state, jurisdiction_type
            HAVING COUNT(DISTINCT channel_id) > 0
            ORDER BY youtube_channel_count DESC, jurisdiction_name
        """

        cursor.execute(query, params)
        jurisdictions = cursor.fetchall()
        cursor.close()

        logger.info(f"Found {len(jurisdictions)} jurisdictions with YouTube channels (source=bronze.bronze_events_youtube)")
        return jurisdictions
    
    def is_channel_flagged(self, channel_id: str) -> tuple[bool, str]:
        """Check if channel is flagged as junk in bronze.bronze_events_channels."""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                SELECT flagged_as_junk, flag_reason, is_government
                FROM bronze.bronze_events_channels
                WHERE channel_id = %s
            """, (channel_id,))
            
            result = cursor.fetchone()
            
            if result:
                flagged, reason, is_govt = result
                if flagged:
                    return True, reason or "Flagged as junk"
                if is_govt == False:  # Explicitly marked as NOT government
                    return True, "Confirmed non-government channel"
            
            return False, ""
            
        except Exception as e:
            logger.debug(f"Error checking channel flag status: {e}")
            return False, ""
        finally:
            cursor.close()
    
    def extract_channel_ids(
        self,
        youtube_channels_json: Any,
        *,
        trust_catalog: bool = False,
    ) -> List[Dict[str, Any]]:
        """Extract channel IDs and metadata from youtube_channels JSONB field.
        
        Filters to ONLY include government/official channels using:
        1. in_localview = true (verified government channels)
        2. policy_score > 0 (channels with policy/government relevance)
        3. Government-related title keywords
        
        Excludes churches, businesses, news, entertainment, etc.
        """
        if not youtube_channels_json:
            return []
        
        # INCLUDE patterns for government channels (must have at least one)
        GOVERNMENT_KEYWORDS = [
            'city', 'town', 'village', 'municipal', 'municipality',
            'county', 'parish',
            'state', 'commonwealth', 'government', 'gov',
            'council', 'commission', 'board',
            'school district', 'public schools',
            'department of', 'bureau of', 'office of'
        ]
        
        # EXCLUDE patterns for CLEARLY non-government channels
        EXCLUDE_PATTERNS = [
            'church', 'chapel', 'cathedral', 'ministry', 'ministries',  # Religious
            'bible', 'christian', 'baptist', 'methodist', 'lutheran', 'catholic',  # Religious
            'llc', 'inc', 'incorporated', 'company', 'corp',  # Business entities
            'carpet', 'floor', 'furniture', 'auto', 'car', 'truck',  # Businesses
            'software', 'tech', 'technologies',  # Software/tech companies
            'cnn', 'fox news', 'msnbc', 'nbc news', 'abc news', 'cbs news',  # Major news networks
            'news network', 'breaking news', 'live news',  # News channels
            'news.net', 'news group', 'newsgroup', 'newspaper', 'the post', ' post',  # News media
            'press', 'media', 'journalism',  # News media
            'coast to coast', 'radio', 'am official', 'fm official',  # Radio shows
            'gossip', 'rumors', 'drama', 'tea', 'free press', 'getto',  # Gossip/drama channels
            '- topic',  # YouTube auto-generated channels
            'vevo',  # Music video platform
            'last week tonight', 'john oliver', 'daily show', 'stephen colbert',  # Entertainment shows
            'podcast', 'radio show',  # Media shows
            'real estate', 'realty', 'properties',  # Real estate
        ]
        
        channels = []
        
        # Handle different JSON formats
        if isinstance(youtube_channels_json, str):
            youtube_channels_json = json.loads(youtube_channels_json)
        
        if isinstance(youtube_channels_json, list):
            for item in youtube_channels_json:
                if isinstance(item, dict):
                    # Extract channel_id from various possible field names
                    channel_id = (
                        item.get('channel_id') or 
                        item.get('channelId') or
                        item.get('id')
                    )
                    
                    channel_title = item.get('channel_title') or item.get('title', '')
                    
                    if not channel_id:
                        continue
                    
                    # Check if channel is flagged in database
                    is_flagged, flag_reason = self.is_channel_flagged(channel_id)
                    if is_flagged:
                        logger.debug(f"  Skipping flagged channel: {channel_title} - {flag_reason}")
                        continue

                    # Channels already linked in bronze.bronze_events_youtube (catalog refresh)
                    if trust_catalog:
                        channel_url = item.get('channel_url') or f"https://www.youtube.com/channel/{channel_id}"
                        channels.append({
                            'channel_id': channel_id,
                            'channel_title': channel_title or channel_id,
                            'channel_type': item.get('channel_type', 'municipal'),
                            'channel_url': channel_url,
                            'discovery_method': item.get('discovery_method'),
                            'confidence_score': item.get('confidence') or item.get('confidence_score'),
                        })
                        logger.debug(
                            "  ✓ Including catalog channel: {} ({})",
                            channel_title or channel_id,
                            channel_id,
                        )
                        continue
                    
                    # FIRST: Check exclusion patterns (hard block)
                    if channel_title:
                        title_lower = channel_title.lower()
                        if any(pattern in title_lower for pattern in EXCLUDE_PATTERNS):
                            logger.debug(f"  ❌ Excluding non-government channel: {channel_title}")
                            continue
                    
                    # SECOND: Check if channel is verified in LocalView (auto-include)
                    in_localview = item.get('in_localview', False)
                    if in_localview:
                        logger.debug(f"  ✓ Including LocalView channel: {channel_title}")
                        # This is a verified government channel, include it
                    else:
                        # NOT in LocalView - need additional validation
                        
                        # Check policy_score (only include if > 0)
                        policy_score = item.get('policy_score', 0)
                        
                        # Check if title contains government keywords
                        has_govt_keyword = False
                        if channel_title:
                            title_lower = channel_title.lower()
                            has_govt_keyword = any(keyword in title_lower for keyword in GOVERNMENT_KEYWORDS)
                        
                        # ONLY include if policy_score > 0 OR has government keywords
                        if policy_score == 0 and not has_govt_keyword:
                            logger.debug(f"  ⏭️  Skipping non-government channel: {channel_title} (policy_score={policy_score}, no govt keywords)")
                            continue
                        
                        if policy_score > 0 or has_govt_keyword:
                            logger.debug(f"  ✓ Including government channel: {channel_title} (policy_score={policy_score})")
                        else:
                            # Neither policy_score nor keywords indicate government
                            logger.debug(f"  ⏭️  Skipping unverified channel: {channel_title}")
                            continue
                    
                    # Determine channel type
                    channel_type = 'unknown'
                    if channel_title:
                        title_lower = channel_title.lower()
                        if any(word in title_lower for word in ['city', 'town', 'village', 'municipal']):
                            channel_type = 'municipal'
                        elif any(word in title_lower for word in ['county']):
                            channel_type = 'county'
                        elif any(word in title_lower for word in ['state', 'commonwealth']):
                            channel_type = 'state'
                        elif any(word in title_lower for word in ['school', 'district', 'education']):
                            channel_type = 'school'
                    
                    # Add channel to list
                    channel_url = item.get('channel_url') or f"https://www.youtube.com/channel/{channel_id}"
                    channels.append({
                        'channel_id': channel_id,
                        'channel_title': channel_title,
                        'channel_type': channel_type,
                        'channel_url': channel_url,
                        'discovery_method': item.get('discovery_method'),
                        'confidence_score': item.get('confidence') or item.get('confidence_score'),
                    })
        
        return channels
    
    def video_to_event_record(
        self,
        video: Dict,
        jurisdiction_id: str,
        jurisdiction_name: str,
        jurisdiction_type: str,
        state_code: str,
        state: str,
        channel_id: str,
        channel_type: str = 'unknown'
    ) -> Dict[str, Any]:
        """Convert YouTube video metadata to bronze_events_youtube record format."""
        
        # Parse published date; meeting date may come from title (e.g. 9/23/2024 council meeting)
        event_date = None
        event_time = None
        published_at = None
        if video.get('published_at'):
            try:
                dt = pd.to_datetime(video['published_at'])
                event_time = dt.time()
                published_at = dt  # Keep full timestamp for bronze layer
            except Exception:
                pass
        title = video.get('title', 'Meeting Video')[:500]
        resolved = resolve_meeting_event_date(
            title,
            published_at=published_at,
        )
        if resolved:
            try:
                event_date = pd.to_datetime(resolved).date()
            except Exception:
                pass
        
        # Extract city from jurisdiction name if it's a city
        city = None
        if jurisdiction_type == 'city':
            # Remove state suffix like ", AL" from "Birmingham, AL"
            city = jurisdiction_name.split(',')[0].strip()
        
        # Use description as-is, don't append view/duration info
        description = video.get('description', '')
        
        # Construct channel URL
        channel_url = f"https://www.youtube.com/channel/{channel_id}" if channel_id else None
        
        # Generate event_id from video_id hash
        video_id = video.get('video_id')
        event_id = hash(f"youtube_{video_id}") % 2147483647 if video_id else None
        
        return {
            'event_id': event_id,
            'video_id': video_id,
            'jurisdiction_id': jurisdiction_id,
            'channel_id': channel_id,
            'channel_url': channel_url,
            'title': title,
            'description': description,
            'event_date': event_date,
            'event_time': event_time,
            'published_at': published_at,
            'jurisdiction_name': jurisdiction_name,
            'jurisdiction_type': jurisdiction_type,
            'state_code': state_code,
            'state': state,
            'city': city,
            'location': None,
            'location_description': video.get('location_description'),
            'meeting_type': video.get('meeting_type', 'YouTube Video'),
            'video_url': video.get('video_url'),
            'view_count': video.get('view_count'),
            'duration_minutes': video.get('duration_minutes'),
            'like_count': video.get('like_count'),
            'language': video.get('language', 'en'),
            'channel_type': channel_type,
            'datasource': 'youtube',
            'datasource_id': video_id,  # YouTube video ID
            'last_updated': datetime.now()
        }
    
    @staticmethod
    def _youtube_block_signal(message: str) -> bool:
        """True when YouTube/yt-dlp errors indicate IP or bot blocking."""
        u = (message or "").upper()
        return any(
            token in u
            for token in (
                "IP BLOCKED",
                "IPBLOCKED",
                "REQUEST BLOCKED",
                "REQUESTBLOCKED",
                "NOT A BOT",
                "SIGN IN TO CONFIRM",
                "429",
                "TOO MANY REQUESTS",
                "RESOURCE_EXHAUSTED",
            )
        )

    @staticmethod
    def _raise_rate_limited(video_id: str, reason: str) -> None:
        raise Exception(f"RATE_LIMITED: {reason} (video_id={video_id})")

    @staticmethod
    def _is_unavailable_format_error(message: str) -> bool:
        u = (message or "").upper()
        return (
            "REQUESTED FORMAT IS NOT AVAILABLE" in u
            or "FORMAT IS NOT AVAILABLE" in u
            or "NO VIDEO FORMATS FOUND" in u
        )

    @staticmethod
    def _ytdlp_quiet_logger():
        class _QuietLogger:
            def debug(self, msg):
                return None

            def warning(self, msg):
                return None

            def error(self, msg):
                return None

        return _QuietLogger()

    def _ytdlp_transcript_opts(
        self,
        *,
        use_cookies: bool,
        relaxed: bool = False,
    ) -> Dict[str, Any]:
        """yt-dlp options for subtitle-only extraction (no video download)."""
        from scripts.datasources.youtube.download_audio_to_drive import _yt_dlp_youtube_ejs_opts

        opts: Dict[str, Any] = {
            "skip_download": True,
            # Preferred mode requests subtitle metadata directly. Relaxed mode falls
            # back to generic metadata extraction when some videos reject format picks.
            "writesubtitles": not relaxed,
            "writeautomaticsub": not relaxed,
            "subtitleslangs": ["en"],
            "subtitlesformat": "vtt/best",
            "ignore_no_formats_error": True,
            "quiet": True,
            "no_warnings": True,
            "logger": self._ytdlp_quiet_logger(),
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "referer": "https://www.youtube.com/",
        }
        if relaxed:
            # Avoid strict subtitle/format selectors for hard-to-resolve videos.
            opts["format"] = "best/bestaudio/bestvideo"
            opts.pop("subtitlesformat", None)
        ejs = _yt_dlp_youtube_ejs_opts()
        if ejs:
            opts.update(ejs)
        if use_cookies and self.cookies_file:
            cookie_path = Path(self.cookies_file)
            if cookie_path.is_file():
                opts["cookiefile"] = str(cookie_path.resolve())
        if self.proxy_url:
            opts["proxy"] = self.proxy_url
        return opts

    def fetch_transcript_ytdlp(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Fetch transcript using yt-dlp as fallback."""
        try:
            url = f'https://www.youtube.com/watch?v={video_id}'
            info = None
            last_err: Optional[Exception] = None
            # Android client works best without cookies; cookiefile often causes
            # "Requested format is not available" unless EJS + Node/Deno are installed.
            attempts = (False, True) if self.cookies_file else (False,)
            for use_cookies in attempts:
                try:
                    with yt_dlp.YoutubeDL(
                        self._ytdlp_transcript_opts(use_cookies=use_cookies)
                    ) as ydl:
                        info = ydl.extract_info(url, download=False)
                    break
                except Exception as exc:
                    last_err = exc
                    err = str(exc)
                    # Some videos reject the default subtitle extraction path and raise
                    # "Requested format is not available". Retry with relaxed opts.
                    if self._is_unavailable_format_error(err):
                        try:
                            with yt_dlp.YoutubeDL(
                                self._ytdlp_transcript_opts(
                                    use_cookies=use_cookies,
                                    relaxed=True,
                                )
                            ) as ydl:
                                info = ydl.extract_info(url, download=False)
                            break
                        except Exception as exc_relaxed:
                            last_err = exc_relaxed
                            err = str(exc_relaxed)
                    if (
                        use_cookies
                        and self.cookies_file
                        and ("Requested format is not available" in err or "not a bot" in err.lower())
                    ):
                        logger.debug(
                            f"    yt-dlp retry without cookies for {video_id} "
                            f"(cookies often need EJS: https://github.com/yt-dlp/yt-dlp/wiki/EJS)"
                        )
                        continue
                    raise
            if info is None:
                if last_err:
                    raise last_err
                return None

            # Try manual subtitles first, then auto-generated
            subtitles = info.get('subtitles', {})
            auto_captions = info.get('automatic_captions', {})

            transcript_data = None
            is_auto = False
            language = 'en'

            if 'en' in subtitles:
                transcript_data = subtitles['en']
                is_auto = False
            elif 'en' in auto_captions:
                transcript_data = auto_captions['en']
                is_auto = True
            else:
                if subtitles:
                    lang = list(subtitles.keys())[0]
                    transcript_data = subtitles[lang]
                    language = lang
                    is_auto = False
                elif auto_captions:
                    lang = list(auto_captions.keys())[0]
                    transcript_data = auto_captions[lang]
                    language = lang
                    is_auto = True

            if not transcript_data:
                return None

            subtitle_url = None
            for fmt in transcript_data:
                if fmt.get('ext') in ['vtt', 'srv3', 'json3']:
                    subtitle_url = fmt.get('url')
                    break

            if not subtitle_url and transcript_data:
                subtitle_url = transcript_data[0].get('url')

            if not subtitle_url:
                return None

            import re

            import requests

            response = requests.get(subtitle_url, timeout=10)
            response.raise_for_status()

            raw_content = response.text
            segments = []
            lines = raw_content.split('\n')
            i = 0

            while i < len(lines):
                line = lines[i].strip()

                if '-->' in line:
                    timestamp_match = re.match(
                        r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})',
                        line,
                    )

                    if timestamp_match:
                        start_str = timestamp_match.group(1)
                        end_str = timestamp_match.group(2)

                        def timestamp_to_seconds(ts: str) -> float:
                            h, m, s = ts.split(':')
                            return int(h) * 3600 + int(m) * 60 + float(s)

                        start = timestamp_to_seconds(start_str)
                        end = timestamp_to_seconds(end_str)
                        duration = end - start

                        i += 1
                        text_lines = []
                        while i < len(lines):
                            text_line = lines[i].strip()
                            if (
                                not text_line
                                or '-->' in text_line
                                or text_line.startswith('WEBVTT')
                            ):
                                break
                            if not text_line.isdigit():
                                clean_text = re.sub(r'<[^>]+>', '', text_line)
                                if clean_text:
                                    text_lines.append(clean_text)
                            i += 1

                        if text_lines:
                            segments.append({
                                'text': ' '.join(text_lines),
                                'start': start,
                                'duration': duration,
                            })

                i += 1

            raw_text = ' '.join([seg['text'] for seg in segments])

            if not raw_text:
                return None

            return {
                'video_id': video_id,
                'raw_text': raw_text,
                'segments': segments,
                'language': language,
                'is_auto_generated': is_auto,
                'transcript_source': 'yt-dlp',
            }

        except Exception as e:
            error_msg = str(e)
            if self._youtube_block_signal(error_msg):
                logger.warning(f"    ⚠️ yt-dlp blocked/rate-limited for {video_id}")
                self._raise_rate_limited(video_id, error_msg[:200])
            logger.debug(f"    yt-dlp transcript error for {video_id}: {error_msg[:200]}")
            return None
    
    def fetch_transcript(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Fetch transcript/captions for a YouTube video."""
        if not video_id:
            return None
        
        # Try youtube_transcript_api first (faster and cleaner)
        try:
            from scripts.datasources.youtube.transcript_api_client import (
                build_youtube_transcript_api,
            )

            api = build_youtube_transcript_api(self.proxy_url)
            
            # Try to get English transcript first
            try:
                fetched_transcript = api.fetch(video_id, languages=['en'])
                language = 'en'
                is_auto = fetched_transcript.is_generated
            except NoTranscriptFound:
                # Try any available language
                try:
                    transcript_list = api.list(video_id)
                    # Get first available transcript
                    available = list(transcript_list)
                    if not available:
                        raise NoTranscriptFound(video_id)
                    first_transcript = available[0]
                    fetched_transcript = first_transcript.fetch()
                    language = first_transcript.language_code
                    is_auto = first_transcript.is_generated
                except:
                    raise NoTranscriptFound(video_id)
            
            # Extract both raw text and structured segments with timing
            raw_text = ' '.join([snippet.text for snippet in fetched_transcript.snippets])
            
            # Preserve timing data in structured format
            segments = [
                {
                    'text': snippet.text,
                    'start': snippet.start,
                    'duration': snippet.duration
                }
                for snippet in fetched_transcript.snippets
            ]
            
            return {
                'video_id': video_id,
                'raw_text': raw_text,
                'segments': segments,
                'language': language,
                'is_auto_generated': is_auto,
                'transcript_source': 'youtube_api'
            }
            
        except TranscriptsDisabled:
            if self.use_ytdlp_fallback:
                logger.debug(
                    f"    Caption API reports disabled for {video_id} — trying yt-dlp"
                )
                result = self.fetch_transcript_ytdlp(video_id)
                if result:
                    return result
            logger.warning(f"    Captions disabled by uploader for {video_id}")
            return None
        except VideoUnavailable:
            logger.warning(f"    Video unavailable (private/deleted) for {video_id}")
            return None
        except IpBlocked:
            if self.use_ytdlp_fallback:
                logger.warning(
                    f"    ⚠️ IP blocked on transcript API for {video_id} — trying yt-dlp fallback"
                )
                ytdlp_result = self.fetch_transcript_ytdlp(video_id)
                if ytdlp_result is None:
                    self._raise_rate_limited(
                        video_id,
                        "IP blocked on caption API and yt-dlp fallback returned no transcript",
                    )
                return ytdlp_result
            self._raise_rate_limited(video_id, "IP blocked by YouTube (caption API)")
        except (NoTranscriptFound, Exception) as e:
            if type(e).__name__ in ("RequestBlocked", "IpBlocked"):
                if self.use_ytdlp_fallback:
                    logger.warning(
                        f"    ⚠️ Request blocked for {video_id} — trying yt-dlp fallback"
                    )
                    try:
                        ytdlp_result = self.fetch_transcript_ytdlp(video_id)
                    except Exception as ytdlp_exc:
                        if self._youtube_block_signal(str(ytdlp_exc)):
                            self._raise_rate_limited(video_id, str(ytdlp_exc)[:200])
                        raise
                    if ytdlp_result is None:
                        self._raise_rate_limited(
                            video_id,
                            "Request blocked on caption API and yt-dlp fallback failed",
                        )
                    return ytdlp_result
                self._raise_rate_limited(video_id, str(e)[:200])
            # Fall back to yt-dlp ONLY if enabled and not rate limited
            error_msg = str(e)
            # Check for rate limiting
            if '429' in error_msg or 'Too Many Requests' in error_msg:
                logger.warning(f"    ⚠️ Rate limited (YouTube API) for {video_id}")
                # Signal rate limit to caller
                raise Exception(f"RATE_LIMITED: {error_msg}")
            elif self.use_ytdlp_fallback:
                logger.debug(f"    youtube_transcript_api failed for {video_id}, trying yt-dlp fallback...")
                result = self.fetch_transcript_ytdlp(video_id)
                if result is None:
                    logger.warning(
                        f"    No transcript for {video_id} after API + yt-dlp "
                        f"({type(e).__name__}: {error_msg[:120]})"
                    )
                return result
            else:
                logger.warning(
                    f"    No transcript for {video_id} ({type(e).__name__}: {error_msg[:120]})"
                )
                return None
    
    def insert_events(self, events: List[Dict[str, Any]], batch_size: int = 500) -> int:
        """Insert events into bronze.bronze_events_youtube table."""
        if not events:
            return 0
        
        insert_query = """
            INSERT INTO bronze.bronze_events_youtube AS y (
                event_id, video_id, jurisdiction_id, channel_id, channel_url, 
                title, description, event_date, event_time, published_at,
                jurisdiction_name, jurisdiction_type, state_code, state, city,
                location, location_description, meeting_type,
                video_url, view_count, duration_minutes, like_count,
                language, channel_type, datasource, datasource_id, last_updated
            ) VALUES (
                %(event_id)s, %(video_id)s, %(jurisdiction_id)s, %(channel_id)s, %(channel_url)s,
                %(title)s, %(description)s, %(event_date)s, %(event_time)s, %(published_at)s,
                %(jurisdiction_name)s, %(jurisdiction_type)s, %(state_code)s, %(state)s, %(city)s,
                %(location)s, %(location_description)s, %(meeting_type)s,
                %(video_url)s, %(view_count)s, %(duration_minutes)s, %(like_count)s,
                %(language)s, %(channel_type)s, %(datasource)s, %(datasource_id)s, %(last_updated)s
            )
            ON CONFLICT (video_id) DO UPDATE SET
                jurisdiction_id = EXCLUDED.jurisdiction_id,
                jurisdiction_name = EXCLUDED.jurisdiction_name,
                jurisdiction_type = EXCLUDED.jurisdiction_type,
                state_code = EXCLUDED.state_code,
                state = EXCLUDED.state,
                city = EXCLUDED.city,
                channel_id = EXCLUDED.channel_id,
                channel_url = EXCLUDED.channel_url,
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                event_date = COALESCE(EXCLUDED.event_date, y.event_date),
                event_time = COALESCE(EXCLUDED.event_time, y.event_time),
                published_at = COALESCE(EXCLUDED.published_at, y.published_at),
                view_count = EXCLUDED.view_count,
                like_count = EXCLUDED.like_count,
                last_updated = EXCLUDED.last_updated
            RETURNING y.id, y.event_id, y.video_id
        """
        
        cursor = self.conn.cursor()
        inserted = 0
        event_ids = {}  # Map video_id to event_id
        
        try:
            # Insert events and collect their IDs
            for event in events:
                cursor.execute(insert_query, event)
                result = cursor.fetchone()
                if result:
                    db_id, event_id, video_id = result
                    if video_id:
                        event_ids[video_id] = event_id
                    inserted += 1
            
            self.conn.commit()
            
            # Fetch and insert transcripts if enabled
            if self.fetch_transcripts and event_ids:
                jurisdiction_id = (events[0].get("jurisdiction_id") or "").strip() if events else ""
                logger.info(f"  📝 Fetching transcripts for {len(event_ids)} videos (delay: {self.transcript_delay}s each)...")
                transcripts_inserted = self.insert_transcripts(
                    event_ids, jurisdiction_id=jurisdiction_id or None
                )
                logger.info(f"  ✓ Inserted {transcripts_inserted} transcripts")
            elif not self.fetch_transcripts and event_ids:
                logger.info(f"  ⏭️  Skipped fetching transcripts for {len(event_ids)} videos (use --skip-transcripts=false to enable)")
            
            return inserted
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error inserting events: {e}")
            raise
        finally:
            cursor.close()
    
    def insert_transcripts(
        self,
        event_ids: Dict[str, int],
        *,
        jurisdiction_id: Optional[str] = None,
    ) -> int:
        """Fetch and insert transcripts for events with exponential backoff on rate limits."""
        import time

        if jurisdiction_id and len(event_ids) > 1:
            from scripts.datasources.youtube.dedupe_meeting_videos import (
                dedupe_video_id_map,
                fetch_youtube_rows_for_dedupe,
                log_duplicate_skips,
            )

            meta = fetch_youtube_rows_for_dedupe(
                self.database_url,
                jurisdiction_id,
            )
            event_ids, dedupe = dedupe_video_id_map(event_ids, meta)
            title_by_id = {r["video_id"]: str(r.get("title") or "") for r in meta}
            log_duplicate_skips(dedupe, title_by_id=title_by_id)
            if not event_ids:
                return 0

        cursor = self.conn.cursor()
        inserted = 0
        rate_limit_count = 0
        consecutive_rate_limits = 0
        max_backoff = 60  # Maximum 60 seconds backoff
        
        insert_query = """
            INSERT INTO bronze.bronze_events_text_ai (
                event_id, video_id, raw_text, segments, language, 
                is_auto_generated, transcript_source, has_transcript, transcript_quality
            ) VALUES (
                %(event_id)s, %(video_id)s, %(raw_text)s, %(segments)s::jsonb, %(language)s,
                %(is_auto_generated)s, %(transcript_source)s, %(has_transcript)s, %(transcript_quality)s
            )
            ON CONFLICT (video_id) DO UPDATE SET
                raw_text = EXCLUDED.raw_text,
                segments = EXCLUDED.segments,
                language = EXCLUDED.language,
                is_auto_generated = EXCLUDED.is_auto_generated,
                transcript_source = EXCLUDED.transcript_source,
                has_transcript = EXCLUDED.has_transcript,
                transcript_quality = EXCLUDED.transcript_quality,
                last_updated = CURRENT_TIMESTAMP
        """
        
        try:
            for i, (video_id, event_id) in enumerate(event_ids.items(), 1):
                # Progressive delay based on rate limit history
                base_delay = self.transcript_delay
                if consecutive_rate_limits > 0:
                    # Exponential backoff: 2s, 4s, 8s, 16s, 32s, 60s (max)
                    backoff_delay = min(base_delay * (2 ** consecutive_rate_limits), max_backoff)
                    logger.warning(f"  ⏱️  Backing off {backoff_delay:.1f}s due to {consecutive_rate_limits} consecutive rate limits...")
                    time.sleep(backoff_delay)
                elif i > 1:
                    time.sleep(base_delay)
                
                # Fetch transcript with rate limit handling
                transcript_data = None
                try:
                    transcript_data = self.fetch_transcript(video_id)
                    consecutive_rate_limits = 0  # Reset on success
                except Exception as e:
                    if 'RATE_LIMITED' in str(e):
                        rate_limit_count += 1
                        consecutive_rate_limits += 1
                        logger.warning(f"  ⚠️  Rate limited! ({rate_limit_count} total, {consecutive_rate_limits} consecutive)")
                        if consecutive_rate_limits >= 5:
                            logger.error(f"  ❌ Too many consecutive rate limits ({consecutive_rate_limits}), stopping transcript fetching")
                            break
                        continue
                    else:
                        # Other error, skip this video
                        logger.debug(f"  Error fetching transcript for {video_id}: {e}")
                        continue
                
                if transcript_data:
                    transcript_data['event_id'] = event_id
                    
                    # Convert segments list to JSON string for PostgreSQL
                    if 'segments' in transcript_data and transcript_data['segments']:
                        import json
                        transcript_data['segments'] = json.dumps(transcript_data['segments'])
                    else:
                        transcript_data['segments'] = None
                    
                    # Add bronze schema fields
                    transcript_data['has_transcript'] = bool(transcript_data.get('raw_text'))
                    # Quality based on whether auto-generated or manual
                    if transcript_data.get('is_auto_generated'):
                        transcript_data['transcript_quality'] = 'medium'
                    else:
                        transcript_data['transcript_quality'] = 'high'
                    
                    cursor.execute(insert_query, transcript_data)
                    inserted += 1
                    
                    # Commit every 10 transcripts to avoid long transactions
                    if inserted % 10 == 0:
                        self.conn.commit()
            
            # Final commit
            self.conn.commit()
            
            # Report rate limiting if it occurred
            if rate_limit_count > 0:
                logger.warning(f"  ⚠️  Total rate limits encountered: {rate_limit_count}")
                logger.warning(f"  💡 Consider increasing --transcript-delay (current: {self.transcript_delay}s)")
            
            return inserted
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error inserting transcripts: {e}")
            return inserted
        finally:
            cursor.close()
    
    def get_most_recent_video_date(self, jurisdiction_id: str, channel_id: str) -> Optional[datetime]:
        """Get the most recent video insertion timestamp for a specific channel within a jurisdiction.
        
        Uses last_updated timestamp instead of event_date since event_date may be NULL
        for videos without proper date parsing.
        """
        cursor = self.conn.cursor()
        
        try:
            # Get the most recent last_updated timestamp for this specific channel
            cursor.execute("""
                SELECT MAX(last_updated) 
                FROM bronze.bronze_events_youtube 
                WHERE jurisdiction_id = %s
                AND channel_id = %s
                AND datasource = 'youtube'
                AND video_url IS NOT NULL
            """, (jurisdiction_id, channel_id))
            
            result = cursor.fetchone()
            if result and result[0]:
                # last_updated is already a datetime, just make it timezone-aware
                if result[0].tzinfo is None:
                    # If naive, assume UTC
                    return result[0].replace(tzinfo=timezone.utc)
                else:
                    return result[0]
            return None
            
        finally:
            cursor.close()
    
    def process_jurisdiction(self, jurisdiction: Dict) -> int:
        """Process all YouTube channels for a single jurisdiction."""
        jurisdiction_id = jurisdiction['jurisdiction_id']
        jurisdiction_name = jurisdiction['jurisdiction_name']
        state_code = jurisdiction['state_code']
        state = jurisdiction['state']
        jurisdiction_type = jurisdiction['jurisdiction_type']
        
        logger.info(f"Processing: {jurisdiction_name}, {state_code}")
        
        # Extract channel IDs from JSONB (trust bronze catalog — skip policy_score gate on refresh)
        channels = self.extract_channel_ids(
            jurisdiction['youtube_channels'],
            trust_catalog=True,
        )
        
        if not channels:
            logger.warning(f"  No valid channels found in youtube_channels field")
            return 0
        
        logger.info(f"  Found {len(channels)} YouTube channel(s)")
        
        # Collect all events from all channels
        all_events = []
        
        for channel in channels:
            channel_id = channel['channel_id']
            channel_title = channel.get('channel_title', 'Unknown Channel')
            channel_url = channel.get('channel_url', f"https://www.youtube.com/channel/{channel_id}")
            channel_type = channel.get('channel_type', 'unknown')
            discovery_method = str(channel.get('discovery_method') or 'jurisdictions_details').strip() or 'jurisdictions_details'
            confidence_score_raw = channel.get('confidence_score')
            confidence_score = None
            if confidence_score_raw not in (None, ""):
                try:
                    confidence_score = float(confidence_score_raw)
                except (TypeError, ValueError):
                    confidence_score = None
            
            # Track this channel in bronze.bronze_events_channels
            self.upsert_channel(
                channel_id=channel_id,
                channel_url=channel_url,
                channel_title=channel_title,
                channel_type=channel_type,
                jurisdiction_id=jurisdiction_id,
                jurisdiction_name=jurisdiction_name,
                state_code=state_code,
                discovery_method=discovery_method,
                confidence_score=confidence_score,
            )
            
            logger.info(f"  Fetching videos from: {channel_title} ({channel_id})")
            
            # Get most recent video insertion timestamp for THIS SPECIFIC CHANNEL
            most_recent_date = None
            if not self.force_full_fetch:
                most_recent_date = self.get_most_recent_video_date(jurisdiction_id, channel_id)
                if most_recent_date:
                    logger.info(f"    Last video added to database: {most_recent_date.strftime('%Y-%m-%d %H:%M:%S')}")
            
            try:
                # Determine published_after date (use most recent date for incremental fetching)
                published_after = None
                if self.days_lookback:
                    published_after = datetime.now(timezone.utc) - timedelta(days=self.days_lookback)
                    logger.info(f"    Filtering videos from last {self.days_lookback} days")
                elif most_recent_date:
                    # Incremental: only fetch videos newer than what we have for this channel
                    # Note: This compares insertion timestamp with video publish date
                    # Videos published before last insertion are likely already in DB
                    published_after = most_recent_date
                    logger.info(f"    Incremental: fetching videos published after {most_recent_date.strftime('%Y-%m-%d')}")
                    logger.info(f"    Incremental: fetching videos newer than {most_recent_date.date()}")
                
                # Get videos from channel
                videos = self.scraper.get_channel_videos(
                    channel_id=channel_id,
                    max_results=self.max_videos,
                    published_after=published_after
                )
                
                if not videos:
                    logger.info(f"    No new videos found (already up to date)")
                    continue

                if self.min_duration_seconds > 0:
                    min_minutes = self.min_duration_seconds / 60.0
                    eligible_videos: List[Dict[str, Any]] = []
                    skipped_short = 0
                    unknown_duration = 0
                    for video in videos:
                        raw_duration = video.get('duration_minutes')
                        if raw_duration in (None, ""):
                            unknown_duration += 1
                            eligible_videos.append(video)
                            continue
                        try:
                            duration_minutes = float(raw_duration)
                        except (TypeError, ValueError):
                            unknown_duration += 1
                            eligible_videos.append(video)
                            continue
                        if duration_minutes <= 0:
                            unknown_duration += 1
                            eligible_videos.append(video)
                            continue
                        if duration_minutes < min_minutes:
                            skipped_short += 1
                            continue
                        eligible_videos.append(video)

                    if skipped_short > 0:
                        logger.info(
                            "    Filtered out {} short video(s) under {}s",
                            skipped_short,
                            self.min_duration_seconds,
                        )
                    if unknown_duration > 0:
                        logger.debug(
                            "    {} video(s) had unknown duration; kept for safety",
                            unknown_duration,
                        )
                    videos = eligible_videos

                if not videos:
                    logger.info(
                        "    No eligible videos after min-duration filter (%ss)",
                        self.min_duration_seconds,
                    )
                    continue
                
                logger.info(f"    Retrieved {len(videos)} new videos")
                
                # Convert videos to event records
                for video in videos:
                    event = self.video_to_event_record(
                        video=video,
                        jurisdiction_id=jurisdiction_id,
                        jurisdiction_name=jurisdiction_name,
                        jurisdiction_type=jurisdiction_type,
                        state_code=state_code,
                        state=state,
                        channel_id=channel_id,
                        channel_type=channel.get('channel_type', 'unknown')
                    )
                    all_events.append(event)
                
            except Exception as e:
                logger.error(f"    Error fetching videos from channel {channel_id}: {e}")
                continue
        
        # Insert all events for this jurisdiction
        if all_events:
            inserted = self.insert_events(all_events)
            if inserted > 0:
                logger.success(f"  ✓ Inserted {inserted:,} new events")
            else:
                logger.info(f"  No new events to insert (all videos already exist)")
            return inserted
        else:
            logger.info(f"  No new videos found for this jurisdiction")
        
        return 0
    
    def run(
        self,
        states_filter: Optional[List[str]] = None,
        jurisdiction_id: Optional[str] = None,
    ):
        """Run the full loading process."""
        logger.info("=" * 80)
        logger.info("YOUTUBE EVENTS LOADER")
        logger.info("=" * 80)
        logger.info(f"Database: {self.database_url.split('@')[1] if '@' in self.database_url else 'localhost'}")
        logger.info(f"Max videos per channel: {self.max_videos}")
        logger.info(f"Min video duration: {self.min_duration_seconds}s")
        
        if self.fetch_transcripts:
            logger.info(f"Fetch transcripts: YES (delay: {self.transcript_delay}s between fetches)")
            logger.warning("⚠️  Transcript fetching may hit rate limits. Use --skip-transcripts to load events only.")
        else:
            logger.info("Fetch transcripts: NO (skipped - faster load, no rate limits)")
            logger.info("💡 Run backfill_transcripts.py later to add transcripts")
        
        logger.info(f"Incremental mode: {not self.force_full_fetch}")
        if self.days_lookback:
            logger.info(f"Only videos from last {self.days_lookback} days")
        if states_filter:
            logger.info(f"States filter: {', '.join(states_filter)}")
        if jurisdiction_id:
            logger.info(f"Jurisdiction filter: {jurisdiction_id}")
        logger.info("")
        
        start_time = datetime.now()
        
        # Get jurisdictions with YouTube channels
        jurisdictions = self.get_jurisdictions_with_youtube(
            states_filter, jurisdiction_id=jurisdiction_id
        )
        
        if not jurisdictions:
            logger.warning("No jurisdictions found with YouTube channels")
            return
        
        # Process each jurisdiction
        total_inserted = 0
        for i, jurisdiction in enumerate(jurisdictions, 1):
            logger.info(f"\n[{i}/{len(jurisdictions)}] Processing jurisdiction...")
            inserted = self.process_jurisdiction(jurisdiction)
            total_inserted += inserted
        
        # Get final stats
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as total_events,
                COUNT(DISTINCT jurisdiction_id) as jurisdictions_with_events,
                COUNT(DISTINCT state_code) as states,
                MIN(event_date) as earliest_date,
                MAX(event_date) as latest_date
            FROM bronze.bronze_events_youtube
        """)
        stats = cursor.fetchone()
        
        # Get transcript stats
        cursor.execute("""
            SELECT COUNT(*) FROM bronze.bronze_events_text_ai
        """)
        transcript_count = cursor.fetchone()[0]
        cursor.close()
        
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info("")
        if total_inserted > 0:
            logger.success("=" * 80)
            logger.success("✓ LOADING COMPLETE")
            logger.success("=" * 80)
            logger.success(f"New events inserted this run: {total_inserted:,}")
            logger.success(f"Total YouTube events in database: {stats[0]:,}")
            logger.success(f"Total transcripts in database: {transcript_count:,}")
            logger.success(f"Jurisdictions with events: {stats[1]:,}")
            logger.success(f"States covered: {stats[2]}")
            logger.success(f"Date range: {stats[3]} to {stats[4]}")
            logger.success(f"Duration: {duration:.1f} seconds")
        else:
            logger.warning("=" * 80)
            logger.warning("NO NEW EVENT ROWS WRITTEN (NOOP RUN)")
            logger.warning("=" * 80)
            logger.info(f"New events inserted this run: {total_inserted:,}")
            logger.info(f"Total YouTube events in database: {stats[0]:,}")
            logger.info(f"Total transcripts in database: {transcript_count:,}")
            logger.info(f"Jurisdictions with events: {stats[1]:,}")
            logger.info(f"States covered: {stats[2]}")
            logger.info(f"Date range: {stats[3]} to {stats[4]}")
            logger.info(f"Duration: {duration:.1f} seconds")
        logger.info("")
        
        if total_inserted == 0:
            logger.info("No new videos found - all jurisdictions are up to date!")
        else:
            logger.info("Incremental update successful - only new videos were added.")
        
        # Provide guidance based on transcript mode
        logger.info("")
        if not self.fetch_transcripts:
            logger.info("⚡ Next step: Add transcripts (without rate limits)")
            logger.info("")
            logger.info("  Run backfill script to fetch transcripts for existing events:")
            logger.info(f"  python scripts/datasources/youtube/backfill_transcripts.py --states {','.join(states_filter) if states_filter else 'AL,GA,IN,MA,MT,WA,WI'} --limit 100")
            logger.info("")
            logger.info("  💡 Backfill uses slower delays (2s) to avoid rate limits")
        elif transcript_count < stats[0]:
            missing = stats[0] - transcript_count
            logger.warning(f"⚠️  Missing transcripts: {missing:,} events don't have transcripts")
            logger.info("  Run backfill to fetch missing transcripts:")
            logger.info(f"  python scripts/datasources/youtube/backfill_transcripts.py --states {','.join(states_filter) if states_filter else 'AL,GA,IN,MA,MT,WA,WI'}")
        
        logger.info("")
        logger.info("Query examples:")
        logger.info("  SELECT jurisdiction_name, COUNT(*) FROM bronze.bronze_events_youtube GROUP BY jurisdiction_name ORDER BY COUNT(*) DESC LIMIT 10")
        logger.info("  SELECT COUNT(*) FROM bronze.bronze_events_text_ai")
        logger.info("")
        logger.info("View in app: http://localhost:5173/meetings")
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Load YouTube events from jurisdictions into event')
    
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated list of state codes to process (e.g., AL,MA,WI)'
    )

    parser.add_argument(
        '--jurisdiction-id',
        type=str,
        default='',
        help='Process only this jurisdiction (e.g. municipality_0155200 for Northport, AL)',
    )
    
    parser.add_argument(
        '--days',
        type=int,
        help='Only process videos published in the last N days'
    )
    
    parser.add_argument(
        '--max-videos',
        type=int,
        default=100,
        help='Maximum videos to fetch per channel (default: 100)'
    )

    parser.add_argument(
        '--min-duration-seconds',
        type=int,
        default=120,
        help='Skip videos shorter than this many seconds (default: 120)'
    )
    
    parser.add_argument(
        '--skip-transcripts',
        action='store_true',
        help='Skip fetching video transcripts - MUCH FASTER, avoids rate limits (recommended for large loads)'
    )
    
    parser.add_argument(
        '--text-transcripts-only',
        action='store_true',
        help='Fetch text transcripts only, skip VTT file downloads (uses youtube_transcript_api only, faster and cleaner)'
    )
    
    parser.add_argument(
        '--no-ytdlp-fallback',
        action='store_true',
        help='Disable yt-dlp VTT fallback for transcripts (reduces API calls to YouTube, use if getting IP blocked)'
    )
    
    parser.add_argument(
        '--transcript-delay',
        type=float,
        default=2.0,
        help='Delay between transcript fetches in seconds (default: 2.0, increase if rate limited)'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force full fetch (ignore incremental mode, refetch all videos)'
    )
    
    parser.add_argument(
        '--cookies',
        type=str,
        help='Path to cookies.txt file (Netscape format) for authenticated requests. Helps bypass IP blocks. Export from browser with extension like "Get cookies.txt LOCALLY"'
    )
    
    parser.add_argument(
        '--proxy',
        type=str,
        help='Proxy URL to use for requests (e.g., http://user:pass@proxy.com:8080). Helps bypass IP blocks.'
    )
    
    
    args = parser.parse_args()
    
    # Parse states filter
    states_filter = None
    if args.states:
        states_filter = [s.strip().upper() for s in args.states.split(',')]
    
    # Initialize loader
    loader = YouTubeEventsLoader(
        database_url=DATABASE_URL,
        youtube_api_key=YOUTUBE_API_KEY,
        max_videos_per_channel=args.max_videos,
        min_duration_seconds=args.min_duration_seconds,
        days_lookback=args.days,
        fetch_transcripts=not args.skip_transcripts,
        force_full_fetch=args.force,
        transcript_delay=args.transcript_delay,
        use_ytdlp_fallback=not (args.no_ytdlp_fallback or args.text_transcripts_only),
        cookies_file=args.cookies,
        proxy_url=args.proxy
    )
    
    jurisdiction_id = (args.jurisdiction_id or '').strip() or None

    try:
        loader.run(states_filter=states_filter, jurisdiction_id=jurisdiction_id)
        return 0
    except Exception as e:
        logger.error(f"✗ Loading failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        loader.close()


if __name__ == "__main__":
    sys.exit(main())
