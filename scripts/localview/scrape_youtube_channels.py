#!/usr/bin/env python3
"""
Scrape Municipal YouTube Channels for Meeting Videos

Downloads meeting videos and metadata from municipal government YouTube channels.
Updates LocalView dataset with 2025/2026 data.

FALLBACK METHOD: If YouTube API quota is exceeded, automatically switches to yt-dlp
which scrapes the public site directly instead of using the restricted API key system.

Usage:
    # Scrape all known channels
    python scripts/localview/scrape_youtube_channels.py --update
    
    # Scrape specific channels
    python scripts/localview/scrape_youtube_channels.py --channels "UCxxxxx,UCyyyyy"
    
    # Scrape by state
    python scripts/localview/scrape_youtube_channels.py --states AL,GA,IN,MA,MT,WA,WI
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Optional
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

# Configure logger
logger.add(sys.stderr, format="{time} {level} {message}", level="INFO")


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
        
        videos = []
        
        try:
            # Get channel's uploads playlist
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
            
            while len(videos) < max_results:
                playlist_request = self.youtube.playlistItems().list(
                    playlistId=uploads_playlist_id,
                    part='snippet,contentDetails',
                    maxResults=min(50, max_results - len(videos)),
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
                    
                    # Get additional video details
                    video_details = self.get_video_details(video_id)
                    
                    if video_details:
                        videos.append(video_details)
                
                next_page_token = playlist_response.get('nextPageToken')
                if not next_page_token:
                    break
                
                # Rate limiting
                time.sleep(0.5)
        
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
        
        return videos
    
    def get_video_details(self, video_id: str) -> Optional[Dict]:
        """Get detailed information about a video"""
        # Skip API if in quota cooldown
        if self.quota_exceeded_at:
            time_since_quota_exceeded = (datetime.now() - self.quota_exceeded_at).total_seconds() / 60
            if time_since_quota_exceeded < self.quota_cooldown_minutes:
                return None  # Will be handled by fallback methods
        
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
    
    def get_channel_videos_ytdlp(
        self,
        channel_id: str,
        max_results: int = 50,
        published_after: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Fallback method using yt-dlp when YouTube API quota is exceeded.
        
        Why it works: yt-dlp scrapes the public YouTube site directly 
        instead of using the restricted API key system.
        
        Args:
            channel_id: YouTube channel ID
            max_results: Maximum number of videos to return
            published_after: Only get videos after this date
        
        Returns:
            List of video dictionaries with metadata
        """
        if not YT_DLP_AVAILABLE:
            logger.error("yt-dlp not available. Install with: pip install yt-dlp")
            return []
        
        videos = []
        
        # Try multiple URL patterns for channels that may not have a videos tab
        url_patterns = [
            f"https://www.youtube.com/channel/{channel_id}/videos",  # Standard videos tab
            f"https://www.youtube.com/channel/{channel_id}/streams",  # Live streams tab
            f"https://www.youtube.com/channel/{channel_id}",  # Channel homepage (all content)
        ]
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Don't download, just get metadata
            'playlistend': max_results,
            'ignoreerrors': True,  # Continue on download errors
            'nocheckcertificate': True,  # Avoid SSL issues
        }
        
        # Add cookies if provided (helps bypass IP blocks)
        if self.cookies_file:
            ydl_opts['cookiefile'] = self.cookies_file
        
        # Add proxy if provided (helps bypass IP blocks)
        if self.proxy_url:
            ydl_opts['proxy'] = self.proxy_url
        
        info = None
        successful_url = None
        
        try:
            logger.info(f"Using yt-dlp fallback for channel {channel_id}")
            
            # Suppress yt-dlp error output to stderr
            import sys
            import os
            
            # Save original stderr
            original_stderr = sys.stderr
            
            try:
                # Redirect stderr to devnull to suppress yt-dlp ERROR messages
                sys.stderr = open(os.devnull, 'w')
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Try each URL pattern until one works
                    for channel_url in url_patterns:
                        try:
                            info = ydl.extract_info(channel_url, download=False)
                            if info and 'entries' in info:
                                successful_url = channel_url
                                # Restore stderr before logging
                                sys.stderr.close()
                                sys.stderr = original_stderr
                                
                                # Log which pattern worked
                                if '/videos' in channel_url:
                                    logger.success(f"  ✓ Extracted from videos tab")
                                elif '/streams' in channel_url:
                                    logger.success(f"  ✓ Extracted from streams tab (no videos tab)")
                                else:
                                    logger.success(f"  ✓ Extracted from channel homepage (no videos/streams tabs)")
                                break
                        except Exception as url_error:
                            # These are expected errors as we try different patterns
                            continue
                
            finally:
                # Always restore stderr
                if sys.stderr != original_stderr:
                    sys.stderr.close()
                    sys.stderr = original_stderr
            
            # Check if we successfully found content
            if not info or 'entries' not in info:
                logger.warning(f"No videos found for channel {channel_id} after trying all URL patterns")
                return []
            
            # Process video entries
            for entry in info['entries']:
                    if not entry:
                        continue
                    
                    # Parse published date
                    published_at = None
                    if 'upload_date' in entry:
                        try:
                            date_str = entry['upload_date']  # Format: YYYYMMDD
                            published_at = datetime.strptime(date_str, '%Y%m%d')
                        except:
                            pass
                    
                    # Filter by date if specified
                    if published_after and published_at and published_at < published_after:
                        continue
                    
                    # Parse duration
                    duration_minutes = 0
                    if 'duration' in entry and entry['duration']:
                        duration_minutes = entry['duration'] // 60
                    
                    # Detect meeting type
                    title = entry.get('title', '')
                    meeting_type = self.detect_meeting_type(title)
                    
                    video_data = {
                        'video_id': entry.get('id', ''),
                        'title': title,
                        'description': entry.get('description', ''),
                        'published_at': published_at.isoformat() if published_at else '',
                        'channel_id': channel_id,
                        'channel_title': entry.get('channel', ''),
                        'duration_minutes': duration_minutes,
                        'has_captions': False,  # yt-dlp doesn't provide this easily
                        'view_count': entry.get('view_count', 0),
                        'like_count': entry.get('like_count', 0),  # May be 0 if not available from yt-dlp
                        'meeting_type': meeting_type,
                        'video_url': entry.get('url', f"https://www.youtube.com/watch?v={entry.get('id')}")
                    }
                    
                    videos.append(video_data)
                    
                    if len(videos) >= max_results:
                        break
            
            # Log final count
            if videos:
                logger.info(f"  → Found {len(videos)} videos")
            else:
                logger.warning(f"  → No videos found (channel may be empty)")
            
        except Exception as e:
            logger.error(f"yt-dlp error for channel {channel_id}: {e}")
        
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
    main()
