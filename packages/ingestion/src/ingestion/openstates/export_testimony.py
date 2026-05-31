#!/usr/bin/env python3
"""
Export Testimony Data from OpenStates Database

Extracts legislative testimony from hearing events to support AI policy analysis.

Usage:
    python scripts/datasources/openstates/export_testimony.py
    python scripts/datasources/openstates/export_testimony.py --states GA,MA,WA
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
OUTPUT_FILE = GOLD_DIR / "bills_testimony.parquet"

# Database connection
DB_URL = os.getenv('OPENSTATES_DATABASE_URL', 'postgresql://postgres:postgres@localhost:5433/openstates')


def export_testimony(states: list = None):
    """
    Export legislative testimony from OpenStates database
    
    Args:
        states: List of state codes (e.g., ['GA', 'MA']). None = all states.
    """
    
    logger.info("=" * 80)
    logger.info("EXPORTING LEGISLATIVE TESTIMONY")
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
    logger.info("Fetching testimony data...")
    
    where_clause = ""
    if states:
        state_list = "', '".join(states)
        where_clause = f"AND j.division_id IN (SELECT CONCAT('ocd-division/country:us/state:', LOWER(code)) FROM unnest(ARRAY['{state_list}']) AS code)"
    
    query = f"""
        SELECT 
            -- Event info
            e.id as event_id,
            e.name as event_name,
            e.description as event_description,
            e.start_date,
            e.location_name,
            
            -- Jurisdiction
            j.name as jurisdiction_name,
            UPPER(SUBSTRING(j.division_id FROM 'state:([a-z]{{2}})')) as state,
            
            -- Participant (testifier)
            ep.id as participant_id,
            ep.name as testifier_name,
            ep.note as participant_note,
            
            -- Agenda item (what they testified about)
            ai.description as agenda_item,
            ai.notes as agenda_notes,
            
            -- Related bill (if any)
            rb.identifier as bill_number,
            rb.id as bill_id,
            
            -- Document (testimony text if available)
            ed.note as document_note,
            edl.url as document_url,
            edl.media_type
            
        FROM opencivicdata_event e
        JOIN opencivicdata_jurisdiction j ON e.jurisdiction_id = j.id
        LEFT JOIN opencivicdata_eventparticipant ep ON ep.event_id = e.id
        LEFT JOIN opencivicdata_eventagendaitem ai ON ai.event_id = e.id
        LEFT JOIN opencivicdata_relatedbill erb ON erb.agenda_item_id = ai.id
        LEFT JOIN opencivicdata_bill rb ON erb.bill_id = rb.id
        LEFT JOIN opencivicdata_eventdocument ed ON ed.event_id = e.id
        LEFT JOIN opencivicdata_eventdocumentlink edl ON edl.document_id = ed.id
        
        WHERE e.name ILIKE '%hearing%' OR e.name ILIKE '%testimony%' OR e.name ILIKE '%public comment%'
        {where_clause}
        
        ORDER BY e.start_date DESC, j.name, e.name
    """
    
    df = pd.read_sql(query, conn)
    
    logger.info(f"✅ Fetched {len(df):,} testimony records")
    
    if len(df) == 0:
        logger.warning("No testimony data found")
        conn.close()
        return
    
    # Stats
    logger.info("\n📊 Statistics:")
    logger.info(f"   Events: {df['event_id'].nunique():,}")
    logger.info(f"   Testifiers: {df['testifier_name'].nunique():,}")
    logger.info(f"   States: {df['state'].nunique()}")
    logger.info(f"   Related bills: {df['bill_id'].notna().sum():,}")
    logger.info(f"   With documents: {df['document_url'].notna().sum():,}")
    
    # Top states
    logger.info("\n🗺️  Top states by testimony records:")
    top_states = df['state'].value_counts().head(10)
    for state, count in top_states.items():
        logger.info(f"   {state}: {count:,} records")
    
    # Save to parquet
    logger.info(f"\nSaving to {OUTPUT_FILE}...")
    GOLD_DIR.mkdir(exist_ok=True)
    df.to_parquet(OUTPUT_FILE, index=False)
    
    size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
    logger.info(f"✅ Saved {len(df):,} records ({size_mb:.2f} MB)")
    
    # Sample data
    logger.info("\n📝 Sample testimony records:")
    sample = df[df['testifier_name'].notna()].head(3)
    for _, row in sample.iterrows():
        logger.info(f"\n   Event: {row['event_name']}")
        logger.info(f"   Date: {row['start_date']}")
        logger.info(f"   State: {row['state']}")
        logger.info(f"   Testifier: {row['testifier_name']}")
        if row['bill_number']:
            logger.info(f"   Bill: {row['bill_number']}")
        if row['agenda_item']:
            logger.info(f"   Topic: {row['agenda_item'][:100]}...")
    
    conn.close()
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ EXPORT COMPLETE!")
    logger.info("=" * 80)
    logger.info(f"\nNext steps:")
    logger.info(f"1. Review data: .venv/bin/python -c \"import pandas as pd; print(pd.read_parquet('{OUTPUT_FILE}').head())\"")
    logger.info(f"2. Integrate with AI analysis: Pass testimony to PolicyReasoningAnalyzer")


def main():
    parser = argparse.ArgumentParser(description="Export testimony from OpenStates")
    parser.add_argument("--states", help="Comma-separated state codes (e.g., GA,MA,WA)")
    args = parser.parse_args()
    
    states = args.states.split(',') if args.states else None
    
    export_testimony(states)


if __name__ == "__main__":
    main()
