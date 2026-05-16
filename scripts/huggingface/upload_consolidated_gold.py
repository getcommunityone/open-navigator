#!/usr/bin/env python3
"""
Upload Consolidated Gold Tables to HuggingFace

Uploads the consolidated gold parquet files (21 files) to HuggingFace Datasets.
Works with the new consolidated structure where state data is combined with
a 'state' column instead of separate state directories.

Usage:
    python scripts/huggingface/upload_consolidated_gold.py
    python scripts/huggingface/upload_consolidated_gold.py --private
    python scripts/huggingface/upload_consolidated_gold.py --file bills_bills.parquet
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
from huggingface_hub import HfApi, create_repo
from datasets import Dataset
from loguru import logger
from dotenv import load_dotenv
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables
load_dotenv()

# Configuration
HF_TOKEN = os.getenv('HF_TOKEN')
HF_ORGANIZATION = os.getenv('HF_ORGANIZATION', 'CommunityOne')
HF_DATASET_PREFIX = os.getenv('HF_DATASET_PREFIX', 'one')

# Path to consolidated gold directory
GOLD_DIR = Path("data/gold")


def get_dataset_name(file_stem: str) -> str:
    """
    Convert file stem to HuggingFace dataset name.
    
    Examples:
        bills_bills -> bills
        nonprofits_organizations -> nonprofits-organizations
        events_documents -> event-documents
    """
    # Special cases - simplify some names
    simplifications = {
        'bills_bills': 'bills',
        'bills_bill_actions': 'bill-actions',
        'bills_bill_sponsorships': 'bill-sponsorships',
        'contacts_officials': 'officials',
        'contacts_local_officials': 'local-officials',
        'events_participants': 'event-participants',
        'events_documents': 'event-documents',
    }
    
    if file_stem in simplifications:
        return simplifications[file_stem]
    
    # Default: replace underscores with hyphens
    return file_stem.replace('_', '-')


def upload_parquet_to_hf(
    file_path: Path,
    api: HfApi,
    private: bool = False,
    max_rows: int = None
) -> dict:
    """
    Upload a single parquet file to HuggingFace.
    
    Args:
        file_path: Path to parquet file
        api: HuggingFace API instance
        private: Whether to make the dataset private
        max_rows: Optional limit on rows to upload (for testing large files)
    
    Returns:
        Dict with upload results
    """
    if not file_path.exists():
        logger.warning(f"⚠️  Skipping {file_path.name} - file not found")
        return {"error": "File not found"}
    
    # Get dataset name
    dataset_name = get_dataset_name(file_path.stem)
    repo_id = f"{HF_ORGANIZATION}/{HF_DATASET_PREFIX}-{dataset_name}"
    
    # Get file size
    size_mb = file_path.stat().st_size / (1024 * 1024)
    
    logger.info(f"📤 Uploading {file_path.name} ({size_mb:.1f} MB) to {repo_id}...")
    
    try:
        # Load parquet file
        df = pd.read_parquet(file_path)
        original_rows = len(df)
        
        # Limit rows if requested (for testing)
        if max_rows and len(df) > max_rows:
            logger.info(f"   Limiting to {max_rows:,} rows (testing mode)")
            df = df.head(max_rows)
        
        logger.info(f"   Loaded {len(df):,} records with {len(df.columns)} columns")
        logger.debug(f"   Columns: {', '.join(df.columns.tolist()[:10])}...")
        
        # Check if state column exists (for consolidated state files)
        if 'state' in df.columns:
            states = df['state'].unique()
            logger.info(f"   States: {', '.join(sorted(states))}")
        
        # Create HuggingFace dataset
        dataset = Dataset.from_pandas(df)
        
        # Create repo if it doesn't exist
        try:
            create_repo(
                repo_id=repo_id,
                repo_type="dataset",
                private=private,
                exist_ok=True,
                token=HF_TOKEN
            )
            logger.debug(f"   Created/verified repo: {repo_id}")
        except Exception as e:
            logger.debug(f"   Repo handling: {e}")
        
        # Push to hub
        dataset.push_to_hub(
            repo_id=repo_id,
            private=private,
            commit_message=f"Upload consolidated gold table - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            token=HF_TOKEN
        )
        
        url = f"https://huggingface.co/datasets/{repo_id}"
        logger.success(f"   ✅ Uploaded {len(df):,} records to {url}")
        
        return {
            "file": file_path.name,
            "repo_id": repo_id,
            "url": url,
            "records": len(df),
            "original_records": original_rows,
            "size_mb": size_mb,
            "columns": len(df.columns)
        }
        
    except Exception as e:
        logger.error(f"   ❌ Upload failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "file": file_path.name,
            "error": str(e)
        }


def main():
    """Upload all consolidated gold tables to HuggingFace."""
    
    parser = argparse.ArgumentParser(description="Upload consolidated gold tables to HuggingFace")
    parser.add_argument("--private", action="store_true", help="Make datasets private")
    parser.add_argument("--file", help="Upload only this specific file")
    parser.add_argument("--max-rows", type=int, help="Limit rows per file (for testing)")
    parser.add_argument("--skip-large", action="store_true", help="Skip files larger than 100MB")
    args = parser.parse_args()
    
    # Validate token
    if not HF_TOKEN:
        logger.error("❌ HF_TOKEN not set")
        logger.error("   Set it in .env file or export HF_TOKEN=your_token")
        sys.exit(1)
    
    logger.info("=" * 70)
    logger.info("UPLOADING CONSOLIDATED GOLD TABLES TO HUGGINGFACE")
    logger.info("=" * 70)
    logger.info(f"Organization: {HF_ORGANIZATION}")
    logger.info(f"Prefix: {HF_DATASET_PREFIX}")
    logger.info(f"Private: {args.private}")
    logger.info(f"Gold directory: {GOLD_DIR}")
    logger.info("=" * 70)
    
    # Initialize HuggingFace API
    api = HfApi(token=HF_TOKEN)
    
    # Get list of parquet files
    if args.file:
        # Upload specific file
        parquet_files = [GOLD_DIR / args.file]
        if not parquet_files[0].exists():
            logger.error(f"❌ File not found: {parquet_files[0]}")
            sys.exit(1)
    else:
        # Upload all parquet files
        parquet_files = sorted(GOLD_DIR.glob("*.parquet"))
    
    if not parquet_files:
        logger.error(f"❌ No parquet files found in {GOLD_DIR}")
        sys.exit(1)
    
    logger.info(f"\nFound {len(parquet_files)} parquet files to upload\n")
    
    # Upload each file
    results = []
    skipped = []
    
    for i, file_path in enumerate(parquet_files, 1):
        # Check file size
        size_mb = file_path.stat().st_size / (1024 * 1024)
        
        if args.skip_large and size_mb > 100:
            logger.info(f"⏭️  Skipping {file_path.name} ({size_mb:.1f} MB) - too large")
            skipped.append(file_path.name)
            continue
        
        logger.info(f"\n[{i}/{len(parquet_files)}] Processing {file_path.name}")
        logger.info("-" * 70)
        
        result = upload_parquet_to_hf(
            file_path,
            api,
            private=args.private,
            max_rows=args.max_rows
        )
        results.append(result)
    
    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("UPLOAD SUMMARY")
    logger.info("=" * 70)
    
    successful = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]
    
    if successful:
        logger.info(f"\n✅ Successfully uploaded {len(successful)} datasets:\n")
        for r in successful:
            logger.info(f"   • {r['file']}: {r['records']:,} records → {r['url']}")
    
    if failed:
        logger.info(f"\n❌ Failed uploads ({len(failed)}):\n")
        for r in failed:
            logger.error(f"   • {r['file']}: {r['error']}")
    
    if skipped:
        logger.info(f"\n⏭️  Skipped {len(skipped)} large files:\n")
        for f in skipped:
            logger.info(f"   • {f}")
    
    # Final stats
    total_records = sum(r.get('records', 0) for r in successful)
    total_size_mb = sum(r.get('size_mb', 0) for r in successful)
    
    logger.info("")
    logger.info(f"Total records uploaded: {total_records:,}")
    logger.info(f"Total data size: {total_size_mb:.1f} MB")
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. View datasets at https://huggingface.co/CommunityOne")
    logger.info("2. Test loading: from datasets import load_dataset")
    logger.info(f"3. Example: ds = load_dataset('{HF_ORGANIZATION}/{HF_DATASET_PREFIX}-bills')")


if __name__ == "__main__":
    main()
