#!/usr/bin/env python3
"""
Export Legislators from OpenCivicData to Gold Parquet files

Exports legislators directly from opencivicdata_person, opencivicdata_membership,
and opencivicdata_post tables (no need for openstates_people table).

Files are saved to: data/gold/states/{STATE}/contact_official.parquet

Usage:
    python scripts/datasources/openstates/export_legislators_to_gold.py
    
    # Export specific states
    python scripts/datasources/openstates/export_legislators_to_gold.py --states MA,WA,AL
"""

import argparse
import psycopg2
import pandas as pd
from pathlib import Path
from loguru import logger
from typing import List, Optional

# Dev states for initial export
DEV_STATES = ['WA', 'MA', 'AL', 'GA', 'WI', 'IN']

# All US states
ALL_STATES = [
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
    'DC', 'PR'  # Include DC and Puerto Rico
]

# Database connection
DB_URL = "postgresql://postgres:password@localhost:5433/openstates"

# Output directory
GOLD_DIR = Path("data/gold")
STATES_DIR = GOLD_DIR / "states"
STATES_DIR.mkdir(parents=True, exist_ok=True)


def export_legislators_for_state(conn, state: str) -> Optional[pd.DataFrame]:
    """
    Export current legislators for a state from opencivicdata tables.
    
    Args:
        conn: Database connection
        state: Two-letter state code (e.g., 'MA', 'WA')
        
    Returns:
        DataFrame with legislator data or None if no data found
    """
    logger.info(f"Exporting legislators for {state}...")
    
    # Build jurisdiction ID
    jurisdiction_id = f"ocd-jurisdiction/country:us/state:{state.lower()}/government"
    
    query = """
        WITH recent_memberships AS (
            SELECT DISTINCT ON (m.person_id, org.classification)
                m.person_id,
                m.role,
                m.post_id,
                m.organization_id,
                m.start_date,
                m.end_date,
                org.classification,
                ROW_NUMBER() OVER (PARTITION BY m.person_id, org.classification ORDER BY m.start_date DESC) as rn
            FROM opencivicdata_membership m
            INNER JOIN opencivicdata_organization org ON org.id = m.organization_id
            WHERE org.jurisdiction_id = %(jurisdiction_id)s
              AND org.classification IN ('upper', 'lower', 'legislature')
            ORDER BY m.person_id, org.classification, m.start_date DESC
        )
        SELECT 
            p.id as official_id,
            p.name as full_name,
            %(state)s as state,
            p.primary_party as party,
            rm.role as role_type,
            post.label as district,
            rm.organization_id as jurisdiction,
            %(state)s as jurisdiction_name,
            p.email,
            NULL as phone,
            NULL as address,
            p.image as photo_url,
            rm.classification as chamber,
            rm.start_date,
            rm.end_date
        FROM opencivicdata_person p
        INNER JOIN recent_memberships rm ON rm.person_id = p.id
        LEFT JOIN opencivicdata_post post ON post.id = rm.post_id
        WHERE (rm.end_date IS NULL OR rm.end_date >= '2024-01-01')
        ORDER BY p.name
    """
    
    df = pd.read_sql(
        query,
        conn,
        params={'state': state.upper(), 'jurisdiction_id': jurisdiction_id}
    )
    
    if len(df) == 0:
        logger.warning(f"  No legislators found for {state}")
        return None
    
    # Create state directory
    state_dir = STATES_DIR / state.upper()
    state_dir.mkdir(parents=True, exist_ok=True)
    
    # Save to parquet
    output_path = state_dir / "contact_official.parquet"
    df.to_parquet(output_path, index=False, engine='pyarrow', compression='snappy')
    
    logger.info(f"  ✅ Exported {len(df):,} legislators to {output_path}")
    logger.info(f"  📧 With email: {df['email'].notna().sum()}")
    logger.info(f"  🏛️  Upper chamber: {(df['chamber'] == 'upper').sum()}")
    logger.info(f"  🏛️  Lower chamber: {(df['chamber'] == 'lower').sum()}")
    logger.info(f"  🎭 By party: {df['party'].value_counts().to_dict()}")
    
    return df


def main():
    parser = argparse.ArgumentParser(
        description="Export legislators from OpenCivicData to Gold parquet files"
    )
    parser.add_argument(
        "--states",
        help="Comma-separated list of state codes (e.g., 'MA,WA,AL'). Default: dev states"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Export all states"
    )
    parser.add_argument(
        "--db-url",
        default=DB_URL,
        help="PostgreSQL connection URL"
    )
    
    args = parser.parse_args()
    
    # Determine which states to export
    if args.all:
        states_to_export = ALL_STATES
    elif args.states:
        states_to_export = [s.strip().upper() for s in args.states.split(',')]
    else:
        states_to_export = DEV_STATES
    
    logger.info("=" * 80)
    logger.info("EXPORTING LEGISLATORS TO GOLD TABLES")
    logger.info("=" * 80)
    logger.info(f"Database: {args.db_url.split('@')[1] if '@' in args.db_url else args.db_url}")
    logger.info(f"States to export: {', '.join(states_to_export)}")
    logger.info(f"Output directory: {STATES_DIR}")
    logger.info("")
    
    # Connect to database
    try:
        conn = psycopg2.connect(args.db_url)
        logger.info("✅ Connected to OpenStates database")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return
    
    # Export each state
    total_legislators = 0
    successful_states = []
    
    for state in states_to_export:
        try:
            df = export_legislators_for_state(conn, state)
            if df is not None:
                total_legislators += len(df)
                successful_states.append(state)
        except Exception as e:
            logger.error(f"Error exporting {state}: {e}")
            continue
    
    conn.close()
    
    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ EXPORT COMPLETE")
    logger.info("=" * 80)
    logger.info(f"States exported: {len(successful_states)}/{len(states_to_export)}")
    logger.info(f"Total legislators: {total_legislators:,}")
    logger.info(f"Output directory: {STATES_DIR}")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Load into Neon search: python scripts/deployment/neon/migrate.py")
    logger.info("  2. Or upload to HuggingFace: python scripts/huggingface/upload_to_huggingface.py")


if __name__ == "__main__":
    main()
