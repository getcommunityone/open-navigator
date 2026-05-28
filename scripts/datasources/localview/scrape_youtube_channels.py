#!/usr/bin/env python3
"""
Scrape Municipal YouTube Channels for Meeting Videos

Downloads meeting videos and metadata from municipal government YouTube channels.
Updates LocalView dataset with 2025/2026 data.

FALLBACK METHOD: If YouTube API quota is exceeded, automatically switches to yt-dlp
which scrapes the public site directly instead of using the restricted API key system.

Channel listing merges **Videos** and **Streams** tabs (deduped by ``video_id``). The YouTube
Data API path also merges completed live broadcasts from ``search.list`` (``eventType=completed``).

Usage:
    # Scrape all known channels
    python scripts/localview/scrape_youtube_channels.py --update
    
    # Scrape specific channels
    python scripts/localview/scrape_youtube_channels.py --channels "UCxxxxx,UCyyyyy"
    
    # Scrape by state
    python scripts/localview/scrape_youtube_channels.py --states AL,GA,IN,MA,MT,WA,WI
"""

import argparse
import contextlib
import os
import sys
import threading
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import re
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger
import polars as pl
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
import os
from dotenv import load_dotenv

# Try to import yt-dlp for fallback when API quota exceeded
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    logger.warning("yt-dlp not installed. Install with: pip install yt-dlp")

# Load environment variables
load_dotenv()

# Logging is configured by load_youtube_events_to_postgres (or CLI entry below).
_YTDLP_STDERR_LOCK = threading.Lock()


def _parse_published_at(value: Any) -> Optional[datetime]:
    """Parse published_at from API ISO strings or yt-dlp upload_date."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            pass
        if len(text) == 8 and text.isdigit():
            try:
                return datetime.strptime(text, "%Y%m%d")
            except ValueError:
                return None
    return None


def dedupe_videos_by_id(videos: List[Dict], max_results: int) -> List[Dict]:
    """Merge video dicts; on duplicate ``video_id`` keep the newer row, then cap."""
    by_id: Dict[str, Dict] = {}
    for video in videos:
        video_id = (video.get("video_id") or "").strip()
        if not video_id:
            continue
        existing = by_id.get(video_id)
        if existing is None:
            by_id[video_id] = video
            continue
        new_dt = _parse_published_at(video.get("published_at")) or datetime.min
        old_dt = _parse_published_at(existing.get("published_at")) or datetime.min
        if new_dt >= old_dt:
            by_id[video_id] = video
    deduped = list(by_id.values())
    deduped.sort(
        key=lambda v: _parse_published_at(v.get("published_at")) or datetime.min,
        reverse=True,
    )
    return deduped[:max_results]


class MunicipalYouTubeScraper:
    """
    Scrape municipal government YouTube channels for meeting videos
    
    Uses YouTube Data API by default, falls back to yt-dlp if quota exceeded.
    """
    
    def __init__(self, api_key: Optional[str] = None, cookies_file: Optional[str] = None, proxy_url: Optional[str] = None):
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        self.cookies_file = cookies_file  # Path to cookies.txt for authenticated requests
        self.proxy_url = proxy_url  # Proxy URL to bypass IP blocks
        self.use_ytdlp_fallback = False  # Track if we should use fallback
        self.quota_exceeded_at = None  # Track when quota was exceeded
        self.quota_cooldown_minutes = 15  # Wait 15 minutes before retrying API
        
        # Try to initialize YouTube API
        if self.api_key:
            try:
                self.youtube = build('youtube', 'v3', developerKey=self.api_key)
            except Exception as e:
                logger.warning(f"YouTube API initialization failed: {e}")
                self.youtube = None
        else:
            logger.warning("No YOUTUBE_API_KEY found, will use yt-dlp fallback")
            self.youtube = None
            self.use_ytdlp_fallback = True
        
        self.cache_dir = Path("data/cache/localview")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Known municipal YouTube channels
        self.known_channels = self.load_known_channels()
    
    def load_known_channels(self) -> List[Dict]:
        """Load known municipal YouTube channels from cache"""
        channels_file = self.cache_dir / "municipality_channels.csv"
        
        if channels_file.exists():
            df = pl.read_csv(channels_file)
            return df.to_dicts()
        else:
            # Default starter list
            return [
                {"municipality": "Seattle, WA", "channel_id": "UCMFAKdxL6sATpkRqLdJyKUg", "state": "WA"},
                {"municipality": "Boston, MA", "channel_id": "UCiMB3gH6PLe-JMDhxX4ZsmA", "state": "MA"},
                # Add more as discovered
            ]
    
    def get_channel_videos(
        self,
        channel_id: str,
        max_results: int = 50,
        published_after: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get videos from a YouTube channel
        
        Args:
            channel_id: YouTube channel ID
            max_results: Maximum number of videos to return
            published_after: Only get videos after this date
        
        Returns:
            List of video dictionaries with metadata
        """
        # Check if we're in quota cooldown period
        if self.quota_exceeded_at:
            time_since_quota_exceeded = (datetime.now() - self.quota_exceeded_at).total_seconds() / 60
            if time_since_quota_exceeded < self.quota_cooldown_minutes:
                remaining = self.quota_cooldown_minutes - time_since_quota_exceeded
                logger.info(f"API quota cooldown active ({remaining:.1f} min remaining), using yt-dlp fallback")
                return self.get_channel_videos_ytdlp(channel_id, max_results, published_after)
            else:
                # Cooldown expired, reset and try API again
                logger.info(f"Quota cooldown expired, attempting YouTube API again")
                self.quota_exceeded_at = None
                self.use_ytdlp_fallback = False
        
        # Use yt-dlp fallback if previously failed or no API key
        if self.use_ytdlp_fallback or not self.youtube:
            return self.get_channel_videos_ytdlp(channel_id, max_results, published_after)
        
        videos: List[Dict] = []
        seen_ids: set[str] = set()
        
        try:
            # Get channel's uploads playlist (Videos tab equivalent)
            channel_response = self.youtube.channels().list(
                id=channel_id,
                part='contentDetails'
            ).execute()
            
            if not channel_response.get('items'):
                logger.warning(f"Channel {channel_id} not found")
                return []
            
            uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # Get videos from uploads playlist
            next_page_token = None
            
            while len(seen_ids) < max_results:
                playlist_request = self.youtube.playlistItems().list(
                    playlistId=uploads_playlist_id,
                    part='snippet,contentDetails',
                    maxResults=min(50, max_results - len(seen_ids)),
                    pageToken=next_page_token
                )
                
                playlist_response = playlist_request.execute()
                
                for item in playlist_response.get('items', []):
                    snippet = item['snippet']
                    
                    # Parse published date
                    published_at = datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00'))
                    
                    # Filter by date if specified
                    if published_after and published_at < published_after:
                        continue
                    
                    video_id = snippet['resourceId']['videoId']
                    if video_id in seen_ids:
                        continue
                    
                    # Get additional video details
                    video_details = self.get_video_details(video_id)
                    
                    if video_details:
                        seen_ids.add(video_id)
                        videos.append(video_details)
                
                next_page_token = playlist_response.get('nextPageToken')
                if not next_page_token:
                    break
                
                # Rate limiting
                time.sleep(0.5)

            # Streams tab equivalent: completed live broadcasts not always in uploads order
            streams_added = self._append_api_completed_live_videos(
                channel_id=channel_id,
                videos=videos,
                seen_ids=seen_ids,
                max_results=max_results,
                published_after=published_after,
            )
            if streams_added:
                logger.info(f"  + {streams_added} video(s) from completed live streams (API)")
        
        except HttpError as e:
            # Check if it's a quota error
            if 'quotaExceeded' in str(e) or e.resp.status == 403:
                logger.warning(f"YouTube API quota exceeded for channel {channel_id}")
                logger.warning(f"⏱️  Entering {self.quota_cooldown_minutes}-minute cooldown - will use yt-dlp fallback")
                self.use_ytdlp_fallback = True
                self.quota_exceeded_at = datetime.now()
                
                # Try yt-dlp fallback
                return self.get_channel_videos_ytdlp(channel_id, max_results, published_after)
            else:
                logger.error(f"YouTube API error for channel {channel_id}: {e}")
        
        return dedupe_videos_by_id(videos, max_results)

    def _is_quota_exceeded_error(self, error: Exception) -> bool:
        """Return True when a YouTube API error indicates daily quota exhaustion."""
        msg = str(error)
        return (
            isinstance(error, HttpError)
            and getattr(error, "resp", None) is not None
            and int(getattr(error.resp, "status", 0)) == 403
            and (
                "quotaExceeded" in msg
                or "youtube.quota" in msg
                or "exceeded your" in msg.lower()
            )
        )

    def get_video_details_ytdlp(self, video_id: str) -> Optional[Dict]:
        """Fallback detail extraction for a single video using yt-dlp metadata only."""
        if not YT_DLP_AVAILABLE:
            return None

        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            with yt_dlp.YoutubeDL(self._ytdlp_base_opts(max_results=1)) as ydl:
                info = ydl.extract_info(watch_url, download=False)
        except Exception as exc:
            logger.debug(f"yt-dlp detail fallback failed for {video_id}: {exc}")
            return None

        if not info:
            return None

        published_at = _parse_published_at(info.get('upload_date'))
        duration_minutes = 0
        if info.get('duration'):
            try:
                duration_minutes = int(info['duration']) // 60
            except Exception:
                duration_minutes = 0

        title = info.get('title', '') or ''
        channel_id = info.get('channel_id') or info.get('uploader_id') or ''
        return {
            'video_id': video_id,
            'title': title,
            'description': info.get('description', '') or '',
            'published_at': published_at.isoformat() if published_at else '',
            'channel_id': channel_id,
            'channel_title': info.get('channel', '') or info.get('uploader', '') or '',
            'duration_minutes': duration_minutes,
            'has_captions': False,
            'view_count': info.get('view_count', 0) or 0,
            'like_count': info.get('like_count', 0) or 0,
            'meeting_type': self.detect_meeting_type(title),
            'language': info.get('language') or 'en',
            'location_description': None,
            'video_url': watch_url,
        }
    
    def _append_api_completed_live_videos(
        self,
        channel_id: str,
        videos: List[Dict],
        seen_ids: set[str],
        max_results: int,
        published_after: Optional[datetime],
    ) -> int:
        """Add completed live streams via search API (deduped against uploads)."""
        if len(seen_ids) >= max_results:
            return 0
        added = 0
        try:
            search_response = self.youtube.search().list(
                channelId=channel_id,
                part='id,snippet',
                type='video',
                eventType='completed',
                order='date',
                maxResults=min(50, max_results - len(seen_ids)),
            ).execute()
            for item in search_response.get('items', []):
                video_id = (item.get('id') or {}).get('videoId')
                if not video_id or video_id in seen_ids:
                    continue
                snippet = item.get('snippet') or {}
                if published_after and snippet.get('publishedAt'):
                    published_at = datetime.fromisoformat(
                        snippet['publishedAt'].replace('Z', '+00:00')
                    )
                    if published_at < published_after:
                        continue
                video_details = self.get_video_details(video_id)
                if not video_details:
                    continue
                seen_ids.add(video_id)
                videos.append(video_details)
                added += 1
                if len(seen_ids) >= max_results:
                    break
                time.sleep(0.2)
        except HttpError as e:
            logger.debug(f"Completed live stream search skipped for {channel_id}: {e}")
        return added
    
    def get_video_details(self, video_id: str) -> Optional[Dict]:
        """Get detailed information about a video"""
        # Skip API if in quota cooldown
        if self.quota_exceeded_at:
            time_since_quota_exceeded = (datetime.now() - self.quota_exceeded_at).total_seconds() / 60
            if time_since_quota_exceeded < self.quota_cooldown_minutes:
                return self.get_video_details_ytdlp(video_id)
        
        try:
            response = self.youtube.videos().list(
                id=video_id,
                part='snippet,contentDetails,statistics,recordingDetails'
            ).execute()
            
            if not response.get('items'):
                return None
            
            item = response['items'][0]
            snippet = item['snippet']
            content_details = item['contentDetails']
            recording_details = item.get('recordingDetails', {})
            
            # Parse duration (ISO 8601 format: PT1H2M10S)
            duration_str = content_details['duration']
            duration_minutes = self.parse_duration(duration_str)
            
            # Check if captions available
            has_captions = content_details.get('caption', 'false') == 'true'
            
            # Detect meeting type from title
            meeting_type = self.detect_meeting_type(snippet['title'])
            
            # Extract language (prefer audio language, fallback to default language)
            language = snippet.get('defaultAudioLanguage') or snippet.get('defaultLanguage') or 'en'
            
            # Extract location if available
            location_description = recording_details.get('locationDescription')
            location_coords = recording_details.get('location')  # {latitude, longitude}
            
            return {
                'video_id': video_id,
                'title': snippet['title'],
                'description': snippet.get('description', ''),
                'published_at': snippet['publishedAt'],
                'channel_id': snippet['channelId'],
                'channel_title': snippet['channelTitle'],
                'duration_minutes': duration_minutes,
                'has_captions': has_captions,
                'view_count': int(item['statistics'].get('viewCount', 0)),
                'like_count': int(item['statistics'].get('likeCount', 0)),
                'meeting_type': meeting_type,
                'language': language,
                'location_description': location_description,
                'video_url': f"https://www.youtube.com/watch?v={video_id}"
            }
        
        except HttpError as e:
            if self._is_quota_exceeded_error(e):
                first_hit = self.quota_exceeded_at is None
                self.use_ytdlp_fallback = True
                self.quota_exceeded_at = datetime.now()
                if first_hit:
                    logger.warning(
                        f"YouTube API quota exceeded while fetching {video_id}; switching to yt-dlp fallback for {self.quota_cooldown_minutes} minutes"
                    )
                return self.get_video_details_ytdlp(video_id)

            logger.error(f"Error getting details for video {video_id}: {e}")
            return None
    
    def parse_duration(self, duration_str: str) -> int:
        """Parse ISO 8601 duration to minutes"""
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if not match:
            return 0
        
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        return hours * 60 + minutes + (1 if seconds > 30 else 0)
    
    def detect_meeting_type(self, title: str) -> str:
        """Detect meeting type from video title"""
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['city council', 'council meeting']):
            return 'City Council'
        elif any(word in title_lower for word in ['planning', 'zoning']):
            return 'Planning Commission'
        elif any(word in title_lower for word in ['school board', 'board of education']):
            return 'School Board'
        elif 'special' in title_lower:
            return 'Special Meeting'
        elif 'workshop' in title_lower:
            return 'Workshop'
        else:
            return 'Other'
    
    def _ytdlp_base_opts(self, max_results: int) -> Dict[str, Any]:
        opts: Dict[str, Any] = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'playlistend': max_results,
            'ignoreerrors': True,
            'nocheckcertificate': True,
        }
        if self.cookies_file:
            cookie_path = Path(self.cookies_file)
            if cookie_path.is_file():
                opts['cookiefile'] = str(cookie_path.resolve())
        if self.proxy_url:
            opts['proxy'] = self.proxy_url
        return opts

    def _ytdlp_extract_tab_entries(
        self, channel_url: str, max_results: int
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Extract flat playlist entries from a channel tab URL."""
        if not YT_DLP_AVAILABLE:
            return [], channel_url

        info = None
        with _YTDLP_STDERR_LOCK:
            with open(os.devnull, "w") as devnull:
                with contextlib.redirect_stderr(devnull):
                    try:
                        with yt_dlp.YoutubeDL(self._ytdlp_base_opts(max_results)) as ydl:
                            info = ydl.extract_info(channel_url, download=False)
                    except Exception:
                        return [], channel_url

        if not info or 'entries' not in info:
            return [], channel_url
        entries = [e for e in (info.get('entries') or []) if e]
        return entries, channel_url

    def _video_dict_from_ytdlp_entry(
        self, entry: Dict[str, Any], channel_id: str
    ) -> Optional[Dict]:
        video_id = (entry.get('id') or '').strip()
        if not video_id:
            return None
        published_at = _parse_published_at(entry.get('upload_date'))
        duration_minutes = 0
        if entry.get('duration'):
            duration_minutes = int(entry['duration']) // 60
        title = entry.get('title', '') or ''
        return {
            'video_id': video_id,
            'title': title,
            'description': entry.get('description', '') or '',
            'published_at': published_at.isoformat() if published_at else '',
            'channel_id': channel_id,
            'channel_title': entry.get('channel', '') or '',
            'duration_minutes': duration_minutes,
            'has_captions': False,
            'view_count': entry.get('view_count', 0) or 0,
            'like_count': entry.get('like_count', 0) or 0,
            'meeting_type': self.detect_meeting_type(title),
            'video_url': entry.get('url') or f"https://www.youtube.com/watch?v={video_id}",
        }

    def get_channel_videos_ytdlp(
        self,
        channel_id: str,
        max_results: int = 50,
        published_after: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Fallback using yt-dlp: always merge **Videos** and **Streams** tabs, dedupe by video_id.
        Falls back to channel homepage only when both tabs are empty.
        """
        if not YT_DLP_AVAILABLE:
            logger.error("yt-dlp not available. Install with: pip install yt-dlp")
            return []

        base = f"https://www.youtube.com/channel/{channel_id}"
        tab_urls = [
            (f"{base}/videos", "videos"),
            (f"{base}/streams", "streams"),
        ]

        merged_entries: List[Dict[str, Any]] = []
        tab_counts: Dict[str, int] = {}

        try:
            logger.info(f"Using yt-dlp for channel {channel_id} (videos + streams tabs)")

            for channel_url, tab_label in tab_urls:
                entries, _ = self._ytdlp_extract_tab_entries(channel_url, max_results)
                if entries:
                    tab_counts[tab_label] = len(entries)
                    merged_entries.extend(entries)
                    logger.success(f"  ✓ {len(entries)} entries from {tab_label} tab")

            if not merged_entries:
                homepage_url = base
                entries, _ = self._ytdlp_extract_tab_entries(homepage_url, max_results)
                if entries:
                    tab_counts['homepage'] = len(entries)
                    merged_entries.extend(entries)
                    logger.success(f"  ✓ {len(entries)} entries from channel homepage (no videos/streams)")

            if not merged_entries:
                logger.warning(f"No videos found for channel {channel_id} (videos, streams, homepage)")
                return []

            videos: List[Dict] = []
            cutoff = (
                published_after.replace(tzinfo=None)
                if published_after and published_after.tzinfo
                else published_after
            )

            for entry in merged_entries:
                video = self._video_dict_from_ytdlp_entry(entry, channel_id)
                if not video:
                    continue
                published_at = _parse_published_at(video.get('published_at'))
                if cutoff and published_at and published_at < cutoff:
                    continue
                videos.append(video)

            videos = dedupe_videos_by_id(videos, max_results)
            if tab_counts.get('streams'):
                logger.info(
                    f"  → {len(videos)} unique videos "
                    f"(videos tab: {tab_counts.get('videos', 0)}, "
                    f"streams tab: {tab_counts.get('streams', 0)})"
                )
            else:
                logger.info(f"  → {len(videos)} unique videos")

        except Exception as e:
            logger.error(f"yt-dlp error for channel {channel_id}: {e}")
            return []

        return videos
    
    def scrape_channels(
        self,
        channel_ids: List[str],
        states: Optional[List[str]] = None,
        since_days: int = 30
    ) -> pl.DataFrame:
        """
        Scrape videos from multiple channels
        
        Uses YouTube Data API by default. If API quota is exceeded,
        automatically falls back to yt-dlp which scrapes the public site directly.
        
        Args:
            channel_ids: List of YouTube channel IDs
            states: Filter to specific states
            since_days: Only get videos from last N days
        
        Returns:
            DataFrame with video metadata
        """
        all_videos = []
        published_after = datetime.now() - timedelta(days=since_days)
        
        for channel_info in self.known_channels:
            channel_id = channel_info['channel_id']
            
            # Filter by channel_ids if specified
            if channel_ids and channel_id not in channel_ids:
                continue
            
            # Filter by states if specified
            if states and channel_info.get('state') not in states:
                continue
            
            logger.info(f"Scraping {channel_info['municipality']} ({channel_id})")
            
            # Use yt-dlp if already in fallback mode or no API available
            if self.use_ytdlp_fallback or not self.youtube:
                videos = self.get_channel_videos_ytdlp(
                    channel_id,
                    max_results=100,
                    published_after=published_after
                )
            else:
                # Try API first, will fallback to yt-dlp if quota exceeded
                videos = self.get_channel_videos(
                    channel_id,
                    max_results=100,
                    published_after=published_after
                )
            
            # Add municipality info
            for video in videos:
                video['municipality'] = channel_info['municipality']
                video['state'] = channel_info.get('state', 'Unknown')
            
            all_videos.extend(videos)
            logger.info(f"  Found {len(videos)} videos")
            
            # Rate limiting
            time.sleep(1)
        
        if not all_videos:
            logger.warning("No videos found")
            return pl.DataFrame()
        
        return pl.DataFrame(all_videos)
    
    def save_videos(self, videos_df: pl.DataFrame, year: int = None):
        """Save videos to LocalView format"""
        if len(videos_df) == 0:
            logger.warning("No videos to save")
            return
        
        year = year or datetime.now().year
        output_file = self.cache_dir / f"videos_{year}.csv"
        
        # Convert to LocalView format
        localview_df = videos_df.select([
            pl.col('video_id'),
            pl.col('municipality'),
            pl.col('published_at').str.slice(0, 10).alias('meeting_date'),
            pl.col('meeting_type'),
            pl.col('video_url'),
            pl.lit('youtube').alias('platform'),
            pl.col('duration_minutes'),
            pl.col('has_captions'),
            pl.col('has_captions').alias('transcript_available')
        ])
        
        # Append or create
        if output_file.exists():
            existing_df = pl.read_csv(output_file)
            combined_df = pl.concat([existing_df, localview_df])
            combined_df = combined_df.unique(subset=['video_id'])
            combined_df.write_csv(output_file)
            logger.info(f"✅ Updated {output_file} ({len(combined_df)} total videos)")
        else:
            localview_df.write_csv(output_file)
            logger.info(f"✅ Created {output_file} ({len(localview_df)} videos)")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape municipal YouTube channels for meeting videos"
    )
    parser.add_argument(
        '--channels',
        type=str,
        help='Comma-separated YouTube channel IDs'
    )
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated state codes (e.g., CA,MA,TX)'
    )
    parser.add_argument(
        '--since-days',
        type=int,
        default=30,
        help='Only get videos from last N days (default: 30)'
    )
    parser.add_argument(
        '--update',
        action='store_true',
        help='Update all known channels'
    )
    
    args = parser.parse_args()
    
    # Parse inputs
    channel_ids = None
    if args.channels:
        channel_ids = [c.strip() for c in args.channels.split(',')]
    
    states = None
    if args.states:
        states = [s.strip().upper() for s in args.states.split(',')]
    
    # Initialize scraper
    logger.info("=" * 80)
    logger.info("LOCALVIEW YOUTUBE SCRAPER")
    logger.info("=" * 80)
    
    try:
        scraper = MunicipalYouTubeScraper()
    except ValueError as e:
        logger.error(str(e))
        logger.info("\nSet YOUTUBE_API_KEY in .env file:")
        logger.info("  YOUTUBE_API_KEY=your_api_key_here")
        logger.info("\nGet an API key at: https://console.cloud.google.com/apis/credentials")
        sys.exit(1)
    
    # Scrape videos
    videos_df = scraper.scrape_channels(
        channel_ids=channel_ids,
        states=states,
        since_days=args.since_days
    )
    
    # Save results
    if len(videos_df) > 0:
        scraper.save_videos(videos_df)
        logger.success(f"\n✅ Scraped {len(videos_df)} videos")
    else:
        logger.warning("\n⚠️  No videos found")


if __name__ == "__main__":
    _root = Path(__file__).resolve().parents[2]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from scrapers.youtube.youtube_loader_logging import (
        configure_youtube_loader_logging,
    )

    configure_youtube_loader_logging(workers=1)
    main()
