#!/usr/bin/env python3
"""
Extract Transcripts from YouTube Videos

Downloads captions/transcripts from YouTube videos and saves to text files.

Usage:
    # Extract from all videos in cache
    python scripts/localview/extract_transcripts.py
    
    # Extract from specific videos
    python scripts/localview/extract_transcripts.py --video-ids "abc123,def456"
    
    # Extract from recent videos only
    python scripts/localview/extract_transcripts.py --year 2026
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger
import polars as pl
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

# Configure logger
logger.add(sys.stderr, format="{time} {level} {message}", level="INFO")


class TranscriptExtractor:
    """Extract transcripts from YouTube videos"""
    
    def __init__(self):
        self.cache_dir = Path("data/cache/localview")
        self.transcript_dir = self.cache_dir / "transcripts"
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
    
    def load_videos(self, year: Optional[int] = None) -> pl.DataFrame:
        """Load videos from cache"""
        if year:
            video_file = self.cache_dir / f"videos_{year}.csv"
            if not video_file.exists():
                logger.error(f"Video file not found: {video_file}")
                return pl.DataFrame()
            return pl.read_csv(video_file)
        else:
            # Load all years
            all_videos = []
            for video_file in self.cache_dir.glob("videos_*.csv"):
                df = pl.read_csv(video_file)
                all_videos.append(df)
            
            if not all_videos:
                logger.error(f"No video files found in {self.cache_dir}")
                return pl.DataFrame()
            
            return pl.concat(all_videos)
    
    def extract_transcript(self, video_id: str) -> Optional[dict]:
        """
        Extract transcript from a YouTube video
        
        Returns:
            Dict with 'text' (full transcript) and 'segments' (timestamped)
        """
        try:
            # Get transcript (tries auto-generated if manual not available)
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            
            # Combine into full text
            full_text = ' '.join([segment['text'] for segment in transcript_list])
            
            return {
                'text': full_text,
                'segments': transcript_list
            }
        
        except TranscriptsDisabled:
            logger.debug(f"Transcripts disabled for {video_id}")
            return None
        except NoTranscriptFound:
            logger.debug(f"No transcript found for {video_id}")
            return None
        except Exception as e:
            logger.error(f"Error extracting transcript for {video_id}: {e}")
            return None
    
    def save_transcript(self, video_id: str, transcript: dict, metadata: dict = None):
        """Save transcript to text file"""
        # Save plain text
        text_file = self.transcript_dir / f"{video_id}.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(transcript['text'])
        
        # Save segments with timestamps as JSON
        json_file = self.transcript_dir / f"{video_id}.json"
        data = {
            'video_id': video_id,
            'segments': transcript['segments']
        }
        
        if metadata:
            data['metadata'] = metadata
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def process_videos(
        self,
        videos_df: pl.DataFrame,
        video_ids: Optional[List[str]] = None
    ) -> dict:
        """
        Process videos and extract transcripts
        
        Returns:
            Statistics dict with counts
        """
        stats = {
            'total': 0,
            'extracted': 0,
            'failed': 0,
            'skipped': 0
        }
        
        for row in videos_df.iter_rows(named=True):
            video_id = row.get('video_id')
            
            if not video_id:
                continue
            
            # Filter by video_ids if specified
            if video_ids and video_id not in video_ids:
                continue
            
            stats['total'] += 1
            
            # Check if already extracted
            text_file = self.transcript_dir / f"{video_id}.txt"
            if text_file.exists():
                logger.debug(f"Skipping {video_id} (already extracted)")
                stats['skipped'] += 1
                continue
            
            # Check if captions available
            if not row.get('has_captions', False):
                logger.debug(f"Skipping {video_id} (no captions)")
                stats['skipped'] += 1
                continue
            
            logger.info(f"Extracting transcript for {video_id} ({row.get('municipality')})")
            
            # Extract transcript
            transcript = self.extract_transcript(video_id)
            
            if transcript:
                # Save transcript
                metadata = {
                    'municipality': row.get('municipality'),
                    'meeting_date': row.get('meeting_date'),
                    'meeting_type': row.get('meeting_type'),
                    'video_url': row.get('video_url')
                }
                
                self.save_transcript(video_id, transcript, metadata)
                stats['extracted'] += 1
                logger.success(f"  ✅ Extracted {len(transcript['text'])} characters")
            else:
                stats['failed'] += 1
        
        return stats


def main():
    parser = argparse.ArgumentParser(
        description="Extract transcripts from YouTube videos"
    )
    parser.add_argument(
        '--video-ids',
        type=str,
        help='Comma-separated video IDs to process'
    )
    parser.add_argument(
        '--year',
        type=int,
        help='Process videos from specific year only'
    )
    
    args = parser.parse_args()
    
    # Parse video IDs
    video_ids = None
    if args.video_ids:
        video_ids = [v.strip() for v in args.video_ids.split(',')]
    
    # Initialize extractor
    logger.info("=" * 80)
    logger.info("TRANSCRIPT EXTRACTION")
    logger.info("=" * 80)
    
    extractor = TranscriptExtractor()
    
    # Load videos
    logger.info(f"\n📖 Loading videos...")
    videos_df = extractor.load_videos(year=args.year)
    
    if len(videos_df) == 0:
        logger.error("No videos found")
        sys.exit(1)
    
    logger.info(f"   Found {len(videos_df)} videos")
    
    # Process videos
    logger.info(f"\n🎬 Extracting transcripts...")
    stats = extractor.process_videos(videos_df, video_ids=video_ids)
    
    # Show results
    logger.info("\n" + "=" * 80)
    logger.info("RESULTS")
    logger.info("=" * 80)
    logger.info(f"Total videos: {stats['total']}")
    logger.info(f"✅ Extracted: {stats['extracted']}")
    logger.info(f"⏭️  Skipped: {stats['skipped']}")
    logger.info(f"❌ Failed: {stats['failed']}")
    
    logger.info(f"\n💾 Transcripts saved to: {extractor.transcript_dir}")


if __name__ == "__main__":
    main()
