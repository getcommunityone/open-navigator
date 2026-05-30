#!/usr/bin/env python3
"""
Fix and publish the 5 failed datasets
"""
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from huggingface_hub import HfApi, create_repo
from datasets import Dataset
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv('HF_TOKEN')
HF_ORGANIZATION = os.getenv('HF_ORGANIZATION', 'CommunityOne')
GOLD_DIR = Path("data/gold")


def fix_and_publish_jurisdictions():
    """Fix and publish the 4 jurisdiction files."""
    
    jurisdiction_files = [
        'data/gold/reference/jurisdictions_cities.parquet',
        'data/gold/reference/jurisdictions_counties.parquet',
        'data/gold/reference/jurisdictions_school_districts.parquet',
        'data/gold/reference/jurisdictions_townships.parquet',
    ]
    
    api = HfApi(token=HF_TOKEN)
    
    for file_str in jurisdiction_files:
        file_path = Path(file_str)
        dataset_name = f"reference-{file_path.stem.replace('_', '-')}"
        repo_id = f"{HF_ORGANIZATION}/{dataset_name}"
        
        logger.info(f"📤 Processing {file_path.name}...")
        
        try:
            # Load file
            df = pd.read_parquet(file_path)
            logger.info(f"   Loaded {len(df):,} records, {len(df.columns)} columns")
            
            # FIX: Convert ALL columns to standard types
            # This fixes the Arrow dictionary/categorical issue
            for col in df.columns:
                if df[col].dtype.name == 'category':
                    logger.info(f"   Converting categorical column: {col}")
                    df[col] = df[col].astype(str)
                elif df[col].dtype == 'object':
                    # Ensure all object columns are strings
                    df[col] = df[col].astype(str)
            
            # Reset index
            df = df.reset_index(drop=True)
            
            logger.info(f"   Creating HuggingFace dataset...")
            dataset = Dataset.from_pandas(df, preserve_index=False)
            
            # Create repo
            try:
                create_repo(
                    repo_id=repo_id,
                    repo_type="dataset",
                    private=False,
                    exist_ok=True,
                    token=HF_TOKEN
                )
            except Exception as e:
                logger.debug(f"   Repo may already exist: {e}")
            
            # Push to hub
            logger.info(f"   Pushing to {repo_id}...")
            dataset.push_to_hub(
                repo_id=repo_id,
                private=False,
                commit_message=f"Update {dataset_name} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                token=HF_TOKEN
            )
            
            url = f"https://huggingface.co/datasets/{repo_id}"
            logger.success(f"   ✅ Published {len(df):,} records to {url}\n")
            
        except Exception as e:
            logger.error(f"   ❌ Failed: {e}\n")


def check_old_meeting_files():
    """Check if we have old meetings.parquet files that should be replaced."""
    
    logger.info("🔍 Checking for old meeting file naming...")
    
    events_events = Path('data/gold/national/events_events.parquet')
    old_meetings_calendar = Path('data/gold/national/meetings_calendar.parquet')
    old_meetings = Path('data/gold/national/meetings.parquet')
    
    if events_events.exists():
        try:
            df = pd.read_parquet(events_events)
            logger.success(f"✅ Found events_events.parquet with {len(df):,} records (new naming)")
            
            if old_meetings_calendar.exists() or old_meetings.exists():
                logger.warning("⚠️  Old meeting files still exist - these can be deleted:")
                if old_meetings_calendar.exists():
                    logger.info(f"   - meetings_calendar.parquet")
                if old_meetings.exists():
                    logger.info(f"   - meetings.parquet")
                logger.info("   Run migration to rename old files to events_* naming\n")
        except Exception as e:
            logger.error(f"❌ events_events.parquet error: {e}")
    else:
        logger.warning("⚠️  events_events.parquet not found - run pipeline to generate")
        
    # Check if old files exist
    if old_meetings_calendar.exists():
        try:
            df = pd.read_parquet(old_meetings_calendar)
            logger.info(f"📋 Old meetings_calendar.parquet has {len(df):,} records")
        except Exception as e:
            logger.error(f"❌ meetings_calendar.parquet is corrupted: {e}")
    
    if old_meetings.exists():
        try:
            df = pd.read_parquet(old_meetings)
            logger.info(f"📋 Old meetings.parquet has {len(df):,} records")
        except Exception as e:
            logger.error(f"❌ meetings.parquet is corrupted: {e}")
            logger.info(f"   File size: {old_meetings.stat().st_size / 1024 / 1024:.2f} MB")
    
    logger.info("")


def main():
    """Fix and publish failed datasets."""
    
    if not HF_TOKEN:
        logger.error("❌ HF_TOKEN not set")
        return
    
    logger.info("=" * 80)
    logger.info("🔧 Fixing and Publishing Failed Datasets")
    logger.info("=" * 80)
    print()
    
    # Check for old meeting file naming
    check_old_meeting_files()
    
    # Fix and publish jurisdiction files
    logger.info("📋 Publishing 4 jurisdiction reference datasets...")
    print()
    fix_and_publish_jurisdictions()
    
    # Summary
    logger.info("=" * 80)
    logger.success("✅ Done! Check your datasets at: https://huggingface.co/CommunityOne")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
