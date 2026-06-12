#!/usr/bin/env python3
"""
Batch download Form 990 XMLs from GivingTuesday S3
Separates download (network I/O) from parsing (CPU) for maximum speed

Usage:
    # Download all MA health org XMLs (fast!)
    python scripts/batch_download_990s.py --state MA --health-only --concurrent 1000
    
    # Download all MA XMLs
    python scripts/batch_download_990s.py --state MA --concurrent 1000
    
    # Then process from cache (instant)
    python scripts/enrich_ma_990_fast.py --concurrent 500
"""

import asyncio
import boto3
from botocore import UNSIGNED
from botocore.config import Config
import pandas as pd
from pathlib import Path
import argparse
from loguru import logger
import sys
from tqdm import tqdm
import json

logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


class BatchDownloader:
    def __init__(self, max_concurrent=1000):
        self.s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
        self.bucket = 'gt990datalake-rawdata'
        self.cache_dir = Path('data/cache/form990')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Load GT990 index
        index_path = Path('data/cache/form990_gt_index.parquet')
        if not index_path.exists():
            raise FileNotFoundError(
                f"GT990 index not found at {index_path}\n"
                "Download it first: python -m scrapers.irs.enrich_nonprofits_gt990 --download-index"
            )
        
        logger.info("Loading GT990 index...")
        self.index_df = pd.read_parquet(index_path)
        self.index_df['EIN'] = self.index_df['EIN'].astype(str).str.zfill(9)
        logger.success(f"Loaded {len(self.index_df):,} Form 990 filings")
    
    async def download_xml(self, ein: str, object_id: str) -> bool:
        """Download XML for one EIN (raw download, no parsing)"""
        async with self.semaphore:
            ein = str(ein).zfill(9)
            cache_file = self.cache_dir / f"{ein}.json"
            
            # Skip if already cached
            if cache_file.exists():
                return True
            
            xml_key = f"EfileData/XmlFiles/{object_id}_public.xml"
            
            try:
                loop = asyncio.get_event_loop()
                xml_obj = await loop.run_in_executor(
                    None,
                    lambda: self.s3.get_object(Bucket=self.bucket, Key=xml_key)
                )
                xml_content = xml_obj['Body'].read()
                
                # Save raw XML to cache (minimal processing)
                cache_data = {
                    'ein': ein,
                    'object_id': object_id,
                    'xml_size': len(xml_content),
                    'downloaded': True,
                    'xml_content': xml_content.decode('utf-8', errors='ignore')
                }
                
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f)
                
                return True
                
            except self.s3.exceptions.NoSuchKey:
                # Cache negative result
                cache_data = {
                    'ein': ein,
                    'object_id': object_id,
                    'downloaded': False,
                    'error': 'not_found'
                }
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f)
                return False
            except Exception as e:
                logger.debug(f"Error downloading {ein}: {e}")
                return False


async def main():
    parser = argparse.ArgumentParser(description='Batch download Form 990 XMLs')
    parser.add_argument('--state', required=True, help='State code (e.g., MA)')
    parser.add_argument('--concurrent', type=int, default=1000, help='Concurrent downloads')
    parser.add_argument('--health-only', action='store_true', help='Only NTEE E* orgs')
    parser.add_argument('--sample', type=int, help='Limit to N orgs for testing')
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("BATCH DOWNLOAD FORM 990 XMLs")
    logger.info("=" * 70)
    
    downloader = BatchDownloader(max_concurrent=args.concurrent)
    
    # Load MA organizations
    logger.info(f"\nLoading {args.state} organizations...")
    ma_df = pd.read_parquet(f'data/gold/states/{args.state}/nonprofits_organizations.parquet')
    logger.info(f"   ✅ Loaded {len(ma_df):,} organizations")
    
    # Apply filters
    if args.health_only:
        ma_df = ma_df[ma_df['ntee_cd'].str.startswith('E', na=False)]
        logger.info(f"   🏥 Filtered to health orgs: {len(ma_df):,}")
    
    if args.sample:
        ma_df = ma_df.head(args.sample)
        logger.info(f"   🎲 Sampled: {len(ma_df):,}")
    
    # Join with GT990 index to get ObjectIds
    ma_df['ein_9digit'] = ma_df['ein'].astype(str).str.zfill(9)
    
    # Get latest filing for each EIN
    logger.info("\nMatching with GT990 index...")
    latest_filings = downloader.index_df.sort_values('TaxPeriod', ascending=False).groupby('EIN').first().reset_index()
    
    joined = ma_df.merge(latest_filings, left_on='ein_9digit', right_on='EIN', how='inner')
    logger.info(f"   ✅ Found {len(joined):,} organizations with Form 990 filings")
    
    if len(joined) == 0:
        logger.error("No organizations matched with GT990 index!")
        return
    
    # Download XMLs
    logger.info(f"\n🚀 Downloading {len(joined):,} XMLs (concurrency: {args.concurrent})...")
    logger.info(f"   Cache directory: {downloader.cache_dir}")
    
    tasks = []
    for _, row in joined.iterrows():
        ein = row['ein_9digit']
        object_id = row['ObjectId']
        tasks.append(downloader.download_xml(ein, object_id))
    
    # Run downloads with progress bar
    results = []
    with tqdm(total=len(tasks), desc="Downloading", unit="xml") as pbar:
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            pbar.update(1)
    
    # Stats
    success_count = sum(results)
    logger.success(f"\n✅ Downloaded: {success_count:,}/{len(results):,} XMLs")
    logger.info(f"   Failed: {len(results) - success_count:,}")
    logger.info(f"\n💾 Cache location: {downloader.cache_dir}")
    logger.info(f"\n🎉 Next step: python scripts/enrich_ma_990_fast.py --concurrent 500")
    logger.info("   (Processing from cache will be INSTANT!)")


if __name__ == '__main__':
    asyncio.run(main())
