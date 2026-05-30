#!/usr/bin/env python3
"""
Reorganize nonprofit data files for HuggingFace dataset format.

HuggingFace best practices:
- Flat file structure (no nested directories)
- Clear, discoverable filenames
- One file per state for easy partial downloads
- Standard naming: {dataset}_{state}.parquet
"""

import shutil
from pathlib import Path

import pandas as pd
from loguru import logger


def split_by_state(input_file: Path, base_output_dir: Path, dataset_name: str):
    """Split a parquet file by state into state directories."""
    logger.info(f"\n📂 Processing: {input_file.name}")
    
    if not input_file.exists():
        logger.warning(f"   ⚠️  File not found, skipping")
        return
    
    # Read the full dataset
    df = pd.read_parquet(input_file)
    logger.info(f"   Loaded {len(df):,} rows")
    
    # Check if state column exists
    if 'state' not in df.columns:
        logger.warning(f"   ⚠️  No 'state' column found, skipping")
        return
    
    # Get unique states
    states = sorted(df['state'].unique())
    logger.info(f"   Found {len(states)} states/territories")
    
    # Split by state
    total_size = 0
    for state in states:
        state_df = df[df['state'] == state]
        
        # Create state directory
        state_dir = base_output_dir / state
        state_dir.mkdir(parents=True, exist_ok=True)
        
        # Output file in state directory
        output_file = state_dir / f"{dataset_name}.parquet"
        
        state_df.to_parquet(output_file, index=False, compression='snappy')
        size = output_file.stat().st_size
        total_size += size
        
        logger.info(f"   ✅ {state}: {len(state_df):,} rows → {state}/{dataset_name}.parquet ({size / 1024 / 1024:.1f} MB)")
    
    logger.success(f"   📦 Total: {len(states)} state directories, {total_size / 1024 / 1024:.1f} MB")
    return len(states)


def remove_partitioned_backups():
    """Remove old Hive-style partitioned backup directories."""
    backup_dir = Path("data/gold/partitioned_backup")
    
    if not backup_dir.exists():
        logger.info("\n✅ No partitioned_backup directory found")
        return
    
    logger.info(f"\n🗑️  Removing partitioned backup: {backup_dir}")
    
    # Count directories before deletion
    subdirs = list(backup_dir.glob("*/"))
    logger.info(f"   Found {len(subdirs)} partitioned datasets")
    
    # Calculate total size
    total_size = sum(f.stat().st_size for f in backup_dir.rglob("*") if f.is_file())
    logger.info(f"   Total size: {total_size / 1024 / 1024:.1f} MB")
    
    # Remove the entire directory
    shutil.rmtree(backup_dir)
    logger.success(f"   ✅ Removed {backup_dir}")


def main():
    """Main reorganization process."""
    logger.info("=" * 70)
    logger.info("🚀 Reorganizing data for HuggingFace dataset format")
    logger.info("=" * 70)
    
    # Define base output directory and datasets to process
    base_output_dir = Path("data/gold/states")
    
    datasets = [
        {"input": Path("data/gold/nonprofits_organizations.parquet"), "name": "nonprofits_organizations"},
        {"input": Path("data/gold/nonprofits_locations.parquet"), "name": "nonprofits_locations"},
        {"input": Path("data/gold/nonprofits_financials.parquet"), "name": "nonprofits_financials"},
        {"input": Path("data/gold/nonprofits_programs.parquet"), "name": "nonprofits_programs"},
    ]
    
    # Process each dataset
    total_states = 0
    for dataset in datasets:
        count = split_by_state(
            dataset["input"],
            base_output_dir,
            dataset["name"]
        )
        if count and total_states == 0:
            total_states = count
    
    # Remove old partitioned backups
    remove_partitioned_backups()
    
    # Remove old by_state directory if it exists
    old_by_state = Path("data/gold/by_state")
    if old_by_state.exists():
        logger.info(f"\n🗑️  Removing old by_state directory: {old_by_state}")
        shutil.rmtree(old_by_state)
        logger.success(f"   ✅ Removed {old_by_state}")
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.success(f"✅ COMPLETE: Created {total_states} state directories")
    logger.info("=" * 70)
    logger.info("\n📁 New structure:")
    logger.info("   data/gold/states/")
    logger.info("   ├── AL/")
    logger.info("   │   ├── nonprofits_organizations.parquet")
    logger.info("   │   ├── nonprofits_locations.parquet")
    logger.info("   │   ├── nonprofits_financials.parquet")
    logger.info("   │   └── nonprofits_programs.parquet")
    logger.info("   ├── CA/")
    logger.info("   │   ├── nonprofits_organizations.parquet")
    logger.info("   │   └── ...")
    logger.info("   └── ... (62 state/territory directories)")
    logger.info("\n💡 HuggingFace users can now:")
    logger.info("   - Browse datasets by state directory")
    logger.info("   - Download only the states they need")
    logger.info("   - See all data for a state in one place")
    logger.info("\n📖 Example usage:")
    logger.info("   # Load California nonprofits")
    logger.info("   df = pd.read_parquet('states/CA/nonprofits_organizations.parquet')")
    logger.info("\n   # Load all datasets for a state")
    logger.info("   import glob")
    logger.info("   ca_files = glob.glob('states/CA/*.parquet')")
    logger.info("   data = {f.split('/')[-1].replace('.parquet', ''): pd.read_parquet(f) for f in ca_files}")
    logger.info("\n   # Load one dataset across multiple states")
    logger.info("   states = ['CA', 'NY', 'TX']")
    logger.info("   dfs = [pd.read_parquet(f'states/{s}/nonprofits_organizations.parquet') for s in states]")
    logger.info("   df = pd.concat(dfs)")


if __name__ == "__main__":
    main()
