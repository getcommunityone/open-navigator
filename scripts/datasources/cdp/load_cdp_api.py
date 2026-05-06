#!/usr/bin/env python3
"""
Load Council Data Project (CDP) Events to Bronze (Direct API)

Fetches meeting events from CDP GraphQL API and loads them into bronze tables.
This version uses direct API calls instead of cdp-data package to avoid dependencies.

CDP Documentation: https://councildataproject.org/

Usage:
    python load_cdp_api.py --instance seattle --limit 100
    python load_cdp_api.py --instance portland --start-date 2024-01-01
"""

import os
import sys
import argparse
import requests
import json
from datetime import datetime
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import pandas as pd
    from sqlalchemy import create_engine
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    print("⚠️  pandas/sqlalchemy not installed - dry-run mode only")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
DATABASE_URL = f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator'

# CDP GraphQL API endpoints
CDP_API_ENDPOINTS = {
    'seattle': 'https://councildataproject.org/seattle/graphql',
    'portland': 'https://councildataproject.org/portland/graphql',
    'boston': 'https://councildataproject.org/boston/graphql',
    'denver': 'https://councildataproject.org/denver/graphql',
    'king-county': 'https://councildataproject.org/king-county/graphql',
    'alameda': 'https://councildataproject.org/alameda/graphql',
    'oakland': 'https://councildataproject.org/oakland/graphql',
    'charlotte': 'https://councildataproject.org/charlotte/graphql',
    'san-jose': 'https://councildataproject.org/san-jose/graphql',
}

# Jurisdiction mapping
JURISDICTION_MAPPING = {
    'seattle': {'city': 'Seattle', 'state_code': 'WA', 'state': 'Washington', 'type': 'city'},
    'portland': {'city': 'Portland', 'state_code': 'OR', 'state': 'Oregon', 'type': 'city'},
    'boston': {'city': 'Boston', 'state_code': 'MA', 'state': 'Massachusetts', 'type': 'city'},
    'denver': {'city': 'Denver', 'state_code': 'CO', 'state': 'Colorado', 'type': 'city'},
    'king-county': {'city': None, 'county': 'King County', 'state_code': 'WA', 'state': 'Washington', 'type': 'county'},
    'alameda': {'city': None, 'county': 'Alameda County', 'state_code': 'CA', 'state': 'California', 'type': 'county'},
    'oakland': {'city': 'Oakland', 'state_code': 'CA', 'state': 'California', 'type': 'city'},
    'charlotte': {'city': 'Charlotte', 'state_code': 'NC', 'state': 'North Carolina', 'type': 'city'},
    'san-jose': {'city': 'San José', 'state_code': 'CA', 'state': 'California', 'type': 'city'},
}


def fetch_cdp_events(instance_slug: str, limit: int = 100, start_date: str = None):
    """
    Fetch events from CDP GraphQL API.
    
    Args:
        instance_slug: CDP instance name (e.g., 'seattle')
        limit: Maximum number of events to fetch
        start_date: Optional start date filter (YYYY-MM-DD)
    
    Returns:
        List of event dictionaries
    """
    api_url = CDP_API_ENDPOINTS.get(instance_slug)
    if not api_url:
        raise ValueError(f"Unknown CDP instance: {instance_slug}")
    
    # GraphQL query for events
    query = """
    query GetEvents($limit: Int!) {
      events(first: $limit, orderBy: {field: EVENT_DATETIME, direction: DESC}) {
        edges {
          node {
            id
            eventDatetime
            agendaUri
            minutesUri
            body {
              name
              description
            }
            sessions {
              videoUri
              sessionDatetime
              sessionContentHash
            }
          }
        }
      }
    }
    """
    
    variables = {"limit": limit}
    
    try:
        logger.info(f"📥 Fetching events from {instance_slug} CDP instance...")
        
        response = requests.post(
            api_url,
            json={'query': query, 'variables': variables},
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"❌ API request failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return []
        
        data = response.json()
        
        if 'errors' in data:
            logger.error(f"❌ GraphQL errors: {data['errors']}")
            return []
        
        events = [edge['node'] for edge in data.get('data', {}).get('events', {}).get('edges', [])]
        logger.info(f"✅ Fetched {len(events)} events from {instance_slug}")
        
        return events
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error fetching from CDP API: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"❌ Error parsing CDP response: {e}")
        return []


def transform_to_bronze(events: list, instance_slug: str):
    """Transform CDP events to bronze_events_search schema."""
    if not HAS_DEPS:
        logger.warning("⚠️  Cannot transform without pandas - showing raw data instead")
        return events
    
    jurisdiction = JURISDICTION_MAPPING[instance_slug]
    
    rows = []
    for event in events:
        # Extract body information
        body = event.get('body', {}) or {}
        body_name = body.get('name', 'City Council')
        body_desc = body.get('description')
        
        # Extract session information (use first session if available)
        sessions = event.get('sessions', []) or []
        video_url = sessions[0].get('videoUri') if sessions else None
        session_hash = sessions[0].get('sessionContentHash') if sessions else None
        
        row = {
            'event_datetime': event.get('eventDatetime'),
            'title': f"{body_name} Meeting",
            'description': body_desc,
            'body_name': body_name,
            'body_description': body_desc,
            'agenda_url': event.get('agendaUri'),
            'minutes_url': event.get('minutesUri'),
            'external_source_id': event.get('id'),
            'video_url': video_url,
            'session_content_hash': session_hash,
            'jurisdiction_name': jurisdiction.get('city') or jurisdiction.get('county'),
            'jurisdiction_type': jurisdiction['type'],
            'city': jurisdiction.get('city'),
            'county': jurisdiction.get('county'),
            'state_code': jurisdiction['state_code'],
            'state': jurisdiction['state'],
            'source': 'cdp',
            'source_url': f'https://councildataproject.org/{instance_slug}',
            'ingestion_timestamp': datetime.now().isoformat(),
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    
    # Convert datetime strings to pandas datetime
    if 'event_datetime' in df.columns:
        df['event_datetime'] = pd.to_datetime(df['event_datetime'])
    
    return df


def show_sample_data(data, title="Sample Data"):
    """Display sample data."""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}\n")
    
    if isinstance(data, list):
        # Show first 3 events
        for i, event in enumerate(data[:3], 1):
            print(f"Event {i}:")
            print(f"  ID: {event.get('id')}")
            print(f"  Date: {event.get('eventDatetime')}")
            body = event.get('body', {}) or {}
            print(f"  Body: {body.get('name', 'N/A')}")
            print(f"  Agenda: {event.get('agendaUri', 'N/A')}")
            print(f"  Minutes: {event.get('minutesUri', 'N/A')}")
            sessions = event.get('sessions', []) or []
            if sessions:
                print(f"  Video: {sessions[0].get('videoUri', 'N/A')}")
            print()
    elif HAS_DEPS:
        # Show DataFrame info
        print(f"Shape: {data.shape}")
        print(f"\nColumns: {', '.join(data.columns.tolist())}")
        print(f"\nFirst 3 rows:")
        print(data.head(3).to_string())
        print(f"\nData types:")
        print(data.dtypes)


def load_to_database(df, table_name='bronze_events_search', schema='bronze'):
    """Load DataFrame to PostgreSQL."""
    if not HAS_DEPS:
        logger.error("❌ Cannot load to database without pandas/sqlalchemy")
        return
    
    engine = create_engine(DATABASE_URL)
    
    try:
        df.to_sql(
            table_name,
            engine,
            schema=schema,
            if_exists='append',
            index=False,
            method='multi',
            chunksize=1000
        )
        logger.info(f"✅ Loaded {len(df)} rows to {schema}.{table_name}")
    except Exception as e:
        logger.error(f"❌ Error loading to database: {e}")
        raise
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description='Load Council Data Project events via GraphQL API'
    )
    parser.add_argument(
        '--instance',
        required=True,
        choices=list(CDP_API_ENDPOINTS.keys()),
        help='CDP instance to fetch from'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Maximum number of events to fetch (default: 100)'
    )
    parser.add_argument(
        '--start-date',
        help='Start date filter (YYYY-MM-DD) - not yet implemented'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be loaded without loading'
    )
    
    args = parser.parse_args()
    
    # Fetch events from CDP API
    events = fetch_cdp_events(args.instance, args.limit, args.start_date)
    
    if not events:
        logger.warning("⚠️  No events fetched")
        return
    
    # Transform to bronze schema
    bronze_df = transform_to_bronze(events, args.instance)
    
    # Show or load data
    if args.dry_run or not HAS_DEPS:
        show_sample_data(bronze_df, f"CDP {args.instance.title()} Events")
    else:
        logger.info(f"📊 Transformed {len(bronze_df)} events")
        load_to_database(bronze_df)
        logger.info("✅ CDP data loaded successfully!")


if __name__ == '__main__':
    main()
