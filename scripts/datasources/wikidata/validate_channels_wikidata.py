#!/usr/bin/env python3
"""
Validate YouTube Channels against WikiData

Uses existing jurisdictions from public.c1_jurisdiction and validates
their YouTube channels against WikiData. Updates intermediate.int_events_channels_registry with
in_wikidata flags.

This is faster than querying all WikiData jurisdictions because we only
check the jurisdictions we already know about.

Usage:
    python scripts/datasources/wikidata/validate_channels_wikidata.py --states AL,GA,IN,MA,MT,WA,WI
    
    python scripts/datasources/wikidata/validate_channels_wikidata.py --states AL --limit 10
"""
import os
import sys
import argparse
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from scripts.datasources.wikidata.wikidata_integration import WikidataQuery

load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')


class WikiDataChannelValidator:
    """Validate YouTube channels against WikiData."""
    
    def __init__(self, database_url: str):
        self.conn = psycopg2.connect(database_url)
        self.wikidata = WikidataQuery()
    
    def get_jurisdictions(self, states_filter: Optional[List[str]] = None, limit: Optional[int] = None) -> List[Dict]:
        """Get jurisdictions from database."""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                jurisdiction_id,
                name AS jurisdiction_name,
                state_code,
                state,
                type AS jurisdiction_type,
                youtube_channels
            FROM c1_jurisdiction
            WHERE youtube_channel_count > 0
                AND youtube_channels IS NOT NULL
        """
        
        params = []
        if states_filter:
            query += " AND state_code = ANY(%s)"
            params.append(states_filter)
        
        query += " ORDER BY state_code, jurisdiction_name"
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, params)
        jurisdictions = cursor.fetchall()
        cursor.close()
        
        logger.info(f"Found {len(jurisdictions)} jurisdictions to validate")
        return jurisdictions
    
    async def validate_jurisdiction(self, jurisdiction: Dict) -> Dict:
        """Validate a jurisdiction's YouTube channels against WikiData."""
        jurisdiction_name = jurisdiction['jurisdiction_name']
        state_code = jurisdiction['state_code']
        jurisdiction_type = jurisdiction['jurisdiction_type']
        
        try:
            # Query WikiData for this jurisdiction
            wikidata_info = await self.wikidata.get_jurisdiction_info(
                name=jurisdiction_name,
                state=state_code,
                jurisdiction_type=jurisdiction_type
            )
            
            if not wikidata_info:
                return {
                    'jurisdiction_id': jurisdiction['jurisdiction_id'],
                    'jurisdiction_name': jurisdiction_name,
                    'wikidata_found': False,
                    'youtube_channel_id': None,
                    'official_website': None
                }
            
            return {
                'jurisdiction_id': jurisdiction['jurisdiction_id'],
                'jurisdiction_name': jurisdiction_name,
                'wikidata_found': True,
                'wikidata_id': wikidata_info.get('wikidata_id'),
                'youtube_channel_id': wikidata_info.get('youtube_channel_id'),
                'official_website': wikidata_info.get('website'),
                'facebook': wikidata_info.get('facebook'),
                'twitter': wikidata_info.get('twitter'),
                'population': wikidata_info.get('population')
            }
            
        except Exception as e:
            logger.debug(f"Error validating {jurisdiction_name}: {e}")
            return {
                'jurisdiction_id': jurisdiction['jurisdiction_id'],
                'jurisdiction_name': jurisdiction_name,
                'wikidata_found': False,
                'error': str(e)
            }
    
    def update_channel_wikidata_flag(self, channel_id: str, in_wikidata: bool):
        """Update in_wikidata flag for a channel."""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE intermediate.int_events_channels_registry
                SET 
                    in_wikidata = %s,
                    is_government = CASE 
                        WHEN %s = TRUE THEN TRUE
                        ELSE is_government
                    END,
                    last_updated = CURRENT_TIMESTAMP
                WHERE channel_id = %s
            """, (in_wikidata, in_wikidata, channel_id))
            
            self.conn.commit()
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error updating channel {channel_id}: {e}")
        finally:
            cursor.close()
    
    async def validate_all(self, states_filter: Optional[List[str]] = None, limit: Optional[int] = None):
        """Validate all jurisdictions."""
        logger.info("")
        logger.info("=" * 80)
        logger.info("WIKIDATA CHANNEL VALIDATION")
        logger.info("=" * 80)
        
        jurisdictions = self.get_jurisdictions(states_filter, limit)
        
        validated_count = 0
        wikidata_found = 0
        channels_validated = 0
        channels_not_in_wikidata = 0
        
        for idx, jurisdiction in enumerate(jurisdictions, 1):
            logger.info(f"[{idx}/{len(jurisdictions)}] {jurisdiction['jurisdiction_name']}, {jurisdiction['state_code']}")
            
            # Validate against WikiData
            result = await self.validate_jurisdiction(jurisdiction)
            validated_count += 1
            
            wikidata_youtube = None  # Initialize
            
            if result.get('wikidata_found'):
                wikidata_found += 1
                logger.info(f"  ✓ Found in WikiData: {result.get('wikidata_id')}")
                
                wikidata_youtube = result.get('youtube_channel_id')
                if wikidata_youtube:
                    logger.success(f"    YouTube channel: {wikidata_youtube}")
                    # Update this channel as validated
                    self.update_channel_wikidata_flag(wikidata_youtube, True)
                    channels_validated += 1
                
                if result.get('official_website'):
                    logger.info(f"    Website: {result.get('official_website')}")
            else:
                logger.debug(f"  ✗ Not found in WikiData")
            
            # Check jurisdiction's channels against WikiData
            import json
            youtube_channels = jurisdiction.get('youtube_channels')
            if youtube_channels:
                if isinstance(youtube_channels, str):
                    youtube_channels = json.loads(youtube_channels)
                
                for channel in youtube_channels:
                    if isinstance(channel, dict):
                        channel_id = channel.get('channel_id') or channel.get('id')
                        
                        if channel_id:
                            # Check if this channel matches WikiData
                            if wikidata_youtube and channel_id == wikidata_youtube:
                                # Already updated above
                                pass
                            else:
                                # Channel not in WikiData for this jurisdiction
                                channels_not_in_wikidata += 1
            
            # Rate limit
            await asyncio.sleep(0.5)
        
        # Summary
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE in_wikidata = TRUE) as in_wikidata,
                COUNT(*) FILTER (WHERE in_localview = TRUE) as in_localview,
                COUNT(*) FILTER (WHERE is_government = TRUE) as confirmed_govt
            FROM intermediate.int_events_channels_registry
        """)
        stats = cursor.fetchone()
        cursor.close()
        
        logger.info("")
        logger.success("=" * 80)
        logger.success("VALIDATION COMPLETE")
        logger.success("=" * 80)
        logger.success(f"Jurisdictions validated: {validated_count}")
        logger.success(f"Jurisdictions found in WikiData: {wikidata_found}")
        logger.success(f"Channels validated in WikiData: {channels_validated}")
        logger.info("")
        logger.info("Channel database statistics:")
        logger.info(f"  Total channels: {stats['total']}")
        logger.info(f"  In WikiData: {stats['in_wikidata']}")
        logger.info(f"  In LocalView: {stats['in_localview']}")
        logger.info(f"  Confirmed government: {stats['confirmed_govt']}")
        logger.info("")
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Validate YouTube channels against WikiData')
    
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated list of state codes (e.g., AL,MA,WI)'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of jurisdictions to validate (for testing)'
    )
    
    args = parser.parse_args()
    
    # Parse states
    states_filter = None
    if args.states:
        states_filter = [s.strip().upper() for s in args.states.split(',')]
    
    # Validate
    validator = WikiDataChannelValidator(DATABASE_URL)
    
    try:
        await validator.validate_all(states_filter, args.limit)
    finally:
        validator.close()


if __name__ == '__main__':
    asyncio.run(main())
