#!/usr/bin/env python3
"""
Fast Form 990 enrichment for Massachusetts using DuckDB pre-filtering

Optimizations:
1. Use DuckDB to join MA orgs with GT990 index (filter 22K that have filings)
2. Skip organizations without filings in index (saves 21K wasted lookups)
3. Process in priority order (health orgs first)
4. Higher concurrency (100-200)
5. Skip already-enriched records

Usage:
    python scripts/enrich_ma_990_fast.py --concurrent 100
"""

import asyncio
import sys
from pathlib import Path

# Ported: GivingTuesday990Enricher now lives in the scrapers package.
from scrapers.irs.enrich_nonprofits_gt990 import GivingTuesday990Enricher
import duckdb
import pandas as pd
from loguru import logger
import argparse
from datetime import datetime

logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


async def main():
    parser = argparse.ArgumentParser(description='Fast MA nonprofit enrichment')
    parser.add_argument('--concurrent', type=int, default=100, help='Concurrent requests')
    parser.add_argument('--health-only', action='store_true', help='Only health orgs (NTEE E)')
    parser.add_argument('--sample', type=int, help='Sample N orgs for testing')
    parser.add_argument('--use-local', action='store_true', help='Use locally extracted XMLs')
    args = parser.parse_args()
    
    conn = duckdb.connect()
    
    logger.info("=" * 70)
    logger.info("FAST MASSACHUSETTS FORM 990 ENRICHMENT")
    logger.info("=" * 70)
    
    # Step 1: Load GT990 index and filter to MA EINs
    logger.info("\n📊 Step 1: Pre-filtering with DuckDB...")
    
    if args.use_local:
        logger.info("   Using locally extracted Form 990 XMLs...")
        index_path = 'data/cache/form990/local_index_dev_states.parquet'
        index_df = pd.read_parquet(index_path)
        logger.info(f"   ✅ Loaded {len(index_df):,} local XMLs")
        # Rename columns to match GT990 format
        index_df['ObjectId'] = index_df['object_id']
        index_df['TaxPeriod'] = index_df['tax_year'].astype(str) + '12'  # Assume December
        index_df['EIN'] = index_df['ein']
    else:
        logger.info("   Loading GT990 index (925 MB)...")
        index_df = pd.read_parquet('data/cache/form990_gt_index.parquet')
        logger.info(f"   ✅ Loaded {len(index_df):,} Form 990 filings")
    
    # Load MA organizations
    logger.info("   Loading MA organizations...")
    ma_df = pd.read_parquet('data/gold/states/MA/nonprofits_organizations.parquet')
    logger.info(f"   ✅ Loaded {len(ma_df):,} MA nonprofits")
    
    # Apply health filter if requested
    if args.health_only:
        ma_df = ma_df[ma_df['ntee_cd'].str.startswith('E', na=False)]
        logger.info(f"   🏥 Filtered to health orgs (NTEE E): {len(ma_df):,}")
    
    # Convert EINs to 9-digit format
    ma_df['ein_9digit'] = ma_df['ein'].astype(str).str.zfill(9)
    index_df['EIN'] = index_df['EIN'].astype(str).str.zfill(9)
    
    # Join to find which MA orgs have filings
    logger.info("   Joining MA orgs with GT990 index...")
    
    # Use DuckDB for fast join
    conn.register('ma_orgs', ma_df)
    conn.register('gt990_index', index_df)
    
    # Get all column names from ma_orgs except ein_9digit
    ma_cols = [c for c in ma_df.columns if c != 'ein_9digit']
    ma_cols_sql = ', '.join([f'm.{c}' for c in ma_cols])
    group_by_sql = ', '.join([f'm.{c}' for c in ma_cols])
    
    joined = conn.execute(f"""
        SELECT 
            {ma_cols_sql},
            COUNT(DISTINCT g.ObjectId) as filing_count,
            MAX(g.TaxPeriod) as latest_tax_period
        FROM ma_orgs m
        INNER JOIN gt990_index g ON m.ein_9digit = g.EIN
        GROUP BY {group_by_sql}
        ORDER BY 
            -- Priority: Health orgs first, then by asset size
            CASE WHEN SUBSTRING(m.ntee_cd, 1, 1) = 'E' THEN 0 ELSE 1 END,
            m.asset_amt DESC NULLS LAST
    """).fetchdf()
    
    logger.success(f"   ✅ Found {len(joined):,} MA orgs with Form 990 filings in index")
    logger.info(f"   📉 Skipping {len(ma_df) - len(joined):,} orgs without filings")
    
    # Sample if requested
    if args.sample:
        joined = joined.head(args.sample)
        logger.info(f"   🎲 Sampled {len(joined):,} orgs for testing")
    
    # Step 2: Enrich with GT990
    logger.info(f"\n🚀 Step 2: Enriching {len(joined):,} organizations...")
    logger.info(f"   Concurrency: {args.concurrent}")
    logger.info(f"   Mode: {'LOCAL XMLs' if args.use_local else 'DOWNLOAD from S3'}")
    
    enricher = GivingTuesday990Enricher(
        max_concurrent=args.concurrent,
        use_local_xmls=args.use_local
    )
    
    enriched_df = await enricher.enrich_dataframe(
        joined,
        skip_enriched=False,  # First run - don't skip
        batch_size=2000
    )
    
    # Step 3: Merge back with original dataset
    logger.info("\n💾 Step 3: Saving results...")
    
    # Save enriched subset
    output_path = 'data/gold/states/MA/nonprofits_organizations.parquet'
    
    # Read original
    original_df = pd.read_parquet(output_path)
    
    # Update enriched records (merge on EIN)
    # First, drop form_990 columns from original if they exist
    form_990_cols = [c for c in original_df.columns if c.startswith('form_990_')]
    if form_990_cols:
        original_df = original_df.drop(columns=form_990_cols)
    
    # Merge
    updated_df = original_df.merge(
        enriched_df[['ein'] + [c for c in enriched_df.columns if c.startswith('form_990_')]],
        on='ein',
        how='left'
    )
    
    # Save
    updated_df.to_parquet(output_path, index=False)
    logger.success(f"✅ Saved to: {output_path}")
    
    # Stats
    enriched_count = enriched_df['form_990_status'].eq('found').sum()
    logger.info(f"\n📊 Results:")
    logger.info(f"   Total processed: {len(enriched_df):,}")
    logger.info(f"   Successfully enriched: {enriched_count:,}")
    logger.info(f"   Not found: {len(enriched_df) - enriched_count:,}")
    logger.info(f"   Total dataset size: {len(updated_df):,}")
    
    # Show sample
    if enriched_count > 0:
        sample = enriched_df[enriched_df['form_990_status'] == 'found'].head(3)
        logger.info(f"\n📋 Sample enriched orgs:")
        for _, row in sample.iterrows():
            logger.info(f"   • {row['name']}")
            if row.get('form_990_total_revenue'):
                logger.info(f"     Revenue: ${row['form_990_total_revenue']:,.0f}")
            if row.get('form_990_officers'):
                import json
                try:
                    officers = json.loads(row['form_990_officers'])
                    logger.info(f"     Officers: {len(officers)}")
                except:
                    pass
    
    logger.success("\n🎉 Enrichment complete!")
    
    conn.close()


if __name__ == '__main__':
    asyncio.run(main())
