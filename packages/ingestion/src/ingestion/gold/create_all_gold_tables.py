"""
Create All Gold Tables - Main Orchestration Script

This script runs both pipelines:
1. Meeting data gold tables (from LocalView cache 2006-2023)
2. Nonprofit data gold tables (from ProPublica API + other sources)

Usage:
    # Run both pipelines
    python scripts/create_all_gold_tables.py
    
    # Run only meetings pipeline
    python scripts/create_all_gold_tables.py --meetings-only
    
    # Run only nonprofits pipeline
    python scripts/create_all_gold_tables.py --nonprofits-only
    
    # Specify states for nonprofit discovery
    python scripts/create_all_gold_tables.py --states AL MI NY CA
    
    # Skip nonprofit API discovery, use cached data
    python scripts/create_all_gold_tables.py --skip-discovery

Output:
    data/gold/national/meetings_*.parquet
    data/gold/nonprofits_*.parquet
"""

import sys
from pathlib import Path
import argparse
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pipeline.create_meetings_gold_tables import MeetingGoldTableCreator
from pipeline.create_nonprofits_gold_tables import NonprofitGoldTableCreator
from pipeline.create_contacts_gold_tables import ContactsGoldTableCreator


def main():
    """Main orchestration function"""
    parser = argparse.ArgumentParser(
        description="Create all gold tables from meeting and nonprofit data"
    )
    parser.add_argument(
        "--meetings-only",
        action="store_true",
        help="Only create meeting gold tables"
    )
    parser.add_argument(
        "--nonprofits-only",
        action="store_true",
        help="Only create nonprofit gold tables"
    )
    parser.add_argument(
        "--states",
        nargs="+",
        default=["AL", "MI"],
        help="State codes for nonprofit discovery (e.g., AL MI NY)"
    )
    parser.add_argument(
        "--ntee-codes",
        nargs="+",
        default=None,
        help="NTEE codes to search (e.g., E P K). Default: E P K L S W. Use 'ALL' to skip filtering."
    )
    parser.add_argument(
        "--skip-discovery",
        action="store_true",
        help="Skip nonprofit API discovery, use existing bronze data"
    )
    parser.add_argument(
        "--use-irs",
        action="store_true",
        help="Use IRS EO-BMF bulk data instead of ProPublica API (RECOMMENDED - gets ALL nonprofits!)"
    )
    parser.add_argument(
        "--download-all-irs",
        action="store_true",
        help="Download ALL 1.9M+ nonprofits from IRS (4 regional files). Requires --use-irs."
    )
    parser.add_argument(
        "--extract-contacts",
        action="store_true",
        help="Extract contacts (officials) from meeting transcripts after creating meeting tables"
    )
    
    args = parser.parse_args()
    
    # Determine which pipelines to run
    run_meetings = not args.nonprofits_only
    run_nonprofits = not args.meetings_only
    
    logger.info("=" * 70)
    logger.info("GOLD TABLE CREATION PIPELINE")
    logger.info("=" * 70)
    logger.info(f"Run Meetings Pipeline: {run_meetings}")
    logger.info(f"Run Nonprofits Pipeline: {run_nonprofits}")
    if run_nonprofits:
        logger.info(f"States: {', '.join(args.states)}")
        logger.info(f"Skip Discovery: {args.skip_discovery}")
    logger.info("=" * 70)
    logger.info("")
    
    # Run meetings pipeline
    if run_meetings:
        logger.info("")
        logger.info("🗓️  STARTING MEETINGS PIPELINE")
        logger.info("-" * 70)
        try:
            meeting_creator = MeetingGoldTableCreator()
            meeting_creator.create_all_gold_tables()
            logger.success("✅ Meetings pipeline completed successfully!")
            
            # Extract contacts if requested
            if args.extract_contacts:
                logger.info("")
                logger.info("👥 EXTRACTING CONTACTS FROM MEETINGS")
                logger.info("-" * 70)
                contacts_creator = ContactsGoldTableCreator()
                contacts_creator.create_all_contacts_tables()
                logger.success("✅ Contacts extraction completed successfully!")
        except Exception as e:
            logger.error(f"❌ Meetings pipeline failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Run nonprofits pipeline
    if run_nonprofits:
        logger.info("")
        logger.info("🏛️  STARTING NONPROFITS PIPELINE")
        logger.info("-" * 70)
        try:
            nonprofit_creator = NonprofitGoldTableCreator()
            
            # Handle NTEE codes argument
            ntee_codes = args.ntee_codes
            if ntee_codes and len(ntee_codes) == 1 and ntee_codes[0].upper() == 'ALL':
                ntee_codes = []  # Empty list means get all nonprofits
            
            nonprofit_creator.create_all_gold_tables(
                states=args.states,
                ntee_codes=ntee_codes,
                skip_discovery=args.skip_discovery,
                use_irs_data=args.use_irs,
                download_all_irs=args.download_all_irs
            )
            logger.success("✅ Nonprofits pipeline completed successfully!")
        except Exception as e:
            logger.error(f"❌ Nonprofits pipeline failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Final summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 70)
    
    gold_dir = Path("data/gold")
    if gold_dir.exists():
        import pandas as pd
        
        all_gold_files = sorted(gold_dir.glob("*.parquet"))
        
        if all_gold_files:
            logger.info(f"\n📊 Created {len(all_gold_files)} gold tables:\n")
            
            # Separate by category
            meeting_files = [f for f in all_gold_files if 'meeting' in f.name]
            nonprofit_files = [f for f in all_gold_files if 'nonprofit' in f.name]
            contacts_files = [f for f in all_gold_files if 'contacts_' in f.name]
            other_files = [f for f in all_gold_files if f not in meeting_files + nonprofit_files + contacts_files]
            
            if meeting_files:
                logger.info("📅 Meeting Tables:")
                for file in meeting_files:
                    df = pd.read_parquet(file)
                    size_mb = file.stat().st_size / (1024 * 1024)
                    logger.info(f"   • {file.name}: {len(df):,} records ({size_mb:.2f} MB)")
            
            if contacts_files:
                logger.info("\n👥 Contacts Tables:")
                for file in contacts_files:
                    df = pd.read_parquet(file)
                    size_mb = file.stat().st_size / (1024 * 1024)
                    logger.info(f"   • {file.name}: {len(df):,} records ({size_mb:.2f} MB)")
            
            if nonprofit_files:
                logger.info("\n🏛️  Nonprofit Tables:")
                for file in nonprofit_files:
                    df = pd.read_parquet(file)
                    size_mb = file.stat().st_size / (1024 * 1024)
                    logger.info(f"   • {file.name}: {len(df):,} records ({size_mb:.2f} MB)")
            
            if other_files:
                logger.info("\n📂 Other Tables:")
                for file in other_files:
                    df = pd.read_parquet(file)
                    size_mb = file.stat().st_size / (1024 * 1024)
                    logger.info(f"   • {file.name}: {len(df):,} records ({size_mb:.2f} MB)")
            
            # Calculate totals
            total_records = sum(len(pd.read_parquet(f)) for f in all_gold_files)
            total_size_mb = sum(f.stat().st_size for f in all_gold_files) / (1024 * 1024)
            
            logger.info("")
            logger.info(f"📊 Total: {total_records:,} records across {len(all_gold_files)} tables ({total_size_mb:.2f} MB)")
        else:
            logger.warning("No gold tables found!")
    else:
        logger.warning("Gold directory does not exist!")
    
    logger.info("=" * 70)
    logger.success("✅ ALL PIPELINES COMPLETED!")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
