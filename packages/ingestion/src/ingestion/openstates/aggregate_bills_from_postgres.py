#!/usr/bin/env python3
"""
Aggregate Bill Statistics from PostgreSQL

Queries OpenStates postgres database for all 50 states and pre-aggregates statistics
by state and topic. Improves upon file-based aggregation by:
- Getting ALL 50 states from postgres (not just 5 with parquet files)
- Better classification logic that considers sentiment/context
- Direct database queries for accurate status tracking

Output: data/gold/national/bill_map_aggregate.parquet
- Topic (fluoride, dental, medicaid, etc.)
- State
- Bill counts, type distribution, status breakdown
- Sample bills with titles and current status

Usage:
    python scripts/aggregate_bills_from_postgres.py
"""

import os
import psycopg2
import pandas as pd
import numpy as np
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

# Setup
project_root = Path(__file__).resolve().parents[5]
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

# Database connection
DB_URL = os.getenv('OPENSTATES_DATABASE_URL', 'postgresql://postgres:postgres@localhost:5433/openstates')


def classify_bill_type(title: str, topic: str, bill_number: str = None, state: str = None) -> str:
    """
    Classify bill type based on title and topic with improved sentiment analysis.
    
    CRITICAL: Check for negative sentiment (ban, prohibit, removal) FIRST
    before checking for positive sentiment (mandate, require).
    
    This prevents "prohibit fluoride" from being classified as "mandate"
    just because it contains "fluoride".
    """
    title_lower = title.lower()
    topic_lower = topic.lower() if topic else ""
    
    # MANUAL OVERRIDES: Known bills with generic titles that need manual classification
    # These are verified by external sources (CareQuest, FAN, bill text analysis)
    if bill_number and state:
        state_upper = state.upper()
        bill_upper = bill_number.upper()
        
        # Louisiana SB 4 (2026) - Confirmed by CareQuest as outright ban
        if state_upper == 'LA' and bill_upper == 'SB 4':
            return 'removal'
    
    # EXCEPTION: Fluoride varnish/dental coverage bills (not water fluoridation)
    # Check this BEFORE water fluoridation classification
    if any(word in title_lower for word in ['varnish', 'sealant', 'dental', 'medicaid', 'medical assistance']) and 'fluoride' in title_lower:
        if any(word in title_lower for word in ['coverage', 'expand', 'expansion', 'benefit']):
            return 'coverage_expansion'
        elif any(word in title_lower for word in ['screening', 'examination', 'check']):
            return 'screening'
        # If it mentions dental/varnish but unclear type, it's dental "other" not fluoridation
        return 'other'
    
    # Fluoridation-specific classifications (WATER fluoridation only)
    if 'fluoride' in topic_lower or 'fluoride' in title_lower:
        # FIRST: Check for REMOVAL/BAN/PROHIBITION (negative sentiment)
        if any(word in title_lower for word in [
            'prohibit', 'prohibition', 'prohibited', 'prohibiting',
            'ban', 'banning', 'banned',
            'discontinue', 'discontinuation',
            'cease', 'ceasing',
            'eliminate', 'elimination',
            'removal', 'remove', 'removing',
            'prevent', 'preventing',
            'repeal', 'repealing', 'repealed',
            'optional', 'opt-out', 'opt out',
            'fluoride-free', 'fluoride free'
        ]):
            # But check if it's "prohibit removal" (double negative = pro-fluoride)
            if any(phrase in title_lower for phrase in ['prohibit removal', 'prevent removal', 'ban removal']):
                return 'mandate'  # Prohibiting removal = mandate to keep
            return 'removal'
        
        # SECOND: Check for notification/monitoring (before "require" check)
        # Bills like "notification required" are about monitoring, not mandating fluoridation
        elif any(phrase in title_lower for phrase in [
            'notification', 'notify', 'notifying',
            'report to', 'reporting', 'report when',
            'monitor', 'monitoring'
        ]):
            return 'study'
        
        # THIRD: Check for MANDATE/REQUIRE (positive sentiment)  
        # Changed to be more specific - just "require" or "requiring" alone isn't enough
        elif any(phrase in title_lower for phrase in [
            'mandate', 'mandating', 'shall fluoridate', 'shall add fluoride',
            'must fluoridate', 'must add fluoride',
            'require fluoridation', 'require water system to fluoridate'
        ]):
            return 'mandate'
        
        # FOURTH: Check for funding
        elif any(word in title_lower for word in ['fund', 'funding', 'appropriation', 'grant', 'reimburse', 'subsidy']):
            return 'funding'
        
        # FIFTH: Check for study/research
        elif any(word in title_lower for word in ['study', 'research', 'review', 'assess', 'investigation', 'report on']):
            return 'study'
        
        # Default for fluoride
        return 'other'
    
    # Dental-specific
    if 'dental' in topic_lower:
        if any(word in title_lower for word in ['expand', 'expansion', 'increase coverage']):
            return 'coverage_expansion'
        elif any(word in title_lower for word in ['screening', 'examination', 'check']):
            return 'screening'
        elif any(word in title_lower for word in ['provider', 'dentist', 'hygienist']):
            return 'provider_access'
        elif any(word in title_lower for word in ['fund', 'grant']):
            return 'funding'
        return 'other'
    
    # Medicaid-specific
    if 'medicaid' in topic_lower:
        if any(word in title_lower for word in ['expand', 'expansion']):
            return 'expansion'
        elif any(word in title_lower for word in ['coverage', 'benefit']):
            return 'coverage'
        elif any(word in title_lower for word in ['reimburse', 'payment', 'rate']):
            return 'reimbursement'
        elif any(word in title_lower for word in ['eligib']):
            return 'eligibility'
        return 'other'
    
    # Education-specific
    if 'education' in topic_lower:
        if any(word in title_lower for word in ['require', 'requirement', 'mandate']):
            return 'requirement'
        elif any(word in title_lower for word in ['curriculum', 'course', 'instruction']):
            return 'curriculum'
        elif any(word in title_lower for word in ['fund', 'budget', 'appropriation']):
            return 'funding'
        elif any(word in title_lower for word in ['reform', 'restructur']):
            return 'reform'
        return 'other'
    
    # Health-specific
    if 'health' in topic_lower:
        if any(word in title_lower for word in ['protect', 'protection']):
            return 'protection'
        elif any(word in title_lower for word in ['restrict', 'restriction', 'limit']):
            return 'restriction'
        elif any(word in title_lower for word in ['fund', 'grant']):
            return 'funding'
        elif any(word in title_lower for word in ['reform', 'restructur']):
            return 'reform'
        return 'other'
    
    return 'other'


def determine_status(latest_action: str, classification: list) -> str:
    """
    Determine bill status from latest action description.
    
    Returns: 'enacted', 'failed', or 'pending'
    """
    if not latest_action:
        return 'pending'
    
    action_lower = latest_action.lower()
    
    # Enacted indicators
    if any(word in action_lower for word in [
        'signed', 'enacted', 'act no.', 'chaptered',
        'effective', 'approved by governor', 'became law'
    ]):
        return 'enacted'
    
    # Failed indicators
    if any(word in action_lower for word in [
        'failed', 'defeated', 'rejected', 'vetoed',
        'withdrawn', 'postponed indefinitely', 'died'
    ]):
        return 'failed'
    
    # Check bill classification for failure signals
    if classification and isinstance(classification, list):
        if any('dead' in str(c).lower() or 'failed' in str(c).lower() for c in classification):
            return 'failed'
    
    # Default to pending
    return 'pending'


def aggregate_state_bills(conn, state: str, topic: str) -> dict:
    """
    Aggregate bills for a specific state and topic from postgres.
    
    Returns dict with:
    - total_bills
    - type_counts (dict)
    - status_counts (dict)  
    - sample_bills (list of dicts)
    - type_status_counts (nested dict)
    """
    # Build topic search pattern
    if topic == 'fluoride':
        topic_pattern = "(%fluorid% OR %fluorin%)"
    elif topic == 'oral health':
        topic_pattern = "(%oral% AND %health%)"
    else:
        topic_pattern = f"%{topic}%"
    
    # Extract state code from ALL_STATES format (uppercase)
    state_code = state.upper()
    jurisdiction_pattern = f'ocd-jurisdiction/country:us/state:{state_code.lower()}/%'
    
    query = f"""
        SELECT 
            b.identifier as bill_number,
            b.title,
            b.classification,
            b.latest_action_description,
            b.latest_action_date,
            s.identifier as session,
            SUBSTRING(j.id FROM 'ocd-jurisdiction/country:us/state:([a-z]{{2}})') as state
        FROM opencivicdata_bill b
        JOIN opencivicdata_legislativesession s ON b.legislative_session_id = s.id
        JOIN opencivicdata_jurisdiction j ON s.jurisdiction_id = j.id
        WHERE j.id LIKE %s
            AND (LOWER(b.title) LIKE %s OR LOWER(b.title) LIKE %s)
        ORDER BY b.latest_action_date DESC NULLS LAST
    """
    
    # Create search patterns
    if topic == 'fluoride':
        pattern1 = '%fluorid%'
        pattern2 = '%fluorin%'
    elif topic == 'oral health':
        # For "oral health", we need both words
        pattern1 = '%oral%health%'
        pattern2 = '%health%oral%'
    else:
        pattern1 = f'%{topic}%'
        pattern2 = f'%{topic}%'  # Same pattern for single-word topics
    
    try:
        df = pd.read_sql(query, conn, params=(jurisdiction_pattern, pattern1, pattern2))
        
        if len(df) == 0:
            return None
        
        # For fluoride topic, exclude varnish/dental coverage bills (they're not about water fluoridation)
        if topic == 'fluoride':
            # Exclude bills that are clearly about dental coverage, not water fluoridation
            varnish_pattern = r'varnish|sealant|dental.*coverage|medicaid.*dental|medical assistance.*dental'
            df = df[~df['title'].str.lower().str.contains(varnish_pattern, na=False, regex=True)]
            
            # Exclude firefighting foam bills (industrial chemicals, not water)
            foam_pattern = r'fire.*foam|firefighting.*foam|foam.*fluorinated|fire.*marshal.*fluorinated'
            df = df[~df['title'].str.lower().str.contains(foam_pattern, na=False, regex=True)]
            
            if len(df) == 0:
                return None
        
        # Classify bills
        df['type'] = df.apply(lambda row: classify_bill_type(row['title'], topic, row['bill_number'], row['state']), axis=1)
        df['status'] = df.apply(lambda row: determine_status(row['latest_action_description'], row['classification']), axis=1)
        
        # Count by type
        type_counts = df['type'].value_counts().to_dict()
        
        # Count by status
        status_counts = df['status'].value_counts().to_dict()
        
        # Nested counts: type x status
        type_status_counts = {}
        for bill_type in df['type'].unique():
            type_df = df[df['type'] == bill_type]
            type_status_counts[bill_type] = type_df['status'].value_counts().to_dict()
        
        # Get sample bills (top 3 most recent)
        sample_bills = []
        for _, row in df.head(3).iterrows():
            # Format date as "Jan 2026" or "Pending"
            date_str = ''
            if pd.notna(row['latest_action_date']):
                date_obj = pd.to_datetime(row['latest_action_date'])
                date_str = date_obj.strftime('%b %Y')
            
            sample_bills.append({
                'bill_number': row['bill_number'],
                'title': row['title'],
                'status': row['status'],
                'type': row['type'],
                'action': row['latest_action_description'] or '',
                'date': date_str,
                'state': row['state']
            })
        
        # Determine primary type (most common)
        primary_type = df['type'].mode()[0] if len(df) > 0 else 'other'
        
        # Determine primary status (most common)
        primary_status = df['status'].mode()[0] if len(df) > 0 else 'pending'
        
        # Map category for visualization
        map_category = f"{primary_type}_{primary_status}"
        
        return {
            'state': state_code,
            'topic': topic,
            'total_bills': len(df),
            'type_counts': type_counts,
            'status_counts': status_counts,
            'type_status_counts': type_status_counts,
            'primary_type': primary_type,
            'primary_status': primary_status,
            'map_category': map_category,
            'sample_bills': sample_bills
        }
        
    except Exception as e:
        logger.error(f"Error aggregating {state} {topic}: {e}")
        return None


def main():
    """Main aggregation process."""
    logger.info("Starting bill statistics aggregation from PostgreSQL...")
    logger.info(f"Database: {DB_URL.split('@')[1] if '@' in DB_URL else DB_URL}")  # Don't log password
    
    # Connect to database
    try:
        conn = psycopg2.connect(DB_URL)
        logger.info("✅ Connected to OpenStates database")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        logger.error("Make sure postgres is running: docker start openstates-db")
        return
    
    # Aggregate data
    all_aggregates = []
    
    for topic in TOPICS:
        logger.info(f"Processing topic: {topic}")
        
        for state in ALL_STATES:
            result = aggregate_state_bills(conn, state, topic)
            
            if result:
                all_aggregates.append(result)
                logger.info(f"  ✅ {state}: {result['total_bills']} bills")
    
    conn.close()
    
    if not all_aggregates:
        logger.error("No data aggregated!")
        return
    
    # Convert to DataFrame
    logger.info(f"Creating DataFrame from {len(all_aggregates)} aggregates...")
    
    # Flatten the nested dicts for parquet storage
    rows = []
    for agg in all_aggregates:
        row = {
            'state': agg['state'],
            'topic': agg['topic'],
            'total_bills': agg['total_bills'],
            'sample_bills': agg['sample_bills'],
            'primary_type': agg['primary_type'],
            'primary_status': agg['primary_status'],
            'map_category': agg['map_category']
        }
        
        # Add type counts as separate columns
        for bill_type, count in agg['type_counts'].items():
            row[f'type_{bill_type}'] = count
        
        # Add status counts
        for status, count in agg['status_counts'].items():
            row[f'status_{status}'] = count
        
        # Store nested type_status_counts as JSON-like dict
        row['type_status_counts'] = agg['type_status_counts']
        
        rows.append(row)
    
    df = pd.DataFrame(rows)
    
    # Fill NaN values with 0 for numeric columns
    numeric_cols = [c for c in df.columns if c.startswith('type_') or c.startswith('status_')]
    for col in numeric_cols:
        if col != 'type_status_counts':
            df[col] = df[col].fillna(0).astype(int)
    
    # Save to parquet
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_FILE, index=False, engine='pyarrow', compression='snappy')
    
    file_size = OUTPUT_FILE.stat().st_size / 1024  # KB
    logger.info(f"✅ Saved {len(df)} aggregates to {OUTPUT_FILE}")
    logger.info(f"   File size: {file_size:.1f} KB")
    
    # Summary
    print(f"\n📊 Summary:")
    print(f"   Topics: {', '.join(TOPICS)}")
    print(f"   States with data: {df['state'].nunique()}")
    print(f"   Total aggregates: {len(df)}")
    print(f"   Total bills tracked: {df['total_bills'].sum():,}")
    print(f"\nTop 10 states by bill count:")
    print(df.groupby('state')['total_bills'].sum().sort_values(ascending=False).head(10))


if __name__ == "__main__":
    main()
