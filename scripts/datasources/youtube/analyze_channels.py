#!/usr/bin/env python3
"""
Analyze YouTube Channels in intermediate.int_events_channels_enriched

This script helps identify junk channels and provides statistics
about channel sources and quality.

Usage:
    python scripts/datasources/youtube/analyze_channels.py
    python scripts/datasources/youtube/analyze_channels.py --flag-junk
"""
import os
import argparse
from typing import List, Dict
import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')

# Patterns that indicate non-government channels
JUNK_PATTERNS = [
    'cnn', 'fox news', 'msnbc', 'nbc news', 'abc news', 'cbs news',
    '- topic', 'vevo', 'music',
    'last week tonight', 'john oliver', 'daily show', 'stephen colbert',
    'hamilton', 'broadway', 'lin-manuel', 'cast recording',
    'bernie sanders', 'adam kinzinger', 'elizabeth',
    'usao', 'u.s. attorney',
    'debate central', 'american network news',
    'point of view', 'radio talk show',
    'dialogue initiatives', 'b.r.i.c.s.',
]


def get_channel_statistics(conn) -> Dict:
    """Get statistics about channels."""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    stats = {}
    
    # Total channels
    cursor.execute("SELECT COUNT(*) as total FROM intermediate.int_events_channels_enriched")
    stats['total_channels'] = cursor.fetchone()['total']
    
    # Channels in LocalView
    cursor.execute("SELECT COUNT(*) as count FROM intermediate.int_events_channels_enriched WHERE in_localview = TRUE")
    stats['in_localview'] = cursor.fetchone()['count']
    
    # Channels in jurisdictions_details
    cursor.execute("SELECT COUNT(*) as count FROM intermediate.int_events_channels_enriched WHERE in_jurisdictions_details = TRUE")
    stats['in_jurisdictions_details'] = cursor.fetchone()['count']
    
    # Flagged as junk
    cursor.execute("SELECT COUNT(*) as count FROM intermediate.int_events_channels_enriched WHERE flagged_as_junk = TRUE")
    stats['flagged_as_junk'] = cursor.fetchone()['count']
    
    # Confirmed government
    cursor.execute("SELECT COUNT(*) as count FROM intermediate.int_events_channels_enriched WHERE is_government = TRUE")
    stats['confirmed_government'] = cursor.fetchone()['count']
    
    # Confirmed NOT government
    cursor.execute("SELECT COUNT(*) as count FROM intermediate.int_events_channels_enriched WHERE is_government = FALSE")
    stats['confirmed_not_government'] = cursor.fetchone()['count']
    
    # By channel type
    cursor.execute("""
        SELECT channel_type, COUNT(*) as count 
        FROM intermediate.int_events_channels_enriched 
        GROUP BY channel_type 
        ORDER BY count DESC
    """)
    stats['by_type'] = cursor.fetchall()
    
    cursor.close()
    return stats


def identify_junk_channels(conn) -> List[Dict]:
    """Identify channels that match junk patterns."""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Build query to find channels matching junk patterns
    pattern_conditions = " OR ".join([f"LOWER(channel_title) LIKE LOWER('%{pattern}%')" for pattern in JUNK_PATTERNS])
    
    query = f"""
        SELECT 
            channel_id,
            channel_title,
            channel_type,
            channel_url,
            in_localview,
            flagged_as_junk,
            is_government,
            jurisdictions
        FROM intermediate.int_events_channels_enriched
        WHERE ({pattern_conditions})
          AND flagged_as_junk = FALSE
          AND (is_government IS NULL OR is_government = FALSE)
        ORDER BY channel_title
    """
    
    cursor.execute(query)
    channels = cursor.fetchall()
    cursor.close()
    
    return channels


def flag_channel_as_junk(conn, channel_id: str, reason: str):
    """Flag a channel as junk."""
    cursor = conn.cursor()
    
    # Writes go to the base table (the _enriched form is a VIEW and not writable).
    cursor.execute("""
        UPDATE intermediate.int_events_channels
        SET
            flagged_as_junk = TRUE,
            is_government = FALSE,
            flag_reason = %s,
            last_updated = CURRENT_TIMESTAMP
        WHERE channel_id = %s
    """, (reason, channel_id))
    
    conn.commit()
    cursor.close()


def main():
    parser = argparse.ArgumentParser(description='Analyze YouTube channels')
    parser.add_argument('--flag-junk', action='store_true', help='Flag identified junk channels')
    parser.add_argument('--show-junk', action='store_true', help='Show potential junk channels')
    args = parser.parse_args()
    
    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)
    logger.info(f"Connected to database: {DATABASE_URL.split('@')[1]}")
    
    # Get statistics
    stats = get_channel_statistics(conn)
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("CHANNEL STATISTICS")
    logger.info("=" * 80)
    logger.info(f"Total channels: {stats['total_channels']:,}")
    logger.info(f"  In LocalView: {stats['in_localview']:,}")
    logger.info(f"  In jurisdictions_details: {stats['in_jurisdictions_details']:,}")
    logger.info(f"  Flagged as junk: {stats['flagged_as_junk']:,}")
    logger.info(f"  Confirmed government: {stats['confirmed_government']:,}")
    logger.info(f"  Confirmed NOT government: {stats['confirmed_not_government']:,}")
    logger.info("")
    logger.info("By channel type:")
    for row in stats['by_type']:
        logger.info(f"  {row['channel_type']:15s}: {row['count']:,}")
    
    # Identify potential junk
    junk_channels = identify_junk_channels(conn)
    logger.info("")
    logger.info(f"Potential junk channels identified: {len(junk_channels):,}")
    
    if args.show_junk or args.flag_junk:
        logger.info("")
        logger.info("=" * 80)
        logger.info("POTENTIAL JUNK CHANNELS")
        logger.info("=" * 80)
        
        for channel in junk_channels:
            logger.info(f"\nChannel: {channel['channel_title']}")
            logger.info(f"  ID: {channel['channel_id']}")
            logger.info(f"  URL: {channel['channel_url']}")
            logger.info(f"  Type: {channel['channel_type']}")
            logger.info(f"  In LocalView: {channel['in_localview']}")
            
            if channel['jurisdictions']:
                import json
                jurisdictions = json.loads(channel['jurisdictions']) if isinstance(channel['jurisdictions'], str) else channel['jurisdictions']
                logger.info(f"  Jurisdictions: {', '.join([j['jurisdiction_name'] for j in jurisdictions])}")
    
    # Flag channels if requested
    if args.flag_junk:
        logger.info("")
        logger.info(f"Flagging {len(junk_channels)} channels as junk...")
        
        for channel in junk_channels:
            # Determine reason based on title
            title_lower = channel['channel_title'].lower()
            
            if any(word in title_lower for word in ['cnn', 'fox', 'msnbc', 'nbc', 'abc', 'cbs']):
                reason = 'News channel, not government'
            elif '- topic' in title_lower:
                reason = 'YouTube auto-generated topic channel'
            elif any(word in title_lower for word in ['hamilton', 'broadway']):
                reason = 'Entertainment/musical content'
            elif any(word in title_lower for word in ['sanders', 'kinzinger']):
                reason = 'Political figure, not municipal government'
            else:
                reason = 'Non-government channel identified by pattern matching'
            
            flag_channel_as_junk(conn, channel['channel_id'], reason)
            logger.info(f"  ✓ Flagged: {channel['channel_title']} - {reason}")
        
        logger.success(f"\n✓ Flagged {len(junk_channels)} channels as junk")
        
        # Re-run statistics
        stats = get_channel_statistics(conn)
        logger.info(f"\nUpdated statistics:")
        logger.info(f"  Flagged as junk: {stats['flagged_as_junk']:,}")
    
    conn.close()


if __name__ == '__main__':
    main()
