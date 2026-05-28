#!/usr/bin/env python3
"""
Create nonprofit officer contacts tables from Form 990 enrichment data.

Normalizes the form_990_officers JSON field into proper contact tables:
- contacts_nonprofit_officers.parquet (current snapshot)
- contacts_nonprofit_officers_YYYY.parquet (annual snapshots)
- contacts_nonprofit_officers_history.parquet (multi-year salary history)

Usage:
    python scripts/create_nonprofit_officer_contacts.py
    python scripts/create_nonprofit_officer_contacts.py --state MA
    python scripts/create_nonprofit_officer_contacts.py --all-states
"""

import sys
from pathlib import Path
import argparse
from loguru import logger

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.create_contacts_gold_tables import ContactsGoldTableCreator

logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


def main():
    parser = argparse.ArgumentParser(
        description='Create nonprofit officer contact tables from Form 990 data'
    )
    parser.add_argument('--state', type=str, help='Process single state (e.g., MA)')
    parser.add_argument('--all-states', action='store_true', help='Process all states')
    parser.add_argument('--years', type=int, nargs='+', help='Tax years to create snapshots for')
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    gold_dir = project_root / "data" / "gold"
    
    logger.info("=" * 80)
    logger.info("CREATE NONPROFIT OFFICER CONTACTS")
    logger.info("=" * 80)
    logger.info("")
    
    # Determine states to process
    if args.state:
        states = [args.state]
    elif args.all_states:
        states_dir = gold_dir / "states"
        if not states_dir.exists():
            logger.error(f"States directory not found: {states_dir}")
            return 1
        states = [d.name for d in states_dir.iterdir() if d.is_dir()]
    else:
        # Default: find states with form990 data
        states_dir = gold_dir / "states"
        if states_dir.exists():
            states = [
                d.name for d in states_dir.iterdir() 
                if d.is_dir() and (d / "nonprofits_form990.parquet").exists()
            ]
        else:
            logger.error("No states directory found. Run enrichment first.")
            return 1
    
    if not states:
        logger.error("No states with Form 990 data found.")
        logger.info("Run: ./scripts/enrich_all_states_local.sh")
        return 1
    
    logger.info(f"Processing {len(states)} states: {', '.join(states)}")
    logger.info("")
    
    # Process each state
    for state in states:
        logger.info(f"\n{'='*80}")
        logger.info(f"STATE: {state}")
        logger.info(f"{'='*80}\n")
        
        state_dir = gold_dir / "states" / state
        
        # Check if form990 data exists
        form990_file = state_dir / "nonprofits_form990.parquet"
        if not form990_file.exists():
            logger.warning(f"⚠️  No Form 990 data found: {form990_file}")
            logger.info("   Run: ./scripts/enrich_all_states_local.sh")
            continue
        
        # Create contacts creator for this state
        creator = ContactsGoldTableCreator(
            meetings_gold_dir=gold_dir,  # Used to find state dirs
            output_dir=state_dir
        )
        
        # Create current snapshot
        logger.info("Creating current officer contacts snapshot...")
        contacts_df = creator.create_contacts_nonprofit_officers()
        
        if contacts_df.empty:
            logger.warning(f"⚠️  No officer data extracted for {state}")
            continue
        
        # Get unique years from the data
        unique_years = sorted(contacts_df['snapshot_year'].dropna().unique(), reverse=True)
        logger.info(f"\nFound data for years: {unique_years}")
        
        # Create year-specific snapshots if requested
        if args.years:
            years_to_process = args.years
        else:
            # Default: create snapshots for last 3 years
            years_to_process = unique_years[:3] if len(unique_years) >= 3 else unique_years
        
        if years_to_process:
            logger.info(f"\nCreating annual snapshots for years: {years_to_process}")
            for year in years_to_process:
                logger.info(f"\nYear {year}:")
                creator.create_contacts_nonprofit_officers(snapshot_year=year)
            
            # Create history table combining all years
            logger.info("\nCreating multi-year history table...")
            history_df = creator.create_nonprofit_officers_history(years=years_to_process)
            
            if not history_df.empty:
                # Show compensation trends
                logger.info("\n📊 Compensation Trends:")
                avg_by_year = history_df.groupby('snapshot_year')['compensation'].agg(['mean', 'median', 'count'])
                for year, row in avg_by_year.iterrows():
                    logger.info(
                        f"   {year}: "
                        f"Mean: ${row['mean']:,.0f} | "
                        f"Median: ${row['median']:,.0f} | "
                        f"Officers: {int(row['count']):,}"
                    )
    
    logger.info("\n" + "=" * 80)
    logger.success("✅ OFFICER CONTACTS CREATION COMPLETE!")
    logger.info("=" * 80)
    logger.info("\nCreated tables per state:")
    logger.info("  • contacts_nonprofit_officers.parquet (current)")
    logger.info("  • contacts_nonprofit_officers_YYYY.parquet (annual snapshots)")
    logger.info("  • contacts_nonprofit_officers_history.parquet (multi-year trends)")
    logger.info("")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
