#!/usr/bin/env python3
"""
Aggregate bill statistics by state for fast map visualization.

Creates a national aggregated dataset with pre-computed counts by:
- State
- Topic (fluoridation, dental, medicaid, etc.)
- Bill type (mandate, removal, funding, protection, etc.)
- Bill status (enacted, failed, pending)

Output: data/gold/national/bill_map_aggregate.parquet

This eliminates the need to load 50 state files on every map request.
"""
import sys
from pathlib import Path
import pandas as pd
import duckdb
from loguru import logger
from datetime import datetime

# Add project root to path so the FastAPI `api` package is importable.
# This module lives at packages/ingestion/src/ingestion/publication/gold/, so the
# repository root is parents[6].
project_root = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(project_root))

from api.routes.bills import classify_bill_type, determine_bill_status, get_legend_for_topic

GOLD_DIR = project_root / "data" / "gold"
OUTPUT_FILE = GOLD_DIR / "national" / "bill_map_aggregate.parquet"

# Topics to pre-aggregate
TOPICS = ['fluoride', 'dental', 'oral health', 'medicaid', 'education', 'health']

# All US states
ALL_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
]


def aggregate_state_bills(state_code: str, topic: str) -> dict:
    """Aggregate bills for one state and topic."""
    try:
        bills_file = GOLD_DIR / "states" / state_code / "bills_bills.parquet"
        
        if not bills_file.exists():
            return None
        
        conn = duckdb.connect()
        
        # Load bills matching topic
        sql = """
            SELECT 
                title,
                classification,
                latest_action_description,
                session
            FROM read_parquet(?)
            WHERE LOWER(title) LIKE LOWER(?)
        """
        
        rows = conn.execute(sql, [str(bills_file), f'%{topic}%']).fetchall()
        conn.close()
        
        if not rows:
            return None
        
        # Get topic-specific categories
        legend_categories = get_legend_for_topic(topic)
        
        # Initialize counters
        type_counts = {cat: 0 for cat in legend_categories.keys()}
        status_counts = {'enacted': 0, 'failed': 0, 'pending': 0}
        type_status_counts = {}
        sessions = set()
        
        # Sample bills for display (top 3 most recent)
        sample_bills = []
        
        for row in rows:
            title = row[0]
            classification = row[1] if row[1] else []
            latest_action = row[2] if row[2] else ''
            session = row[3] if row[3] else ''
            
            bill_type = classify_bill_type(title, classification, topic)
            bill_status = determine_bill_status(latest_action, '')
            
            # Ensure bill_type exists
            if bill_type not in type_counts:
                bill_type = 'other'
            
            type_counts[bill_type] += 1
            status_counts[bill_status] += 1
            sessions.add(session)
            
            # Track type+status combinations
            key = f"{bill_type}_{bill_status}"
            type_status_counts[key] = type_status_counts.get(key, 0) + 1
            
            # Collect sample bills
            if len(sample_bills) < 3:
                sample_bills.append({
                    'title': title[:100],  # Truncate long titles
                    'type': bill_type,
                    'status': bill_status,
                    'action': latest_action[:80]
                })
        
        # Determine primary type and status
        primary_type = max(type_counts, key=type_counts.get)
        primary_status = max(status_counts, key=status_counts.get)
        
        return {
            'state': state_code,
            'topic': topic,
            'total_bills': len(rows),
            'type_counts': type_counts,
            'status_counts': status_counts,
            'type_status_counts': type_status_counts,
            'primary_type': primary_type,
            'primary_status': primary_status,
            'map_category': f"{primary_type}_{primary_status}",
            'sessions': list(sessions),
            'sample_bills': sample_bills,
            'last_updated': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error aggregating {state_code} for {topic}: {e}")
        return None


def main():
    """Aggregate bill statistics for all states and topics."""
    logger.info("Starting bill statistics aggregation...")
    
    results = []
    
    for topic in TOPICS:
        logger.info(f"Processing topic: {topic}")
        
        for state_code in ALL_STATES:
            logger.debug(f"  Aggregating {state_code}...")
            
            result = aggregate_state_bills(state_code, topic)
            if result:
                results.append(result)
                logger.info(f"  ✅ {state_code}: {result['total_bills']} bills")
    
    # Convert to DataFrame
    logger.info(f"Creating DataFrame from {len(results)} aggregates...")
    df = pd.DataFrame(results)
    
    # Expand nested dicts into columns
    type_counts_df = pd.json_normalize(df['type_counts'])
    status_counts_df = pd.json_normalize(df['status_counts'])
    
    # Merge back
    df = pd.concat([
        df.drop(['type_counts', 'status_counts'], axis=1),
        type_counts_df.add_prefix('type_'),
        status_counts_df.add_prefix('status_')
    ], axis=1)
    
    # Save to parquet
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_FILE, index=False)
    
    logger.info(f"✅ Saved {len(df)} aggregates to {OUTPUT_FILE}")
    logger.info(f"   File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")
    
    # Print summary
    print(f"\n📊 Summary:")
    print(f"   Topics: {', '.join(TOPICS)}")
    print(f"   States with data: {df['state'].nunique()}")
    print(f"   Total aggregates: {len(df)}")
    print(f"   Total bills tracked: {df['total_bills'].sum()}")
    print(f"\nTop 5 states by bill count:")
    print(df.groupby('state')['total_bills'].sum().sort_values(ascending=False).head())


if __name__ == "__main__":
    main()
