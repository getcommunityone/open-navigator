---
title: Fast Nonprofit Enrichment Strategy
---

# FAST Nonprofit Enrichment Strategy

This document explains how to enrich 1.9M+ nonprofits MUCH faster than sequential API calls.

Current Problem:
- Sequential: 1.9M × 0.5sec = 11.3 days (Every.org)
- Sequential: 1.9M × 1.0sec = 22.6 days (ProPublica)
- Total: ~34 days 😱

Fast Solutions:
1. ✅ Skip Already Enriched (INSTANT)
2. 🚀 Async Parallel Requests (50-100x faster)
3. 🎯 Smart Sampling (99% faster)
4. 💾 Incremental Updates (only enrich new/changed)
5. 🔄 Batch Processing (process in chunks)

```python
# ==============================================================================
# SOLUTION 1: Skip Already Enriched (INSTANT) ✅
# ==============================================================================

"""
Most nonprofits in IRS data are ALREADY in the enriched file!

Check:
    import pandas as pd
    
    base = pd.read_parquet('data/gold/nonprofits_organizations.parquet')
    enriched = pd.read_parquet('data/gold/nonprofits_organizations_everyorg.parquet')
    
    print(f"Base: {len(base):,}")
    print(f"Enriched: {len(enriched):,}")
    print(f"Already done: {len(enriched) / len(base) * 100:.1f}%")
    
    # Find which ones need enrichment
    needs_enrichment = base[~base['ein'].isin(enriched['ein'])]
    print(f"Needs enrichment: {len(needs_enrichment):,}")

Result: You probably only need to enrich a FEW THOUSAND, not 1.9M!
"""

# ==============================================================================
# SOLUTION 2: Async Parallel Requests (50-100x FASTER) 🚀
# ==============================================================================

"""
Use asyncio + aiohttp to make MANY requests concurrently.

Every.org allows reasonable concurrent requests. Test with 50-100 concurrent workers.

Example speedup:
- Sequential: 1.9M × 0.5sec = 11.3 days
- 50 workers: 1.9M × 0.5sec / 50 = 5.4 hours ⚡
- 100 workers: 1.9M × 0.5sec / 100 = 2.7 hours ⚡⚡

WARNING: Test first with small batch to avoid API bans!
"""

import asyncio
import aiohttp
from typing import List, Dict
import pandas as pd


async def fetch_nonprofit_async(session: aiohttp.ClientSession, ein: str, api_key: str) -> Dict:
    """Fetch single nonprofit asynchronously"""
    clean_ein = str(ein).replace('-', '').zfill(9)
    url = f"https://partners.every.org/v0.2/nonprofit/{clean_ein}"
    headers = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    
    try:
        async with session.get(url, headers=headers, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                return {'ein': ein, 'success': True, 'data': data}
            else:
                return {'ein': ein, 'success': False, 'error': response.status}
    except Exception as e:
        return {'ein': ein, 'success': False, 'error': str(e)}


async def enrich_batch_async(eins: List[str], api_key: str, max_concurrent: int = 50) -> List[Dict]:
    """Enrich a batch of nonprofits with controlled concurrency"""
    # Use semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_with_semaphore(session, ein):
        async with semaphore:
            return await fetch_nonprofit_async(session, ein, api_key)
    
    # Create session with connection pooling
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
    timeout = aiohttp.ClientTimeout(total=30)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [fetch_with_semaphore(session, ein) for ein in eins]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results


def enrich_nonprofits_fast(
    df: pd.DataFrame,
    api_key: str,
    batch_size: int = 1000,
    max_concurrent: int = 50,
    output_file: str = 'data/gold/nonprofits_enriched_fast.parquet'
):
    """
    Enrich nonprofits using async parallel processing
    
    Args:
        df: DataFrame with 'ein' column
        api_key: Every.org API key
        batch_size: Process this many at once
        max_concurrent: Concurrent requests per batch
        output_file: Where to save results
    
    Example:
        df = pd.read_parquet('data/gold/nonprofits_organizations.parquet')
        
        # Test with small sample first!
        sample = df.head(1000)
        enrich_nonprofits_fast(sample, api_key, batch_size=100, max_concurrent=10)
        
        # Then scale up
        enrich_nonprofits_fast(df, api_key, batch_size=5000, max_concurrent=50)
    """
    from tqdm import tqdm
    
    all_results = []
    
    # Process in batches to avoid memory issues
    for i in tqdm(range(0, len(df), batch_size), desc="Processing batches"):
        batch_df = df.iloc[i:i+batch_size]
        eins = batch_df['ein'].tolist()
        
        # Run async batch
        results = asyncio.run(enrich_batch_async(eins, api_key, max_concurrent))
        all_results.extend(results)
        
        # Save incrementally every 10 batches
        if (i // batch_size) % 10 == 0 and all_results:
            temp_df = pd.DataFrame(all_results)
            temp_df.to_parquet(f"{output_file}.tmp", index=False)
    
    # Convert results to DataFrame
    results_df = pd.DataFrame(all_results)
    results_df.to_parquet(output_file, index=False)
    
    success_rate = results_df['success'].sum() / len(results_df) * 100
    print(f"\n✅ Enriched {len(results_df):,} nonprofits")
    print(f"   Success rate: {success_rate:.1f}%")
    print(f"   Saved to: {output_file}")


# ==============================================================================
# SOLUTION 3: Smart Sampling (99% FASTER) 🎯
# ==============================================================================

"""
Do you REALLY need ALL 1.9M enriched?

For most use cases, a representative sample is sufficient:

- Dashboard/website: Sample 10,000-100,000 (0.5-5%)
- Research: Stratified sample by state/category
- Production: Only enrich what users request (on-demand)

Example:
    # Sample by state to get representative coverage
    import pandas as pd
    
    df = pd.read_parquet('data/gold/nonprofits_organizations.parquet')
    
    # Get 1000 per state (ensures geographic coverage)
    sampled = df.groupby('state').sample(n=min(1000, len(df)), replace=False)
    
    # Result: ~50,000 nonprofits instead of 1.9M
    # Enrichment time: 50K × 0.5sec / 50 workers = 8 minutes ⚡⚡⚡
"""

# ==============================================================================
# SOLUTION 4: Incremental Updates (ONLY NEW/CHANGED) 💾
# ==============================================================================

"""
Only enrich NEW nonprofits or re-enrich ones older than X days.

Check the existing enrich script - it already supports this!

Usage:
    python scripts/enrich_nonprofits_everyorg.py \\
        --input data/gold/nonprofits_organizations.parquet \\
        --output data/gold/nonprofits_organizations_everyorg.parquet \\
        --incremental \\
        --max-age-days 30

This will:
1. ✅ Skip nonprofits already enriched in last 30 days
2. ✅ Only enrich NEW nonprofits not in enriched file
3. ✅ Re-enrich old entries (>30 days)

Result: Maybe only 10,000-50,000 need enrichment = 2-10 hours
"""

# ==============================================================================
# SOLUTION 5: Batch Processing (CHUNKS) 🔄
# ==============================================================================

"""
Process in manageable chunks instead of all at once.

Example workflow:
    1. Split by state: 50 files × 40K nonprofits each
    2. Process 1 state per day = 50 days (manageable)
    3. Or run multiple states in parallel on different machines

Usage:
    # Split by state
    df = pd.read_parquet('data/gold/nonprofits_organizations.parquet')
    
    for state in df['state'].unique():
        state_df = df[df['state'] == state]
        state_df.to_parquet(f'data/chunks/nonprofits_{state}.parquet')
    
    # Then enrich each chunk
    for state in ['AL', 'AK', 'AZ', ...]:
        python scripts/enrich_nonprofits_everyorg.py \\
            --input data/chunks/nonprofits_{state}.parquet \\
            --output data/enriched/nonprofits_{state}_enriched.parquet
"""

# ==============================================================================
# RECOMMENDED APPROACH 🎯
# ==============================================================================

"""
PHASE 1: Smart Sampling (TODAY)
- Sample 50,000 representative nonprofits
- Enrich with async (50 concurrent workers)
- Time: ~15 minutes
- Use for dashboard/website launch

PHASE 2: Incremental Enrichment (ONGOING)
- Enrich new nonprofits as they're added monthly
- Re-enrich popular ones every 30 days
- Time: 1-2 hours per month

PHASE 3: On-Demand Enrichment (PRODUCTION)
- When user searches/views a nonprofit, enrich it if not already done
- Cache result for 30 days
- No upfront cost!

PHASE 4: Full Enrichment (OPTIONAL)
- If you REALLY need all 1.9M enriched
- Use async with 100 workers
- Run overnight on dedicated server
- Time: ~3-6 hours
"""

# ==============================================================================
# COST ANALYSIS 💰
# ==============================================================================

"""
Every.org API Pricing:
- Free tier: 10,000 requests/month
- Paid tier: $0.001 per request (1 million = $1,000)

For 1.9M nonprofits:
- Cost: 1,952,238 × $0.001 = $1,952.24

ProPublica API:
- FREE (but slow rate limits)

Recommendation:
- Use FREE ProPublica data (already have it!)
- Use Every.org for 50K sample or incremental updates (within free tier)
"""

# ==============================================================================
# EXAMPLE: FAST ENRICHMENT SCRIPT
# ==============================================================================

if __name__ == "__main__":
    import argparse
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Fast nonprofit enrichment with async")
    parser.add_argument("--input", required=True, help="Input parquet file")
    parser.add_argument("--output", required=True, help="Output parquet file")
    parser.add_argument("--sample", type=int, help="Sample size (e.g., 50000)")
    parser.add_argument("--concurrent", type=int, default=50, help="Concurrent requests")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size")
    
    args = parser.parse_args()
    
    api_key = os.getenv('EVERYORG_API_KEY')
    if not api_key:
        print("ERROR: EVERYORG_API_KEY not found in .env")
        exit(1)
    
    # Load data
    df = pd.read_parquet(args.input)
    print(f"Loaded {len(df):,} nonprofits")
    
    # Sample if requested
    if args.sample:
        df = df.sample(n=min(args.sample, len(df)))
        print(f"Sampling {len(df):,} nonprofits")
    
    # Enrich!
    enrich_nonprofits_fast(
        df,
        api_key,
        batch_size=args.batch_size,
        max_concurrent=args.concurrent,
        output_file=args.output
    )
```
