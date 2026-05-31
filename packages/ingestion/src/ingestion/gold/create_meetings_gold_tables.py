"""
Create Gold Tables from Event Data (LocalView Cache)

This script processes meeting/event data from the cache layer (2006-2023) and creates
curated gold tables for analysis and dashboards.

Gold Tables Created:
1. events_events - Event dates, locations, jurisdictions (data/gold/national/)
2. events_event_documents - Full searchable meeting text and documents (data/gold/national/)
3. events_event_agenda_items - Extracted topics and agenda items
4. events_participants - Link events to jurisdiction demographics and attendees
5. events_event_bills - Identified policy decisions and votes

Input: data/cache/localview/meetings.YYYY.parquet (2006-2023)
Output: data/gold/national/events_*.parquet (national-level aggregated data)
        data/gold/states/{STATE}/events_*.parquet (state-partitioned data)
"""

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import re
from loguru import logger
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings


class EventGoldTableCreator:
    """Process event/meeting cache data into curated gold tables"""
    
    def __init__(
        self,
        cache_dir: str = "data/cache/localview",
        gold_dir: str = "data/gold"
    ):
        self.cache_dir = Path(cache_dir)
        self.gold_dir = Path(gold_dir)
        self.gold_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Cache directory: {self.cache_dir}")
        logger.info(f"Gold directory: {self.gold_dir}")
    
    def load_all_meeting_data(self) -> pd.DataFrame:
        """Load all meeting parquet files from cache"""
        logger.info("Loading all meeting data from cache...")
        
        meeting_files = sorted(self.cache_dir.glob("meetings.*.parquet"))
        
        if not meeting_files:
            logger.error(f"No meeting files found in {self.cache_dir}")
            return pd.DataFrame()
        
        logger.info(f"Found {len(meeting_files)} meeting files")
        
        dfs = []
        for file in meeting_files:
            logger.info(f"Loading {file.name}...")
            df = pd.read_parquet(file)
            logger.info(f"  - {len(df):,} records")
            dfs.append(df)
        
        combined_df = pd.concat(dfs, ignore_index=True)
        logger.success(f"Loaded {len(combined_df):,} total meeting records")
        
        return combined_df
    
    def create_events_events(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create events_events gold table
        
        Columns: event_id, jurisdiction, channel_type, event_date, year, 
                 location, duration, record_count
        """
        logger.info("Creating events_events gold table...")
        
        # Extract date information
        calendar_data = []
        
        for idx, row in df.iterrows():
            # Generate event_id (you can customize this)
            event_id = f"{row.get('jurisdiction', 'unknown')}_{idx}"
            
            calendar_data.append({
                'event_id': event_id,
                'jurisdiction': row.get('jurisdiction', 'Unknown'),
                'channel_type': row.get('channel_type', 'OFFICIAL GOVT'),
                'record_index': idx,
                # Add more fields as needed from your actual schema
            })
        
        calendar_df = pd.DataFrame(calendar_data)
        
        # Save to parquet in national directory
        national_dir = self.gold_dir / "national"
        national_dir.mkdir(parents=True, exist_ok=True)
        output_path = national_dir / "events_events.parquet"
        calendar_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(calendar_df):,} records")
        
        return calendar_df
    
    def create_events_event_documents(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create events_event_documents gold table
        
        Columns: event_id, document_id, jurisdiction, transcript_text, text_clean,
                 word_count, has_captions, document_type
        """
        logger.info("Creating events_event_documents gold table...")
        
        transcript_data = []
        
        for idx, row in df.iterrows():
            event_id = f"{row.get('jurisdiction', 'unknown')}_{idx}"
            
            # Get transcript text
            caption_text = row.get('caption_text_clean', '') or row.get('caption_text', '')
            
            if caption_text:
                word_count = len(str(caption_text).split())
                
                transcript_data.append({
                    'event_id': event_id,
                    'document_id': f"{event_id}_transcript",
                    'jurisdiction': row.get('jurisdiction', 'Unknown'),
                    'document_type': 'transcript',
                    'full_text': caption_text,
                    'word_count': word_count,
                    'has_captions': True,
                })
        
        transcript_df = pd.DataFrame(transcript_data)
        
        # Save to parquet in national directory
        national_dir = self.gold_dir / "national"
        national_dir.mkdir(parents=True, exist_ok=True)
        output_path = national_dir / "events_event_documents.parquet"
        transcript_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(transcript_df):,} records")
        
        return transcript_df
    
    def create_events_participants(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create events_participants gold table
        
        Links event data with demographic context from census data
        """
        logger.info("Creating events_participants gold table...")
        
        demo_data = []
        
        for idx, row in df.iterrows():
            event_id = f"{row.get('jurisdiction', 'unknown')}_{idx}"
            
            demo_record = {
                'participant_id': f"{event_id}_context",
                'event_id': event_id,
                'jurisdiction': row.get('jurisdiction', 'Unknown'),
                'participant_type': 'jurisdiction_context',
            }
            
            # Add all demographic fields (ACS data)
            demo_fields = [
                'acs_18_pop', 'acs_18_median_age', 'acs_18_median_hh_inc',
                'acs_18_median_gross_rent', 'acs_18_white', 'acs_18_black',
                'acs_18_asian', 'acs_18_hispanic', 'acs_18_amind', 'acs_18_nhapi'
            ]
            
            for field in demo_fields:
                if field in row:
                    demo_record[field] = row[field]
            
            demo_data.append(demo_record)
        
        demo_df = pd.DataFrame(demo_data)
        
        # Save to parquet in national directory
        national_dir = self.gold_dir / "national"
        national_dir.mkdir(parents=True, exist_ok=True)
        output_path = national_dir / "events_participants.parquet"
        demo_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(demo_df):,} records")
        
        return demo_df
    
    def extract_topics(self, text: str) -> List[str]:
        """Extract key topics from meeting text using keyword matching"""
        if not text or pd.isna(text):
            return []
        
        text_lower = str(text).lower()
        topics = []
        
        # Define topic keywords
        topic_keywords = {
            'budget': ['budget', 'appropriation', 'fiscal', 'funding', 'dollars', 'expense'],
            'infrastructure': ['road', 'water', 'sewer', 'repair', 'construction', 'maintenance'],
            'public_safety': ['police', 'fire', 'safety', 'emergency', 'officer'],
            'health': ['health', 'dental', 'medical', 'clinic', 'hospital', 'public health'],
            'education': ['school', 'education', 'student', 'teacher', 'learning'],
            'parks': ['park', 'recreation', 'playground', 'facility'],
            'zoning': ['zoning', 'ordinance', 'permit', 'variance', 'development'],
            'contracts': ['contract', 'bid', 'vendor', 'agreement'],
            'ordinances': ['ordinance', 'resolution', 'motion', 'approval'],
            'public_comment': ['public comment', 'citizen', 'resident', 'audience'],
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    def create_events_event_agenda_items(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create events_event_agenda_items gold table
        
        Extract and categorize topics discussed in events/meetings
        """
        logger.info("Creating events_event_agenda_items gold table...")
        
        topic_data = []
        
        for idx, row in df.iterrows():
            event_id = f"{row.get('jurisdiction', 'unknown')}_{idx}"
            caption_text = row.get('caption_text_clean', '') or row.get('caption_text', '')
            
            if caption_text:
                topics = self.extract_topics(caption_text)
                
                topic_data.append({
                    'agenda_item_id': f"{event_id}_topics",
                    'event_id': event_id,
                    'jurisdiction': row.get('jurisdiction', 'Unknown'),
                    'title': ','.join(topics) if topics else 'general',
                    'item_type': 'extracted_topics',
                })
        
        topic_df = pd.DataFrame(topic_data)
        
        # Save to parquet in national directory
        national_dir = self.gold_dir / "national"
        national_dir.mkdir(parents=True, exist_ok=True)
        output_path = national_dir / "events_event_agenda_items.parquet"
        topic_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(topic_df):,} records")
        
        return topic_df
    
    def extract_decisions(self, text: str) -> List[Dict]:
        """Extract policy decisions, votes, and resolutions from meeting text"""
        if not text or pd.isna(text):
            return []
        
        text_str = str(text)
        decisions = []
        
        # Look for voting patterns
        vote_patterns = [
            r'roll call.*?motion carr(?:y|ied)',
            r'all (?:those )?in favor.*?aye',
            r'council member.*?yes',
            r'motion (?:to )?approve.*?second',
            r'resolution.*?adopt',
        ]
        
        for pattern in vote_patterns:
            matches = re.finditer(pattern, text_str, re.IGNORECASE | re.DOTALL)
            for match in matches:
                decisions.append({
                    'text': match.group(0)[:200],  # First 200 chars
                    'type': 'vote'
                })
        
        return decisions
    
    def create_events_event_bills(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create events_event_bills gold table
        
        Extract policy decisions, votes, and resolutions
        """
        logger.info("Creating events_event_bills gold table...")
        
        decision_data = []
        
        for idx, row in df.iterrows():
            event_id = f"{row.get('jurisdiction', 'unknown')}_{idx}"
            caption_text = row.get('caption_text_clean', '') or row.get('caption_text', '')
            
            if caption_text:
                decisions = self.extract_decisions(caption_text)
                
                decision_data.append({
                    'event_bill_id': f"{event_id}_decisions",
                    'event_id': event_id,
                    'jurisdiction': row.get('jurisdiction', 'Unknown'),
                    'action_taken': 'vote' if len(decisions) > 0 else 'discussion',
                    'discussion_summary': f"{len(decisions)} decisions extracted",
                })
        
        decision_df = pd.DataFrame(decision_data)
        
        # Save to parquet in national directory
        national_dir = self.gold_dir / "national"
        national_dir.mkdir(parents=True, exist_ok=True)
        output_path = national_dir / "events_event_bills.parquet"
        decision_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(decision_df):,} records")
        
        return decision_df
    
    def create_all_gold_tables(self):
        """Create all event gold tables"""
        logger.info("=" * 60)
        logger.info("CREATING EVENT GOLD TABLES")
        logger.info("=" * 60)
        
        # Load all meeting data
        df = self.load_all_meeting_data()
        
        if df.empty:
            logger.error("No meeting/event data found. Exiting.")
            return
        
        # Create each gold table
        self.create_events_events(df)
        self.create_events_event_documents(df)
        self.create_events_participants(df)
        self.create_events_event_agenda_items(df)
        self.create_events_event_bills(df)
        
        logger.success("=" * 60)
        logger.success("ALL EVENT GOLD TABLES CREATED!")
        logger.success("=" * 60)
        
        # Show summary from national directory
        national_dir = self.gold_dir / "national"
        gold_files = list(national_dir.glob("events_*.parquet"))
        logger.info(f"\nCreated {len(gold_files)} gold tables in {national_dir}:")
        for file in sorted(gold_files):
            df_check = pd.read_parquet(file)
            logger.info(f"  - {file.name}: {len(df_check):,} records")


def main():
    """Main execution function"""
    creator = EventGoldTableCreator()
    creator.create_all_gold_tables()


if __name__ == "__main__":
    main()
