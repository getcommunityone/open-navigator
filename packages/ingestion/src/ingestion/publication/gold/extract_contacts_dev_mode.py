#!/usr/bin/env python3
"""
Extract contacts from dev_mode states (WA, MA, AL, GA, WI)

This script:
1. Loads meetings from the 5 dev states
2. Extracts contacts using the ContactsGoldTableCreator
3. Splits contacts back into state directories

Usage:
    python scripts/extract_contacts_dev_mode.py
"""

import sys
from pathlib import Path
import pandas as pd
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.create_contacts_gold_tables import ContactsGoldTableCreator

# Dev mode states
DEV_STATES = ['WA', 'MA', 'AL', 'GA', 'WI']


def consolidate_dev_meetings():
    """Consolidate meetings from dev states into a single file."""
    logger.info("=" * 70)
    logger.info("CONSOLIDATING DEV MODE MEETINGS")
    logger.info("=" * 70)
    
    states_dir = Path("data/gold/states")
    dfs = []
    
    for state in DEV_STATES:
        meeting_file = states_dir / state / "meetings.parquet"
        
        if not meeting_file.exists():
            logger.warning(f"⚠️  No meetings file for {state}")
            continue
        
        df = pd.read_parquet(meeting_file)
        logger.info(f"  {state}: {len(df):,} meetings")
        dfs.append(df)
    
    if not dfs:
        logger.error("No meeting data found!")
        return None
    
    combined_df = pd.concat(dfs, ignore_index=True)
    logger.success(f"✅ Consolidated {len(combined_df):,} total meetings")
    
    # Save temporary consolidated file
    output_dir = Path("data/gold")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / "meetings_transcripts.parquet"
    
    # Need to ensure we have the required columns
    # ContactsGoldTableCreator expects: meeting_id, jurisdiction, transcript_text
    
    # Map columns to expected names
    column_mapping = {
        'caption_text': 'transcript_text',
        'place_name': 'jurisdiction',
        'state': 'state'  # Keep state
    }
    
    # Create meeting_id if it doesn't exist
    if 'meeting_id' not in combined_df.columns:
        if 'vid_id' in combined_df.columns:
            combined_df['meeting_id'] = combined_df['vid_id'].astype(str)
        else:
            # Fallback: create sequential IDs
            combined_df['meeting_id'] = [f"meeting_{i}" for i in range(len(combined_df))]
    
    # Rename columns
    for old_col, new_col in column_mapping.items():
        if old_col in combined_df.columns and new_col not in combined_df.columns:
            combined_df[new_col] = combined_df[old_col]
    
    # Select only needed columns
    required_cols = ['meeting_id', 'jurisdiction', 'transcript_text', 'state']
    available_cols = [col for col in required_cols if col in combined_df.columns]
    
    output_df = combined_df[available_cols].copy()
    output_df.to_parquet(output_path, index=False)
    
    logger.success(f"✅ Saved to {output_path}")
    logger.info(f"  Columns: {list(output_df.columns)}")
    
    return output_path


def extract_contacts():
    """Extract contacts using ContactsGoldTableCreator."""
    logger.info("")
    logger.info("=" * 70)
    logger.info("EXTRACTING CONTACTS FROM MEETINGS")
    logger.info("=" * 70)
    
    creator = ContactsGoldTableCreator(
        meetings_gold_dir="data/gold",
        output_dir="data/gold"
    )
    
    # This creates:
    # - data/gold/contacts_local_officials.parquet
    # - data/gold/contacts_meeting_attendance.parquet
    creator.create_contacts_local_officials()
    
    logger.success("✅ Contacts extraction complete")


def split_contacts_by_state():
    """Split contacts back into state directories."""
    logger.info("")
    logger.info("=" * 70)
    logger.info("SPLITTING CONTACTS BY STATE")
    logger.info("=" * 70)
    
    gold_dir = Path("data/gold")
    states_dir = gold_dir / "states"
    
    # Load contacts data
    officials_file = gold_dir / "contacts_local_officials.parquet"
    attendance_file = gold_dir / "contacts_meeting_attendance.parquet"
    
    if not officials_file.exists():
        logger.error(f"Officials file not found: {officials_file}")
        return
    
    officials_df = pd.read_parquet(officials_file)
    logger.info(f"  Loaded {len(officials_df):,} unique officials")
    
    if attendance_file.exists():
        attendance_df = pd.read_parquet(attendance_file)
        logger.info(f"  Loaded {len(attendance_df):,} attendance records")
    else:
        attendance_df = None
    
    # Need to join with meetings to get state
    meetings_file = gold_dir / "national" / "meetings_transcripts.parquet"
    if meetings_file.exists():
        meetings_df = pd.read_parquet(meetings_file)
        
        # Create state mapping from jurisdiction + state
        state_map = meetings_df[['jurisdiction', 'state']].drop_duplicates()
        
        # Add state to officials
        officials_df = officials_df.merge(
            state_map,
            on='jurisdiction',
            how='left'
        )
        
        # Add state to attendance
        if attendance_df is not None:
            attendance_df = attendance_df.merge(
                state_map,
                on='jurisdiction',
                how='left'
            )
    
    # Split by state
    for state in DEV_STATES:
        state_dir = states_dir / state
        state_dir.mkdir(parents=True, exist_ok=True)
        
        # Filter officials for this state
        state_officials = officials_df[officials_df['state'] == state].copy()
        
        if len(state_officials) > 0:
            # Drop state column before saving
            state_officials = state_officials.drop(columns=['state'])
            
            output_file = state_dir / "contacts_local_officials.parquet"
            state_officials.to_parquet(output_file, index=False)
            logger.success(f"  {state}: {len(state_officials):,} officials → {output_file.name}")
        else:
            logger.warning(f"  {state}: No officials found")
        
        # Filter attendance for this state
        if attendance_df is not None:
            state_attendance = attendance_df[attendance_df['state'] == state].copy()
            
            if len(state_attendance) > 0:
                # Drop state column before saving
                state_attendance = state_attendance.drop(columns=['state'])
                
                output_file = state_dir / "contacts_meeting_attendance.parquet"
                state_attendance.to_parquet(output_file, index=False)
                logger.success(f"  {state}: {len(state_attendance):,} attendance records → {output_file.name}")


def cleanup_temp_files():
    """Remove temporary consolidated files."""
    logger.info("")
    logger.info("=" * 70)
    logger.info("CLEANUP")
    logger.info("=" * 70)
    
    gold_dir = Path("data/gold")
    national_dir = gold_dir / "national"
    temp_files = [
        national_dir / "meetings_transcripts.parquet",
        gold_dir / "contacts_local_officials.parquet",
        gold_dir / "contacts_meeting_attendance.parquet"
    ]
    
    for file in temp_files:
        if file.exists():
            file.unlink()
            logger.info(f"  Removed {file}")
    
    logger.success("✅ Cleanup complete")


def main():
    """Main execution."""
    logger.info("🚀 Extract Contacts - Dev Mode (5 States)")
    logger.info(f"   States: {', '.join(DEV_STATES)}")
    logger.info("")
    
    # Step 1: Consolidate meetings
    meetings_path = consolidate_dev_meetings()
    
    if not meetings_path:
        logger.error("Failed to consolidate meetings")
        return
    
    # Step 2: Extract contacts
    extract_contacts()
    
    # Step 3: Split by state
    split_contacts_by_state()
    
    # Step 4: Cleanup
    cleanup_temp_files()
    
    logger.info("")
    logger.info("=" * 70)
    logger.success("🎉 CONTACTS EXTRACTION COMPLETE!")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Contacts files created in:")
    
    for state in DEV_STATES:
        state_dir = Path(f"data/gold/states/{state}")
        officials_file = state_dir / "contacts_local_officials.parquet"
        attendance_file = state_dir / "contacts_meeting_attendance.parquet"
        
        if officials_file.exists():
            df = pd.read_parquet(officials_file)
            logger.info(f"  {state}/contacts_local_officials.parquet: {len(df):,} officials")
        
        if attendance_file.exists():
            df = pd.read_parquet(attendance_file)
            logger.info(f"  {state}/contacts_meeting_attendance.parquet: {len(df):,} records")


if __name__ == "__main__":
    main()
