#!/usr/bin/env python3
"""
Export OpenStates data from PostgreSQL to Gold Parquet datasets

Exports data for dev states (WA, MA, AL, GA, WI) with new naming conventions:
- contact_official
- bills_bills
- bills_bill_actions
- bills_bill_sponsorships
- events_events
- events_participants

Files are saved to: data/gold/states/{STATE}/

Usage:
    python scripts/export_openstates_to_gold.py
"""

import psycopg2
import pandas as pd
import json
import re
from pathlib import Path
from loguru import logger
from typing import List, Dict, Any

# Dev states for initial export
DEV_STATES = ['WA', 'MA', 'AL', 'GA', 'WI', 'IN']

# Database connection
DB_URL = "postgresql://postgres:password@localhost:5433/openstates"

# Output directory
GOLD_DIR = Path("data/gold")
STATES_DIR = GOLD_DIR / "states"
STATES_DIR.mkdir(parents=True, exist_ok=True)


def get_state_jurisdiction(conn, state: str) -> str:
    """Get jurisdiction ID for a specific state."""
    cursor = conn.cursor()
    
    jur_id = f"ocd-jurisdiction/country:us/state:{state.lower()}/government"
    
    query = """
        SELECT id, name, classification
        FROM opencivicdata_jurisdiction
        WHERE id = %s
    """
    
    cursor.execute(query, (jur_id,))
    result = cursor.fetchone()
    
    if result:
        logger.info(f"Found jurisdiction: {result[1]} ({result[0]})")
        return result[0]
    else:
        logger.warning(f"Jurisdiction not found for state: {state}")
        return None


def parse_jurisdiction_name(ocd_id: str) -> str:
    """Extract city/jurisdiction name from OCD ID.
    
    Examples:
        ocd-jurisdiction/country:us/state:al/place:tuscaloosa/government -> Tuscaloosa
        ocd-jurisdiction/country:us/state:al/government -> Alabama
    """
    if not ocd_id or pd.isna(ocd_id):
        return None
        
    # Extract place name from OCD ID
    match = re.search(r'/place:([^/]+)/', ocd_id)
    if match:
        place = match.group(1)
        # Convert snake_case to Title Case
        return place.replace('_', ' ').title()
    
    # Extract state if no place
    match = re.search(r'/state:([^/]+)/', ocd_id)
    if match:
        return match.group(1).upper()
    
    return None


def extract_contact_info(source_data_json: str) -> Dict[str, Any]:
    """Extract contact information from the source_data JSON field.
    
    For state legislators: checks contact_details array
    For mayors/municipal: checks offices array
    
    Returns:
        Dict with email, phone, address, city_jurisdiction
    """
    if not source_data_json or pd.isna(source_data_json):
        return {'email': None, 'phone': None, 'address': None, 'city_jurisdiction': None}
    
    try:
        data = json.loads(source_data_json) if isinstance(source_data_json, str) else source_data_json
    except (json.JSONDecodeError, TypeError):
        return {'email': None, 'phone': None, 'address': None, 'city_jurisdiction': None}
    
    email = None
    phone = None
    address = None
    city_jurisdiction = None
    
    # Try to get email from top level
    if 'email' in data:
        email = data['email']
    
    # Try contact_details (state legislators)
    contact_details = data.get('contact_details', [])
    for contact in contact_details:
        if contact.get('note') == 'Capitol Office':
            email = email or contact.get('email')
            phone = phone or contact.get('voice')
            address = address or contact.get('address')
    
    # Try offices array (mayors/municipal officials)
    offices = data.get('offices', [])
    for office in offices:
        if office.get('classification') == 'primary':
            email = email or office.get('email')
            phone = phone or office.get('voice')
            address = address or office.get('address')
    
    # Get jurisdiction/city from roles
    roles = data.get('roles', [])
    if roles:
        role = roles[0]  # Get current/first role
        jurisdiction_ocd = role.get('jurisdiction')
        if jurisdiction_ocd:
            city_jurisdiction = parse_jurisdiction_name(jurisdiction_ocd)
    
    return {
        'email': email,
        'phone': phone,
        'address': address,
        'city_jurisdiction': city_jurisdiction
    }


def export_contact_official(conn, state: str, state_dir: Path):
    """Export officials/legislators (people) from openstates_people table."""
    logger.info(f"  Exporting contact_official for {state}...")
    
    query = """
        SELECT 
            id as official_id,
            name as full_name,
            state,
            party,
            role_type,
            district,
            jurisdiction,
            email,
            phone,
            address,
            image as photo_url,
            data::text as source_data
        FROM openstates_people
        WHERE state = %s
        ORDER BY name
    """
    
    df = pd.read_sql(query, conn, params=(state,))
    
    if len(df) == 0:
        logger.warning(f"  No officials found for {state}")
        return None
    
    # Extract contact info from JSON source_data
    logger.info(f"  Parsing contact information from source data...")
    contact_info = df['source_data'].apply(extract_contact_info)
    
    # Update columns with extracted data
    df['email'] = df['email'].fillna(contact_info.apply(lambda x: x['email']))
    df['phone'] = df['phone'].fillna(contact_info.apply(lambda x: x['phone']))
    df['address'] = df['address'].fillna(contact_info.apply(lambda x: x['address']))
    df['city_jurisdiction'] = contact_info.apply(lambda x: x['city_jurisdiction'])
    
    # Parse jurisdiction name from OCD ID
    df['jurisdiction_name'] = df['jurisdiction'].apply(parse_jurisdiction_name)
    
    # Clean up address formatting (remove semicolons)
    df['address'] = df['address'].apply(lambda x: x.replace(';', ', ') if x and isinstance(x, str) else x)
    
    output_path = state_dir / "contact_official.parquet"
    df.to_parquet(output_path, index=False, engine='pyarrow', compression='snappy')
    
    logger.info(f"  ✅ Exported {len(df):,} officials")
    logger.info(f"  📧 With email: {df['email'].notna().sum()}")
    logger.info(f"  📞 With phone: {df['phone'].notna().sum()}")
    logger.info(f"  📍 With address: {df['address'].notna().sum()}")
    
    return df


def export_bills_bills(conn, state: str, jurisdiction_id: str, state_dir: Path):
    """Export bills from opencivicdata_bill table."""
    logger.info(f"  Exporting bills_bills for {state}...")
    
    if not jurisdiction_id:
        logger.warning(f"  No jurisdiction ID for {state}, skipping bills export")
        return None
    
    query = """
        SELECT 
            b.id as bill_id,
            b.identifier as bill_number,
            b.title,
            b.classification,
            b.from_organization_id,
            b.legislative_session_id,
            s.identifier as session,
            s.name as session_name,
            j.name as jurisdiction_name,
            j.id as jurisdiction_ocd_id,
            b.first_action_date,
            b.latest_action_date,
            b.latest_action_description,
            b.created_at,
            b.updated_at,
            (SELECT abstract FROM opencivicdata_billabstract WHERE bill_id = b.id LIMIT 1) as abstract,
            (SELECT url FROM opencivicdata_billsource WHERE bill_id = b.id LIMIT 1) as source_url
        FROM opencivicdata_bill b
        JOIN opencivicdata_legislativesession s ON b.legislative_session_id = s.id
        JOIN opencivicdata_jurisdiction j ON s.jurisdiction_id = j.id
        WHERE j.id = %s
        ORDER BY s.identifier, b.identifier
    """
    
    df = pd.read_sql(query, conn, params=(jurisdiction_id,))
    
    if len(df) == 0:
        logger.warning(f"  No bills found for {state}")
        return None
    
    output_path = state_dir / "bills_bills.parquet"
    df.to_parquet(output_path, index=False, engine='pyarrow', compression='snappy')
    
    logger.info(f"  ✅ Exported {len(df):,} bills")
    logger.info(f"  📝 With abstracts: {df['abstract'].notna().sum():,}")
    logger.info(f"  🔗 With source URLs: {df['source_url'].notna().sum():,}")
    
    return df


def export_bills_versions(conn, state: str, jurisdiction_id: str, state_dir: Path):
    """Export bill versions and their document links."""
    logger.info(f"  Exporting bills_versions for {state}...")
    
    if not jurisdiction_id:
        logger.warning(f"  No jurisdiction ID for {state}, skipping bill versions export")
        return None
    
    query = """
        SELECT 
            v.id as version_id,
            v.bill_id,
            b.identifier as bill_number,
            v.note as version_note,
            v.date as version_date,
            v.classification,
            vl.url as document_url,
            vl.media_type,
            j.name as jurisdiction_name,
            s.identifier as session
        FROM opencivicdata_billversion v
        JOIN opencivicdata_bill b ON v.bill_id = b.id
        JOIN opencivicdata_legislativesession s ON b.legislative_session_id = s.id
        JOIN opencivicdata_jurisdiction j ON s.jurisdiction_id = j.id
        LEFT JOIN opencivicdata_billversionlink vl ON vl.version_id = v.id
        WHERE j.id = %s
        ORDER BY b.identifier, v.date DESC
    """
    
    df = pd.read_sql(query, conn, params=(jurisdiction_id,))
    
    if len(df) == 0:
        logger.info(f"  ℹ️  No bill versions found for {state}")
        return None
    
    output_path = state_dir / "bills_versions.parquet"
    df.to_parquet(output_path, index=False, engine='pyarrow', compression='snappy')
    
    logger.info(f"  ✅ Exported {len(df):,} bill versions")
    logger.info(f"  📄 Unique bills with versions: {df['bill_id'].nunique():,}")
    logger.info(f"  🔗 With document URLs: {df['document_url'].notna().sum():,}")
    
    return df


def export_bills_bill_actions(conn, state: str, jurisdiction_id: str, state_dir: Path):
    """Export bill actions from opencivicdata_billaction table."""
    logger.info(f"  Exporting bills_bill_actions for {state}...")
    
    if not jurisdiction_id:
        logger.warning(f"  No jurisdiction ID for {state}, skipping bill actions export")
        return None
    
    query = """
        SELECT 
            ba.id as action_id,
            ba.bill_id,
            b.identifier as bill_number,
            ba.description,
            ba.date as action_date,
            ba.classification,
            ba.organization_id,
            ba.order as sequence_order,
            j.name as jurisdiction_name
        FROM opencivicdata_billaction ba
        JOIN opencivicdata_bill b ON ba.bill_id = b.id
        JOIN opencivicdata_legislativesession s ON b.legislative_session_id = s.id
        JOIN opencivicdata_jurisdiction j ON s.jurisdiction_id = j.id
        WHERE j.id = %s
        ORDER BY ba.date DESC, ba.order
    """
    
    df = pd.read_sql(query, conn, params=(jurisdiction_id,))
    
    if len(df) == 0:
        logger.warning(f"  No bill actions found for {state}")
        return None
    
    output_path = state_dir / "bills_bill_actions.parquet"
    df.to_parquet(output_path, index=False, engine='pyarrow', compression='snappy')
    
    logger.info(f"  ✅ Exported {len(df):,} bill actions")
    
    return df


def export_bills_bill_sponsorships(conn, state: str, jurisdiction_id: str, state_dir: Path):
    """Export bill sponsorships from opencivicdata_billsponsorship table."""
    logger.info(f"  Exporting bills_bill_sponsorships for {state}...")
    
    if not jurisdiction_id:
        logger.warning(f"  No jurisdiction ID for {state}, skipping sponsorships export")
        return None
    
    query = """
        SELECT 
            bs.id as sponsorship_id,
            bs.bill_id,
            b.identifier as bill_number,
            bs.name as sponsor_name,
            bs.entity_type,
            bs.person_id,
            bs.organization_id,
            bs.primary as is_primary,
            bs.classification,
            j.name as jurisdiction_name
        FROM opencivicdata_billsponsorship bs
        JOIN opencivicdata_bill b ON bs.bill_id = b.id
        JOIN opencivicdata_legislativesession s ON b.legislative_session_id = s.id
        JOIN opencivicdata_jurisdiction j ON s.jurisdiction_id = j.id
        WHERE j.id = %s
        ORDER BY b.identifier, bs.primary DESC
    """
    
    df = pd.read_sql(query, conn, params=(jurisdiction_id,))
    
    if len(df) == 0:
        logger.warning(f"  No sponsorships found for {state}")
        return None
    
    output_path = state_dir / "bills_bill_sponsorships.parquet"
    df.to_parquet(output_path, index=False, engine='pyarrow', compression='snappy')
    
    logger.info(f"  ✅ Exported {len(df):,} sponsorships")
    
    return df


def export_events_events(conn, state: str, jurisdiction_id: str, state_dir: Path):
    """Export events/meetings from opencivicdata_event table."""
    logger.info(f"  Exporting events_events for {state}...")
    
    if not jurisdiction_id:
        logger.warning(f"  No jurisdiction ID for {state}, skipping events export")
        return None
    
    query = """
        SELECT 
            e.id as event_id,
            e.name as event_name,
            e.description,
            e.classification,
            e.start_date,
            e.end_date,
            e.all_day,
            e.status,
            e.location_id,
            j.name as jurisdiction_name,
            j.id as jurisdiction_ocd_id,
            e.created_at,
            e.updated_at
        FROM opencivicdata_event e
        JOIN opencivicdata_jurisdiction j ON e.jurisdiction_id = j.id
        WHERE j.id = %s
        ORDER BY e.start_date DESC
    """
    
    df = pd.read_sql(query, conn, params=(jurisdiction_id,))
    
    if len(df) == 0:
        logger.warning(f"  No events found for {state}")
        return None
    
    output_path = state_dir / "events_events.parquet"
    df.to_parquet(output_path, index=False, engine='pyarrow', compression='snappy')
    
    logger.info(f"  ✅ Exported {len(df):,} events")
    
    return df


def export_events_participants(conn, state: str, jurisdiction_id: str, state_dir: Path):
    """Export event participants from opencivicdata_eventparticipant table."""
    logger.info(f"  Exporting events_participants for {state}...")
    
    if not jurisdiction_id:
        logger.warning(f"  No jurisdiction ID for {state}, skipping event participants export")
        return None
    
    query = """
        SELECT 
            ep.id as participant_id,
            ep.event_id,
            e.name as event_name,
            ep.name as participant_name,
            ep.entity_type,
            ep.person_id,
            ep.organization_id,
            ep.note,
            j.name as jurisdiction_name
        FROM opencivicdata_eventparticipant ep
        JOIN opencivicdata_event e ON ep.event_id = e.id
        JOIN opencivicdata_jurisdiction j ON e.jurisdiction_id = j.id
        WHERE j.id = %s
        ORDER BY e.start_date DESC
    """
    
    df = pd.read_sql(query, conn, params=(jurisdiction_id,))
    
    if len(df) == 0:
        logger.warning(f"  No event participants found for {state}")
        return None
    
    output_path = state_dir / "events_participants.parquet"
    df.to_parquet(output_path, index=False, engine='pyarrow', compression='snappy')
    
    logger.info(f"  ✅ Exported {len(df):,} event participants")
    
    return df


def main():
    """Main export function - exports each state to its own directory."""
    logger.info("=" * 80)
    logger.info("EXPORTING OPENSTATES DATA TO GOLD DATASETS")
    logger.info("=" * 80)
    logger.info(f"Dev States: {', '.join(DEV_STATES)}")
    logger.info(f"Output Directory: {STATES_DIR}")
    logger.info("")
    
    # Connect to database
    logger.info("Connecting to PostgreSQL...")
    conn = psycopg2.connect(DB_URL)
    
    try:
        # Export each state separately
        for state in DEV_STATES:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Processing state: {state}")
            logger.info('=' * 60)
            
            # Create state directory
            state_dir = STATES_DIR / state
            state_dir.mkdir(exist_ok=True)
            
            # Get jurisdiction ID for this state
            jurisdiction_id = get_state_jurisdiction(conn, state)
            
            if not jurisdiction_id:
                logger.warning(f"Skipping {state} - no jurisdiction found")
                continue
            
            # Export all datasets for this state
            export_contact_official(conn, state, state_dir)
            export_bills_bills(conn, state, jurisdiction_id, state_dir)
            export_bills_versions(conn, state, jurisdiction_id, state_dir)
            export_bills_bill_actions(conn, state, jurisdiction_id, state_dir)
            export_bills_bill_sponsorships(conn, state, jurisdiction_id, state_dir)
            export_events_events(conn, state, jurisdiction_id, state_dir)
            export_events_participants(conn, state, jurisdiction_id, state_dir)
            
            # Show summary for this state
            logger.info(f"\n  State {state} files:")
            for file in sorted(state_dir.glob("*.parquet")):
                if file.name.startswith(('bills_', 'contacts_', 'events_')):
                    size_mb = file.stat().st_size / 1024 / 1024
                    logger.info(f"    {file.name}: {size_mb:.2f} MB")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ EXPORT COMPLETE!")
        logger.info("=" * 80)
        logger.info(f"Gold datasets saved to: {STATES_DIR}")
        logger.info("")
        logger.info("Exported states:")
        for state in DEV_STATES:
            state_dir = STATES_DIR / state
            if state_dir.exists():
                leg_files = [f for f in state_dir.glob("*.parquet") 
                           if f.name.startswith(('bills_', 'contacts_', 'events_'))]
                logger.info(f"  {state}: {len(leg_files)} legislative files")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
