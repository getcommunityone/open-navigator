#!/usr/bin/env python3
"""
Delete old datasets and publish ALL gold layer datasets to HuggingFace
"""
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from huggingface_hub import HfApi, create_repo, delete_repo
from datasets import Dataset
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
HF_TOKEN = os.getenv('HF_TOKEN')
HF_ORGANIZATION = os.getenv('HF_ORGANIZATION', 'CommunityOne')

# Paths
GOLD_DIR = Path("data/gold")

# Old datasets to delete (deprecated naming conventions)
OLD_DATASETS = [
    "CommunityOne/one-meetings-calendar",  # Replaced by events_events
    "CommunityOne/one-nonprofits-financials",
    "CommunityOne/one-nonprofits-locations",
    "CommunityOne/one-nonprofits-organizations",
    "CommunityOne/one-nonprofits-programs",
]


def delete_old_datasets(api: HfApi):
    """Delete old datasets that need to be removed."""
    logger.info("🗑️  Deleting old datasets...")
    
    for repo_id in OLD_DATASETS:
        try:
            logger.info(f"   Deleting {repo_id}...")
            delete_repo(
                repo_id=repo_id,
                repo_type="dataset",
                token=HF_TOKEN
            )
            logger.success(f"   ✅ Deleted {repo_id}")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not delete {repo_id}: {e}")
    
    logger.success("✅ Cleanup complete")


def get_dataset_name(file_path: Path, gold_dir: Path) -> str:
    """Generate HuggingFace dataset name from file path.
    
    Examples:
        data/gold/national/events_events.parquet -> national-events-events
        data/gold/reference/causes_ntee_codes -> reference-causes-ntee-codes
        data/gold/states/AL/events_events.parquet -> states-al-events-events
    """
    # Get relative path from gold directory
    rel_path = file_path.relative_to(gold_dir)
    
    # Get parts: ['national', 'events_events.parquet'] or ['states', 'AL', 'events_events.parquet']
    parts = list(rel_path.parts)
    
    # Remove .parquet extension from filename
    filename = parts[-1].replace('.parquet', '')
    
    # Build name based on structure
    if parts[0] == 'national':
        # national/events_events.parquet -> national-events-events
        name = f"national-{filename}"
    elif parts[0] == 'reference':
        # reference/causes_ntee_codes -> reference-causes-ntee-codes
        # Replace underscores with dashes for consistency
        name = f"reference-{filename.replace('_', '-')}"
    elif parts[0] == 'states':
        # states/AL/events_events.parquet -> states-al-events-events
        state_code = parts[1].lower()
        name = f"states-{state_code}-{filename.replace('_', '-')}"
    else:
        # Fallback: use full path with dashes
        name = '-'.join(parts).replace('.parquet', '').replace('_', '-')
    
    return name


def publish_dataset(file_path: Path, api: HfApi, private: bool = False) -> dict:
    """Publish a single parquet file to HuggingFace."""
    
    if not file_path.exists():
        logger.warning(f"⚠️  Skipping {file_path} - file not found")
        return {"error": "File not found"}
    
    # Generate dataset name
    dataset_name = get_dataset_name(file_path, GOLD_DIR)
    repo_id = f"{HF_ORGANIZATION}/{dataset_name}"
    
    logger.info(f"📤 Publishing {file_path.relative_to(GOLD_DIR)} to {repo_id}...")
    
    try:
        # Load parquet file
        df = pd.read_parquet(file_path)
        logger.info(f"   Loaded {len(df):,} records, {len(df.columns)} columns")
        
        # Reset index to avoid Arrow serialization issues
        df = df.reset_index(drop=True)
        
        # Convert categorical columns to string (Arrow doesn't support category dtype)
        for col in df.select_dtypes(include=['category']).columns:
            df[col] = df[col].astype(str)
            logger.debug(f"   Converted {col} from category to string")
        
        # Create HuggingFace dataset
        dataset = Dataset.from_pandas(df, preserve_index=False)
        
        # Create repo if it doesn't exist
        try:
            create_repo(
                repo_id=repo_id,
                repo_type="dataset",
                private=private,
                exist_ok=True,
                token=HF_TOKEN
            )
        except Exception as e:
            logger.debug(f"   Repo may already exist: {e}")
        
        # Push to hub
        dataset.push_to_hub(
            repo_id=repo_id,
            private=private,
            commit_message=f"Update {dataset_name} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            token=HF_TOKEN
        )
        
        url = f"https://huggingface.co/datasets/{repo_id}"
        logger.success(f"   ✅ Published {len(df):,} records to {url}")
        
        return {
            "repo_id": repo_id,
            "url": url,
            "records": len(df),
            "columns": list(df.columns),
            "file": str(file_path.relative_to(GOLD_DIR))
        }
        
    except Exception as e:
        import traceback
        error_msg = str(e) if str(e) else f"{type(e).__name__} (no message)"
        error_trace = traceback.format_exc()
        logger.error(f"   ❌ Failed: {error_msg}")
        logger.debug(f"   Traceback:\n{error_trace}")
        return {"error": error_msg, "traceback": error_trace, "file": str(file_path)}


def main():
    """Delete old datasets and publish all gold datasets to HuggingFace."""
    
    if not HF_TOKEN:
        logger.error("❌ HF_TOKEN not set in environment")
        logger.error("   Set it in .env file or export it")
        return
    
    # Initialize API
    api = HfApi(token=HF_TOKEN)
    
    # Step 1: Delete old datasets
    delete_old_datasets(api)
    
    print()
    logger.info("=" * 80)
    logger.info("📦 Publishing ALL gold datasets to HuggingFace")
    logger.info("=" * 80)
    print()
    
    # Find all parquet files in gold directory
    parquet_files = sorted(GOLD_DIR.glob("**/*.parquet"))
    
    if not parquet_files:
        logger.error(f"❌ No parquet files found in {GOLD_DIR}")
        return
    
    logger.info(f"Found {len(parquet_files)} datasets to publish")
    print()
    
    # Track results
    results = []
    successful = 0
    failed = 0
    
    # Publish each dataset
    for i, file_path in enumerate(parquet_files, 1):
        logger.info(f"[{i}/{len(parquet_files)}] Processing {file_path.relative_to(GOLD_DIR)}")
        result = publish_dataset(file_path, api, private=False)
        results.append(result)
        
        if "error" in result:
            failed += 1
        else:
            successful += 1
        
        print()  # Add spacing between datasets
    
    # Summary
    logger.info("=" * 80)
    logger.info("📊 Publication Summary")
    logger.info("=" * 80)
    logger.info(f"✅ Successful: {successful}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"📦 Total: {len(parquet_files)}")
    print()
    
    # List successful publications
    if successful > 0:
        logger.info("✅ Successfully published datasets:")
        for result in results:
            if "error" not in result:
                logger.info(f"   • {result['repo_id']} ({result['records']:,} records)")
                logger.info(f"     {result['url']}")
    
    # List failures
    if failed > 0:
        print()
        logger.error("❌ Failed publications:")
        for result in results:
            if "error" in result:
                logger.error(f"   • {result.get('file', 'unknown')}: {result['error']}")
    
    print()
    logger.success(f"🎉 Done! View all datasets at: https://huggingface.co/{HF_ORGANIZATION}")


if __name__ == "__main__":
    main()
