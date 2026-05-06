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
        reorganize: bool = False
    ):
        self.database_url = database_url
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.channels_filter = channels_filter
        self.states_filter = states_filter
        self.days_recent = days_recent
        self.skip_existing = skip_existing
        self.reorganize = reorganize
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Stats
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self.reorganized = 0
        self.synced = 0
    
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
            date_str = 'unknown-date'
        
        # Sanitize title
        safe_title = self.sanitize_filename(video['title'], max_length=80)
        
        # Combine: YYYY-MM-DD_title.opus
        filename = f"{date_str}_{safe_title}.opus"
        
        return channel_dir / filename
    
    def get_videos_to_download(self) -> List[Dict]:
        """Query database for videos to download."""
        conn = psycopg2.connect(self.database_url)
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
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video['video_url']])
            
            return True
            
        except Exception as e:
            logger.error(f"  ✗ Download failed: {e}")
            return False
    
    def update_database_download_info(self, video_id: str, file_path: str, file_size_mb: float):
        """Update database with download timestamp and file location."""
        try:
            conn = psycopg2.connect(self.database_url)
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
        conn = psycopg2.connect(self.database_url)
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
                conn = psycopg2.connect(self.database_url)
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
        conn = psycopg2.connect(self.database_url)
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
        
        # List directories created
        dirs = sorted([d for d in self.output_dir.iterdir() if d.is_dir()])
        if dirs:
            logger.info(f"📂 Created {len(dirs)} channel directories:")
            for d in dirs[:10]:  # Show first 10
                file_count = len(list(d.glob('*.opus')))
                logger.info(f"   • {d.name} ({file_count} files)")
            if len(dirs) > 10:
                logger.info(f"   ... and {len(dirs) - 10} more")


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
    
    args = parser.parse_args()
    
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
        reorganize=args.reorganize
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
