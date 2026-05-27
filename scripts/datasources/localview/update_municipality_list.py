#!/usr/bin/env python3
"""
Update Municipality Channel List

Searches for municipal government YouTube channels and adds them to the database.

Usage:
    # Search for channels in specific states
    python scripts/localview/update_municipality_list.py --states AL,GA,IN,MA,MT,WA,WI
    
    # Search for specific municipalities
    python scripts/localview/update_municipality_list.py --cities "Birmingham,Boston,Seattle"
    
    # Verify existing channels
    python scripts/localview/update_municipality_list.py --verify
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger
import polars as pl
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logger
logger.add(sys.stderr, format="{time} {level} {message}", level="INFO")


class ChannelDiscovery:
    """Discover and verify municipal YouTube channels"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        if not self.api_key:
            raise ValueError("YOUTUBE_API_KEY environment variable required")
        
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        self.cache_dir = Path("data/cache/localview")
        self.channels_file = self.cache_dir / "municipality_channels.csv"
    
    def search_channel(self, municipality: str, state: str) -> List[dict]:
        """
        Search for a municipal government YouTube channel
        
        Args:
            municipality: City/town name
            state: Two-letter state code
        
        Returns:
            List of potential channel matches
        """
        search_queries = [
            f"{municipality} {state} government",
            f"{municipality} {state} city council",
            f"{municipality} {state} meetings",
            f"{municipality} city government"
        ]
        
        candidates = []
        
        for query in search_queries:
            try:
                search_response = self.youtube.search().list(
                    q=query,
                    type='channel',
                    part='id,snippet',
                    maxResults=5
                ).execute()
                
                for item in search_response.get('items', []):
                    channel_id = item['id']['channelId']
                    snippet = item['snippet']
                    
                    # Check if it looks like an official government channel
                    title_lower = snippet['title'].lower()
                    desc_lower = snippet.get('description', '').lower()
                    
                    is_government = any(word in title_lower or word in desc_lower 
                                       for word in ['government', 'city', 'official', 'council'])
                    
                    if is_government:
                        candidates.append({
                            'channel_id': channel_id,
                            'title': snippet['title'],
                            'description': snippet.get('description', ''),
                            'search_query': query
                        })
                
                time.sleep(0.5)  # Rate limiting
            
            except HttpError as e:
                logger.error(f"Search error for {query}: {e}")
        
        # Deduplicate by channel_id
        seen = set()
        unique_candidates = []
        for candidate in candidates:
            if candidate['channel_id'] not in seen:
                seen.add(candidate['channel_id'])
                unique_candidates.append(candidate)
        
        return unique_candidates
    
    def verify_channel(self, channel_id: str) -> Optional[dict]:
        """Verify a channel exists and get stats"""
        try:
            response = self.youtube.channels().list(
                id=channel_id,
                part='snippet,statistics,contentDetails'
            ).execute()
            
            if not response.get('items'):
                return None
            
            item = response['items'][0]
            snippet = item['snippet']
            stats = item['statistics']
            
            return {
                'channel_id': channel_id,
                'title': snippet['title'],
                'description': snippet.get('description', ''),
                'subscriber_count': int(stats.get('subscriberCount', 0)),
                'video_count': int(stats.get('videoCount', 0)),
                'view_count': int(stats.get('viewCount', 0))
            }
        
        except HttpError as e:
            logger.error(f"Error verifying channel {channel_id}: {e}")
            return None
    
    def load_channels(self) -> pl.DataFrame:
        """Load existing channel list"""
        if self.channels_file.exists():
            return pl.read_csv(self.channels_file)
        else:
            return pl.DataFrame({
                'municipality': [],
                'channel_id': [],
                'state': [],
                'population': [],
                'added_date': []
            })
    
    def add_channel(
        self,
        municipality: str,
        channel_id: str,
        state: str,
        population: Optional[int] = None
    ):
        """Add a new channel to the list"""
        from datetime import datetime
        
        channels_df = self.load_channels()
        
        # Check if already exists
        if len(channels_df) > 0:
            existing = channels_df.filter(pl.col('channel_id') == channel_id)
            if len(existing) > 0:
                logger.warning(f"Channel {channel_id} already exists")
                return
        
        # Add new row
        new_row = pl.DataFrame({
            'municipality': [municipality],
            'channel_id': [channel_id],
            'state': [state],
            'population': [population or 0],
            'added_date': [datetime.now().strftime('%Y-%m-%d')]
        })
        
        if len(channels_df) > 0:
            channels_df = pl.concat([channels_df, new_row])
        else:
            channels_df = new_row
        
        # Save
        channels_df.write_csv(self.channels_file)
        logger.success(f"✅ Added {municipality} ({channel_id})")
    
    def discover_channels(
        self,
        states: Optional[List[str]] = None,
        cities: Optional[List[str]] = None
    ):
        """Discover channels interactively"""
        # Load list of major municipalities by state
        # (In production, load from census data or municipality database)
        
        if cities:
            # Search specific cities
            for city in cities:
                state = "Unknown"  # Would need to lookup
                logger.info(f"\n🔍 Searching for {city}...")
                candidates = self.search_channel(city, state)
                
                if candidates:
                    logger.info(f"   Found {len(candidates)} candidates:")
                    for i, candidate in enumerate(candidates, 1):
                        logger.info(f"   {i}. {candidate['title']}")
                        logger.info(f"      ID: {candidate['channel_id']}")
                else:
                    logger.warning(f"   No channels found for {city}")
        
        else:
            logger.info("No specific cities provided")
            logger.info("Use --cities flag to search for channels")


def main():
    parser = argparse.ArgumentParser(
        description="Update municipal YouTube channel list"
    )
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated state codes'
    )
    parser.add_argument(
        '--cities',
        type=str,
        help='Comma-separated city names to search'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify existing channels'
    )
    parser.add_argument(
        '--add',
        nargs=3,
        metavar=('MUNICIPALITY', 'CHANNEL_ID', 'STATE'),
        help='Manually add a channel'
    )
    
    args = parser.parse_args()
    
    # Initialize discovery
    logger.info("=" * 80)
    logger.info("MUNICIPALITY CHANNEL DISCOVERY")
    logger.info("=" * 80)
    
    try:
        discovery = ChannelDiscovery()
    except ValueError as e:
        logger.error(str(e))
        logger.info("\nSet YOUTUBE_API_KEY in .env file")
        sys.exit(1)
    
    # Manual add
    if args.add:
        municipality, channel_id, state = args.add
        discovery.add_channel(municipality, channel_id, state)
        return
    
    # Verify existing
    if args.verify:
        channels_df = discovery.load_channels()
        logger.info(f"\n✅ Verifying {len(channels_df)} channels...")
        
        for row in channels_df.iter_rows(named=True):
            channel_id = row['channel_id']
            info = discovery.verify_channel(channel_id)
            
            if info:
                logger.info(f"   {row['municipality']}: {info['video_count']} videos")
            else:
                logger.warning(f"   {row['municipality']}: Channel not found")
            
            time.sleep(0.5)
        return
    
    # Search for new channels
    cities = None
    if args.cities:
        cities = [c.strip() for c in args.cities.split(',')]
    
    states = None
    if args.states:
        states = [s.strip().upper() for s in args.states.split(',')]
    
    discovery.discover_channels(states=states, cities=cities)


if __name__ == "__main__":
    main()
