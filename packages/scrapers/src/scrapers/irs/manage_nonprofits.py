#!/usr/bin/env python3
"""
Unified Nonprofit Data Manager

Manages a single nonprofits_organizations.parquet file with incremental enrichment.
Replaces the pattern of creating multiple files (tuscaloosa, form990, etc).

Usage:
    # Enrich a subset (updates main file in place)
    python scripts/manage_nonprofits.py enrich-990 --states AL --sample 100
    
    # Enrich specific EINs
    python scripts/manage_nonprofits.py enrich-990 --ein-list eins.txt
    
    # Enrich all with BigQuery
    python scripts/manage_nonprofits.py enrich-bigquery
    
    # Show stats
    python scripts/manage_nonprofits.py stats
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

# Single source of truth
MAIN_FILE = Path("data/gold/nonprofits_organizations.parquet")


def load_data():
    """Load the main nonprofits file."""
    if not MAIN_FILE.exists():
        logger.error(f"❌ Main file not found: {MAIN_FILE}")
        logger.error("   Run: python pipeline/create_gold_tables.py --nonprofits-only")
        sys.exit(1)
    
    logger.info(f"📂 Loading: {MAIN_FILE}")
    df = pd.read_parquet(MAIN_FILE)
    logger.info(f"   Loaded {len(df):,} nonprofits")
    return df


def save_data(df):
    """Save back to main file."""
    MAIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(MAIN_FILE, index=False)
    logger.success(f"💾 Saved {len(df):,} nonprofits to: {MAIN_FILE}")


def apply_filters(df, states=None, ntee=None, sample=None, ein_list=None):
    """Apply filters to select subset for enrichment."""
    original_count = len(df)
    filtered = df.copy()
    
    if states:
        filtered = filtered[filtered['state'].isin(states)]
        logger.info(f"   States {states}: {len(filtered):,} nonprofits")
    
    if ntee:
        ntee_patterns = [n.upper() for n in ntee]
        filtered = filtered[filtered['ntee_code'].str.upper().str.startswith(tuple(ntee_patterns), na=False)]
        logger.info(f"   NTEE {ntee}: {len(filtered):,} nonprofits")
    
    if ein_list:
        with open(ein_list) as f:
            eins = [line.strip() for line in f if line.strip()]
        filtered = filtered[filtered['ein'].isin(eins)]
        logger.info(f"   EIN list: {len(filtered):,} nonprofits")
    
    if sample:
        filtered = filtered.sample(n=min(sample, len(filtered)), random_state=42)
        logger.info(f"   Sampled: {len(filtered):,} nonprofits")
    
    if len(filtered) == original_count:
        logger.warning("⚠️  No filters applied - will process ALL nonprofits!")
        confirm = input("   Continue? [y/N]: ")
        if confirm.lower() != 'y':
            logger.info("Aborted.")
            sys.exit(0)
    
    return filtered


def merge_enriched(df_full, df_enriched, prefix='form_990_'):
    """Merge enriched subset back into full dataset."""
    logger.info(f"🔄 Merging {len(df_enriched):,} enriched nonprofits...")
    
    # Get columns added by enrichment
    enriched_cols = [col for col in df_enriched.columns if col.startswith(prefix)]
    
    # Remove old enrichment data for updated EINs
    eins_updated = df_enriched['ein'].values
    df_remaining = df_full[~df_full['ein'].isin(eins_updated)]
    
    # Combine
    df_merged = pd.concat([df_remaining, df_enriched], ignore_index=True)
    df_merged = df_merged.sort_values('ein').reset_index(drop=True)
    
    logger.success(f"✅ Merged: {len(df_merged):,} total, updated {len(df_enriched):,}")
    return df_merged


def cmd_stats(args):
    """Show statistics about the main file."""
    df = load_data()
    
    print("\n" + "=" * 70)
    print("NONPROFIT DATA STATISTICS")
    print("=" * 70)
    
    print(f"\n📊 TOTAL: {len(df):,} organizations")
    
    # By state
    print(f"\n🗺️  TOP 10 STATES:")
    state_counts = df['state'].value_counts().head(10)
    for state, count in state_counts.items():
        print(f"   {state}: {count:,}")
    
    # By NTEE
    print(f"\n📋 TOP 10 NTEE CATEGORIES:")
    ntee_counts = df['ntee_code'].str[0].value_counts().head(10)
    ntee_names = {
        'E': 'Health', 'P': 'Human Services', 'B': 'Education',
        'X': 'Religion', 'A': 'Arts/Culture', 'N': 'Recreation',
        'S': 'Community', 'T': 'Philanthropy', 'Q': 'International',
        'L': 'Housing'
    }
    for ntee, count in ntee_counts.items():
        name = ntee_names.get(ntee, 'Other')
        print(f"   {ntee} ({name}): {count:,}")
    
    # Enrichment status
    print(f"\n💰 ENRICHMENT STATUS:")
    
    if 'form_990_status' in df.columns:
        has_990 = (df['form_990_status'] == 'found').sum()
        print(f"   Form 990 data: {has_990:,} ({100*has_990/len(df):.1f}%)")
    
    if 'bigquery_mission' in df.columns:
        has_bq = df['bigquery_mission'].notna().sum()
        print(f"   BigQuery data: {has_bq:,} ({100*has_bq/len(df):.1f}%)")
    
    if 'cn_star_rating' in df.columns:
        has_cn = df['cn_star_rating'].notna().sum()
        print(f"   Charity Navigator: {has_cn:,} ({100*has_cn/len(df):.1f}%)")
    
    # Combined mission coverage
    mission_cols = [c for c in df.columns if 'mission' in c.lower()]
    if mission_cols:
        has_any_mission = df[mission_cols].notna().any(axis=1).sum()
        print(f"\n📝 MISSION STATEMENTS:")
        print(f"   At least one source: {has_any_mission:,} ({100*has_any_mission/len(df):.1f}%)")
        for col in mission_cols:
            count = df[col].notna().sum()
            print(f"   {col}: {count:,} ({100*count/len(df):.1f}%)")
    
    # File size
    file_size = MAIN_FILE.stat().st_size / (1024 * 1024)
    print(f"\n💾 FILE SIZE: {file_size:.1f} MB")
    
    print("=" * 70)


def cmd_enrich_990(args):
    """Enrich with GivingTuesday Form 990 data."""
    import subprocess
    
    # Build command
    cmd = [
        "python", "scripts/enrich_nonprofits_gt990.py",
        "--input", str(MAIN_FILE),
        "--concurrent", str(args.concurrent)
    ]
    
    if args.states:
        cmd.extend(["--states"] + args.states)
    if args.ntee:
        cmd.extend(["--ntee"] + args.ntee)
    if args.sample:
        cmd.extend(["--sample", str(args.sample)])
    if args.ein_list:
        cmd.extend(["--ein-list", args.ein_list])
    
    logger.info(f"🚀 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        logger.error("❌ Enrichment failed")
        sys.exit(1)
    
    logger.success("✅ Form 990 enrichment complete!")


def cmd_enrich_bigquery(args):
    """Enrich with Google BigQuery data."""
    import subprocess
    
    # Step 1: Export SQL
    sql_file = "scripts/bigquery_query.sql"
    cmd_export = [
        "python", "scripts/enrich_nonprofits_bigquery.py",
        "--input", str(MAIN_FILE),
        "--export-sql", sql_file
    ]
    
    if args.states:
        cmd_export.extend(["--states"] + args.states)
    if args.sample:
        cmd_export.extend(["--sample", str(args.sample)])
    
    logger.info(f"📝 Exporting SQL query...")
    subprocess.run(cmd_export, check=True)
    
    # Instructions for user
    logger.info("\n" + "=" * 70)
    logger.info("NEXT STEPS:")
    logger.info("=" * 70)
    logger.info("1. Go to: https://console.cloud.google.com/bigquery")
    logger.info(f"2. Paste SQL from: {sql_file}")
    logger.info("3. Click 'RUN'")
    logger.info("4. Export as CSV to: data/cache/bigquery_results.csv")
    logger.info("5. Run: python scripts/manage_nonprofits.py merge-bigquery")
    logger.info("=" * 70)


def cmd_merge_bigquery(args):
    """Merge BigQuery CSV results into main file."""
    import subprocess
    
    csv_file = args.csv or "data/cache/bigquery_results.csv"
    
    if not Path(csv_file).exists():
        logger.error(f"❌ CSV file not found: {csv_file}")
        logger.error("   Run 'enrich-bigquery' first and export results")
        sys.exit(1)
    
    cmd = [
        "python", "scripts/enrich_nonprofits_bigquery.py",
        "--input", str(MAIN_FILE),
        "--from-csv", csv_file,
        "--update-in-place"
    ]
    
    logger.info(f"🔄 Merging BigQuery data from: {csv_file}")
    subprocess.run(cmd, check=True)
    
    logger.success("✅ BigQuery data merged!")


def main():
    parser = argparse.ArgumentParser(
        description="Manage unified nonprofit data file",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Stats command
    subparsers.add_parser('stats', help='Show statistics about nonprofit data')
    
    # Form 990 enrichment
    p990 = subparsers.add_parser('enrich-990', help='Enrich with Form 990 data')
    p990.add_argument('--states', nargs='+', help='Filter to states (e.g., AL MI)')
    p990.add_argument('--ntee', nargs='+', help='Filter to NTEE codes (e.g., E P)')
    p990.add_argument('--sample', type=int, help='Sample N organizations')
    p990.add_argument('--ein-list', help='File with EINs to enrich')
    p990.add_argument('--concurrent', type=int, default=20, help='Concurrent downloads')
    
    # BigQuery enrichment
    pbq = subparsers.add_parser('enrich-bigquery', help='Export BigQuery SQL')
    pbq.add_argument('--states', nargs='+', help='Filter to states')
    pbq.add_argument('--sample', type=int, help='Sample N organizations')
    
    # Merge BigQuery
    pmerge = subparsers.add_parser('merge-bigquery', help='Merge BigQuery CSV results')
    pmerge.add_argument('--csv', help='CSV file path (default: data/cache/bigquery_results.csv)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Route to command
    if args.command == 'stats':
        cmd_stats(args)
    elif args.command == 'enrich-990':
        cmd_enrich_990(args)
    elif args.command == 'enrich-bigquery':
        cmd_enrich_bigquery(args)
    elif args.command == 'merge-bigquery':
        cmd_merge_bigquery(args)


if __name__ == '__main__':
    main()
