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

    # Priority states: county channels from bronze_jurisdictions_counties_scraped (Neon dev)
    python scripts/datasources/youtube/load_youtube_events_to_postgres.py \\
        --channel-source counties-scraped --states AL,GA,IN,MA,WA,WI --workers 4

    # Same for municipalities with youtube_channel_url on municipalities_scraped
    python scripts/datasources/youtube/load_youtube_events_to_postgres.py \\
        --channel-source municipalities-scraped --states AL,GA,IN,MA,WA,WI --workers 4
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any, Tuple
from collections import Counter
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

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
from scripts.datasources.jurisdiction_pilot.scrape_priority_states import DEFAULT_PRIORITY_STATES

# Load environment variables
load_dotenv(_root := Path(__file__).resolve().parents[3])
load_dotenv(_root / ".env")


def resolve_loader_database_url() -> str:
    """Match discovery loaders: Neon dev first."""
    return (
        (os.getenv("NEON_DATABASE_URL_DEV") or "").strip()
        or (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip()
        or (os.getenv("NEON_DATABASE_URL") or "").strip()
        or (os.getenv("DATABASE_URL") or "").strip()
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )


DATABASE_URL = resolve_loader_database_url()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

_CHANNEL_ID_RE = re.compile(r"/channel/((?:UC)[A-Za-z0-9_-]{20,})", re.I)
_HANDLE_RE = re.compile(r"youtube\.com/@([^/?#]+)", re.I)
_UC_ID_CAPTURE = r"((?:UC)[A-Za-z0-9_-]{22})"
# ytInitialData / player response embeds (incl. subscribeEndpoint.channelIds)
_HTML_CHANNEL_ID_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("subscribeEndpoint.channelIds", re.compile(
        rf'"subscribeEndpoint"\s*:\s*\{{[^{{}}]*"channelIds"\s*:\s*\[\s*"{_UC_ID_CAPTURE}"',
        re.I,
    )),
    ("channelId", re.compile(rf'"channelId"\s*:\s*"{_UC_ID_CAPTURE}"', re.I)),
    ("externalId", re.compile(rf'"externalId"\s*:\s*"{_UC_ID_CAPTURE}"', re.I)),
    ("browseId", re.compile(rf'"browseId"\s*:\s*"{_UC_ID_CAPTURE}"', re.I)),
    ("channelMetadataRenderer", re.compile(
        rf'"channelMetadataRenderer"[^{{}}]*"externalId"\s*:\s*"{_UC_ID_CAPTURE}"',
        re.I | re.DOTALL,
    )),
    ("canonicalUrl", re.compile(
        rf"https?://www\.youtube\.com/channel/{_UC_ID_CAPTURE}",
        re.I,
    )),
    ("rssFeed", re.compile(
        rf"feeds/videos\.xml\?channel_id={_UC_ID_CAPTURE}",
        re.I,
    )),
)


def _channel_id_from_url(channel_url: str) -> Optional[str]:
    """Parse ``UC…`` from a canonical ``/channel/UC…`` URL without network I/O."""
    match = _CHANNEL_ID_RE.search(channel_url or "")
    return match.group(1) if match else None


def _configure_parallel_worker_logging() -> None:
    """Loguru + thread pool: avoid writing to stderr after yt-dlp redirects it."""
    try:
        logger.remove()
    except ValueError:
        pass
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
        level="INFO",
        enqueue=True,
    )


def _process_jurisdiction_worker(
    database_url: str,
    jurisdiction: Dict[str, Any],
    loader_kwargs: Dict[str, Any],
) -> int:
    """Thread worker: own DB connection and loader per jurisdiction."""
    _configure_parallel_worker_logging()
    loader = YouTubeEventsLoader(database_url=database_url, **loader_kwargs)
    try:
        return loader.process_jurisdiction(jurisdiction)
    finally:
        loader.close()


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
        transcript_workers: int = 1,
        max_transcripts_per_channel: Optional[int] = None,
        resolve_channels_ytdlp: Optional[bool] = None,
        persist_scraped_channel_ids: bool = True,
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
        self.transcript_workers = max(1, int(transcript_workers or 1))
        self.max_transcripts_per_channel = (
            max(0, int(max_transcripts_per_channel))
            if max_transcripts_per_channel is not None
            else None
        )
        if self.max_transcripts_per_channel == 0:
            self.max_transcripts_per_channel = None

        env_ytdlp = (os.getenv("YOUTUBE_RESOLVE_CHANNELS_YTDLP") or "").strip().lower()
        if resolve_channels_ytdlp is None:
            resolve_channels_ytdlp = env_ytdlp in ("1", "true", "yes", "on")
        self.resolve_channels_ytdlp = bool(resolve_channels_ytdlp)
        self._youtube_api_quota_exceeded = False
        self.persist_scraped_channel_ids = bool(persist_scraped_channel_ids)
        self._scraped_channel_id_columns_ready: set[str] = set()

        # Initialize YouTube scraper with cookies/proxy support
        self.scraper = MunicipalYouTubeScraper(
            api_key=youtube_api_key,
            cookies_file=cookies_file,
            proxy_url=proxy_url
        )
        if self.resolve_channels_ytdlp or not youtube_api_key:
            self.scraper.use_ytdlp_fallback = True
        
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
    
    @staticmethod
    def _is_youtube_api_quota_error(exc: Exception) -> bool:
        msg = str(exc)
        return (
            "quotaExceeded" in msg
            or "youtube.quota" in msg
            or "exceeded your" in msg.lower()
        )

    @staticmethod
    def _extract_channel_id_from_youtube_html(
        html: str,
        *,
        final_url: str = "",
    ) -> Optional[str]:
        """
        Parse ``UC…`` from public channel page HTML (ytInitialData), no API quota.

        Includes ``subscribeEndpoint.channelIds`` (e.g. @OfficialBaldwin → UCeV9EK3GqBVa6tgCjpIzXlA).
        """
        if not html:
            return None
        normalized = html.replace("\\/", "/")
        for url in (final_url,):
            m = _CHANNEL_ID_RE.search(url or "")
            if m:
                return m.group(1)
        counts: Counter[str] = Counter()
        for _label, pattern in _HTML_CHANNEL_ID_PATTERNS:
            for match in pattern.finditer(normalized):
                cid = match.group(1)
                if cid.startswith("UC") and len(cid) >= 24:
                    counts[cid] += 3 if _label == "subscribeEndpoint.channelIds" else 1
        if not counts:
            return None
        cid, _hits = counts.most_common(1)[0]
        return cid

    def _youtube_cookie_header(self) -> Optional[str]:
        path = (self.cookies_file or "").strip()
        if not path or not Path(path).is_file():
            return None
        try:
            from http.cookiejar import MozillaCookieJar

            jar = MozillaCookieJar(path)
            jar.load(ignore_discard=True, ignore_expires=True)
            parts = [
                f"{c.name}={c.value}"
                for c in jar
                if "youtube.com" in (c.domain or "")
            ]
            return "; ".join(parts) if parts else None
        except Exception as exc:
            logger.debug("Could not load cookies for channel page fetch: {}", exc)
            return None

    def _resolve_handle_via_page_html(self, handle: str) -> Optional[str]:
        """GET ``/@handle`` (and /videos) and scrape embedded channel id from page source."""
        if not handle:
            return None
        try:
            import httpx
        except ImportError:
            return None

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        cookie_header = self._youtube_cookie_header()
        if cookie_header:
            headers["Cookie"] = cookie_header

        for suffix in ("", "/videos", "/about"):
            page_url = f"https://www.youtube.com/@{handle}{suffix}"
            try:
                with httpx.Client(
                    follow_redirects=True,
                    timeout=30.0,
                    headers=headers,
                ) as client:
                    resp = client.get(page_url)
                    resp.raise_for_status()
                cid = self._extract_channel_id_from_youtube_html(
                    resp.text,
                    final_url=str(resp.url),
                )
                if cid:
                    logger.info(
                        "Resolved @{} → {} from page HTML ({})",
                        handle,
                        cid,
                        suffix or "/",
                    )
                    return cid
            except Exception as exc:
                logger.debug("Page fetch failed for @{}{}: {}", handle, suffix, exc)
        return None

    def _resolve_handle_without_api(self, handle: str) -> Optional[str]:
        """yt-dlp tab extract, then HTML ytInitialData (subscribeEndpoint, channelId, …)."""
        if not handle:
            return None
        for suffix in ("/videos", "/streams", ""):
            tab_url = f"https://www.youtube.com/@{handle}{suffix}"
            entries, _ = self.scraper._ytdlp_extract_tab_entries(tab_url, max_results=3)
            for entry in entries:
                cid = str(entry.get("channel_id") or "").strip()
                if cid.startswith("UC"):
                    return cid
            if entries:
                uploader_id = str((entries[0] or {}).get("uploader_id") or "").strip()
                if uploader_id.startswith("UC"):
                    return uploader_id
        return self._resolve_handle_via_page_html(handle)

    def resolve_channel_id_from_url(self, channel_url: str) -> Tuple[Optional[str], str]:
        """Resolve a UC channel id from ``/channel/UC…`` or ``@handle`` URLs."""
        url = (channel_url or "").strip()
        if not url:
            return None, url

        match = _CHANNEL_ID_RE.search(url)
        if match:
            channel_id = match.group(1)
            return channel_id, f"https://www.youtube.com/channel/{channel_id}"

        handle_match = _HANDLE_RE.search(url)
        if handle_match:
            handle = handle_match.group(1)

            channel_id = self._resolve_handle_without_api(handle)
            if channel_id:
                return channel_id, f"https://www.youtube.com/channel/{channel_id}"

            if (
                not self.resolve_channels_ytdlp
                and not self._youtube_api_quota_exceeded
                and self.scraper.youtube
            ):
                try:
                    response = (
                        self.scraper.youtube.channels()
                        .list(part="id", forHandle=handle)
                        .execute()
                    )
                    items = response.get("items") or []
                    if items:
                        channel_id = str(items[0]["id"])
                        return channel_id, f"https://www.youtube.com/channel/{channel_id}"
                except Exception as exc:
                    if self._is_youtube_api_quota_error(exc):
                        self._youtube_api_quota_exceeded = True
                        self.scraper.use_ytdlp_fallback = True
                        logger.warning(
                            "YouTube Data API quota exceeded — resolving @{} via yt-dlp only",
                            handle,
                        )
                    else:
                        logger.debug("forHandle lookup failed for @{}: {}", handle, exc)

            logger.debug("Could not resolve channel id for @{} (yt-dlp + page HTML + API)", handle)

        return None, url

    _SCRAPED_CHANNEL_TABLES = {
        "counties-scraped": "bronze.bronze_jurisdictions_counties_scraped",
        "municipalities-scraped": "bronze.bronze_jurisdictions_municipalities_scraped",
    }

    def _ensure_scraped_youtube_channel_id_column(self, table: str) -> None:
        if table in self._scraped_channel_id_columns_ready:
            return
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                f"""
                ALTER TABLE {table}
                ADD COLUMN IF NOT EXISTS youtube_channel_id TEXT
                """
            )
            self.conn.commit()
            self._scraped_channel_id_columns_ready.add(table)
        finally:
            cursor.close()

    def persist_scraped_channel_resolution(
        self,
        *,
        table: str,
        geoid: str,
        channel_id: str,
        canonical_url: str,
    ) -> bool:
        """Write resolved ``UC…`` id and canonical channel URL when id was missing."""
        if not self.persist_scraped_channel_ids:
            return False
        gid = (geoid or "").strip()
        cid = (channel_id or "").strip()
        curl = (canonical_url or "").strip()
        if not gid or not cid.startswith("UC"):
            return False
        if not curl.startswith("http"):
            curl = f"https://www.youtube.com/channel/{cid}"

        self._ensure_scraped_youtube_channel_id_column(table)
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                f"""
                UPDATE {table}
                SET youtube_channel_id = %s,
                    youtube_channel_url = %s
                WHERE geoid = %s
                  AND (
                        youtube_channel_id IS NULL
                        OR BTRIM(youtube_channel_id) = ''
                  )
                """,
                (cid, curl, gid),
            )
            updated = cursor.rowcount > 0
            self.conn.commit()
            if updated:
                logger.info(
                    "Persisted youtube_channel_id on {} geoid={} (was empty)",
                    table.split(".")[-1],
                    gid,
                )
            return updated
        except Exception as exc:
            self.conn.rollback()
            logger.warning(
                "Failed to persist youtube_channel_id on {} geoid={}: {}",
                table,
                gid,
                exc,
            )
            return False
        finally:
            cursor.close()

    def backfill_scraped_channel_ids(
        self,
        *,
        channel_source: str,
        states_filter: Optional[List[str]] = None,
        jurisdiction_id: Optional[str] = None,
    ) -> int:
        """Resolve and persist ``youtube_channel_id`` for scraped rows that only have a URL."""
        table = self._SCRAPED_CHANNEL_TABLES.get(channel_source)
        if not table:
            logger.warning("backfill_scraped_channel_ids: unsupported source {}", channel_source)
            return 0

        self._ensure_scraped_youtube_channel_id_column(table)
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        query = f"""
            SELECT geoid, jurisdiction_id, BTRIM(youtube_channel_url) AS youtube_channel_url,
                   BTRIM(youtube_channel_id) AS youtube_channel_id
            FROM {table}
            WHERE youtube_channel_url IS NOT NULL
              AND BTRIM(youtube_channel_url) <> ''
              AND (
                    youtube_channel_id IS NULL
                    OR BTRIM(youtube_channel_id) = ''
              )
        """
        params: list[Any] = []
        if states_filter:
            query += " AND upper(btrim(usps::text)) = ANY(%s)"
            params.append([s.upper() for s in states_filter])
        if jurisdiction_id:
            query += " AND jurisdiction_id = %s"
            params.append(jurisdiction_id.strip())
        query += " ORDER BY usps, geoid"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()

        updated = 0
        skipped = 0
        for row in rows:
            url = str(row["youtube_channel_url"] or "").strip()
            channel_id, canonical_url = self.resolve_channel_id_from_url(url)
            if not channel_id:
                skipped += 1
                logger.warning(
                    "backfill skip {} — could not resolve {}",
                    row.get("jurisdiction_id") or row.get("geoid"),
                    url,
                )
                continue
            if self.persist_scraped_channel_resolution(
                table=table,
                geoid=str(row["geoid"]),
                channel_id=channel_id,
                canonical_url=canonical_url,
            ):
                updated += 1

        logger.info(
            "backfill_scraped_channel_ids: {} updated, {} skipped (of {} rows)",
            updated,
            skipped,
            len(rows),
        )
        return updated

    def get_jurisdictions_from_counties_scraped(
        self,
        states_filter: Optional[List[str]] = None,
        jurisdiction_id: Optional[str] = None,
    ) -> List[Dict]:
        """County jurisdictions with ``youtube_channel_url`` on ``bronze_jurisdictions_counties_scraped``."""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT
                s.geoid,
                s.usps AS state_code,
                COALESCE(j.state, s.usps) AS state,
                s.jurisdiction_id,
                COALESCE(j.name, s.jurisdiction_id) AS jurisdiction_name,
                COALESCE(j.jurisdiction_type, 'county') AS jurisdiction_type,
                BTRIM(s.youtube_channel_url) AS youtube_channel_url,
                BTRIM(s.youtube_channel_id) AS youtube_channel_id,
                s.youtube_channel_selection_method,
                s.youtube_channel_selection_confidence
            FROM bronze.bronze_jurisdictions_counties_scraped s
            LEFT JOIN intermediate.int_jurisdictions j
                ON j.jurisdiction_id = s.jurisdiction_id
            WHERE s.youtube_channel_url IS NOT NULL
              AND BTRIM(s.youtube_channel_url) <> ''
        """
        params: list[Any] = []
        if states_filter:
            query += " AND upper(btrim(s.usps::text)) = ANY(%s)"
            params.append([s.upper() for s in states_filter])
        if jurisdiction_id:
            query += " AND s.jurisdiction_id = %s"
            params.append(jurisdiction_id.strip())
        query += " ORDER BY s.usps, jurisdiction_name"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()

        jurisdictions: List[Dict] = []
        counties_table = "bronze.bronze_jurisdictions_counties_scraped"
        for row in rows:
            channel_url = str(row["youtube_channel_url"] or "").strip()
            stored_id = str(row.get("youtube_channel_id") or "").strip()
            url_id = _channel_id_from_url(channel_url)
            if stored_id.startswith("UC"):
                channel_id = stored_id
                normalized_url = (
                    channel_url
                    if url_id == stored_id
                    else f"https://www.youtube.com/channel/{channel_id}"
                )
            elif url_id:
                channel_id = url_id
                normalized_url = f"https://www.youtube.com/channel/{channel_id}"
                self.persist_scraped_channel_resolution(
                    table=counties_table,
                    geoid=str(row["geoid"]),
                    channel_id=channel_id,
                    canonical_url=normalized_url,
                )
            else:
                channel_id, normalized_url = self.resolve_channel_id_from_url(channel_url)
                if channel_id:
                    self.persist_scraped_channel_resolution(
                        table=counties_table,
                        geoid=str(row["geoid"]),
                        channel_id=channel_id,
                        canonical_url=normalized_url,
                    )
            if not channel_id:
                logger.warning(
                    "Skipping {} — could not resolve channel id from {}",
                    row["jurisdiction_id"],
                    channel_url,
                )
                continue
            jurisdictions.append(
                {
                    "jurisdiction_id": row["jurisdiction_id"],
                    "jurisdiction_name": row["jurisdiction_name"],
                    "state_code": row["state_code"],
                    "state": row["state"],
                    "jurisdiction_type": row["jurisdiction_type"],
                    "youtube_channels": [
                        {
                            "channel_id": channel_id,
                            "channel_url": normalized_url,
                            "channel_title": row["jurisdiction_name"],
                            "channel_type": "county",
                            "discovery_method": row.get("youtube_channel_selection_method")
                            or "counties_scraped",
                            "confidence": row.get("youtube_channel_selection_confidence"),
                        }
                    ],
                    "youtube_channel_count": 1,
                }
            )

        logger.info(
            "Found {} counties with YouTube channels (source=bronze.bronze_jurisdictions_counties_scraped)",
            len(jurisdictions),
        )
        return jurisdictions

    def get_jurisdictions_from_municipalities_scraped(
        self,
        states_filter: Optional[List[str]] = None,
        jurisdiction_id: Optional[str] = None,
    ) -> List[Dict]:
        """Municipality jurisdictions with ``youtube_channel_url`` on ``bronze_jurisdictions_municipalities_scraped``."""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT
                s.geoid,
                s.usps AS state_code,
                COALESCE(j.state, s.usps) AS state,
                s.jurisdiction_id,
                COALESCE(j.name, s.jurisdiction_id) AS jurisdiction_name,
                COALESCE(j.jurisdiction_type, 'municipality') AS jurisdiction_type,
                BTRIM(s.youtube_channel_url) AS youtube_channel_url,
                BTRIM(s.youtube_channel_id) AS youtube_channel_id,
                s.youtube_channel_selection_method,
                s.youtube_channel_selection_confidence
            FROM bronze.bronze_jurisdictions_municipalities_scraped s
            LEFT JOIN intermediate.int_jurisdictions j
                ON j.jurisdiction_id = s.jurisdiction_id
            WHERE s.youtube_channel_url IS NOT NULL
              AND BTRIM(s.youtube_channel_url) <> ''
        """
        params: list[Any] = []
        if states_filter:
            query += " AND upper(btrim(s.usps::text)) = ANY(%s)"
            params.append([s.upper() for s in states_filter])
        if jurisdiction_id:
            query += " AND s.jurisdiction_id = %s"
            params.append(jurisdiction_id.strip())
        query += " ORDER BY s.usps, jurisdiction_name"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()

        jurisdictions: List[Dict] = []
        municipalities_table = "bronze.bronze_jurisdictions_municipalities_scraped"
        for row in rows:
            channel_url = str(row["youtube_channel_url"] or "").strip()
            stored_id = str(row.get("youtube_channel_id") or "").strip()
            url_id = _channel_id_from_url(channel_url)
            if stored_id.startswith("UC"):
                channel_id = stored_id
                normalized_url = (
                    channel_url
                    if url_id == stored_id
                    else f"https://www.youtube.com/channel/{channel_id}"
                )
            elif url_id:
                channel_id = url_id
                normalized_url = f"https://www.youtube.com/channel/{channel_id}"
                self.persist_scraped_channel_resolution(
                    table=municipalities_table,
                    geoid=str(row["geoid"]),
                    channel_id=channel_id,
                    canonical_url=normalized_url,
                )
            else:
                channel_id, normalized_url = self.resolve_channel_id_from_url(channel_url)
                if channel_id:
                    self.persist_scraped_channel_resolution(
                        table=municipalities_table,
                        geoid=str(row["geoid"]),
                        channel_id=channel_id,
                        canonical_url=normalized_url,
                    )
            if not channel_id:
                logger.warning(
                    "Skipping {} — could not resolve channel id from {}",
                    row["jurisdiction_id"],
                    channel_url,
                )
                continue
            jurisdictions.append(
                {
                    "jurisdiction_id": row["jurisdiction_id"],
                    "jurisdiction_name": row["jurisdiction_name"],
                    "state_code": row["state_code"],
                    "state": row["state"],
                    "jurisdiction_type": row["jurisdiction_type"],
                    "youtube_channels": [
                        {
                            "channel_id": channel_id,
                            "channel_url": normalized_url,
                            "channel_title": row["jurisdiction_name"],
                            "channel_type": "municipality",
                            "discovery_method": row.get("youtube_channel_selection_method")
                            or "municipalities_scraped",
                            "confidence": row.get("youtube_channel_selection_confidence"),
                        }
                    ],
                    "youtube_channel_count": 1,
                }
            )

        logger.info(
            "Found {} municipalities with YouTube channels (source=bronze.bronze_jurisdictions_municipalities_scraped)",
            len(jurisdictions),
        )
        return jurisdictions

    def get_jurisdictions_with_youtube(
        self,
        states_filter: Optional[List[str]] = None,
        jurisdiction_id: Optional[str] = None,
        *,
        channel_source: str = "auto",
    ) -> List[Dict]:
        """Get jurisdictions that have YouTube channels.

        ``channel_source=counties-scraped``: ``bronze.bronze_jurisdictions_counties_scraped``.
        ``channel_source=municipalities-scraped``: ``bronze.bronze_jurisdictions_municipalities_scraped``.
        Otherwise: ``intermediate.int_events_channels``, then ``bronze.bronze_events_youtube``.
        """
        if channel_source == "counties-scraped":
            return self.get_jurisdictions_from_counties_scraped(
                states_filter, jurisdiction_id=jurisdiction_id
            )
        if channel_source == "municipalities-scraped":
            return self.get_jurisdictions_from_municipalities_scraped(
                states_filter, jurisdiction_id=jurisdiction_id
            )

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
                cap_note = (
                    f", max {self.max_transcripts_per_channel} transcript(s) per channel"
                    if self.max_transcripts_per_channel
                    else ""
                )
                logger.info(
                    f"  📝 Fetching transcripts for {len(event_ids)} video(s)"
                    f" (delay: {self.transcript_delay}s each{cap_note})..."
                )
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
    
    def _limit_transcript_video_ids(
        self,
        event_ids: Dict[str, int],
        limit: int,
    ) -> Dict[str, int]:
        """Keep only the ``limit`` newest videos by ``published_at`` for caption download."""
        if limit <= 0 or len(event_ids) <= limit:
            return event_ids
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT video_id
                FROM bronze.bronze_events_youtube
                WHERE video_id = ANY(%s)
                ORDER BY published_at DESC NULLS LAST, last_updated DESC NULLS LAST
                LIMIT %s
                """,
                (list(event_ids.keys()), limit),
            )
            keep = {row[0] for row in cursor.fetchall()}
        finally:
            cursor.close()
        return {vid: eid for vid, eid in event_ids.items() if vid in keep}

    def insert_transcripts(
        self,
        event_ids: Dict[str, int],
        *,
        jurisdiction_id: Optional[str] = None,
    ) -> int:
        """Fetch and insert transcripts for events with exponential backoff on rate limits."""
        import time

        if self.max_transcripts_per_channel and len(event_ids) > self.max_transcripts_per_channel:
            before = len(event_ids)
            event_ids = self._limit_transcript_video_ids(
                event_ids, self.max_transcripts_per_channel
            )
            logger.info(
                "  Transcript cap: {} of {} video(s) (--max-transcripts-per-channel {})",
                len(event_ids),
                before,
                self.max_transcripts_per_channel,
            )

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
            items = list(event_ids.items())

            def _fetch_transcript_safe(video_id: str) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
                try:
                    return video_id, self.fetch_transcript(video_id), None
                except Exception as exc:
                    if "RATE_LIMITED" in str(exc):
                        return video_id, None, "RATE_LIMITED"
                    logger.debug(f"  Error fetching transcript for {video_id}: {exc}")
                    return video_id, None, None

            def _persist_transcript(video_id: str, event_id: int, transcript_data: Dict[str, Any]) -> None:
                nonlocal inserted
                transcript_data = dict(transcript_data)
                transcript_data["event_id"] = event_id
                if transcript_data.get("segments"):
                    transcript_data["segments"] = json.dumps(transcript_data["segments"])
                else:
                    transcript_data["segments"] = None
                transcript_data["has_transcript"] = bool(transcript_data.get("raw_text"))
                transcript_data["transcript_quality"] = (
                    "medium" if transcript_data.get("is_auto_generated") else "high"
                )
                cursor.execute(insert_query, transcript_data)
                inserted += 1
                if inserted % 10 == 0:
                    self.conn.commit()

            if self.transcript_workers > 1 and len(items) > 1:
                batch_size = self.transcript_workers
                for batch_start in range(0, len(items), batch_size):
                    batch = items[batch_start : batch_start + batch_size]
                    if batch_start > 0 and consecutive_rate_limits == 0:
                        time.sleep(self.transcript_delay)
                    try:
                        with ThreadPoolExecutor(max_workers=len(batch)) as pool:
                            results = list(
                                pool.map(lambda pair: _fetch_transcript_safe(pair[0]), batch)
                            )
                    except ValueError as exc:
                        if "closed file" not in str(exc).lower():
                            raise
                        logger.warning(
                            "  Parallel transcript fetch hit closed stderr; "
                            "retrying batch sequentially"
                        )
                        results = [_fetch_transcript_safe(pair[0]) for pair in batch]
                    for (video_id, event_id), (vid, transcript_data, err) in zip(batch, results):
                        if err == "RATE_LIMITED":
                            rate_limit_count += 1
                            consecutive_rate_limits += 1
                            logger.warning(
                                f"  ⚠️  Rate limited! ({rate_limit_count} total, {consecutive_rate_limits} consecutive)"
                            )
                            if consecutive_rate_limits >= 5:
                                logger.error(
                                    f"  ❌ Too many consecutive rate limits ({consecutive_rate_limits}), stopping transcript fetching"
                                )
                                return inserted
                            continue
                        if transcript_data:
                            consecutive_rate_limits = 0
                            _persist_transcript(vid, event_id, transcript_data)
                self.conn.commit()
                return inserted

            for i, (video_id, event_id) in enumerate(items, 1):
                base_delay = self.transcript_delay
                if consecutive_rate_limits > 0:
                    backoff_delay = min(base_delay * (2 ** consecutive_rate_limits), max_backoff)
                    logger.warning(
                        f"  ⏱️  Backing off {backoff_delay:.1f}s due to {consecutive_rate_limits} consecutive rate limits..."
                    )
                    time.sleep(backoff_delay)
                elif i > 1:
                    time.sleep(base_delay)

                _, transcript_data, err = _fetch_transcript_safe(video_id)
                if err == "RATE_LIMITED":
                    rate_limit_count += 1
                    consecutive_rate_limits += 1
                    logger.warning(
                        f"  ⚠️  Rate limited! ({rate_limit_count} total, {consecutive_rate_limits} consecutive)"
                    )
                    if consecutive_rate_limits >= 5:
                        logger.error(
                            f"  ❌ Too many consecutive rate limits ({consecutive_rate_limits}), stopping transcript fetching"
                        )
                        break
                    continue
                if transcript_data:
                    consecutive_rate_limits = 0
                
                    _persist_transcript(video_id, event_id, transcript_data)
            
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
        *,
        channel_source: str = "auto",
        workers: int = 1,
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
        logger.info(f"Channel source: {channel_source}")
        if workers > 1:
            logger.info(f"Jurisdiction workers: {workers}")
        if self.transcript_workers > 1 and self.fetch_transcripts:
            logger.info(f"Transcript workers per jurisdiction: {self.transcript_workers}")
        if self.max_transcripts_per_channel and self.fetch_transcripts:
            logger.info(
                f"Max transcripts per channel: {self.max_transcripts_per_channel} (newest by published_at)"
            )
        logger.info("")
        
        start_time = datetime.now()
        
        # Get jurisdictions with YouTube channels
        jurisdictions = self.get_jurisdictions_with_youtube(
            states_filter,
            jurisdiction_id=jurisdiction_id,
            channel_source=channel_source,
        )
        
        if not jurisdictions:
            logger.warning("No jurisdictions found with YouTube channels")
            return
        
        total_inserted = 0
        workers = max(1, int(workers or 1))
        if workers == 1:
            for i, jurisdiction in enumerate(jurisdictions, 1):
                logger.info(f"\n[{i}/{len(jurisdictions)}] Processing jurisdiction...")
                total_inserted += self.process_jurisdiction(jurisdiction)
        else:
            loader_kwargs = self._parallel_loader_kwargs(workers)
            completed = 0
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(
                        _process_jurisdiction_worker,
                        self.database_url,
                        jurisdiction,
                        loader_kwargs,
                    ): jurisdiction
                    for jurisdiction in jurisdictions
                }
                for future in as_completed(futures):
                    jurisdiction = futures[future]
                    completed += 1
                    try:
                        inserted = future.result()
                        total_inserted += inserted
                        logger.info(
                            "[{}/{}] {} — inserted {}",
                            completed,
                            len(jurisdictions),
                            jurisdiction.get("jurisdiction_name"),
                            inserted,
                        )
                    except Exception as exc:
                        logger.error(
                            "[{}/{}] {} failed: {}",
                            completed,
                            len(jurisdictions),
                            jurisdiction.get("jurisdiction_name"),
                            exc,
                        )
        
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

    def _parallel_loader_kwargs(self, jurisdiction_workers: int = 1) -> Dict[str, Any]:
        """Constructor kwargs for per-jurisdiction worker loaders."""
        # Nested thread pools (county workers × transcript workers) break stderr/loguru.
        transcript_workers = (
            1 if jurisdiction_workers > 1 else self.transcript_workers
        )
        if jurisdiction_workers > 1 and self.transcript_workers > 1:
            logger.info(
                "Jurisdiction workers={}: transcript_workers capped at 1 per county",
                jurisdiction_workers,
            )
        return {
            "youtube_api_key": self.youtube_api_key,
            "max_videos_per_channel": self.max_videos,
            "min_duration_seconds": self.min_duration_seconds,
            "days_lookback": self.days_lookback,
            "fetch_transcripts": self.fetch_transcripts,
            "force_full_fetch": self.force_full_fetch,
            "transcript_delay": self.transcript_delay,
            "use_ytdlp_fallback": self.use_ytdlp_fallback,
            "cookies_file": self.cookies_file,
            "proxy_url": self.proxy_url,
            "ensure_schema_setup": False,
            "transcript_workers": transcript_workers,
            "max_transcripts_per_channel": self.max_transcripts_per_channel,
            "resolve_channels_ytdlp": self.resolve_channels_ytdlp,
            "persist_scraped_channel_ids": self.persist_scraped_channel_ids,
        }


def main():
    """Main entry point."""
    try:
        logger.remove()
    except ValueError:
        pass
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
        level="INFO",
        enqueue=True,
    )

    parser = argparse.ArgumentParser(description='Load YouTube events from jurisdictions into event')
    
    parser.add_argument(
        '--states',
        type=str,
        default=",".join(DEFAULT_PRIORITY_STATES),
        help=f'Comma-separated state codes (default: {",".join(DEFAULT_PRIORITY_STATES)})',
    )
    parser.add_argument(
        '--channel-source',
        choices=('auto', 'counties-scraped', 'municipalities-scraped'),
        default='counties-scraped',
        help=(
            'Channel list source (default: counties-scraped). '
            'municipalities-scraped = bronze_jurisdictions_municipalities_scraped'
        ),
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Parallel jurisdiction workers (default: 4)',
    )
    parser.add_argument(
        '--transcript-workers',
        type=int,
        default=3,
        help='Parallel transcript fetches per jurisdiction batch (default: 3)',
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
        help='Maximum videos to catalog per channel (metadata in bronze_events_youtube; default: 100)',
    )

    parser.add_argument(
        '--max-transcripts-per-channel',
        type=int,
        default=None,
        metavar='N',
        help=(
            'Only download captions for the N newest videos per channel (by published_at). '
            'Catalog still uses --max-videos. Example: --max-videos 100 --max-transcripts-per-channel 4'
        ),
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

    parser.add_argument(
        '--resolve-channels-ytdlp',
        action='store_true',
        help=(
            'Resolve @handle URLs with yt-dlp only (no channels.list forHandle). '
            'Use when API quota is exhausted. Same as YOUTUBE_RESOLVE_CHANNELS_YTDLP=1.'
        ),
    )

    parser.add_argument(
        '--backfill-scraped-channel-ids',
        action='store_true',
        help=(
            'Only resolve and persist youtube_channel_id on scraped bronze tables '
            '(counties-scraped or municipalities-scraped); skip video catalog/transcripts.'
        ),
    )

    parser.add_argument(
        '--no-persist-scraped-channel-ids',
        action='store_true',
        help='Do not UPDATE bronze_jurisdictions_*_scraped with resolved youtube_channel_id.',
    )

    args = parser.parse_args()
    
    states_filter = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    
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
        proxy_url=args.proxy,
        transcript_workers=args.transcript_workers,
        max_transcripts_per_channel=args.max_transcripts_per_channel,
        resolve_channels_ytdlp=args.resolve_channels_ytdlp,
        persist_scraped_channel_ids=not args.no_persist_scraped_channel_ids,
    )
    
    jurisdiction_id = (args.jurisdiction_id or '').strip() or None

    try:
        if args.backfill_scraped_channel_ids:
            if args.channel_source not in YouTubeEventsLoader._SCRAPED_CHANNEL_TABLES:
                logger.error(
                    "--backfill-scraped-channel-ids requires --channel-source "
                    "counties-scraped or municipalities-scraped (not auto)"
                )
                return 1
            loader.backfill_scraped_channel_ids(
                channel_source=args.channel_source,
                states_filter=states_filter,
                jurisdiction_id=jurisdiction_id,
            )
            return 0

        loader.run(
            states_filter=states_filter,
            jurisdiction_id=jurisdiction_id,
            channel_source=args.channel_source,
            workers=args.workers,
        )
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
