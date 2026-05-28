#!/usr/bin/env python3
"""
Export Committee Reports from OpenStates Database

Extracts committee reports for bills to support AI policy analysis.

Committee reports contain:
- Expert analysis of bills
- Recommendations (pass, fail, amend)
- Fiscal impact assessments
- Stakeholder input summaries

Usage:
    python scripts/datasources/openstates/export_committee_reports.py
    python scripts/datasources/openstates/export_committee_reports.py --states GA,MA
"""

import pandas as pd
import psycopg2
import os
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
import argparse

load_dotenv()

# Paths
GOLD_DIR = Path("data/gold")
OUTPUT_FILE = GOLD_DIR / "bills_committee_reports.parquet"

# Database connection
DB_URL = os.getenv('OPENSTATES_DATABASE_URL', 'postgresql://postgres:postgres@localhost:5433/openstates')


def export_committee_reports(states: list = None):
    """
    Export committee reports from OpenStates database
    
    Args:
        states: List of state codes (e.g., ['GA', 'MA']). None = all states.
    """
    
    logger.info("=" * 80)
    logger.info("EXPORTING COMMITTEE REPORTS")
    logger.info("=" * 80)
    
    # Connect to database
    logger.info("Connecting to OpenStates database...")
    try:
        conn = psycopg2.connect(DB_URL)
        logger.info("✅ Connected successfully")
    except Exception as e:
        logger.error(f"❌ Could not connect to database: {e}")
        return
    
    # Build query
    logger.info("Fetching committee reports...")
    
    where_clause = ""
    if states:
        state_list = "', '".join(states)
        where_clause = f"AND j.division_id IN (SELECT CONCAT('ocd-division/country:us/state:', LOWER(code)) FROM unnest(ARRAY['{state_list}']) AS code)"
    
    query = f"""
        SELECT 
            -- Bill info
            b.id as bill_id,
            b.identifier as bill_number,
            b.title as bill_title,
            
            -- Session
            s.identifier as session,
            s.name as session_name,
            
            -- Jurisdiction
            j.name as jurisdiction_name,
            UPPER(SUBSTRING(j.division_id FROM 'state:([a-z]{{2}})')) as state,
            
            -- Document info
            bd.id as document_id,
            bd.note as document_note,
            bd.date as document_date,
            
            -- Document links
            bdl.url as document_url,
            bdl.media_type,
            
            -- Metadata
            b.created_at,
            b.updated_at
            
        FROM opencivicdata_billdocument bd
        JOIN opencivicdata_bill b ON bd.bill_id = b.id
        JOIN opencivicdata_legislativesession s ON b.legislative_session_id = s.id
        JOIN opencivicdata_jurisdiction j ON s.jurisdiction_id = j.id
        LEFT JOIN opencivicdata_billdocumentlink bdl ON bdl.document_id = bd.id
        
        WHERE 
            LOWER(bd.note) LIKE '%committee%report%'
            OR LOWER(bd.note) LIKE '%fiscal%note%'
            OR LOWER(bd.note) LIKE '%analysis%'
            OR LOWER(bd.note) LIKE '%summary%'
        {where_clause}
        
        ORDER BY b.updated_at DESC, j.name, b.identifier
    """
    
    df = pd.read_sql(query, conn)
    
    logger.info(f"✅ Fetched {len(df):,} committee report records")
    
    if len(df) == 0:
        logger.warning("No committee reports found")
        conn.close()
        return
    
    # Stats
    logger.info("\n📊 Statistics:")
    logger.info(f"   Unique bills with reports: {df['bill_id'].nunique():,}")
    logger.info(f"   Total reports: {df['document_id'].nunique():,}")
    logger.info(f"   States: {df['state'].nunique()}")
    logger.info(f"   With document URLs: {df['document_url'].notna().sum():,}")
    
    # Report types
    logger.info("\n📑 Report types:")
    report_types = df['document_note'].value_counts().head(10)
    for note, count in report_types.items():
        logger.info(f"   {note}: {count:,}")
    
    # Top states
    logger.info("\n🗺️  Top states by report count:")
    top_states = df['state'].value_counts().head(10)
    for state, count in top_states.items():
        logger.info(f"   {state}: {count:,} reports")
    
    # Save to parquet
    logger.info(f"\nSaving to {OUTPUT_FILE}...")
    GOLD_DIR.mkdir(exist_ok=True)
    df.to_parquet(OUTPUT_FILE, index=False)
    
    size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
    logger.info(f"✅ Saved {len(df):,} records ({size_mb:.2f} MB)")
    
    # Sample data
    logger.info("\n📝 Sample committee reports:")
    sample = df[df['document_url'].notna()].head(3)
    for _, row in sample.iterrows():
        logger.info(f"\n   Bill: {row['bill_number']} ({row['state']})")
        logger.info(f"   Title: {row['bill_title'][:80]}...")
        logger.info(f"   Report Type: {row['document_note']}")
        logger.info(f"   Date: {row['document_date']}")
        logger.info(f"   URL: {row['document_url']}")
    
    conn.close()
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ EXPORT COMPLETE!")
    logger.info("=" * 80)
    logger.info(f"\nNext steps:")
    logger.info(f"1. Review data: .venv/bin/python -c \"import pandas as pd; print(pd.read_parquet('{OUTPUT_FILE}').head())\"")
    logger.info(f"2. Integrate with AI analysis: Pass committee reports to PolicyReasoningAnalyzer")


def main():
    parser = argparse.ArgumentParser(description="Export committee reports from OpenStates")
    parser.add_argument("--states", help="Comma-separated state codes (e.g., GA,MA,WA)")
    args = parser.parse_args()
    
    states = args.states.split(',') if args.states else None
    
    export_committee_reports(states)


if __name__ == "__main__":
    main()
