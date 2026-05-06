#!/usr/bin/env python3
"""
Download YouTube Audio from bronze_events_youtube to Google Drive

This script downloads audio-only files from YouTube videos in the bronze_events_youtube table
and saves them to Google Drive organized by channel and date.

Features:
- Downloads audio in opus format (best quality, smallest size)
- Organizes files by channel → YYYY-MM-DD_title.opus
- Skips already downloaded files
- Works in Google Colab with mounted Drive
- Progress tracking and resumable

Usage (VS Code Extension):
    1. Open this file in VS Code
    2. Press F1 → "Python: Run Python File in Terminal"
       OR right-click → "Run Python File in Terminal"
    3. Or use integrated terminal:
       cd /home/developer/projects/open-navigator
       source .venv/bin/activate
       python scripts/datasources/youtube/download_audio_to_drive.py \
           --output-dir ~/youtube_audio \
           --limit 50 \
           --days 30

    4. To run with arguments from VS Code tasks (Ctrl+Shift+P → "Tasks: Run Task"):
       Add to .vscode/tasks.json:
       {
           "label": "Download YouTube Audio",
           "type": "shell",
           "command": "${workspaceFolder}/.venv/bin/python",
           "args": [
               "${workspaceFolder}/scripts/datasources/youtube/download_audio_to_drive.py",
               "--output-dir", "${workspaceFolder}/data/youtube_audio",
               "--limit", "50",
               "--days", "30"
           ],
           "problemMatcher": []
       }

Usage (Google Colab):
    # Mount Google Drive first
    from google.colab import drive
    drive.mount('/content/drive')
    
    # Navigate to project
    %cd /content/drive/MyDrive/CommunityOne/open-navigator
    
    # Run script
    !python scripts/datasources/youtube/download_audio_to_drive.py \
        --output-dir /content/drive/MyDrive/CommunityOne/youtube_audio \
        --limit 100 \
        --channels "City of Seattle,City of Portland"

Usage (Local Terminal):
    python scripts/datasources/youtube/download_audio_to_drive.py \
        --output-dir ~/youtube_audio \
        --limit 50
"""

import os
import sys
import argparse
import re
import time
import random
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger
from dotenv import load_dotenv
import yt_dlp

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()


class YouTubeAudioDownloader:
    """Download YouTube audio files organized by channel and date."""
    
    def __init__(
        self,
        database_url: str,
        output_dir: str,
        limit: Optional[int] = None,
        channels_filter: Optional[List[str]] = None,
        states_filter: Optional[List[str]] = None,
        days_recent: Optional[int] = None,
        skip_existing: bool = True,
        reorganize: bool = False,
        cookies_file: Optional[str] = None,
        sleep_between_downloads: float = 2.0
    ):
        # Sanitize database URL (fix common issues with Neon/cloud connections)
        self.database_url = self._sanitize_database_url(database_url)
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.channels_filter = channels_filter
        self.states_filter = states_filter
        self.days_recent = days_recent
        self.skip_existing = skip_existing
        self.reorganize = reorganize
        self.cookies_file = cookies_file
        self.sleep_between_downloads = sleep_between_downloads
        
        # Validate cookies file if provided
        if self.cookies_file:
            cookie_path = Path(self.cookies_file)
            if cookie_path.exists():
                file_size = cookie_path.stat().st_size
                file_mtime = cookie_path.stat().st_mtime
                from datetime import datetime
                mod_time = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"🍪 Cookies enabled: Using authentication file")
                logger.info(f"   📁 Path: {cookie_path.resolve()}")
                logger.info(f"   📊 Size: {file_size} bytes")
                logger.info(f"   🕒 Modified: {mod_time}")
                
                # Verify file has content (read first line)
                try:
                    with open(cookie_path, 'r') as f:
                        first_line = f.readline().strip()
                        if first_line:
                            logger.info(f"   ✅ File is readable (first line: {first_line[:50]}...)")
                        else:
                            logger.warning(f"   ⚠️  File is EMPTY - this will cause bot detection errors!")
                except Exception as e:
                    logger.error(f"   ❌ Cannot read file: {e}")
            else:
                logger.warning(f"⚠️  Cookies file not found - downloads may fail due to bot detection")
                logger.warning(f"   Provided path: {self.cookies_file}")
                logger.warning(f"   Absolute path: {Path(self.cookies_file).resolve()}")
                logger.warning(f"   File does NOT exist at this location")
        else:
            logger.info("🔓 Cookies disabled: Downloads may be rate-limited or blocked")
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Stats
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self.reorganized = 0
        self.synced = 0
    
    def _sanitize_database_url(self, url: str) -> str:
        """Sanitize database URL to fix common connection issues."""
        # Strip leading/trailing whitespace from entire URL
        url = url.strip()
        
        # Remove newlines and extra whitespace within the URL
        url = re.sub(r'\s+', ' ', url).replace('\n', '').replace('\r', '')
        
        # Fix channel_binding parameter (common issue with Neon/cloud PostgreSQL)
        # Remove quotes and any whitespace around values
        if 'channel_binding=' in url:
            # First, remove any quotes and whitespace around the value
            url = re.sub(r'channel_binding=\s*["\']?\s*(require|prefer)\s*["\']?\s*', r'channel_binding=prefer', url)
            # Catch any remaining quoted values (with potential whitespace inside)
            url = re.sub(r'channel_binding=\s*["\']([^"\'\&\s]+)\s*["\']', r'channel_binding=\1', url)
        
        # Also fix sslmode if it has quotes or whitespace
        if 'sslmode=' in url:
            url = re.sub(r'sslmode=\s*["\']([^"\'\&\s]+)\s*["\']', r'sslmode=\1', url)
        
        return url
    
    def _connect_to_database(self):
        """Connect to database with helpful error handling."""
        try:
            return psycopg2.connect(self.database_url)
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            
            # Provide helpful error messages for common issues
            if 'channel_binding' in error_msg:
                logger.error("❌ Database connection failed: channel_binding error")
                logger.error("This is a common issue with Neon/cloud PostgreSQL connections.")
                logger.error("")
                logger.error("🔧 Fix: Update your connection string to use channel_binding=prefer")
                logger.error("   Or remove the channel_binding parameter entirely.")
                logger.error("")
                logger.error("Example:")
                logger.error("  Before: postgresql://user:pass@host/db?sslmode=require&channel_binding=require")
                logger.error("  After:  postgresql://user:pass@host/db?sslmode=require")
                logger.error("")
            elif 'sslmode' in error_msg:
                logger.error("❌ Database connection failed: SSL error")
                logger.error("Try using sslmode=require or sslmode=prefer")
            else:
                logger.error(f"❌ Database connection failed: {error_msg}")
            
            raise
    
    def sanitize_filename(self, text: str, max_length: int = 100) -> str:
        """Sanitize text for use in filename."""
        if not text:
            return "untitled"
        
        # Remove special characters
        text = re.sub(r'[<>:"/\\|?*]', '', text)
        
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Trim and limit length
        text = text.strip()[:max_length]
        
        return text
    
    def get_channel_dir(self, channel_title: str, channel_id: str, state_code: str = None) -> Path:
        """Get or create directory for channel, organized by state."""
        # Sanitize channel title
        safe_title = self.sanitize_filename(channel_title, max_length=50)
        
        # Organize by state if available
        if state_code:
            # Create directory: STATE/ChannelName_ChannelID
            state_dir = self.output_dir / state_code.upper()
            state_dir.mkdir(parents=True, exist_ok=True)
            dir_name = f"{safe_title}_{channel_id[:8]}"
            channel_dir = state_dir / dir_name
        else:
            # Fallback: ChannelName_ChannelID (no state)
            dir_name = f"{safe_title}_{channel_id[:8]}"
            channel_dir = self.output_dir / dir_name
        
        channel_dir.mkdir(parents=True, exist_ok=True)
        
        return channel_dir
    
    def get_output_filename(self, video: Dict, channel_dir: Path) -> Path:
        """Generate output filename: YYYY-MM-DD_title.opus"""
        # Get date prefix
        if video['event_date']:
            date_str = video['event_date'].strftime('%Y-%m-%d')
        else:
            # Try to extract date from title as fallback
            title = video['title']
            # Match patterns like "5-23-2023", "05-23-2023", "5/23/2023", "2023-05-23"
            date_patterns = [
                r'(\d{4})-(\d{1,2})-(\d{1,2})',  # 2023-05-23 or 2023-5-23
                r'(\d{1,2})-(\d{1,2})-(\d{4})',  # 5-23-2023 or 05-23-2023
                r'(\d{1,2})/(\d{1,2})/(\d{4})',  # 5/23/2023 or 05/23/2023
            ]
            
            date_str = 'unknown-date'
            for pattern in date_patterns:
                match = re.search(pattern, title)
                if match:
                    groups = match.groups()
                    try:
                        # Determine if year is first or last
                        if len(groups[0]) == 4:  # YYYY-MM-DD format
                            year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                        else:  # MM-DD-YYYY or MM/DD/YYYY format
                            month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                        
                        # Validate date
                        parsed_date = datetime(year, month, day)
                        date_str = parsed_date.strftime('%Y-%m-%d')
                        logger.debug(f"   📅 Extracted date from title: {date_str}")
                        break
                    except (ValueError, IndexError):
                        continue
            
            if date_str == 'unknown-date':
                logger.warning(f"   ⚠️  No valid date found in database or title: {title[:50]}...")
        
        # Sanitize title
        safe_title = self.sanitize_filename(video['title'], max_length=80)
        
        # Combine: YYYY-MM-DD_title.opus
        filename = f"{date_str}_{safe_title}.opus"
        
        return channel_dir / filename
    
    def get_videos_to_download(self) -> List[Dict]:
        """Query database for videos to download."""
        conn = self._connect_to_database()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build WHERE conditions
        conditions = ["video_url IS NOT NULL"]
        
        if self.channels_filter:
            # Match channel titles (case-insensitive partial match)
            channel_conditions = " OR ".join([
                f"LOWER(channel_id) LIKE LOWER('%{ch}%')" 
                for ch in self.channels_filter
            ])
            conditions.append(f"({channel_conditions})")
        
        if self.states_filter:
            states_list = "','".join(self.states_filter)
            conditions.append(f"state_code IN ('{states_list}')")
        
        if self.days_recent:
            conditions.append(f"event_date >= CURRENT_DATE - INTERVAL '{self.days_recent} days'")
        
        where_clause = " AND ".join(conditions)
        
        # Query
        query = f"""
            SELECT 
                id,
                video_id,
                video_url,
                title,
                event_date,
                channel_id,
                jurisdiction_name,
                state_code
            FROM bronze.bronze_events_youtube
            WHERE {where_clause}
            ORDER BY event_date DESC, channel_id
        """
        
        if self.limit:
            query += f" LIMIT {self.limit}"
        
        cursor.execute(query)
        videos = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return videos
    
    def download_audio(self, video: Dict, output_path: Path) -> bool:
        """Download audio from YouTube video."""
        try:
            # yt-dlp options for audio-only opus
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(output_path.with_suffix('')),  # Remove extension, yt-dlp will add it
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'opus',
                    'preferredquality': '128',
                }],
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                # Anti-bot detection measures
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'referer': 'https://www.youtube.com/',
                'http_headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Sec-Fetch-Mode': 'navigate',
                },
                # Retry on failures
                'retries': 3,
                'fragment_retries': 3,
                'skip_unavailable_fragments': False,
            }
            
            # Add cookies if provided (to avoid YouTube bot detection)
            if self.cookies_file:
                ydl_opts['cookiefile'] = self.cookies_file
                logger.debug(f"  🍪 Using cookies for authentication (bot detection bypass)")
                logger.debug(f"   Cookie file passed to yt-dlp: {self.cookies_file}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video['video_url']])
            
            return True
            
        except Exception as e:
            logger.error(f"  ✗ Download failed: {e}")
            return False
    
    def update_database_download_info(self, video_id: str, file_path: str, file_size_mb: float):
        """Update database with download timestamp and file location."""
        try:
            conn = self._connect_to_database()
            cursor = conn.cursor()
            
            # Update the bronze table with download info
            cursor.execute("""
                UPDATE bronze.bronze_events_youtube
                SET 
                    audio_downloaded_at = CURRENT_TIMESTAMP,
                    audio_file_path = %s,
                    audio_file_size_mb = %s
                WHERE video_id = %s
            """, (file_path, file_size_mb, video_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.warning(f"  ⚠️  Could not update database: {e}")
            # Don't fail the download if DB update fails
    
    def reorganize_existing_files(self):
        """Reorganize existing files from old channel-only structure to state-based structure."""
        logger.info("="*80)
        logger.info("🔄 REORGANIZING EXISTING FILES")
        logger.info("="*80)
        logger.info(f"Output directory: {self.output_dir}")
        logger.info("")
        
        # Find all existing .opus files not already in state folders
        old_structure_files = []
        
        for file_path in self.output_dir.rglob('*.opus'):
            # Check if file is in old structure (direct child of channel dir, not state dir)
            # Old: output_dir/ChannelName_ChannelID/file.opus
            # New: output_dir/STATE/ChannelName_ChannelID/file.opus
            
            relative_parts = file_path.relative_to(self.output_dir).parts
            
            # If only 2 parts (channel_dir/file.opus), it's old structure
            # If 3 parts (state/channel_dir/file.opus), it's already organized
            if len(relative_parts) == 2:
                old_structure_files.append(file_path)
        
        if not old_structure_files:
            logger.success("✅ No files to reorganize - all files are already in state-based structure")
            return
        
        logger.info(f"📁 Found {len(old_structure_files)} files in old structure")
        logger.info("")
        
        # Get channel to state mapping from database
        conn = self._connect_to_database()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT DISTINCT channel_id, state_code, jurisdiction_name
            FROM bronze.bronze_events_youtube
            WHERE state_code IS NOT NULL
        """)
        
        channel_state_map = {}
        for row in cursor.fetchall():
            channel_state_map[row['channel_id']] = {
                'state_code': row['state_code'],
                'jurisdiction_name': row['jurisdiction_name']
            }
        
        cursor.close()
        conn.close()
        
        logger.info(f"📊 Loaded state info for {len(channel_state_map)} channels")
        logger.info("")
        
        # Reorganize each file
        for old_path in old_structure_files:
            try:
                # Extract channel_id from directory name
                # Format: ChannelName_ChannelID
                channel_dir_name = old_path.parent.name
                
                # Get channel_id (last 8 chars after underscore)
                if '_' not in channel_dir_name:
                    logger.warning(f"⏭️  Skipped (invalid dir format): {channel_dir_name}")
                    continue
                
                channel_id_short = channel_dir_name.split('_')[-1]
                
                # Find matching channel_id in map
                matching_channel = None
                for full_channel_id, info in channel_state_map.items():
                    if full_channel_id.startswith(channel_id_short):
                        matching_channel = full_channel_id
                        state_code = info['state_code']
                        jurisdiction_name = info['jurisdiction_name']
                        break
                
                if not matching_channel:
                    logger.warning(f"⏭️  Skipped (channel not found in DB): {channel_dir_name}")
                    continue
                
                # Create new path with state organization
                new_channel_dir = self.get_channel_dir(
                    jurisdiction_name,
                    matching_channel,
                    state_code
                )
                new_path = new_channel_dir / old_path.name
                
                # Skip if destination already exists
                if new_path.exists():
                    logger.info(f"⏭️  Skipped (already exists): {new_path.relative_to(self.output_dir)}")
                    continue
                
                # Move file
                old_path.rename(new_path)
                
                # Update database with new path
                relative_new_path = str(new_path.relative_to(self.output_dir))
                file_size_mb = new_path.stat().st_size / (1024 * 1024)
                
                # Extract video_id from filename (need to query DB)
                conn = self._connect_to_database()
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                cursor.execute("""
                    SELECT video_id
                    FROM bronze.bronze_events_youtube
                    WHERE audio_file_path = %s
                    LIMIT 1
                """, (str(old_path.relative_to(self.output_dir)),))
                
                result = cursor.fetchone()
                if result:
                    video_id = result['video_id']
                    
                    # Update with new path
                    cursor.execute("""
                        UPDATE bronze.bronze_events_youtube
                        SET audio_file_path = %s
                        WHERE video_id = %s
                    """, (relative_new_path, video_id))
                    
                    conn.commit()
                
                cursor.close()
                conn.close()
                
                logger.success(f"✓ Moved: {old_path.name}")
                logger.info(f"  From: {old_path.relative_to(self.output_dir)}")
                logger.info(f"  To:   {new_path.relative_to(self.output_dir)}")
                self.reorganized += 1
                
            except Exception as e:
                logger.error(f"✗ Failed to reorganize {old_path.name}: {e}")
        
        # Clean up empty old directories
        for dir_path in self.output_dir.iterdir():
            if dir_path.is_dir() and len(dir_path.name) == 2:  # Skip state dirs (2-letter codes)
                continue
            
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                dir_path.rmdir()
                logger.info(f"🗑️  Removed empty directory: {dir_path.name}")
        
        logger.info("")
        logger.success("="*80)
        logger.success("REORGANIZATION COMPLETE")
        logger.success("="*80)
        logger.success(f"✓ Reorganized: {self.reorganized:,} files")
        logger.success(f"📁 Output: {self.output_dir}")
        logger.info("")
    
    def sync_metadata(self):
        """Sync metadata for existing files that don't have database records."""
        logger.info("="*80)
        logger.info("🔄 SYNCING METADATA FOR EXISTING FILES")
        logger.info("="*80)
        logger.info(f"Output directory: {self.output_dir}")
        logger.info("")
        
        # Find all existing .opus files
        all_files = list(self.output_dir.rglob('*.opus'))
        
        if not all_files:
            logger.warning("⚠️  No audio files found in output directory")
            return
        
        logger.info(f"📁 Found {len(all_files)} audio files")
        logger.info("")
        
        # Connect to database
        conn = self._connect_to_database()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all videos from database
        cursor.execute("""
            SELECT video_id, channel_id, state_code, jurisdiction_name, title, event_date
            FROM bronze.bronze_events_youtube
        """)
        
        videos = cursor.fetchall()
        videos_by_id = {v['video_id']: v for v in videos}
        
        logger.info(f"📊 Loaded {len(videos)} videos from database")
        logger.info("")
        
        # Process each file
        for file_path in all_files:
            try:
                relative_path = str(file_path.relative_to(self.output_dir))
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
                
                # Check if this file already has metadata
                cursor.execute("""
                    SELECT video_id, audio_downloaded_at, audio_file_path
                    FROM bronze.bronze_events_youtube
                    WHERE audio_file_path = %s
                """, (relative_path,))
                
                existing = cursor.fetchone()
                
                if existing and existing['audio_downloaded_at'] is not None:
                    # Already has metadata
                    continue
                
                # Try to match file to video by filename pattern
                # Expected format: YYYY-MM-DD_title.opus
                filename = file_path.stem  # Without .opus extension
                
                # Extract date from filename (YYYY-MM-DD)
                date_match = re.match(r'(\d{4}-\d{2}-\d{2})', filename)
                if not date_match:
                    logger.warning(f"⏭️  Skipped (no date in filename): {file_path.name}")
                    continue
                
                file_date = date_match.group(1)
                
                # Get state and channel from file path
                # Expected: STATE/Channel_ID/YYYY-MM-DD_title.opus
                parts = file_path.relative_to(self.output_dir).parts
                
                if len(parts) == 3:  # state/channel/file
                    state_code = parts[0]
                    channel_dir = parts[1]
                    channel_id_short = channel_dir.split('_')[-1] if '_' in channel_dir else None
                elif len(parts) == 2:  # channel/file (old structure)
                    channel_dir = parts[0]
                    channel_id_short = channel_dir.split('_')[-1] if '_' in channel_dir else None
                    state_code = None
                else:
                    logger.warning(f"⏭️  Skipped (unexpected path structure): {relative_path}")
                    continue
                
                # Find matching video in database
                matching_video = None
                for video_id, video in videos_by_id.items():
                    # Match by date and channel
                    video_date = str(video['event_date'])
                    video_channel = video['channel_id']
                    
                    if video_date == file_date:
                        # Check if channel matches
                        if channel_id_short and video_channel.startswith(channel_id_short):
                            matching_video = video
                            break
                        # Or match by state if available
                        elif state_code and video.get('state_code') == state_code:
                            # Check if title similarity is high enough
                            video_title_clean = self.sanitize_filename(video['title'])
                            if video_title_clean[:30] in filename or filename[:30] in video_title_clean:
                                matching_video = video
                                break
                
                if not matching_video:
                    logger.warning(f"⏭️  Skipped (no matching video in DB): {file_path.name}")
                    continue
                
                # Update database with metadata
                cursor.execute("""
                    UPDATE bronze.bronze_events_youtube
                    SET 
                        audio_downloaded_at = CURRENT_TIMESTAMP,
                        audio_file_path = %s,
                        audio_file_size_mb = %s
                    WHERE video_id = %s
                """, (relative_path, file_size_mb, matching_video['video_id']))
                
                conn.commit()
                
                logger.success(f"✓ Synced: {file_path.name}")
                logger.info(f"  Path: {relative_path}")
                logger.info(f"  Video ID: {matching_video['video_id']}")
                logger.info(f"  Size: {file_size_mb:.1f} MB")
                self.synced += 1
                
            except Exception as e:
                logger.error(f"✗ Failed to sync {file_path.name}: {e}")
        
        cursor.close()
        conn.close()
        
        logger.info("")
        logger.success("="*80)
        logger.success("METADATA SYNC COMPLETE")
        logger.success("="*80)
        logger.success(f"✓ Synced: {self.synced:,} files")
        logger.success(f"📁 Output: {self.output_dir}")
        logger.info("")
    
    def run(self):
        """Run the download process."""
        logger.info("=" * 80)
        logger.info("YOUTUBE AUDIO DOWNLOADER")
        logger.info("=" * 80)
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Database: {self.database_url.split('@')[1] if '@' in self.database_url else 'localhost'}")
        
        # Security: Indicate if cookies are being used (but don't log the path)
        if self.cookies_file:
            logger.info("🍪 Using browser cookies for authentication")
        
        if self.limit:
            logger.info(f"Limit: {self.limit} videos")
        if self.channels_filter:
            logger.info(f"Channels filter: {', '.join(self.channels_filter)}")
        if self.states_filter:
            logger.info(f"States filter: {', '.join(self.states_filter)}")
        
        logger.info("")
        
        # Get videos to download
        logger.info("📊 Querying database for videos...")
        videos = self.get_videos_to_download()
        logger.info(f"Found {len(videos):,} videos to process")
        logger.info("")
        
        if not videos:
            logger.warning("No videos found matching criteria")
            return
        
        # Group by channel for organization
        videos_by_channel = {}
        for video in videos:
            channel_id = video['channel_id']
            if channel_id not in videos_by_channel:
                videos_by_channel[channel_id] = {
                    'videos': [],
                    'channel_title': video['jurisdiction_name']  # Use jurisdiction as channel name
                }
            videos_by_channel[channel_id]['videos'].append(video)
        
        logger.info(f"📁 Organized into {len(videos_by_channel)} channels")
        logger.info("")
        
        # Download videos
        for channel_id, channel_data in videos_by_channel.items():
            channel_title = channel_data['channel_title']
            channel_videos = channel_data['videos']
            
            # Get state from first video (all in same channel should have same state)
            state_code = channel_videos[0].get('state_code') if channel_videos else None
            
            logger.info(f"📺 Channel: {channel_title} ({len(channel_videos)} videos)")
            
            # Create channel directory (organized by state)
            channel_dir = self.get_channel_dir(channel_title, channel_id, state_code)
            logger.info(f"   Directory: {channel_dir}")
            
            # Download each video
            for i, video in enumerate(channel_videos, 1):
                output_path = self.get_output_filename(video, channel_dir)
                
                # Check if already exists
                if self.skip_existing and output_path.exists():
                    logger.info(f"   [{i}/{len(channel_videos)}] ⏭️  Skipped (exists): {output_path.name}")
                    self.skipped += 1
                    continue
                
                logger.info(f"   [{i}/{len(channel_videos)}] ⬇️  Downloading: {video['title'][:60]}...")
                
                # Download
                success = self.download_audio(video, output_path)
                
                if success:
                    file_size = output_path.stat().st_size / (1024 * 1024)  # MB
                    logger.success(f"   ✓ Downloaded: {output_path.name} ({file_size:.1f} MB)")
                    self.downloaded += 1
                    
                    # Update database with download info
                    relative_path = str(output_path.relative_to(self.output_dir))
                    self.update_database_download_info(video['video_id'], relative_path, file_size)
                    
                    # Throttle to avoid rate limiting (add random jitter to look more human)
                    if self.sleep_between_downloads > 0 and i < len(channel_videos):
                        jitter = random.uniform(0.5, 1.5)  # ±50% random variance
                        sleep_time = self.sleep_between_downloads * jitter
                        logger.debug(f"   😴 Sleeping {sleep_time:.1f}s to avoid rate limiting...")
                        time.sleep(sleep_time)
                else:
                    logger.error(f"   ✗ Failed: {video['title'][:60]}")
                    self.failed += 1
            
            logger.info("")
        
        # Summary
        logger.success("=" * 80)
        logger.success("DOWNLOAD COMPLETE")
        logger.success("=" * 80)
        logger.success(f"✓ Downloaded: {self.downloaded:,}")
        logger.success(f"⏭️  Skipped (existing): {self.skipped:,}")
        logger.success(f"✗ Failed: {self.failed:,}")
        logger.success(f"📁 Output: {self.output_dir}")
        logger.info("")
        
        # List channel directories (STATE/Channel/ structure)
        channel_dirs = sorted([
            d for d in self.output_dir.rglob('*')
            if d.is_dir() and d.parent != self.output_dir and d.parent.parent == self.output_dir
        ])
        # Fall back to top-level dirs if no nested structure found
        if not channel_dirs:
            channel_dirs = sorted([d for d in self.output_dir.iterdir() if d.is_dir()])
        if channel_dirs:
            logger.info(f"📂 Channel directories ({len(channel_dirs)} total):")
            for d in channel_dirs:
                file_count = len(list(d.glob('*.opus')))
                state = d.parent.name if d.parent != self.output_dir else ''
                label = f"{state}/{d.name}" if state else d.name
                logger.info(f"   • {label} ({file_count} files)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download YouTube audio from bronze_events_youtube to Google Drive"
    )
    
    parser.add_argument(
        '--output-dir',
        default='/content/drive/MyDrive/CommunityOne/youtube_audio',
        help='Output directory for audio files (default: Google Drive path for Colab)'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of videos to download'
    )
    
    parser.add_argument(
        '--channels',
        help='Comma-separated list of channel names to filter (partial match)'
    )
    
    parser.add_argument(
        '--states',
        help='Comma-separated list of state codes (e.g., AL,MA,WI)'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        help='Only download videos from last N days'
    )
    
    parser.add_argument(
        '--no-skip-existing',
        action='store_true',
        help='Re-download files even if they already exist'
    )
    
    parser.add_argument(
        '--reorganize',
        action='store_true',
        help='Reorganize existing files from old channel-only structure to new state-based structure'
    )
    
    parser.add_argument(
        '--sync-metadata',
        action='store_true',
        help='Sync metadata for existing files that are missing database records'
    )
    
    parser.add_argument(
        '--database-url',
        default=os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator'),
        help='Database connection URL'
    )
    
    parser.add_argument(
        '--cookies',
        help='Path to Netscape cookies file (to avoid YouTube bot detection). Export from browser using extension.'
    )
    
    parser.add_argument(
        '--sleep',
        type=float,
        default=2.0,
        help='Seconds to sleep between downloads (default: 2.0, with random jitter). Set to 0 to disable throttling.'
    )
    
    args = parser.parse_args()

    # File logger: one rotating log per output directory, kept for 7 days
    log_dir = Path(args.output_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "download_{time:YYYY-MM-DD}.log",
        rotation="00:00",       # new file each day
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
        encoding="utf-8",
    )

    # Show startup configuration for debugging
    logger.info("=" * 80)
    logger.info("🚀 YouTube Audio Downloader - Startup Configuration")
    logger.info("=" * 80)
    logger.info(f"📁 Output directory: {args.output_dir}")
    logger.info(f"🎯 Limit: {args.limit if args.limit else 'No limit'}")
    logger.info(f"📺 Channels filter: {args.channels if args.channels else 'All channels'}")
    logger.info(f"🗺️  States filter: {args.states if args.states else 'All states'}")
    logger.info(f"📅 Days recent: {args.days if args.days else 'All time'}")
    logger.info(f"⏭️  Skip existing: {not args.no_skip_existing}")
    logger.info(f"📂 Reorganize mode: {args.reorganize}")
    logger.info(f"🔄 Sync metadata mode: {args.sync_metadata}")
    
    # Check cookies file with size info
    if args.cookies:
        cookie_path = Path(args.cookies)
        if cookie_path.exists():
            file_size = cookie_path.stat().st_size
            logger.info(f"🍪 Cookies: ✅ PROVIDED: {args.cookies} ({file_size} bytes)")
        else:
            logger.info(f"🍪 Cookies: ⚠️  PROVIDED BUT FILE NOT FOUND: {args.cookies}")
    else:
        logger.info(f"🍪 Cookies: ❌ NOT PROVIDED (may trigger bot detection)")
    
    logger.info(f"� Throttling: {args.sleep}s between downloads (with random jitter)" if args.sleep > 0 else "⚡ Throttling: DISABLED (may trigger rate limiting)")
    logger.info(f"�🗄️  Database: {args.database_url[:50]}..." if len(args.database_url) > 50 else args.database_url)
    logger.info("=" * 80)
    
    # Parse filters
    channels_filter = args.channels.split(',') if args.channels else None
    states_filter = args.states.split(',') if args.states else None
    
    # Create downloader
    downloader = YouTubeAudioDownloader(
        database_url=args.database_url,
        output_dir=args.output_dir,
        limit=args.limit,
        channels_filter=channels_filter,
        states_filter=states_filter,
        days_recent=args.days,
        skip_existing=not args.no_skip_existing,
        reorganize=args.reorganize,
        cookies_file=args.cookies,
        sleep_between_downloads=args.sleep
    )
    
    # Run reorganization if requested
    if args.reorganize:
        downloader.reorganize_existing_files()
    elif args.sync_metadata:
        downloader.sync_metadata()
    else:
        # Run normal download
        downloader.run()


if __name__ == '__main__':
    main()
