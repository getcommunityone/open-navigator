#!/usr/bin/env python3
"""
Backfill transcripts for YouTube events that don't have them yet.

This script:
1. Finds all YouTube events in event that don't have transcripts
2. Fetches transcripts (with timing data) for those videos
3. Inserts them into events_text_search table

Usage:
    # Backfill all missing transcripts
    python packages/scrapers/src/scrapers/youtube/backfill_transcripts.py
    
    # Limit to specific states
    python packages/scrapers/src/scrapers/youtube/backfill_transcripts.py --states AL,MA,WI
    
    # Limit number of transcripts to fetch
    python packages/scrapers/src/scrapers/youtube/backfill_transcripts.py --limit 100
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')


def extract_video_id_from_url(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL."""
    if not url:
        return None
    
    # Handle various YouTube URL formats
    if 'youtube.com/watch?v=' in url:
        return url.split('watch?v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    elif '/embed/' in url:
        return url.split('/embed/')[1].split('?')[0]
    
    return None


def fetch_transcript_simple(video_id: str) -> Optional[Dict[str, Any]]:
    """Simplified transcript fetching without loader initialization."""
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
    import yt_dlp
    import requests
    import re
    
    if not video_id:
        return None
    
    # Try youtube_transcript_api first
    try:
        api = YouTubeTranscriptApi()
        
        try:
            fetched_transcript = api.fetch(video_id, languages=['en'])
            language = 'en'
            is_auto = fetched_transcript.is_generated
        except NoTranscriptFound:
            try:
                transcript_list = api.list(video_id)
                available = list(transcript_list)
                if not available:
                    raise NoTranscriptFound(video_id)
                first_transcript = available[0]
                fetched_transcript = first_transcript.fetch()
                language = first_transcript.language_code
                is_auto = first_transcript.is_generated
            except:
                raise NoTranscriptFound(video_id)
        
        raw_text = ' '.join([snippet.text for snippet in fetched_transcript.snippets])
        segments = [
            {'text': snippet.text, 'start': snippet.start, 'duration': snippet.duration}
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
        
    except (TranscriptsDisabled, VideoUnavailable):
        return None
    except Exception as e:
        # Check for rate limiting - re-raise to handle in caller
        error_msg = str(e)
        if '429' in error_msg or 'Too Many Requests' in error_msg:
            raise  # Re-raise rate limit errors
        # Try yt-dlp fallback for other errors
        try:
            ydl_opts = {
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en'],
                'quiet': True,
                'no_warnings': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=False)
                
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
                            line
                        )
                        
                        if timestamp_match:
                            start_str = timestamp_match.group(1)
                            end_str = timestamp_match.group(2)
                            
                            def timestamp_to_seconds(ts):
                                h, m, s = ts.split(':')
                                return int(h) * 3600 + int(m) * 60 + float(s)
                            
                            start = timestamp_to_seconds(start_str)
                            end = timestamp_to_seconds(end_str)
                            duration = end - start
                            
                            i += 1
                            text_lines = []
                            while i < len(lines):
                                text_line = lines[i].strip()
                                if not text_line or '-->' in text_line or text_line.startswith('WEBVTT'):
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
                                    'duration': duration
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
                    'transcript_source': 'yt-dlp'
                }
                
        except Exception as e:
            # Check for rate limiting - re-raise to handle in caller
            error_msg = str(e)
            if '429' in error_msg or 'Too Many Requests' in error_msg:
                raise  # Re-raise rate limit errors
            return None  # Other errors - no transcript available


def get_events_missing_transcripts(conn, states: Optional[List[str]] = None, limit: Optional[int] = None) -> List[Dict]:
    """Get all YouTube events that don't have transcripts yet."""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Build query to find videos without transcripts.
        # int_events_union merges every event source that carries a meeting
        # video URL (event mart + LocalView), deduped to one row per video_id.
        # Anti-join the bronze transcript landing on video_id to skip videos
        # whose transcript is already landed.
        query = """
            SELECT
                u.event_id,
                u.video_url,
                u.event_title,
                u.jurisdiction_name,
                u.state_code
            FROM intermediate.int_events_union u
            LEFT JOIN bronze.bronze_events_text_ai t ON t.video_id = u.video_id
            WHERE u.video_url IS NOT NULL
              AND t.id IS NULL  -- No transcript landed yet
        """

        params = []

        if states:
            placeholders = ','.join(['%s'] * len(states))
            query += f" AND u.state_code IN ({placeholders})"
            params.extend(states)

        # Newest meetings first: recent uploads are far more likely to carry
        # (auto-)captions than decades-old municipal videos, so this maximises
        # the transcript hit-rate under --limit.
        query += " ORDER BY u.event_date DESC NULLS LAST, u.event_id ASC"
        
        if limit:
            query += " LIMIT %s"
            params.append(limit)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        return [dict(row) for row in results]
        
    finally:
        cursor.close()


def backfill_transcripts(
    database_url: str,
    youtube_api_key: Optional[str] = None,
    states: Optional[List[str]] = None,
    limit: Optional[int] = None
):
    """Backfill missing transcripts for YouTube events."""
    
    # Connect to database
    conn = psycopg2.connect(database_url)
    
    try:
        # Get events missing transcripts
        logger.info("Finding YouTube events without transcripts...")
        events = get_events_missing_transcripts(conn, states=states, limit=limit)
        
        if not events:
            logger.success("✓ All YouTube events already have transcripts!")
            return
        
        logger.info(f"Found {len(events)} events missing transcripts")
        
        # Import transcript fetching functions directly (avoid loader initialization which creates tables/indexes)
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
        import yt_dlp
        import requests
        import re
        
        # Process each event
        inserted = 0
        failed = 0
        rate_limited = 0
        consecutive_rate_limits = 0
        max_backoff = 60  # Maximum 60 seconds backoff
        base_delay = 2.0  # 2 seconds between fetches
        
        import time
        
        for i, event in enumerate(events, 1):
            # Progressive delay based on rate limit history
            if consecutive_rate_limits > 0:
                # Exponential backoff: 2s, 4s, 8s, 16s, 32s, 60s (max)
                backoff_delay = min(base_delay * (2 ** consecutive_rate_limits), max_backoff)
                logger.warning(f"  ⏱️  Backing off {backoff_delay:.1f}s due to {consecutive_rate_limits} consecutive rate limits...")
                time.sleep(backoff_delay)
            elif i > 1:
                time.sleep(base_delay)  # Normal delay between requests
            event_id = event['event_id']
            video_url = event['video_url']
            title = event['event_title']
            jurisdiction = event['jurisdiction_name']
            state = event['state_code']
            
            # Extract video ID
            video_id = extract_video_id_from_url(video_url)
            
            if not video_id:
                logger.warning(f"[{i}/{len(events)}] Could not extract video ID from: {video_url}")
                failed += 1
                continue
            
            logger.info(f"[{i}/{len(events)}] Fetching transcript for: {jurisdiction}, {state} - {title[:50]}...")
            logger.debug(f"  Video ID: {video_id}, Event ID: {event_id}")
            
            # Fetch transcript (inline - avoid loader initialization)
            try:
                transcript_data = fetch_transcript_simple(video_id)
                if transcript_data:
                    consecutive_rate_limits = 0  # Reset on success
            except Exception as e:
                error_msg = str(e)
                if '429' in error_msg or 'Too Many Requests' in error_msg:
                    rate_limited += 1
                    consecutive_rate_limits += 1
                    logger.warning(f"  ⚠️  Rate limited! ({rate_limited} total, {consecutive_rate_limits} consecutive)")
                    if consecutive_rate_limits >= 5:
                        logger.error(f"  ❌ Too many consecutive rate limits ({consecutive_rate_limits}), stopping")
                        break
                    failed += 1
                    continue
                else:
                    logger.warning(f"  ⊘ No transcript available: {error_msg[:100]}")
                    failed += 1
                    continue
            
            if transcript_data:
                # Insert transcript
                cursor = conn.cursor()
                
                try:
                    import json
                    
                    # Prepare data
                    transcript_data['event_id'] = event_id
                    
                    # Convert segments list to JSON string
                    if 'segments' in transcript_data and transcript_data['segments']:
                        transcript_data['segments'] = json.dumps(transcript_data['segments'])
                    else:
                        transcript_data['segments'] = None
                    
                    insert_query = """
                        INSERT INTO bronze.bronze_events_text_ai (
                            event_id, video_id, raw_text, segments, language,
                            is_auto_generated, transcript_source
                        ) VALUES (
                            %(event_id)s, %(video_id)s, %(raw_text)s, %(segments)s::jsonb, %(language)s,
                            %(is_auto_generated)s, %(transcript_source)s
                        )
                        ON CONFLICT (video_id) DO UPDATE SET
                            raw_text = EXCLUDED.raw_text,
                            segments = EXCLUDED.segments,
                            language = EXCLUDED.language,
                            is_auto_generated = EXCLUDED.is_auto_generated,
                            transcript_source = EXCLUDED.transcript_source
                    """
                    
                    cursor.execute(insert_query, transcript_data)
                    conn.commit()
                    
                    inserted += 1
                    logger.success(f"  ✓ Inserted transcript ({len(transcript_data.get('segments', '[]'))} segments)")
                    
                    # Commit every 10 transcripts
                    if inserted % 10 == 0:
                        logger.info(f"Progress: {inserted}/{len(events)} transcripts inserted")
                    
                except Exception as e:
                    conn.rollback()
                    error_msg = str(e)
                    if '429' in error_msg or 'Too Many Requests' in error_msg:
                        logger.warning(f"  ✗ Rate limited during insert: {error_msg[:100]}")
                        rate_limited += 1
                        consecutive_rate_limits += 1
                        time.sleep(5)  # Longer pause after rate limit
                    else:
                        logger.error(f"  ✗ Error inserting transcript: {e}")
                    failed += 1
                finally:
                    cursor.close()
            else:
                logger.warning(f"  ⊘ No transcript available")
                failed += 1
        
        # Summary
        logger.info("")
        logger.success("=" * 80)
        logger.success("✓ BACKFILL COMPLETE")
        logger.success("=" * 80)
        logger.success(f"Transcripts inserted: {inserted}")
        logger.success(f"Failed/unavailable: {failed}")
        if rate_limited > 0:
            logger.warning(f"Rate limited: {rate_limited} (consider reducing concurrency)")
        logger.success(f"Total processed: {len(events)}")
        
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Backfill transcripts for YouTube events')
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated list of state codes (e.g., AL,MA,WI)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of transcripts to fetch'
    )
    
    args = parser.parse_args()
    
    # Parse states
    states = None
    if args.states:
        states = [s.strip().upper() for s in args.states.split(',')]
        logger.info(f"Filtering to states: {', '.join(states)}")
    
    # Run backfill
    backfill_transcripts(
        database_url=DATABASE_URL,
        youtube_api_key=YOUTUBE_API_KEY,
        states=states,
        limit=args.limit
    )


if __name__ == '__main__':
    main()
