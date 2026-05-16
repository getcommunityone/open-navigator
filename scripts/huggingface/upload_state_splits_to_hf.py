#!/usr/bin/env python3
"""
Upload state-split parquet files to Hugging Face Datasets.

This script uploads the state-split files created by split_gold_by_state.py
to HuggingFace, organized by state for easier access and distribution.

Each state gets its own dataset with all relevant data:
- CommunityOne/one-data-AL (Alabama data)
- CommunityOne/one-data-AK (Alaska data)
- etc.

Benefits:
- Users can download only the state(s) they need
- Smaller file sizes (faster downloads)
- Better organization for state-specific analysis

Usage:
    # Upload all states
    python scripts/upload_state_splits_to_hf.py --all
    
    # Upload specific state
    python scripts/upload_state_splits_to_hf.py --state AL
    
    # Upload multiple states
    python scripts/upload_state_splits_to_hf.py --states AL AK AZ
    
    # Dry run (see what would be uploaded)
    python scripts/upload_state_splits_to_hf.py --all --dry-run
"""

import argparse
import os
from pathlib import Path
from typing import List, Dict
import pandas as pd
from datasets import Dataset
from huggingface_hub import login, create_repo, HfApi
from loguru import logger

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not installed")


class StateDataUploader:
    """Upload state-split data files to HuggingFace."""
    
    # US States and territories
    ALL_STATES = [
        'AA', 'AE', 'AK', 'AL', 'AP', 'AR', 'AS', 'AZ', 'CA', 'CO', 'CT', 
        'DC', 'DE', 'FL', 'FM', 'GA', 'GU', 'HI', 'IA', 'ID', 'IL', 'IN', 
        'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MH', 'MI', 'MN', 'MO', 'MP', 
        'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM', 'NV', 'NY', 'OH', 
        'OK', 'OR', 'PA', 'PR', 'PW', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 
        'VA', 'VI', 'VT', 'WA', 'WI', 'WV', 'WY'
    ]
    
    # State names for better descriptions
    STATE_NAMES = {
        'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
        'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
        'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
        'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
        'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
        'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
        'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
        'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
        'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
        'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
        'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
        'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
        'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia',
        'PR': 'Puerto Rico', 'VI': 'Virgin Islands', 'GU': 'Guam',
        'AS': 'American Samoa', 'MP': 'Northern Mariana Islands',
        'AA': 'Armed Forces Americas', 'AE': 'Armed Forces Europe', 'AP': 'Armed Forces Pacific',
        'FM': 'Federated States of Micronesia', 'MH': 'Marshall Islands', 'PW': 'Palau'
    }
    
    def __init__(self, repo_prefix: str = None, token: str = None, splits_dir: str = "data/gold/by_state"):
        """
        Initialize uploader.
        
        Args:
            repo_prefix: HF repo prefix (e.g., "CommunityOne/one-data")
            token: HF token (or set HF_TOKEN environment variable)
            splits_dir: Directory containing state-split parquet files
        """
        self.repo_prefix = repo_prefix or "CommunityOne/one-data"
        self.token = token or os.getenv("HF_TOKEN")
        self.splits_dir = Path(splits_dir)
        
        if not self.token:
            raise ValueError(
                "Hugging Face token required! "
                "Get it from https://huggingface.co/settings/tokens "
                "and set HF_TOKEN environment variable"
            )
        
        # Login
        login(token=self.token)
        logger.info(f"✅ Logged in to Hugging Face")
        logger.info(f"📦 Dataset prefix: {self.repo_prefix}")
    
    def get_state_files(self, state: str) -> List[Path]:
        """Get all parquet files for a specific state."""
        pattern = f"*_{state}.parquet"
        files = list(self.splits_dir.glob(pattern))
        return sorted(files)
    
    def upload_state(self, state: str, dry_run: bool = False) -> bool:
        """
        Upload all files for a specific state to HuggingFace.
        
        Args:
            state: State abbreviation (e.g., 'AL', 'AK')
            dry_run: If True, only report what would be done
            
        Returns:
            True if successful, False otherwise
        """
        files = self.get_state_files(state)
        
        if not files:
            logger.warning(f"No files found for state: {state}")
            return False
        
        repo_name = f"{self.repo_prefix}-{state}"
        state_name = self.STATE_NAMES.get(state, state)
        
        logger.info(f"📂 Processing {state_name} ({state})")
        logger.info(f"  Files: {len(files)}")
        
        if dry_run:
            logger.info(f"  [DRY RUN] Would create repo: {repo_name}")
            for f in files:
                logger.info(f"    [DRY RUN] Would upload: {f.name}")
            return True
        
        # Create repo
        try:
            create_repo(
                repo_id=repo_name,
                repo_type="dataset",
                private=False,
                exist_ok=True
            )
            logger.info(f"✅ Repository ready: https://huggingface.co/datasets/{repo_name}")
        except Exception as e:
            logger.error(f"❌ Failed to create repo: {e}")
            return False
        
        # Upload each file as a separate split
        api = HfApi()
        total_records = 0
        total_size = 0
        
        for file_path in files:
            try:
                # Determine split name from filename
                # e.g., nonprofits_organizations_AL.parquet -> organizations
                base_name = file_path.stem.replace(f"_{state}", "")
                split_name = base_name.replace("nonprofits_", "").replace("jurisdictions_", "").replace("domains_", "")
                
                # Read and upload
                df = pd.read_parquet(file_path)
                records = len(df)
                size_mb = file_path.stat().st_size / 1024 / 1024
                
                total_records += records
                total_size += size_mb
                
                logger.info(f"  📤 Uploading {split_name}: {records:,} records ({size_mb:.2f} MB)")
                
                # Convert to HF Dataset and push
                dataset = Dataset.from_pandas(df)
                dataset.push_to_hub(
                    repo_id=repo_name,
                    split=split_name,
                    token=self.token
                )
                
                logger.success(f"    ✅ Uploaded {split_name}")
                
            except Exception as e:
                logger.error(f"    ❌ Failed to upload {file_path.name}: {e}")
        
        logger.success(f"✅ {state_name} complete: {total_records:,} records, {total_size:.2f} MB")
        logger.success(f"   View at: https://huggingface.co/datasets/{repo_name}")
        
        return True
    
    def upload_all_states(self, dry_run: bool = False) -> Dict[str, bool]:
        """
        Upload all available states.
        
        Args:
            dry_run: If True, only report what would be done
            
        Returns:
            Dict mapping state to success status
        """
        logger.info("🚀 Uploading all states to HuggingFace...")
        logger.info(f"  Input directory: {self.splits_dir}")
        logger.info("")
        
        # Find which states have data
        available_states = set()
        for f in self.splits_dir.glob("*_??.parquet"):
            state = f.stem[-2:]
            if state in self.ALL_STATES:
                available_states.add(state)
        
        available_states = sorted(available_states)
        logger.info(f"Found data for {len(available_states)} states/territories")
        logger.info("")
        
        results = {}
        for state in available_states:
            try:
                success = self.upload_state(state, dry_run=dry_run)
                results[state] = success
                logger.info("")
            except Exception as e:
                logger.error(f"❌ Error processing {state}: {e}")
                results[state] = False
                logger.info("")
        
        # Summary
        successful = sum(1 for v in results.values() if v)
        logger.success("=" * 60)
        logger.success(f"✅ Uploaded {successful}/{len(results)} states")
        logger.success("=" * 60)
        
        return results


def main():
    parser = argparse.ArgumentParser(
        description="Upload state-split parquet files to HuggingFace Datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload all states
  python scripts/upload_state_splits_to_hf.py --all
  
  # Upload Alabama data
  python scripts/upload_state_splits_to_hf.py --state AL
  
  # Upload multiple states
  python scripts/upload_state_splits_to_hf.py --states AL AK AZ CA
  
  # Dry run (see what would be uploaded)
  python scripts/upload_state_splits_to_hf.py --all --dry-run
        """
    )
    
    parser.add_argument('--all', action='store_true',
                       help='Upload all available states')
    parser.add_argument('--state', type=str,
                       help='Upload a specific state (e.g., AL)')
    parser.add_argument('--states', nargs='+',
                       help='Upload multiple states (e.g., AL AK AZ)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without actually uploading')
    parser.add_argument('--repo-prefix', type=str, default='CommunityOne/one-data',
                       help='HuggingFace repo prefix (default: CommunityOne/one-data)')
    parser.add_argument('--splits-dir', type=str, default='data/gold/by_state',
                       help='Directory containing state-split files (default: data/gold/by_state)')
    
    args = parser.parse_args()
    
    # Initialize uploader
    uploader = StateDataUploader(
        repo_prefix=args.repo_prefix,
        splits_dir=args.splits_dir
    )
    
    # Handle commands
    if args.all:
        uploader.upload_all_states(dry_run=args.dry_run)
    
    elif args.state:
        uploader.upload_state(args.state.upper(), dry_run=args.dry_run)
    
    elif args.states:
        for state in args.states:
            uploader.upload_state(state.upper(), dry_run=args.dry_run)
            logger.info("")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
