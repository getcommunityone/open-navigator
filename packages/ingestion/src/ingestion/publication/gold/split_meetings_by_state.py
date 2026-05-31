#!/usr/bin/env python3
"""
Split meetings_calendar.parquet and meetings_transcripts.parquet by state.

Creates state-specific files in data/gold/states/{STATE}/ directories.
"""

from pathlib import Path
import pandas as pd
from loguru import logger


def split_transcripts_by_state():
    """Split meetings_transcripts.parquet by state."""
    logger.info("📝 Splitting meetings_transcripts.parquet by state...")
    
    # Load transcripts from national directory
    transcripts_file = Path("data/gold/national/meetings_transcripts.parquet")
    df_trans = pd.read_parquet(transcripts_file)
    
    logger.info(f"   Loaded {len(df_trans):,} transcripts from {len(df_trans['state'].unique())} states")
    
    states_dir = Path("data/gold/states")
    states_dir.mkdir(parents=True, exist_ok=True)
    
    total_size = 0
    
    for state in sorted(df_trans['state'].unique()):
        state_df = df_trans[df_trans['state'] == state].copy()
        
        # Create state directory
        state_dir = states_dir / state
        state_dir.mkdir(parents=True, exist_ok=True)
        
        # Save transcripts
        output_file = state_dir / "meetings_transcripts.parquet"
        state_df.to_parquet(output_file, index=False, compression='snappy')
        
        size = output_file.stat().st_size
        total_size += size
        
        logger.success(
            f"   ✅ {state}: {len(state_df):,} transcripts → "
            f"{output_file} ({size / 1024 / 1024:.1f} MB)"
        )
    
    logger.success(
        f"   📦 Total: {len(df_trans['state'].unique())} states, "
        f"{total_size / 1024 / 1024:.1f} MB"
    )
    
    return df_trans


def create_calendar_from_state_meetings():
    """Create calendar files from existing state meetings.parquet files."""
    logger.info("\n📅 Creating meetings_calendar.parquet from state meetings...")
    
    states_dir = Path("data/gold/states")
    
    # Find all state directories with meetings.parquet
    state_dirs = sorted([d for d in states_dir.iterdir() if d.is_dir() and (d / "meetings.parquet").exists()])
    
    if not state_dirs:
        logger.warning("   ⚠️  No state directories with meetings.parquet found")
        return
    
    logger.info(f"   Found {len(state_dirs)} states with meeting data")
    
    total_size = 0
    total_records = 0
    
    for state_dir in state_dirs:
        state = state_dir.name
        meetings_file = state_dir / "meetings.parquet"
        
        # Load full meetings data
        df = pd.read_parquet(meetings_file)
        
        # Create calendar with essential columns
        calendar_cols = {
            'vid_id': 'meeting_id',
            'place_name': 'jurisdiction', 
            'channel_type': 'channel_type',
            'meeting_date': 'meeting_date',
            'vid_upload_date': 'upload_date',
            'vid_title': 'title',
            'vid_length_min': 'duration_min',
        }
        
        # Select and rename columns that exist
        available_cols = {k: v for k, v in calendar_cols.items() if k in df.columns}
        calendar_df = df[list(available_cols.keys())].copy()
        calendar_df = calendar_df.rename(columns=available_cols)
        
        # Save calendar
        output_file = state_dir / "meetings_calendar.parquet"
        calendar_df.to_parquet(output_file, index=False, compression='snappy')
        
        size = output_file.stat().st_size
        total_size += size
        total_records += len(calendar_df)
        
        logger.success(
            f"   ✅ {state}: {len(calendar_df):,} calendar records → "
            f"{output_file} ({size / 1024 / 1024:.2f} MB)"
        )
    
    logger.success(
        f"   📦 Total: {len(state_dirs)} states, {total_records:,} records, "
        f"{total_size / 1024 / 1024:.1f} MB"
    )


def main():
    """Split both meetings files by state."""
    logger.info("🚀 Starting meetings data split by state...\n")
    
    # Split transcripts (has state column in source file)
    split_transcripts_by_state()
    
    # Create calendar files from existing state meetings data
    create_calendar_from_state_meetings()
    
    logger.success("\n✅ Done! Meetings data split by state")
    logger.info("\nFiles created in: data/gold/states/{STATE}/")
    logger.info("  - meetings_transcripts.parquet")
    logger.info("  - meetings_calendar.parquet")


if __name__ == "__main__":
    main()
