#!/usr/bin/env python3
"""
Publish Gold Layer Parquet Files to HuggingFace

Publishes national-level gold datasets to HuggingFace for public sharing.
"""
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from huggingface_hub import HfApi, login, create_repo
from datasets import Dataset
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
HF_TOKEN = os.getenv('HF_TOKEN')
HF_ORGANIZATION = os.getenv('HF_ORGANIZATION', 'CommunityOne')
HF_DATASET_PREFIX = os.getenv('HF_DATASET_PREFIX', 'one')

# Paths
GOLD_DIR = Path("data/gold/national")

# Dataset mappings (file -> HuggingFace dataset name)
DATASETS = {
    "meetings_calendar.parquet": "meetings-calendar",
    "nonprofits_organizations.parquet": "nonprofits-organizations",
    "nonprofits_financials.parquet": "nonprofits-financials",
    "nonprofits_programs.parquet": "nonprofits-programs",
    "nonprofits_locations.parquet": "nonprofits-locations",
}


def publish_dataset(file_path: Path, dataset_name: str, api: HfApi, private: bool = False) -> dict:
    """Publish a single parquet file to HuggingFace."""
    
    if not file_path.exists():
        logger.warning(f"⚠️  Skipping {file_path.name} - file not found")
        return {"error": "File not found"}
    
    # Create repo ID
    repo_id = f"{HF_ORGANIZATION}/{HF_DATASET_PREFIX}-{dataset_name}"
    
    logger.info(f"📤 Publishing {file_path.name} to {repo_id}...")
    
    try:
        # Load parquet file
        df = pd.read_parquet(file_path)
        logger.info(f"   Loaded {len(df):,} records")
        
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
            "columns": list(df.columns)
        }
        
    except Exception as e:
        logger.error(f"   ❌ Failed: {e}")
        return {"error": str(e)}


def main():
    """Publish all gold datasets to HuggingFace."""
    
    if not HF_TOKEN:
        logger.error("❌ HF_TOKEN not set in environment")
        logger.error("   Set it in .env file or export it")
        return
    
    # Login to HuggingFace
    login(token=HF_TOKEN)
    api = HfApi(token=HF_TOKEN)
    
    # Get user info
    user_info = api.whoami(token=HF_TOKEN)
    username = user_info['name']
    
    logger.info("=" * 70)
    logger.info("🚀 Publishing Gold Datasets to HuggingFace")
    logger.info("=" * 70)
    logger.info(f"👤 User: {username}")
    logger.info(f"🏢 Organization: {HF_ORGANIZATION}")
    logger.info(f"📂 Source: {GOLD_DIR}")
    logger.info("")
    
    results = {}
    
    for filename, dataset_name in DATASETS.items():
        file_path = GOLD_DIR / filename
        result = publish_dataset(file_path, dataset_name, api, private=False)
        results[dataset_name] = result
        print()
    
    # Summary
    logger.info("=" * 70)
    logger.info("📊 PUBLICATION SUMMARY")
    logger.info("=" * 70)
    
    successful = 0
    failed = 0
    total_records = 0
    
    for name, info in results.items():
        if "url" in info:
            logger.success(f"✅ {name}: {info['records']:,} records")
            logger.info(f"   {info['url']}")
            successful += 1
            total_records += info['records']
        else:
            logger.error(f"❌ {name}: {info.get('error', 'Unknown error')}")
            failed += 1
    
    logger.info("")
    logger.info(f"📈 Published {successful} dataset(s) with {total_records:,} total records")
    
    if failed > 0:
        logger.warning(f"⚠️  Failed to publish {failed} dataset(s)")
    
    logger.success("🎉 Done!")


if __name__ == "__main__":
    main()
