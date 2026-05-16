#!/usr/bin/env python3
"""
Retry publishing just the failed datasets
"""
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from huggingface_hub import HfApi, create_repo
from datasets import Dataset
from loguru import logger
from dotenv import load_dotenv
import traceback

# Load environment variables
load_dotenv()

# Configuration
HF_TOKEN = os.getenv('HF_TOKEN')
HF_ORGANIZATION = os.getenv('HF_ORGANIZATION', 'CommunityOne')

# Failed datasets to retry
FAILED_FILES = [
    "data/gold/national/meetings.parquet",
    "data/gold/reference/jurisdictions_cities.parquet",
    "data/gold/reference/jurisdictions_counties.parquet",
    "data/gold/reference/jurisdictions_school_districts.parquet",
    "data/gold/reference/jurisdictions_townships.parquet",
]

GOLD_DIR = Path("data/gold")


def get_dataset_name(file_path: Path, gold_dir: Path) -> str:
    """Generate HuggingFace dataset name from file path."""
    rel_path = file_path.relative_to(gold_dir)
    parts = list(rel_path.parts)
    filename = parts[-1].replace('.parquet', '')
    
    if parts[0] == 'national':
        name = f"national-{filename}"
    elif parts[0] == 'reference':
        name = f"reference-{filename.replace('_', '-')}"
    elif parts[0] == 'states':
        state_code = parts[1].lower()
        name = f"states-{state_code}-{filename.replace('_', '-')}"
    else:
        name = '-'.join(parts).replace('.parquet', '').replace('_', '-')
    
    return name


def publish_dataset(file_path: Path, api: HfApi, private: bool = False) -> dict:
    """Publish a single parquet file to HuggingFace."""
    
    if not file_path.exists():
        logger.warning(f"⚠️  Skipping {file_path} - file not found")
        return {"error": "File not found"}
    
    dataset_name = get_dataset_name(file_path, GOLD_DIR)
    repo_id = f"{HF_ORGANIZATION}/{dataset_name}"
    
    logger.info(f"📤 Publishing {file_path.relative_to(GOLD_DIR)} to {repo_id}...")
    
    try:
        # Load parquet file
        df = pd.read_parquet(file_path)
        logger.info(f"   Loaded {len(df):,} records, {len(df.columns)} columns")
        logger.info(f"   Columns: {list(df.columns)}")
        
        # Reset index and ensure clean data
        df = df.reset_index(drop=True)
        
        # Convert any complex types to strings if needed
        for col in df.columns:
            if df[col].dtype == 'object':
                # Check if it contains complex objects
                try:
                    first_val = df[col].dropna().iloc[0] if len(df[col].dropna()) > 0 else None
                    if first_val is not None and not isinstance(first_val, (str, int, float, bool)):
                        logger.warning(f"   Converting complex column {col} to string")
                        df[col] = df[col].astype(str)
                except:
                    pass
        
        # Create HuggingFace dataset
        logger.info(f"   Creating dataset...")
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
        logger.info(f"   Pushing to hub...")
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
        }
        
    except Exception as e:
        logger.error(f"   ❌ Failed: {e}")
        logger.error(f"   Full traceback:\n{traceback.format_exc()}")
        return {"error": str(e), "file": str(file_path)}


def main():
    """Retry publishing failed datasets."""
    
    if not HF_TOKEN:
        logger.error("❌ HF_TOKEN not set in environment")
        return
    
    api = HfApi(token=HF_TOKEN)
    
    logger.info("=" * 80)
    logger.info(f"♻️  Retrying {len(FAILED_FILES)} failed datasets")
    logger.info("=" * 80)
    print()
    
    successful = 0
    failed = 0
    
    for file_str in FAILED_FILES:
        file_path = Path(file_str)
        logger.info(f"Processing {file_path.relative_to(GOLD_DIR)}")
        result = publish_dataset(file_path, api, private=False)
        
        if "error" in result:
            failed += 1
        else:
            successful += 1
        
        print()
    
    logger.info("=" * 80)
    logger.success(f"✅ Successful: {successful}")
    logger.error(f"❌ Failed: {failed}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
