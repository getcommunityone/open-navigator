#!/usr/bin/env python3
"""
Create contacts data organized by state.

For each state with meetings_transcripts.parquet:
- Extract contacts_local_officials.parquet
- Extract contacts_meeting_attendance.parquet
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the contacts extraction logic
from pipeline.create_contacts_gold_tables import ContactsGoldTableCreator


def create_contacts_for_state(state: str, state_dir: Path):
    """Create contacts files for a single state."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing {state}")
    logger.info(f"{'='*60}")
    
    transcripts_file = state_dir / "meetings_transcripts.parquet"
    
    if not transcripts_file.exists():
        logger.warning(f"  ⚠️  No transcripts found: {transcripts_file}")
        return None
    
    # Load transcripts
    df = pd.read_parquet(transcripts_file)
    logger.info(f"  📝 Loaded {len(df):,} meeting transcripts")
    
    # Create temporary contacts creator (will process in-memory)
    creator = ContactsGoldTableCreator(
        meetings_gold_dir=state_dir.parent.parent,  # Not used for state-level
        output_dir=state_dir
    )
    
    # Extract officials from each meeting
    all_officials = []
    
    for idx, row in df.iterrows():
        if idx > 0 and idx % 1000 == 0:
            logger.info(f"    Processing {idx:,}/{len(df):,} meetings...")
        
        officials = creator.extract_officials_from_transcript(
            row.get('transcript_text', ''),
            row.get('jurisdiction', 'Unknown')
        )
        
        for official in officials:
            official['meeting_id'] = row['meeting_id']
            # Add state info
            official['state'] = state
            all_officials.append(official)
    
    if not all_officials:
        logger.warning(f"  ⚠️  No officials extracted for {state}")
        return {'state': state, 'officials': 0, 'attendance': 0}
    
    officials_df = pd.DataFrame(all_officials)
    logger.info(f"  ✅ Extracted {len(officials_df):,} official mentions")
    
    # 1. Create meeting attendance table (junction table)
    attendance_df = officials_df[[
        'meeting_id', 'name', 'title', 'jurisdiction', 'source', 'state'
    ]].copy()
    attendance_df['last_updated'] = datetime.now().isoformat()
    
    attendance_output = state_dir / "contacts_meeting_attendance.parquet"
    attendance_df.to_parquet(attendance_output, index=False, compression='snappy')
    
    size_attendance = attendance_output.stat().st_size / 1024 / 1024
    logger.success(
        f"  💾 {attendance_output.name}: {len(attendance_df):,} records ({size_attendance:.2f} MB)"
    )
    
    # 2. Create aggregated officials table
    grouped = officials_df.groupby(['name', 'jurisdiction']).agg({
        'title': lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],
        'meeting_id': 'count',
        'source': 'first',
        'state': 'first'
    }).reset_index()
    
    grouped.rename(columns={'meeting_id': 'meetings_count'}, inplace=True)
    grouped['last_updated'] = datetime.now().isoformat()
    grouped['data_source'] = 'LocalView meeting transcripts'
    
    # Reorder columns
    officials_summary = grouped[[
        'name', 'title', 'jurisdiction', 'state',
        'meetings_count', 'source', 'data_source', 'last_updated'
    ]]
    
    officials_output = state_dir / "contacts_local_officials.parquet"
    officials_summary.to_parquet(officials_output, index=False, compression='snappy')
    
    size_officials = officials_output.stat().st_size / 1024 / 1024
    logger.success(
        f"  💾 {officials_output.name}: {len(officials_summary):,} unique officials ({size_officials:.2f} MB)"
    )
    
    # Show top officials
    logger.info(f"\n  📊 Top 5 officials by meeting attendance:")
    top_officials = officials_summary.sort_values('meetings_count', ascending=False).head(5)
    for _, row in top_officials.iterrows():
        logger.info(
            f"    • {row['name']} ({row['title']}) - {row['jurisdiction']} - "
            f"{row['meetings_count']} meetings"
        )
    
    return {
        'state': state,
        'officials': len(officials_summary),
        'attendance': len(attendance_df),
        'size_mb': size_officials + size_attendance
    }


def main():
    """Process all states with meeting transcripts."""
    logger.info("🚀 Creating contacts data by state...\n")
    
    states_dir = Path("data/gold/states")
    
    if not states_dir.exists():
        logger.error(f"States directory not found: {states_dir}")
        return
    
    # Find all state directories with transcripts
    state_dirs = sorted([
        d for d in states_dir.iterdir() 
        if d.is_dir() and (d / "meetings_transcripts.parquet").exists()
    ])
    
    if not state_dirs:
        logger.error("No state directories with meetings_transcripts.parquet found")
        logger.info("Run: python scripts/split_meetings_by_state.py first")
        return
    
    logger.info(f"Found {len(state_dirs)} states with transcript data\n")
    
    results = []
    
    for state_dir in state_dirs:
        state = state_dir.name
        result = create_contacts_for_state(state, state_dir)
        if result:
            results.append(result)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("📊 SUMMARY")
    logger.info(f"{'='*60}\n")
    
    if results:
        results_df = pd.DataFrame(results)
        
        total_officials = results_df['officials'].sum()
        total_attendance = results_df['attendance'].sum()
        total_size = results_df['size_mb'].sum()
        
        logger.success(f"Processed {len(results)} states:")
        for _, row in results_df.iterrows():
            logger.info(
                f"  {row['state']}: {row['officials']:,} officials, "
                f"{row['attendance']:,} attendance records"
            )
        
        logger.info("")
        logger.success(f"📦 Total: {total_officials:,} unique officials")
        logger.success(f"📦 Total: {total_attendance:,} attendance records")
        logger.success(f"📦 Total size: {total_size:.1f} MB")
        
        logger.info("\n✅ Files created in each state directory:")
        logger.info("  - contacts_local_officials.parquet")
        logger.info("  - contacts_meeting_attendance.parquet")
    else:
        logger.warning("No contacts created")


if __name__ == "__main__":
    main()
