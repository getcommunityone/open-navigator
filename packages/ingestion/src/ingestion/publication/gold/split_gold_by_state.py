#!/usr/bin/env python3
"""
Split gold parquet files by state for easier distribution and access.

This script splits large monolithic parquet files into state-specific files:
- nonprofits_organizations.parquet → nonprofits_organizations_AL.parquet, nonprofits_organizations_AK.parquet, etc.
- nonprofits_locations.parquet → nonprofits_locations_AL.parquet, nonprofits_locations_AK.parquet, etc.
- jurisdictions_*.parquet → jurisdictions_*_AL.parquet, etc.
- domains_gsa_domains.parquet → domains_gsa_domains_AL.parquet, etc.

Benefits:
- Smaller file sizes (easier downloads)
- Faster queries (load only needed states)
- Better HuggingFace upload (avoid file size limits)

Usage:
    # Split all files
    python scripts/split_gold_by_state.py --all
    
    # Split specific file
    python scripts/split_gold_by_state.py --file nonprofits_organizations.parquet
    
    # Dry run (see what would happen)
    python scripts/split_gold_by_state.py --all --dry-run
"""

import argparse
from pathlib import Path
import pandas as pd
from loguru import logger
from typing import Dict, List


class GoldFileSplitter:
    """Split gold parquet files by state."""
    
    # Files that have direct 'state' column
    STATE_COLUMN_FILES = {
        'nonprofits_organizations.parquet': 'state',
        'nonprofits_locations.parquet': 'state',
        'nonprofits_financials.parquet': 'state',
        'nonprofits_programs.parquet': 'state',
        'nonprofits_tuscaloosa_form990.parquet': 'state',
    }
    
    # Files that have 'State' column (capitalized)
    STATE_UPPER_FILES = {
        'domains_gsa_domains.parquet': 'State',
    }
    
    # Files that have 'USPS' column (state abbreviation)
    USPS_FILES = {
        'jurisdictions_cities.parquet': 'USPS',
        'jurisdictions_counties.parquet': 'USPS',
        'jurisdictions_school_districts.parquet': 'USPS',
        'jurisdictions_townships.parquet': 'USPS',
    }
    
    def __init__(self, gold_dir: str = "data/gold", output_dir: str = None):
        """
        Initialize splitter.
        
        DEPRECATED: Use create_partitioned_datasets.py instead for better performance.
        
        Args:
            gold_dir: Directory containing gold parquet files
            output_dir: Directory to write split files (defaults to gold_dir/by_state/)
        """
        self.gold_dir = Path(gold_dir)
        self.output_dir = Path(output_dir) if output_dir else self.gold_dir / "by_state"
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Combined mapping of all files to split
        self.all_files = {
            **self.STATE_COLUMN_FILES,
            **self.STATE_UPPER_FILES,
            **self.USPS_FILES,
        }
    
    def get_state_column(self, filename: str) -> str:
        """Get the state column name for a file."""
        if filename in self.STATE_COLUMN_FILES:
            return self.STATE_COLUMN_FILES[filename]
        elif filename in self.STATE_UPPER_FILES:
            return self.STATE_UPPER_FILES[filename]
        elif filename in self.USPS_FILES:
            return self.USPS_FILES[filename]
        else:
            raise ValueError(f"Unknown file: {filename}")
    
    def split_file(self, filename: str, dry_run: bool = False) -> Dict[str, int]:
        """
        Split a single parquet file by state.
        
        Args:
            filename: Name of file to split (e.g., 'nonprofits_organizations.parquet')
            dry_run: If True, only report what would be done
            
        Returns:
            Dict mapping state abbreviation to record count
        """
        input_path = self.gold_dir / filename
        
        if not input_path.exists():
            logger.warning(f"File not found: {input_path}")
            return {}
        
        logger.info(f"📂 Processing: {filename}")
        
        # Read the file
        df = pd.read_parquet(input_path)
        logger.info(f"  Total records: {len(df):,}")
        
        # Get state column
        state_col = self.get_state_column(filename)
        
        if state_col not in df.columns:
            logger.error(f"  ❌ Column '{state_col}' not found in {filename}")
            logger.error(f"  Available columns: {df.columns.tolist()}")
            return {}
        
        # Get unique states
        unique_states = sorted(df[state_col].dropna().unique())
        logger.info(f"  Unique states: {len(unique_states)}")
        
        # Split by state
        state_counts = {}
        base_name = filename.replace('.parquet', '')
        
        for state in unique_states:
            state_df = df[df[state_col] == state]
            count = len(state_df)
            state_counts[state] = count
            
            # Create output filename
            output_filename = f"{base_name}_{state}.parquet"
            output_path = self.output_dir / output_filename
            
            if dry_run:
                logger.info(f"  [DRY RUN] Would create: {output_filename} ({count:,} records)")
            else:
                # Write state-specific file
                state_df.to_parquet(output_path, index=False, engine='pyarrow')
                size_mb = output_path.stat().st_size / 1024 / 1024
                logger.success(f"  ✅ Created: {output_filename} ({count:,} records, {size_mb:.2f} MB)")
        
        return state_counts
    
    def split_all(self, dry_run: bool = False) -> None:
        """
        Split all configured files by state.
        
        Args:
            dry_run: If True, only report what would be done
        """
        logger.info("🚀 Splitting all gold files by state...")
        logger.info(f"  Input directory: {self.gold_dir}")
        logger.info(f"  Output directory: {self.output_dir}")
        logger.info("")
        
        total_files = 0
        total_states = 0
        
        for filename in self.all_files.keys():
            try:
                state_counts = self.split_file(filename, dry_run=dry_run)
                if state_counts:
                    total_files += 1
                    total_states += len(state_counts)
                logger.info("")
            except Exception as e:
                logger.error(f"❌ Error processing {filename}: {e}")
                logger.info("")
        
        logger.success("=" * 60)
        logger.success(f"✅ Split {total_files} files into {total_states} state-specific files")
        logger.success(f"📂 Output directory: {self.output_dir}")
        logger.success("=" * 60)
    
    def list_split_files(self) -> List[Path]:
        """List all split files in the output directory."""
        return sorted(self.output_dir.glob("*.parquet"))
    
    def get_split_stats(self) -> pd.DataFrame:
        """Get statistics about split files."""
        files = self.list_split_files()
        
        stats = []
        for f in files:
            df = pd.read_parquet(f)
            stats.append({
                'filename': f.name,
                'records': len(df),
                'size_mb': f.stat().st_size / 1024 / 1024,
                'columns': len(df.columns)
            })
        
        return pd.DataFrame(stats)


def main():
    parser = argparse.ArgumentParser(
        description="Split gold parquet files by state",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Split all files
  python scripts/split_gold_by_state.py --all
  
  # Split specific file
  python scripts/split_gold_by_state.py --file nonprofits_organizations.parquet
  
  # Dry run (see what would happen)
  python scripts/split_gold_by_state.py --all --dry-run
  
  # View statistics
  python scripts/split_gold_by_state.py --stats
        """
    )
    
    parser.add_argument('--all', action='store_true',
                       help='Split all configured files')
    parser.add_argument('--file', type=str,
                       help='Split a specific file')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without actually splitting')
    parser.add_argument('--stats', action='store_true',
                       help='Show statistics about split files')
    parser.add_argument('--gold-dir', type=str, default='data/gold',
                       help='Directory containing gold parquet files (default: data/gold)')
    parser.add_argument('--output-dir', type=str,
                       help='Output directory for split files (default: data/gold/by_state)')
    
    args = parser.parse_args()
    
    # Initialize splitter
    splitter = GoldFileSplitter(
        gold_dir=args.gold_dir,
        output_dir=args.output_dir
    )
    
    # Handle commands
    if args.stats:
        logger.info("📊 Split file statistics:")
        stats_df = splitter.get_split_stats()
        if len(stats_df) == 0:
            logger.warning("No split files found. Run with --all first.")
        else:
            print(stats_df.to_string(index=False))
            print(f"\nTotal files: {len(stats_df)}")
            print(f"Total records: {stats_df['records'].sum():,}")
            print(f"Total size: {stats_df['size_mb'].sum():.2f} MB")
    
    elif args.all:
        splitter.split_all(dry_run=args.dry_run)
    
    elif args.file:
        splitter.split_file(args.file, dry_run=args.dry_run)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
