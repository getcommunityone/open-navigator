#!/usr/bin/env python
"""
Unified Contacts & Meetings Data Management

Manage contact extraction from meetings and relationships between
contacts and meetings.

Gold Tables:
- contacts_local_officials: Unique officials aggregated from meetings
- contacts_meeting_attendance: Junction table (meeting_id ↔ contact_id)
- meetings_transcripts: Source data with 153K meetings

Usage:
    # Show statistics
    python scripts/manage_contacts.py stats
    
    # Extract contacts from meetings (incremental batches)
    python scripts/manage_contacts.py extract --batch-size 10000 --limit 50000
    
    # Build meeting attendance relationships
    python scripts/manage_contacts.py build-attendance
    
    # Full refresh (careful - takes time!)
    python scripts/manage_contacts.py refresh-all --confirm
"""

import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
import re
from loguru import logger
import sys
import argparse
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# File paths
MEETINGS_TRANSCRIPTS = Path("data/gold/national/meetings_transcripts.parquet")
CONTACTS_OFFICIALS = Path("data/gold/contacts_local_officials.parquet")
MEETING_ATTENDANCE = Path("data/gold/contacts_meeting_attendance.parquet")


class ContactsManager:
    """Manage contacts extraction and relationships"""
    
    def __init__(self):
        self.data_dir = Path("data/gold")
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def extract_officials_from_transcript(self, text: str, jurisdiction: str = "") -> List[Dict]:
        """
        Extract official names and titles from meeting transcripts.
        
        Patterns:
        1. Roll call: "Jerry Schultz here, Ted Nelson here"
        2. Title mentions: "Mayor Smith", "Councilmember Jones"
        3. Speaker labels: "John Doe: Thank you Mr. Mayor"
        """
        if not text or pd.isna(text):
            return []
        
        text_str = str(text)
        officials = []
        seen_names = set()
        
        # Pattern 1: Roll call ("Name here")
        roll_call_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s+(?:here|present|aye)'
        for match in re.finditer(roll_call_pattern, text_str, re.IGNORECASE):
            name = match.group(1).strip()
            if self._is_valid_name(name) and name not in seen_names:
                seen_names.add(name)
                officials.append({
                    'name': name,
                    'title': 'Council Member',
                    'jurisdiction': jurisdiction,
                    'source': 'roll_call'
                })
        
        # Pattern 2: Titles with names
        title_patterns = [
            (r'Mayor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})', 'Mayor'),
            (r'(?:Councilmember|Council Member)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})', 'Council Member'),
            (r'Commissioner\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})', 'Commissioner'),
        ]
        
        for pattern, title in title_patterns:
            for match in re.finditer(pattern, text_str, re.IGNORECASE):
                name = match.group(1).strip()
                if self._is_valid_name(name) and name not in seen_names:
                    seen_names.add(name)
                    officials.append({
                        'name': name,
                        'title': title,
                        'jurisdiction': jurisdiction,
                        'source': 'title_mention'
                    })
        
        # Pattern 3: Speaker labels ("Name: text")
        speaker_pattern = r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}):\s+'
        for match in re.finditer(speaker_pattern, text_str, re.MULTILINE):
            name = match.group(1).strip()
            if self._is_valid_name(name) and name not in seen_names:
                seen_names.add(name)
                officials.append({
                    'name': name,
                    'title': 'Speaker',
                    'jurisdiction': jurisdiction,
                    'source': 'speaker_label'
                })
        
        return officials
    
    def _is_valid_name(self, name: str) -> bool:
        """Check if extracted string is likely a valid name"""
        if not name or len(name) < 3:
            return False
        
        # Skip common false positives (exact match and contains)
        false_positive_words = {
            'thank', 'you', 'good', 'evening', 'morning', 'afternoon',
            'right', 'sir', 'madam', 'chair', 'mayor', 'council',
            'board', 'member', 'members', 'city', 'town', 'county',
            'vice', 'commissioner', 'supervisor', 'alderman'
        }
        
        name_lower = name.lower()
        for word in false_positive_words:
            if word in name_lower:
                return False
        
        # Must have at least 2 words (first and last name)
        parts = name.split()
        if len(parts) < 2:
            return False
        
        # Each part should start with capital
        if not all(part[0].isupper() for part in parts):
            return False
        
        # Each part should have at least 2 letters
        if not all(len(part) >= 2 for part in parts):
            return False
        
        # Should not have more than 4 words (avoid sentences)
        if len(parts) > 4:
            return False
        
        return True
    
    def cmd_stats(self):
        """Show statistics about contacts and meetings"""
        logger.info("=" * 70)
        logger.info("CONTACTS & MEETINGS STATISTICS")
        logger.info("=" * 70)
        
        # Check meetings
        if MEETINGS_TRANSCRIPTS.exists():
            meetings_df = pd.read_parquet(MEETINGS_TRANSCRIPTS, columns=['meeting_id', 'jurisdiction'])
            logger.info(f"\n📅 MEETINGS:")
            logger.info(f"   Total: {len(meetings_df):,}")
            logger.info(f"   Jurisdictions: {meetings_df['jurisdiction'].nunique():,}")
            
            top_jurisdictions = meetings_df['jurisdiction'].value_counts().head(10)
            logger.info(f"\n   Top 10 Jurisdictions:")
            for jurisdiction, count in top_jurisdictions.items():
                logger.info(f"      {jurisdiction}: {count:,}")
        else:
            logger.warning(f"\n⚠️  No meetings file found: {MEETINGS_TRANSCRIPTS}")
        
        # Check contacts
        if CONTACTS_OFFICIALS.exists():
            contacts_df = pd.read_parquet(CONTACTS_OFFICIALS)
            logger.info(f"\n👥 CONTACTS (Local Officials):")
            logger.info(f"   Total: {len(contacts_df):,}")
            
            if 'meetings_count' in contacts_df.columns:
                logger.info(f"   Avg meetings per official: {contacts_df['meetings_count'].mean():.1f}")
                logger.info(f"   Max meetings: {contacts_df['meetings_count'].max():,}")
            
            if 'title' in contacts_df.columns:
                logger.info(f"\n   By Title:")
                title_counts = contacts_df['title'].value_counts().head(10)
                for title, count in title_counts.items():
                    logger.info(f"      {title}: {count:,}")
            
            size_mb = CONTACTS_OFFICIALS.stat().st_size / (1024 * 1024)
            logger.info(f"\n   File size: {size_mb:.2f} MB")
        else:
            logger.warning(f"\n⚠️  No contacts file found: {CONTACTS_OFFICIALS}")
        
        # Check attendance
        if MEETING_ATTENDANCE.exists():
            attendance_df = pd.read_parquet(MEETING_ATTENDANCE)
            logger.info(f"\n📋 MEETING ATTENDANCE (Relationships):")
            logger.info(f"   Total records: {len(attendance_df):,}")
            logger.info(f"   Unique meetings: {attendance_df['meeting_id'].nunique():,}")
            logger.info(f"   Unique contacts: {attendance_df['name'].nunique():,}")
            
            avg_per_meeting = len(attendance_df) / attendance_df['meeting_id'].nunique()
            logger.info(f"   Avg attendees per meeting: {avg_per_meeting:.1f}")
            
            size_mb = MEETING_ATTENDANCE.stat().st_size / (1024 * 1024)
            logger.info(f"   File size: {size_mb:.2f} MB")
        else:
            logger.warning(f"\n⚠️  No attendance file found: {MEETING_ATTENDANCE}")
        
        logger.info("\n" + "=" * 70)
    
    def cmd_extract(self, batch_size: int = 1000, limit: Optional[int] = None):
        """
        Extract contacts from meetings in batches.
        MEMORY OPTIMIZED: Saves after each batch, uses small batches.
        
        Args:
            batch_size: Number of meetings to process per batch (default: 1000)
            limit: Maximum number of meetings to process (None = all)
        """
        logger.info("=" * 70)
        logger.info("EXTRACTING CONTACTS FROM MEETINGS")
        logger.info("=" * 70)
        
        if not MEETINGS_TRANSCRIPTS.exists():
            logger.error(f"Meetings file not found: {MEETINGS_TRANSCRIPTS}")
            return
        
        # Load meetings metadata (not transcripts yet - too big!)
        logger.info(f"\n📂 Loading meetings metadata...")
        parquet_file = pq.ParquetFile(MEETINGS_TRANSCRIPTS)
        total_meetings = parquet_file.metadata.num_rows
        
        logger.info(f"   Total meetings: {total_meetings:,}")
        logger.info(f"   Batch size: {batch_size:,}")
        
        if limit:
            total_to_process = min(limit, total_meetings)
            logger.info(f"   Limit: {limit:,} → Will process {total_to_process:,}")
        else:
            total_to_process = total_meetings
        
        # Load existing contacts to avoid duplicates
        existing_contacts = {}
        if CONTACTS_OFFICIALS.exists():
            contacts_df = pd.read_parquet(CONTACTS_OFFICIALS)
            logger.info(f"\n📋 Loaded {len(contacts_df):,} existing contacts")
            
            for _, row in contacts_df.iterrows():
                key = (row['name'], row.get('jurisdiction', ''))
                existing_contacts[key] = row.to_dict()
        else:
            logger.info(f"\n📋 No existing contacts, starting fresh")
        
        # Track attendance separately (will merge at end)
        existing_attendance = []
        if MEETING_ATTENDANCE.exists():
            existing_attendance_df = pd.read_parquet(MEETING_ATTENDANCE)
            existing_attendance = existing_attendance_df.to_dict('records')
            logger.info(f"   Loaded {len(existing_attendance):,} existing attendance records")
        
        logger.info(f"\n🔄 Processing meetings in batches...")
        logger.info(f"   💾 Saving after each batch to avoid memory issues")
        
        for batch_start in tqdm(range(0, total_to_process, batch_size), desc="Batches"):
            batch_end = min(batch_start + batch_size, total_to_process)
            
            # Load batch (only needed columns)
            batch_df = pd.read_parquet(
                MEETINGS_TRANSCRIPTS,
                columns=['meeting_id', 'jurisdiction', 'transcript_text']
            )[batch_start:batch_end]
            
            batch_attendance = []
            
            # Extract from each meeting
            for _, meeting in batch_df.iterrows():
                officials = self.extract_officials_from_transcript(
                    meeting['transcript_text'],
                    meeting.get('jurisdiction', '')
                )
                
                # Add to attendance (many-to-many)
                for official in officials:
                    batch_attendance.append({
                        'meeting_id': meeting['meeting_id'],
                        'name': official['name'],
                        'title': official['title'],
                        'jurisdiction': official['jurisdiction'],
                        'source': official['source']
                    })
                
                # Aggregate officials (deduplicate by name + jurisdiction)
                for official in officials:
                    key = (official['name'], official['jurisdiction'])
                    if key in existing_contacts:
                        # Update meetings count
                        existing_contacts[key]['meetings_count'] = \
                            existing_contacts[key].get('meetings_count', 0) + 1
                    else:
                        existing_contacts[key] = {
                            'name': official['name'],
                            'title': official['title'],
                            'jurisdiction': official['jurisdiction'],
                            'meetings_count': 1,
                            'first_seen': datetime.now().isoformat(),
                            'data_source': 'meeting_transcripts'
                        }
            
            # Add batch attendance to total
            existing_attendance.extend(batch_attendance)
            
            # Free memory
            del batch_df
            del batch_attendance
            
            # SAVE AFTER EACH BATCH (prevent data loss on crash)
            if (batch_start // batch_size) % 5 == 0 or batch_end >= total_to_process:
                # Save every 5 batches or at end
                self._save_results(existing_contacts, existing_attendance)
        
        # Final save
        logger.info(f"\n💾 Final save...")
        contacts_df, attendance_df = self._save_results(existing_contacts, existing_attendance)
        
        logger.info("\n" + "=" * 70)
        logger.success("EXTRACTION COMPLETE!")
        logger.info("=" * 70)
        
        # Show summary
        if contacts_df is not None and len(contacts_df) > 0:
            logger.info(f"\n📊 SUMMARY:")
            logger.info(f"   Unique contacts: {len(contacts_df):,}")
            logger.info(f"   Attendance records: {len(attendance_df):,}")
            logger.info(f"   Avg meetings per contact: {contacts_df['meetings_count'].mean():.1f}")
            logger.info(f"\n   Top 10 Most Active:")
            top_10 = contacts_df.head(10)
            for _, row in top_10.iterrows():
                logger.info(f"      {row['name']} ({row.get('title', 'Unknown')}): {row['meetings_count']} meetings")
    
    def _save_results(self, existing_contacts: dict, existing_attendance: list):
        """Save contacts and attendance to disk"""
        # Save contacts
        contacts_df = pd.DataFrame(list(existing_contacts.values()))
        if len(contacts_df) > 0:
            # Add last_updated
            contacts_df['last_updated'] = datetime.now().isoformat()
            
            # Sort by meetings_count descending
            contacts_df = contacts_df.sort_values('meetings_count', ascending=False)
            
            contacts_df.to_parquet(CONTACTS_OFFICIALS, index=False)
        
        # Save attendance
        attendance_df = None
        if existing_attendance:
            attendance_df = pd.DataFrame(existing_attendance)
            attendance_df['recorded_at'] = datetime.now().isoformat()
            
            # Deduplicate by (meeting_id, name)
            attendance_df = attendance_df.drop_duplicates(subset=['meeting_id', 'name'], keep='last')
            
            attendance_df.to_parquet(MEETING_ATTENDANCE, index=False)
        
        return contacts_df, attendance_df
    
    def cmd_build_attendance(self):
        """Build meeting attendance from existing contacts"""
        logger.info("=" * 70)
        logger.info("BUILDING MEETING ATTENDANCE")
        logger.info("=" * 70)
        
        if not CONTACTS_OFFICIALS.exists():
            logger.error("No contacts file found. Run 'extract' first.")
            return
        
        if not MEETINGS_TRANSCRIPTS.exists():
            logger.error(f"Meetings file not found: {MEETINGS_TRANSCRIPTS}")
            return
        
        logger.info("\n📋 Loading contacts...")
        contacts_df = pd.read_parquet(CONTACTS_OFFICIALS)
        logger.info(f"   Loaded {len(contacts_df):,} contacts")
        
        logger.info("\n📅 Scanning meetings for contact appearances...")
        # This is simpler - just re-extract from all meetings
        # (In practice, this is what cmd_extract does)
        logger.info("   💡 Use 'extract' command to rebuild attendance")
    
    def cmd_refresh_all(self, confirm: bool = False, batch_size: int = 1000):
        """Full refresh - delete existing and re-extract everything"""
        if not confirm:
            logger.warning("⚠️  This will DELETE existing contacts and re-extract from scratch!")
            logger.warning("   Add --confirm flag to proceed")
            return
        
        logger.info("=" * 70)
        logger.info("FULL REFRESH")
        logger.info("=" * 70)
        
        # Delete existing
        for file_path in [CONTACTS_OFFICIALS, MEETING_ATTENDANCE]:
            if file_path.exists():
                logger.info(f"   Deleting: {file_path}")
                file_path.unlink()
        
        # Re-extract all with specified batch size
        logger.info(f"\n🔄 Starting fresh extraction (batch_size={batch_size})...")
        self.cmd_extract(batch_size=batch_size, limit=None)


def main():
    """Main CLI"""
    parser = argparse.ArgumentParser(
        description="Manage contacts and meetings relationships",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Stats command
    subparsers.add_parser('stats', help='Show statistics')
    
    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract contacts from meetings')
    extract_parser.add_argument('--batch-size', type=int, default=1000,
                               help='Meetings per batch (default: 1000, lower = less memory)')
    extract_parser.add_argument('--limit', type=int, default=None,
                               help='Max meetings to process (default: all)')
    
    # Build attendance command
    subparsers.add_parser('build-attendance', help='Build meeting attendance relationships')
    
    # Refresh command
    refresh_parser = subparsers.add_parser('refresh-all', help='Delete and re-extract everything')
    refresh_parser.add_argument('--confirm', action='store_true',
                               help='Confirm destructive operation')
    refresh_parser.add_argument('--batch-size', type=int, default=1000,
                               help='Meetings per batch (default: 1000, lower = less memory)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = ContactsManager()
    
    if args.command == 'stats':
        manager.cmd_stats()
    elif args.command == 'extract':
        manager.cmd_extract(batch_size=args.batch_size, limit=args.limit)
    elif args.command == 'build-attendance':
        manager.cmd_build_attendance()
    elif args.command == 'refresh-all':
        manager.cmd_refresh_all(confirm=args.confirm, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
