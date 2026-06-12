"""  
Create Contacts Gold Tables from Meeting Data and Nonprofit 990 Filings

Extract structured contact information from meeting transcripts and IRS 990 data:
- Local officials (mayors, council members, commissioners)
- State legislators (from Open States API)
- School board members
- Nonprofit officers and board members (from IRS 990 Schedule J)

Gold Tables Created:
1. contacts_local_officials - Extracted from meeting roll calls
2. contacts_state_legislators - From Open States API  
3. contacts_school_board - School board members
4. contacts_nonprofit_officers - Officers, directors, trustees from IRS 990

Versioned Tables (Annual Snapshots):
- contacts_nonprofit_officers_YYYY - Annual snapshots for historical tracking
- contacts_nonprofit_officers_history - Combined history across all years

Input: 
- data/gold/national/meetings_transcripts.parquet
- data/gold/nonprofits_organizations.parquet (with bigquery_officers field)
Output: data/gold/contacts_*.parquet
"""

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
import re
from loguru import logger
import sys

# Add project root to path (module now at packages/ingestion/src/ingestion/publication/gold/
# -> repo root is parents[6]) so the root config/ and scripts/ trees resolve.
sys.path.insert(0, str(Path(__file__).resolve().parents[6]))

from config.settings import settings


class ContactsGoldTableCreator:
    """Extract contact information from meeting data"""
    
    def __init__(
        self,
        meetings_gold_dir: str = "data/gold",
        output_dir: str = "data/gold",
        state_code: Optional[str] = None
    ):
        self.meetings_gold_dir = Path(meetings_gold_dir)
        self.state_code = state_code
        
        # Use state-based directory structure if state_code provided
        if state_code:
            self.output_dir = Path(output_dir) / "states" / state_code
        else:
            self.output_dir = Path(output_dir)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Meetings Gold Dir: {self.meetings_gold_dir}")
        logger.info(f"State Code: {state_code or 'ALL (national)'}")
        logger.info(f"Output Dir: {self.output_dir}")
    
    def extract_officials_from_transcript(self, text: str, jurisdiction: str) -> List[Dict]:
        """
        Extract official names and titles from meeting transcripts.
        
        Patterns we look for:
        - Roll call: "Jerry Schultz here, Ted Nelson here"
        - Title mentions: "Mayor Smith", "Councilmember Jones"
        - Speaker patterns: "John Doe: Thank you Mr. Mayor"
        """
        if not text or pd.isna(text):
            return []
        
        text_str = str(text)
        officials = []
        seen_names = set()
        
        # Pattern 1: Titles with names
        title_patterns = [
            r'(?:Mayor|Councilmember|Council Member|Commissioner|Supervisor)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})(?:,\s*Mayor)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})(?:,\s*(?:Council|Commission)\s+(?:Member|Chair))',
        ]
        
        for pattern in title_patterns:
            matches = re.finditer(pattern, text_str, re.IGNORECASE)
            for match in matches:
                name = match.group(1).strip()
                
                # Skip common false positives
                if self._is_valid_name(name) and name not in seen_names:
                    seen_names.add(name)
                    
                    # Try to extract title from context
                    title = self._extract_title_from_context(text_str, match.start(), match.end())
                    
                    officials.append({
                        'name': name,
                        'title': title,
                        'jurisdiction': jurisdiction,
                        'source': 'meeting_transcript'
                    })
        
        # Pattern 2: Roll call format (very common in transcripts)
        # "call roll Jerry Schultz here Ted Nelson Mike Barbour"
        roll_call_pattern = r'(?:call\s+roll|roll\s+call)[:\s]+((?:[A-Z][a-z]+\s+[A-Z][a-z]+\s+(?:here|present|aye|yes)[\s,]*)+)'
        
        roll_matches = re.finditer(roll_call_pattern, text_str, re.IGNORECASE)
        for roll_match in roll_matches:
            roll_text = roll_match.group(1)
            
            # Extract individual names
            name_pattern = r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s+(?:here|present|aye|yes))'
            name_matches = re.finditer(name_pattern, roll_text)
            
            for name_match in name_matches:
                name = name_match.group(1).strip()
                
                if self._is_valid_name(name) and name not in seen_names:
                    seen_names.add(name)
                    
                    officials.append({
                        'name': name,
                        'title': 'Council Member',  # Default for roll call
                        'jurisdiction': jurisdiction,
                        'source': 'roll_call'
                    })
        
        return officials
    
    def _is_valid_name(self, name: str) -> bool:
        """Check if a name looks valid (not a false positive)"""
        if not name:
            return False
        
        # Must be 2-4 words
        parts = name.split()
        if len(parts) < 2 or len(parts) > 4:
            return False
        
        # Skip common false positives
        skip_words = {
            'City Council', 'Council Meeting', 'Public Comment', 'Mr Mayor',
            'Thank You', 'Good Evening', 'All Right', 'Item Number',
            'United States', 'Texas Flag', 'God Bless', 'Let Us'
        }
        
        if name in skip_words:
            return False
        
        # Each part should start with capital letter
        for part in parts:
            if not part[0].isupper():
                return False
        
        return True
    
    def _extract_title_from_context(self, text: str, start: int, end: int) -> str:
        """Extract title from surrounding context"""
        # Get 50 chars before and after
        context_start = max(0, start - 50)
        context_end = min(len(text), end + 50)
        context = text[context_start:context_end].lower()
        
        # Check for titles in context
        if 'mayor' in context:
            return 'Mayor'
        elif 'council' in context or 'councilmember' in context:
            return 'Council Member'
        elif 'commissioner' in context:
            return 'Commissioner'
        elif 'supervisor' in context:
            return 'Supervisor'
        elif 'chair' in context:
            return 'Chair'
        else:
            return 'Official'
    
    def create_contacts_local_officials(self) -> pd.DataFrame:
        """
        Create contacts_local_officials gold table
        
        Extract official names from meeting transcripts
        """
        logger.info("Creating contacts_local_officials gold table...")
        
        # Load meetings transcripts from national directory
        transcripts_path = self.meetings_gold_dir / "national" / "meetings_transcripts.parquet"
        
        if not transcripts_path.exists():
            logger.error(f"Meetings transcripts not found: {transcripts_path}")
            logger.error("Run: python scripts/create_all_gold_tables.py --meetings-only")
            return pd.DataFrame()
        
        logger.info(f"Loading {transcripts_path}")
        df = pd.read_parquet(transcripts_path)
        logger.info(f"  Loaded {len(df):,} meeting transcripts")
        
        # Extract officials from each meeting
        all_officials = []
        
        for idx, row in df.iterrows():
            if idx % 10000 == 0:
                logger.info(f"  Processed {idx:,}/{len(df):,} meetings...")
            
            officials = self.extract_officials_from_transcript(
                row['transcript_text'],
                row['jurisdiction']
            )
            
            for official in officials:
                official['meeting_id'] = row['meeting_id']
                all_officials.append(official)
        
        officials_df = pd.DataFrame(all_officials)
        
        if officials_df.empty:
            logger.warning("No officials extracted from transcripts")
            return pd.DataFrame()
        
        # Save FULL attendance data (meeting-level) FIRST
        logger.info(f"  Extracted {len(officials_df):,} official mentions")
        
        # Create meeting attendance table (many-to-many junction table)
        attendance_df = officials_df[[
            'meeting_id', 'name', 'title', 'jurisdiction', 'source'
        ]].copy()
        attendance_df['last_updated'] = datetime.now().isoformat()
        
        attendance_output = self.output_dir / "contacts_meeting_attendance.parquet"
        attendance_df.to_parquet(attendance_output, index=False)
        logger.success(f"Created {attendance_output} with {len(attendance_df):,} attendance records")
        
        # Now aggregate by name + jurisdiction for summary table
        grouped = officials_df.groupby(['name', 'jurisdiction']).agg({
            'title': lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],  # Most common title
            'meeting_id': 'count',  # Number of meetings attended
            'source': 'first'
        }).reset_index()
        
        grouped.rename(columns={'meeting_id': 'meetings_count'}, inplace=True)
        
        # Add metadata
        grouped['last_updated'] = datetime.now().isoformat()
        grouped['data_source'] = 'LocalView meeting transcripts'
        
        # Reorder columns
        officials_df = grouped[[
            'name', 'title', 'jurisdiction', 
            'meetings_count', 'source', 'data_source', 'last_updated'
        ]]
        
        # Save to parquet
        output_path = self.output_dir / "contacts_local_officials.parquet"
        officials_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(officials_df):,} unique officials")
        
        # Show sample
        logger.info("\n📊 Sample Officials:")
        sample = officials_df.sort_values('meetings_count', ascending=False).head(10)
        for _, row in sample.iterrows():
            logger.info(f"  {row['name']} ({row['title']}) - {row['jurisdiction']} - {row['meetings_count']} meetings")
        
        return officials_df
    
    def create_contacts_state_legislators(self) -> pd.DataFrame:
        """
        Create contacts_state_legislators gold table
        
        Fetch from Open States API
        """
        logger.info("Creating contacts_state_legislators gold table...")
        
        try:
            from scrapers.openstates.openstates_sources import get_api_key, OPENSTATES_API_BASE
            import requests
        except ImportError:
            logger.error("requests library not installed. Install with: pip install requests")
            return pd.DataFrame()
        
        api_key = get_api_key()
        
        if not api_key:
            logger.warning("⚠️  OPENSTATES_API_KEY not set - skipping state legislators")
            logger.warning("   Sign up at: https://openstates.org/accounts/signup/")
            logger.warning("   Add to .env: OPENSTATES_API_KEY=your-key")
            return pd.DataFrame()
        
        logger.info("Fetching state legislators from Open States API...")
        
        # For now, create placeholder structure
        # Full implementation would fetch from Open States API
        legislators_df = pd.DataFrame(columns=[
            'name', 'title', 'jurisdiction', 'party', 'district',
            'chamber', 'email', 'phone', 'data_source', 'last_updated'
        ])
        
        output_path = self.output_dir / "contacts_state_legislators.parquet"
        legislators_df.to_parquet(output_path, index=False)
        logger.info(f"Created {output_path} (placeholder - add Open States API implementation)")
        
        return legislators_df
    
    def create_contacts_nonprofit_officers(self, snapshot_year: Optional[int] = None) -> pd.DataFrame:
        """
        Create contacts_nonprofit_officers gold table from IRS 990 officer data
        
        Extracts officers, directors, and key employees from Form 990 filings.
        Uses form_990_officers field from GivingTuesday Data Lake enrichment.
        
        Args:
            snapshot_year: If provided, creates versioned snapshot for this tax year
        
        Returns:
            DataFrame with officer contact information
        """
        current_year = snapshot_year or datetime.now().year
        logger.info(f"Creating contacts_nonprofit_officers gold table for year {current_year}...")
        
        # Try to load from state-partitioned files first
        all_nonprofits = []
        states_dir = self.meetings_gold_dir / "states"
        
        if states_dir.exists():
            logger.info(f"Loading nonprofits from state-partitioned files: {states_dir}")
            for state_dir in states_dir.iterdir():
                nonprofit_file = state_dir / "nonprofits_organizations.parquet"
                if nonprofit_file.exists():
                    df = pd.read_parquet(nonprofit_file)
                    all_nonprofits.append(df)
                    logger.info(f"   Loaded {len(df):,} from {state_dir.name}")
            
            if all_nonprofits:
                nonprofits_df = pd.concat(all_nonprofits, ignore_index=True)
                logger.info(f"Total nonprofits loaded: {len(nonprofits_df):,}")
            else:
                logger.warning("No nonprofit files found in state directories")
                return pd.DataFrame()
        else:
            # Fallback to single file
            nonprofits_file = self.meetings_gold_dir / "nonprofits_organizations.parquet"
            
            if not nonprofits_file.exists():
                logger.warning(f"⚠️  Nonprofits file not found: {nonprofits_file}")
                logger.warning("   Run Form 990 enrichment first:")
                logger.warning("   python -m scrapers.irs.enrich_nonprofits_gt990 --input ... --output ...")
                return pd.DataFrame()
            
            logger.info(f"Loading nonprofits from: {nonprofits_file}")
            nonprofits_df = pd.read_parquet(nonprofits_file)
        
        # Check for officer data (prefer form_990_officers from GT990, fallback to bigquery_officers)
        officer_field = None
        if 'form_990_officers' in nonprofits_df.columns:
            officer_field = 'form_990_officers'
            logger.info("✅ Using 'form_990_officers' from GivingTuesday Data Lake")
        elif 'bigquery_officers' in nonprofits_df.columns:
            officer_field = 'bigquery_officers'
            logger.info("✅ Using 'bigquery_officers' from BigQuery (deprecated)")
        else:
            logger.warning("⚠️  No officer data found (form_990_officers or bigquery_officers)")
            logger.warning("   Enrich with Form 990 data first:")
            logger.warning("   python -m scrapers.irs.enrich_nonprofits_gt990 --input ... --output ...")
            return pd.DataFrame()
        
        # Parse officer data from JSON
        import json
        
        officers = []
        for _, org in nonprofits_df.iterrows():
            if not org.get(officer_field):
                continue
            
            try:
                officers_list = json.loads(org[officer_field])
            except (json.JSONDecodeError, TypeError):
                continue
            
            for officer in officers_list:
                # Handle both form_990_officers (GT990) and bigquery_officers formats
                # GT990 format: {"name": "...", "title": "...", "compensation": 123, "hours_per_week": 40}
                # BigQuery format (hypothetical): {"person_name": "...", "title": "...", "compensation_amount": 123}
                
                name = officer.get('name') or officer.get('person_name')
                if not name:
                    continue
                
                officers.append({
                    # Officer info
                    'name': name,
                    'title': officer.get('title'),
                    'compensation': officer.get('compensation') or officer.get('compensation_amount') or officer.get('compensation_org'),
                    'hours_per_week': officer.get('hours_per_week') or officer.get('average_hours_per_week'),
                    
                    # Organization info
                    'organization_ein': org.get('ein'),
                    'organization_name': org.get('organization_name') or org.get('name'),
                    'organization_ntee_code': org.get('ntee_code'),
                    'organization_type': 'nonprofit',
                    
                    # Location
                    'state': org.get('state'),
                    'city': org.get('city'),
                    'zip_code': org.get('zip_code'),
                    
                    # Metadata
                    'snapshot_year': org.get('form_990_tax_year', '').split('-')[0] if org.get('form_990_tax_year') else current_year,
                    'source': 'irs_990_form_990',
                    'source_tax_year': org.get('form_990_tax_year'),
                    'source_updated_date': org.get('form_990_last_updated'),
                    'contact_type': 'nonprofit_officer',
                    'extracted_date': datetime.now().strftime('%Y-%m-%d'),
                    'last_updated': datetime.now().strftime('%Y-%m-%d'),
                })
        
        if not officers:
            logger.warning("⚠️  No officer data found in nonprofits")
            return pd.DataFrame()
        
        contacts_df = pd.DataFrame(officers)
        
        logger.success(f"✅ Extracted {len(contacts_df):,} officer contacts")
        logger.info(f"   Unique officers: {contacts_df['name'].nunique():,}")
        logger.info(f"   Unique organizations: {contacts_df['organization_ein'].nunique():,}")
        logger.info(f"   With compensation data: {contacts_df['compensation'].notna().sum():,}")
        
        # Calculate statistics
        if snapshot_year:
            year_contacts = contacts_df[contacts_df['snapshot_year'] == snapshot_year]
            logger.info(f"   Year {snapshot_year} contacts: {len(year_contacts):,}")
        
        # Save versioned snapshot if year specified
        if snapshot_year:
            snapshot_file = self.output_dir / f"contacts_nonprofit_officers_{snapshot_year}.parquet"
            contacts_df.to_parquet(snapshot_file, index=False)
            logger.success(f"✅ Saved snapshot: {snapshot_file}")
        
        # Save current year
        output_path = self.output_dir / "contacts_nonprofit_officers.parquet"
        contacts_df.to_parquet(output_path, index=False)
        logger.success(f"✅ Saved: {output_path}")
        
        return contacts_df
    
    def create_nonprofit_officers_history(self, years: Optional[List[int]] = None) -> pd.DataFrame:
        """
        Create historical view of nonprofit officers across multiple years
        
        Combines annual snapshots to show officer turnover and compensation changes
        
        Args:
            years: List of years to include (default: last 3 years)
        
        Returns:
            DataFrame with historical officer data
        """
        if years is None:
            current_year = datetime.now().year
            years = [current_year, current_year - 1, current_year - 2]
        
        logger.info(f"Creating nonprofit officers history for years: {years}")
        
        # Load all available snapshot files
        snapshot_files = []
        for year in years:
            snapshot_file = self.output_dir / f"contacts_nonprofit_officers_{year}.parquet"
            if snapshot_file.exists():
                snapshot_files.append((year, snapshot_file))
            else:
                logger.warning(f"⚠️  Snapshot for {year} not found: {snapshot_file}")
        
        if not snapshot_files:
            logger.warning("⚠️  No snapshot files found")
            return pd.DataFrame()
        
        # Combine all snapshots
        dfs = []
        for year, file_path in snapshot_files:
            df = pd.read_parquet(file_path)
            logger.info(f"   Loaded {len(df):,} contacts from {year}")
            dfs.append(df)
        
        history_df = pd.concat(dfs, ignore_index=True)
        
        # Save combined history
        output_path = self.output_dir / "contacts_nonprofit_officers_history.parquet"
        history_df.to_parquet(output_path, index=False)
        logger.success(f"✅ Saved history: {output_path}")
        logger.info(f"   Total historical records: {len(history_df):,}")
        logger.info(f"   Years covered: {sorted(history_df['snapshot_year'].unique())}")
        logger.info(f"   Unique officers: {history_df['name'].nunique():,}")
        
        return history_df
    
    def create_contacts_school_board(self) -> pd.DataFrame:
        """
        Create contacts_school_board gold table
        
        Extract from school district data sources
        """
        logger.info("Creating contacts_school_board gold table...")
        
        # Placeholder for now
        school_board_df = pd.DataFrame(columns=[
            'name', 'title', 'school_district', 'jurisdiction',
            'email', 'phone', 'data_source', 'last_updated'
        ])
        
        output_path = self.output_dir / "contacts_school_board.parquet"
        school_board_df.to_parquet(output_path, index=False)
        logger.info(f"Created {output_path} (placeholder)")
        
        return school_board_df
    
    def create_all_contacts_tables(self, include_nonprofit_officers: bool = True, snapshot_years: Optional[List[int]] = None):
        """Create all contacts gold tables
        
        Args:
            include_nonprofit_officers: Whether to create nonprofit officer contacts
            snapshot_years: Years for nonprofit officer snapshots (default: current + last 2 years)
        """
        logger.info("=" * 60)
        logger.info("CREATING CONTACTS GOLD TABLES")
        logger.info("=" * 60)
        
        # Create each table
        self.create_contacts_local_officials()
        self.create_contacts_state_legislators()
        self.create_contacts_school_board()
        
        if include_nonprofit_officers:
            if snapshot_years is None:
                current_year = datetime.now().year
                snapshot_years = [current_year, current_year - 1, current_year - 2]
            
            # Create current year snapshot
            self.create_contacts_nonprofit_officers(snapshot_year=snapshot_years[0])
            
            # Create snapshots for historical years if data exists
            for year in snapshot_years[1:]:
                logger.info(f"\n📅 Creating snapshot for {year}...")
                self.create_contacts_nonprofit_officers(snapshot_year=year)
            
            # Create combined history
            self.create_nonprofit_officers_history(years=snapshot_years)
        
        logger.success("=" * 60)
        logger.success("ALL CONTACTS GOLD TABLES CREATED!")
        logger.success("=" * 60)
        
        # Show summary
        contacts_files = list(self.output_dir.glob("contacts_*.parquet"))
        if contacts_files:
            logger.info(f"\nCreated {len(contacts_files)} contacts tables:")
            for file in sorted(contacts_files):
                df_check = pd.read_parquet(file)
                size_mb = file.stat().st_size / (1024 * 1024)
                logger.info(f"  - {file.name}: {len(df_check):,} records ({size_mb:.2f} MB)")


def main():
    """Main execution function"""
    creator = ContactsGoldTableCreator()
    creator.create_all_contacts_tables()


if __name__ == "__main__":
    main()
