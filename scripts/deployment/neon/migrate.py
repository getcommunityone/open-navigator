"""
Migration script to load data from Gold parquet files into Neon Postgres
Optimized for HuggingFace deployment - loads aggregate and search data only
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import psycopg2
from psycopg2.extras import execute_values
import pandas as pd
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Database connection - prioritize dev over production
NEON_DATABASE_URL_DEV = os.getenv('NEON_DATABASE_URL_DEV')
NEON_DATABASE_URL = os.getenv('NEON_DATABASE_URL')
DATABASE_URL = NEON_DATABASE_URL_DEV or NEON_DATABASE_URL

if not DATABASE_URL:
    raise ValueError("Neither NEON_DATABASE_URL_DEV nor NEON_DATABASE_URL set in environment")

logger.info(f"Using: {'DEV' if NEON_DATABASE_URL_DEV else 'PROD'} database")

# Paths - relative to this script's location
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent  # Up from neon/ → deployment/ → scripts/ → project root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.utils.calendar_year_util import calendar_year_label

GOLD_DIR = PROJECT_ROOT / "data" / "gold"
SCHEMA_PATH = SCRIPT_DIR / "schema.sql"

# State code to full name mapping (for search optimization)
STATE_NAMES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
    'DC': 'District of Columbia', 'PR': 'Puerto Rico'
}


def parse_yyyymm_date(yyyymm):
    """Convert YYYYMM format (e.g., '195504') to date object"""
    if pd.isna(yyyymm) or not yyyymm:
        return None
    try:
        yyyymm_str = str(int(yyyymm))  # Convert to string, remove decimals
        if len(yyyymm_str) == 6:
            year = int(yyyymm_str[:4])
            month = int(yyyymm_str[4:6])
            return datetime(year, month, 1).date()
    except (ValueError, TypeError):
        pass
    return None


def clean_numeric(value):
    """Convert pandas NaN/None to None, keep valid numbers"""
    if pd.isna(value) or value is None:
        return None
    try:
        # Convert to float first, then check if it's a valid number
        num = float(value)
        if pd.isna(num):
            return None
        return num
    except (ValueError, TypeError):
        return None


def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(DATABASE_URL)


def execute_schema(conn):
    """Execute schema.sql to create tables"""
    if not SCHEMA_PATH.exists():
        logger.error(f"Schema file not found: {SCHEMA_PATH}")
        return False
    
    logger.info("📋 Creating database schema...")
    with open(SCHEMA_PATH, 'r') as f:
        schema_sql = f.read()
    
    try:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
        logger.success("✅ Schema created successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Schema creation failed: {e}")
        conn.rollback()
        return False


def load_jurisdiction_state_aggregate(conn):
    """
    Load pre-computed statistics aggregates
    This is the most critical table for fast dashboard loading
    """
    logger.info("📊 Loading statistics aggregates...")
    
    try:
        cursor = conn.cursor()
        
        # Calculate national stats
        national_stats = calculate_national_stats()
        insert_stat(cursor, **national_stats)
        
        # Calculate state-level stats for each state with data
        states_dir = GOLD_DIR / "states"
        if states_dir.exists():
            for state_dir in states_dir.iterdir():
                if state_dir.is_dir():
                    state = state_dir.name
                    logger.info(f"  Processing state: {state}")
                    state_stats = calculate_state_stats(state)
                    if state_stats:
                        insert_stat(cursor, **state_stats)
        
        conn.commit()
        
        # Get count
        cursor.execute("SELECT COUNT(*) FROM jurisdiction_state_aggregate")
        count = cursor.fetchone()[0]
        logger.success(f"✅ Loaded {count} statistics aggregates")
        
        record_sync(conn, 'jurisdiction_state_aggregate', count)
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to load stats aggregates: {e}")
        conn.rollback()
        return False


def calculate_national_stats():
    """Calculate national-level statistics"""
    stats = {
        'level': 'national',
        'state': None,
        'county': None,
        'city': None,
        'jurisdictions_count': 0,
        'school_districts_count': 0,
        'nonprofits_count': 0,
        'events_count': 0,
        'bills_count': 0,
        'contacts_count': 0,
        'total_revenue': 0,
        'total_assets': 0,
    }
    
    # Count jurisdictions
    for pattern in ['jurisdictions_cities.parquet', 'jurisdictions_counties.parquet', 
                   'jurisdictions_townships.parquet']:
        file_path = GOLD_DIR / 'reference' / pattern
        if file_path.exists():
            df = pd.read_parquet(file_path)
            stats['jurisdictions_count'] += len(df)
    
    # Count school districts
    sd_file = GOLD_DIR / 'reference' / 'jurisdictions_school_districts.parquet'
    if sd_file.exists():
        df = pd.read_parquet(sd_file)
        stats['school_districts_count'] = len(df)
    
    # Count nonprofits and sum financials
    states_dir = GOLD_DIR / "states"
    if states_dir.exists():
        for state_dir in states_dir.iterdir():
            if state_dir.is_dir():
                np_file = state_dir / "nonprofits_organizations.parquet"
                if np_file.exists():
                    df = pd.read_parquet(np_file)
                    stats['nonprofits_count'] += len(df)
                    
                    # Sum revenue/assets if available
                    if 'REVENUE' in df.columns:
                        stats['total_revenue'] += df['REVENUE'].fillna(0).sum()
                    if 'ASSETS' in df.columns:
                        stats['total_assets'] += df['ASSETS'].fillna(0).sum()
                
                # Count events
                events_file = state_dir / "events.parquet"
                if events_file.exists():
                    df = pd.read_parquet(events_file)
                    stats['events_count'] += len(df)
                
                # Count contacts (both nonprofit officers and officials/legislators)
                contacts_file = state_dir / "contacts_nonprofit_officers.parquet"
                if contacts_file.exists():
                    df = pd.read_parquet(contacts_file)
                    stats['contacts_count'] += len(df)
                
                officials_file = state_dir / "contact_official.parquet"
                if officials_file.exists():
                    df = pd.read_parquet(officials_file)
                    stats['contacts_count'] += len(df)
                
                # Count bills
                bills_file = state_dir / "bills_bills.parquet"
                if bills_file.exists():
                    df = pd.read_parquet(bills_file)
                    stats['bills_count'] += len(df)
    
    return stats


def calculate_state_stats(state: str):
    """Calculate state-level statistics"""
    stats = {
        'level': 'state',
        'state': state,
        'county': None,
        'city': None,
        'jurisdictions_count': 0,
        'school_districts_count': 0,
        'nonprofits_count': 0,
        'events_count': 0,
        'bills_count': 0,
        'contacts_count': 0,
        'total_revenue': 0,
        'total_assets': 0,
    }
    
    # Count jurisdictions in this state
    for pattern in ['jurisdictions_cities.parquet', 'jurisdictions_counties.parquet', 
                   'jurisdictions_townships.parquet']:
        file_path = GOLD_DIR / 'reference' / pattern
        if file_path.exists():
            df = pd.read_parquet(file_path)
            # All files now use state_code (2-letter) + state (full name)
            if 'state_code' in df.columns:
                state_df = df[df['state_code'].str.upper() == state.upper()]
                stats['jurisdictions_count'] += len(state_df)
    
    # Count school districts
    sd_file = GOLD_DIR / 'reference' / 'jurisdictions_school_districts.parquet'
    if sd_file.exists():
        df = pd.read_parquet(sd_file)
        # File now uses state_code (2-letter) + state (full name)
        if 'state_code' in df.columns:
            state_df = df[df['state_code'].str.upper() == state.upper()]
            stats['school_districts_count'] = len(state_df)
    
    # State-specific data
    state_dir = GOLD_DIR / "states" / state
    
    # Nonprofits
    np_file = state_dir / "nonprofits_organizations.parquet"
    if np_file.exists():
        df = pd.read_parquet(np_file)
        stats['nonprofits_count'] = len(df)
        
        if 'REVENUE' in df.columns:
            stats['total_revenue'] = int(df['REVENUE'].fillna(0).sum())
        if 'ASSETS' in df.columns:
            stats['total_assets'] = int(df['ASSETS'].fillna(0).sum())
    
    # Events
    events_file = state_dir / "events.parquet"
    if events_file.exists():
        df = pd.read_parquet(events_file)
        stats['events_count'] = len(df)
    
    # Contacts (both nonprofit officers and officials/legislators)
    contacts_file = state_dir / "contacts_nonprofit_officers.parquet"
    if contacts_file.exists():
        df = pd.read_parquet(contacts_file)
        stats['contacts_count'] = len(df)
    
    officials_file = state_dir / "contact_official.parquet"
    if officials_file.exists():
        df = pd.read_parquet(officials_file)
        stats['contacts_count'] += len(df)
    
    # Bills
    bills_file = state_dir / "bills_bills.parquet"
    if bills_file.exists():
        df = pd.read_parquet(bills_file)
        stats['bills_count'] = len(df)
    
    return stats if stats['nonprofits_count'] > 0 else None


def insert_stat(cursor, level, state, county, city, **metrics):
    """Insert statistics record"""
    cursor.execute("""
        INSERT INTO jurisdiction_state_aggregate 
        (level, state, county, city, jurisdictions_count, school_districts_count,
         nonprofits_count, events_count, bills_count, contacts_count,
         total_revenue, total_assets, last_updated)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (level, state, county, city) 
        DO UPDATE SET
            jurisdictions_count = EXCLUDED.jurisdictions_count,
            school_districts_count = EXCLUDED.school_districts_count,
            nonprofits_count = EXCLUDED.nonprofits_count,
            events_count = EXCLUDED.events_count,
            bills_count = EXCLUDED.bills_count,
            contacts_count = EXCLUDED.contacts_count,
            total_revenue = EXCLUDED.total_revenue,
            total_assets = EXCLUDED.total_assets,
            last_updated = EXCLUDED.last_updated
    """, (
        level, state, county, city,
        metrics.get('jurisdictions_count', 0),
        metrics.get('school_districts_count', 0),
        metrics.get('nonprofits_count', 0),
        metrics.get('events_count', 0),
        metrics.get('bills_count', 0),
        metrics.get('contacts_count', 0),
        metrics.get('total_revenue', 0),
        metrics.get('total_assets', 0),
        datetime.now()
    ))


def load_organization_nonprofit(conn, limit_states: Optional[list] = None):
    """
    Load nonprofits into search table
    Args:
        limit_states: List of state codes to load (e.g., ['MA', 'CA']) or None for all
    """
    logger.info("🏢 Loading nonprofits search data...")
    
    # Check if we have a consolidated file (all states) or state-specific files
    consolidated_file = GOLD_DIR / "nonprofits_organizations.parquet"
    states_dir = GOLD_DIR / "states"
    
    if consolidated_file.exists():
        # Load from consolidated file
        logger.info("  Loading from consolidated nonprofits file...")
        df = pd.read_parquet(consolidated_file)
        
        # Filter by states if limit specified
        if limit_states:
            # File now uses state_code (2-letter) + state (full name)
            df = df[df['state_code'].isin(limit_states)]
            logger.info(f"  Filtered to states: {limit_states}")
        
        total_loaded = load_nonprofits_from_df(conn, df)
        
    elif states_dir.exists():
        # Load from state-specific files (old format)
        states_to_load = limit_states or []
        
        # If no limit, scan all states
        if not limit_states:
            states_to_load = [d.name for d in states_dir.iterdir() if d.is_dir()]
        
        total_loaded = 0
        
        for state in states_to_load:
            np_file = states_dir / state / "nonprofits_organizations.parquet"
            if not np_file.exists():
                logger.warning(f"  No nonprofits file for {state}")
                continue
            
            logger.info(f"  Loading nonprofits from {state}...")
            df = pd.read_parquet(np_file)
            total_loaded += load_nonprofits_from_df(conn, df, state_override=state)
    else:
        logger.warning("  No nonprofit data found (neither consolidated nor state-specific files)")
        total_loaded = 0
    
    logger.success(f"✅ Loaded {total_loaded:,} nonprofits into search table")
    record_sync(conn, 'organization_nonprofit', total_loaded)
    return True


def load_nonprofits_from_df(conn, df, state_override=None):
    """Helper function to load nonprofits from a DataFrame"""
    cursor = conn.cursor()
    
    # Filter out rows with null EIN
    df_valid = df[df['ein'].notna()].copy()
    
    records = []
    for _, row in df_valid.iterrows():
        # Use state_code from data or override
        # Parquet files now have state_code (2-letter) and state (full name)
        state_code = state_override or row.get('state_code', '')
        state_name = row.get('state', '')
        
        # Convert ruling date from YYYYMM to proper date
        ruling_date = parse_yyyymm_date(row.get('ruling_date'))
        
        record = (
            str(row.get('ein', '')),
            row.get('organization_name', ''),
            '',  # street_address - not in new format
            row.get('city', ''),
            state_code,  # state_code column
            state_name,  # state column (full name)
            row.get('zip_code', ''),
            '',  # county - not in source data
            row.get('ntee_code', ''),
            row.get('ntee_description'),
            row.get('subsection_code', ''),
            '',  # affiliation_code - not in new format
            '',  # classification_code - not in new format
            clean_numeric(row.get('form_990_total_revenue')),
            clean_numeric(row.get('form_990_total_assets')),
            clean_numeric(row.get('form_990_net_income')),
            ruling_date,
            '',  # foundation_code - not in new format
            '',  # pf_filing_req_cd - not in new format
            None,  # accounting_period
            '',  # asset_code
            '',  # income_code
            '',  # filing_req_cd
            row.get('subsection_code', ''),  # exempt_org_status_cd
            clean_numeric(row.get('tax_period')),
            clean_numeric(row.get('form_990_total_assets')),
            clean_numeric(row.get('form_990_net_income')),
            clean_numeric(row.get('form_990_total_revenue')),
            'irs_bmf',
            datetime.now()
        )
        records.append(record)
    
    # Batch insert
    if records:
        execute_values(cursor, """
            INSERT INTO organization_nonprofit 
            (ein, name, street_address, city, state_code, state, zip_code, county,
             ntee_code, ntee_description, subsection_code, affiliation_code, classification_code,
             revenue, assets, income, ruling_date, foundation_code, pf_filing_requirement_code,
             accounting_period, asset_code, income_code, filing_requirement_code,
             exempt_organization_status_code, tax_period, asset_amount, income_amount,
             form_990_revenue_amount, source, last_updated)
            VALUES %s
            ON CONFLICT (ein) DO UPDATE SET
                name = EXCLUDED.name,
                city = EXCLUDED.city,
                state_code = EXCLUDED.state_code,
                state = EXCLUDED.state,
                revenue = EXCLUDED.revenue,
                assets = EXCLUDED.assets,
                last_updated = EXCLUDED.last_updated
        """, records)
        
        conn.commit()
        logger.info(f"    Loaded {len(records):,} nonprofits")
        return len(records)
    
    return 0



def load_reference_data(conn):
    """Load reference tables (causes, NTEE codes)
    
    Note: For standalone loading, use:
          python scripts/data/load_reference_data.py
          python scripts/datasources/ntee/load_to_postgres.py
    """
    logger.info("📚 Loading reference data...")
    
    cursor = conn.cursor()
    total = 0
    
    # Load NTEE codes into cause_ntee table
    ntee_file = GOLD_DIR / "causes_ntee_codes.parquet"
    if ntee_file.exists():
        df = pd.read_parquet(ntee_file)
        
        # Build lookup dictionary for breadcrumb creation
        code_lookup = {row['ntee_code']: row['description'] for _, row in df.iterrows()}
        
        def build_ntee_breadcrumb(code, parent_code):
            """Build hierarchical breadcrumb path for NTEE"""
            if pd.isna(parent_code) or not parent_code:
                return code_lookup.get(code, code)
            
            path = []
            current = parent_code
            
            # Traverse up to 5 levels to avoid infinite loops
            for _ in range(5):
                if pd.isna(current) or not current:
                    break
                if current in code_lookup:
                    path.insert(0, code_lookup[current])
                # Find parent of current
                parent_row = df[df['ntee_code'] == current]
                if len(parent_row) > 0 and not pd.isna(parent_row.iloc[0].get('parent_code')):
                    current = parent_row.iloc[0]['parent_code']
                else:
                    break
            
            path.append(code_lookup.get(code, code))
            return ' > '.join(path)
        
        records = [
            (
                row['ntee_code'],
                row.get('description', ''),
                row.get('description', ''),
                'ntee',
                row.get('parent_code'),
                row.get('ntee_type'),
                None,
                build_ntee_breadcrumb(row['ntee_code'], row.get('parent_code')),
                'irs',
                datetime.now()
            ) 
            for _, row in df.iterrows()
        ]
        
        execute_values(cursor, """
            INSERT INTO cause_ntee (code, name, description, cause_type, parent_code, category, subcategory, cause_breadcrumb, source, last_updated)
            VALUES %s
            ON CONFLICT (code) DO UPDATE SET 
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                cause_breadcrumb = EXCLUDED.cause_breadcrumb,
                last_updated = EXCLUDED.last_updated
        """, records)
        
        total += len(records)
        logger.info(f"  Loaded {len(records)} NTEE codes")
    else:
        logger.warning(f"  NTEE codes file not found: {ntee_file}")
        logger.info(f"  To generate NTEE data, see: scripts/datasources/ntee/")
    
    # Load EveryOrg causes into cause_ntee table
    causes_file = GOLD_DIR / "causes_everyorg_causes.parquet"
    if causes_file.exists():
        df = pd.read_parquet(causes_file)
        
        # Build lookup dictionary for breadcrumb creation
        cause_lookup = {row['cause_id']: row['cause_name'] for _, row in df.iterrows()}
        
        def build_everyorg_breadcrumb(cause_id, parent_id):
            """Build hierarchical breadcrumb path for EveryOrg"""
            if pd.isna(parent_id) or not parent_id:
                return cause_lookup.get(cause_id, cause_id)
            
            path = []
            current = parent_id
            
            # Traverse up to 5 levels to avoid infinite loops
            for _ in range(5):
                if pd.isna(current) or not current:
                    break
                if current in cause_lookup:
                    path.insert(0, cause_lookup[current])
                # Find parent of current
                parent_row = df[df['cause_id'] == current]
                if len(parent_row) > 0 and not pd.isna(parent_row.iloc[0].get('parent_id')):
                    current = parent_row.iloc[0]['parent_id']
                else:
                    break
            
            path.append(cause_lookup.get(cause_id, cause_id))
            return ' > '.join(path)
        
        records = [
            (
                row['cause_id'],
                row['cause_name'],
                row.get('description'),
                'everyorg',
                row.get('parent_id'),
                row.get('category'),
                None,
                build_everyorg_breadcrumb(row['cause_id'], row.get('parent_id')),
                'everyorg',
                datetime.now()
            )
            for _, row in df.iterrows()
        ]
        
        execute_values(cursor, """
            INSERT INTO cause_ntee (code, name, description, cause_type, parent_code, category, subcategory, cause_breadcrumb, source, last_updated)
            VALUES %s
            ON CONFLICT (code) DO UPDATE SET 
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                cause_breadcrumb = EXCLUDED.cause_breadcrumb,
                last_updated = EXCLUDED.last_updated
        """, records)
        
        total += len(records)
        logger.info(f"  Loaded {len(records)} EveryOrg causes")
    else:
        logger.warning(f"  Causes file not found: {causes_file}")
    
    conn.commit()
    logger.success(f"✅ Loaded {total} reference records into cause_ntee table")
    return True


def load_jurisdiction(conn):
    """Load jurisdictions (cities, counties, townships, school districts)"""
    logger.info("🏛️  Loading jurisdictions search data...")
    
    cursor = conn.cursor()
    total_loaded = 0
    
    # Load cities
    cities_file = GOLD_DIR / "jurisdictions_cities.parquet"
    if cities_file.exists():
        df = pd.read_parquet(cities_file)
        records = [
            (row.get('NAME', ''), 'city', 
             row.get('state_code', ''),  # state_code (2-letter)
             row.get('state', ''),  # state (full name)
             None,  # county
             str(row.get('GEOID', '')).zfill(7) if row.get('GEOID') else None,  # geoid (7 digits)
             None,  # fips_code
             None, clean_numeric(row.get('ALAND_SQMI')),  # population, area_sq_miles
             'census', datetime.now())
            for _, row in df.iterrows()
        ]
        
        execute_values(cursor, """
            INSERT INTO jurisdiction 
            (name, type, state_code, state, county, geoid, fips_code, population, area_sq_miles, source, last_updated)
            VALUES %s
            ON CONFLICT (name, type, state_code, county) DO UPDATE SET
                geoid = EXCLUDED.geoid,
                area_sq_miles = EXCLUDED.area_sq_miles,
                state = EXCLUDED.state
        """, records)
        
        total_loaded += len(records)
        logger.info(f"  Loaded {len(records):,} cities")
    
    # Load counties
    counties_file = GOLD_DIR / "jurisdictions_counties.parquet"
    if counties_file.exists():
        df = pd.read_parquet(counties_file)
        records = [
            (row.get('NAME', ''), 'county', 
             row.get('state_code', ''),  # state_code (2-letter)
             row.get('state', ''),  # state (full name)
             None,
             str(row.get('GEOID', '')).zfill(5) if row.get('GEOID') else None,  # geoid (5 digits)
             str(row.get('GEOID', '')).zfill(5) if row.get('GEOID') else None,  # fips_code (same as geoid)
             None, clean_numeric(row.get('ALAND_SQMI')),
             'census', datetime.now())
            for _, row in df.iterrows()
        ]
        
        execute_values(cursor, """
            INSERT INTO jurisdiction 
            (name, type, state_code, state, county, geoid, fips_code, population, area_sq_miles, source, last_updated)
            VALUES %s
            ON CONFLICT (name, type, state_code, county) DO UPDATE SET
                geoid = EXCLUDED.geoid,
                fips_code = EXCLUDED.fips_code,
                area_sq_miles = EXCLUDED.area_sq_miles,
                state = EXCLUDED.state
        """, records)
        
        total_loaded += len(records)
        logger.info(f"  Loaded {len(records):,} counties")
    
    # Load townships
    townships_file = GOLD_DIR / "jurisdictions_townships.parquet"
    if townships_file.exists():
        df = pd.read_parquet(townships_file)
        records = [
            (row.get('NAME', ''), 'township', 
             row.get('state_code', ''),  # state_code (2-letter)
             row.get('state', ''),  # state (full name)
             None,
             str(row.get('GEOID', '')).zfill(10) if row.get('GEOID') else None,  # geoid (10 digits)
             None,  # fips_code
             None, clean_numeric(row.get('ALAND_SQMI')),
             'census', datetime.now())
            for _, row in df.iterrows()
        ]
        
        execute_values(cursor, """
            INSERT INTO jurisdiction 
            (name, type, state_code, state, county, geoid, fips_code, population, area_sq_miles, source, last_updated)
            VALUES %s
            ON CONFLICT (name, type, state_code, county) DO UPDATE SET
                geoid = EXCLUDED.geoid,
                area_sq_miles = EXCLUDED.area_sq_miles,
                state = EXCLUDED.state
        """, records)
        
        total_loaded += len(records)
        logger.info(f"  Loaded {len(records):,} townships")
    
    # Load school districts
    districts_file = GOLD_DIR / "jurisdictions_school_districts.parquet"
    if districts_file.exists():
        df = pd.read_parquet(districts_file)
        records = [
            (row.get('NAME', ''), 'school_district', 
             row.get('state_code', ''),  # state_code (2-letter)
             row.get('state', ''),  # state (full name)
             None,
             str(row.get('GEOID', '')).zfill(7) if row.get('GEOID') else None,  # geoid (7 digits)
             None,  # fips_code
             None, clean_numeric(row.get('ALAND_SQMI')),
             'census', datetime.now())
            for _, row in df.iterrows()
        ]
        
        execute_values(cursor, """
            INSERT INTO jurisdiction 
            (name, type, state_code, state, county, geoid, fips_code, population, area_sq_miles, source, last_updated)
            VALUES %s
            ON CONFLICT (name, type, state_code, county) DO UPDATE SET
                geoid = EXCLUDED.geoid,
                area_sq_miles = EXCLUDED.area_sq_miles,
                state = EXCLUDED.state
        """, records)
        
        total_loaded += len(records)
        logger.info(f"  Loaded {len(records):,} school districts")
    
    conn.commit()
    logger.success(f"✅ Loaded {total_loaded:,} jurisdictions into search table")
    record_sync(conn, 'jurisdiction', total_loaded)
    return True


def load_event(conn, limit_states=None):
    """Load events from states"""
    logger.info("📅 Loading events search data...")
    
    states_to_load = limit_states or []
    
    # If no limit, scan all states
    if not limit_states:
        states_dir = GOLD_DIR / "states"
        if states_dir.exists():
            states_to_load = [d.name for d in states_dir.iterdir() if d.is_dir()]
    
    total_loaded = 0
    cursor = conn.cursor()
    
    for state in states_to_load:
        events_file = GOLD_DIR / "states" / state / "events.parquet"
        if not events_file.exists():
            continue
        
        logger.info(f"  Loading events from {state}...")
        df = pd.read_parquet(events_file)
        
        state_code = state.upper()
        state_name = STATE_NAMES.get(state_code, state_code)
        
        records = []
        for _, row in df.iterrows():
            # Parse start_date to extract date and time
            start_date = row.get('start_date')
            event_date = None
            event_time = None
            if start_date:
                try:
                    if isinstance(start_date, str):
                        from dateutil import parser
                        dt = parser.parse(start_date)
                        event_date = dt.date()
                        event_time = dt.time()
                    elif hasattr(start_date, 'date'):
                        event_date = start_date.date()
                        event_time = start_date.time()
                except:
                    pass
            
            record = (
                row.get('event_name', ''),
                row.get('description', ''),
                event_date,
                event_time,
                row.get('jurisdiction_name', ''),
                None,  # jurisdiction_type
                state_code,  # state_code
                state_name,  # state (full name)
                None,  # city
                row.get('location_id'),  # location
                row.get('classification', ''),  # meeting_type
                row.get('status', ''),
                None,  # agenda_url
                None,  # minutes_url
                None,  # video_url
                'openstates',
                datetime.now()
            )
            records.append(record)
        
        if records:
            execute_values(cursor, """
                INSERT INTO event 
                (event_title, event_description, event_date, event_time, jurisdiction_name, jurisdiction_type,
                 state_code, state, city, location, meeting_type, status, agenda_url, minutes_url, video_url,
                 source, last_updated)
                VALUES %s
            """, records)
            
            total_loaded += len(records)
            logger.info(f"    Loaded {len(records):,} events from {state}")
    
    conn.commit()
    logger.success(f"✅ Loaded {total_loaded:,} events into search table")
    record_sync(conn, 'event', total_loaded)
    return True


def load_contact(conn, limit_states=None):
    """Load contacts (officials, nonprofit officers) from states"""
    logger.info("👥 Loading contacts search data...")
    
    states_to_load = limit_states or []
    
    # If no limit, scan all states
    if not limit_states:
        states_dir = GOLD_DIR / "states"
        if states_dir.exists():
            states_to_load = [d.name for d in states_dir.iterdir() if d.is_dir()]
    
    total_loaded = 0
    cursor = conn.cursor()
    
    for state in states_to_load:
        # Load state legislators (from OpenStates)
        state_legislators_file = GOLD_DIR / "states" / state / "contact_official.parquet"
        if state_legislators_file.exists():
            df = pd.read_parquet(state_legislators_file)
            
            # Get state info
            state_code = state.upper()
            state_name = STATE_NAMES.get(state_code, state_code)
            
            records = []
            for _, row in df.iterrows():
                chamber_label = "State Senator" if row.get('chamber') == 'upper' else "State Representative"
                if row.get('district'):
                    chamber_label = f"{chamber_label}, District {row.get('district')}"
                
                record = (
                    row.get('full_name', ''),
                    chamber_label,
                    state_name,  # organization_name (use full state name for search)
                    None,  # organization_ein
                    row.get('email'),
                    row.get('phone'),
                    row.get('address'),  # street_address
                    None,  # city
                    state_code,  # state_code
                    state_name,  # state (full name)
                    None,  # zip_code
                    'state_legislator',  # role_type
                    None,  # compensation
                    None,  # hours_per_week
                    'openstates',
                    None,  # tax_year
                    datetime.now()
                )
                records.append(record)
            
            if records:
                execute_values(cursor, """
                    INSERT INTO contact 
                    (name, title, organization_name, organization_ein, email, phone,
                     street_address, city, state_code, state, zip_code, role_type, compensation,
                     hours_per_week, source, tax_year, last_updated)
                    VALUES %s
                """, records)
                
                total_loaded += len(records)
                logger.info(f"  Loaded {len(records):,} state legislators from {state}")
        
        # Load local officials
        officials_file = GOLD_DIR / "states" / state / "contacts_local_officials.parquet"
        if officials_file.exists():
            df = pd.read_parquet(officials_file)
            
            state_code = state.upper()
            state_name = STATE_NAMES.get(state_code, state_code)
            
            records = []
            for _, row in df.iterrows():
                record = (
                    row.get('name', ''),
                    row.get('title', ''),
                    row.get('jurisdiction', ''),  # organization_name
                    None,  # organization_ein
                    None,  # email
                    None,  # phone
                    None,  # street_address
                    None,  # city
                    state_code,  # state_code
                    state_name,  # state (full name)
                    None,  # zip_code
                    'government_official',  # role_type
                    None,  # compensation
                    None,  # hours_per_week
                    'meeting_transcript',
                    None,  # tax_year
                    datetime.now()
                )
                records.append(record)
            
            if records:
                execute_values(cursor, """
                    INSERT INTO contact 
                    (name, title, organization_name, organization_ein, email, phone,
                     street_address, city, state_code, state, zip_code, role_type, compensation,
                     hours_per_week, source, tax_year, last_updated)
                    VALUES %s
                """, records)
                
                total_loaded += len(records)
                logger.info(f"  Loaded {len(records):,} officials from {state}")
        
        # Load nonprofit officers (if exists)
        officers_file = GOLD_DIR / "states" / state / "contacts_nonprofit_officers.parquet"
        if officers_file.exists():
            df = pd.read_parquet(officers_file)
            
            state_code = state.upper()
            state_name = STATE_NAMES.get(state_code, state_code)
            
            records = []
            for _, row in df.iterrows():
                record = (
                    row.get('name', ''),
                    row.get('title', ''),
                    row.get('organization_name', ''),
                    row.get('ein', ''),  # organization_ein
                    None,  # email
                    None,  # phone
                    None,  # street_address
                    None,  # city
                    state_code,  # state_code
                    state_name,  # state (full name)
                    None,  # zip_code
                    'nonprofit_officer',  # role_type
                    clean_numeric(row.get('compensation')),
                    clean_numeric(row.get('hours_per_week')),
                    'irs_form990',
                    calendar_year_label(row.get('tax_year')),
                    datetime.now()
                )
                records.append(record)
            
            if records:
                execute_values(cursor, """
                    INSERT INTO contact 
                    (name, title, organization_name, organization_ein, email, phone,
                     street_address, city, state_code, state, zip_code, role_type, compensation,
                     hours_per_week, source, tax_year, last_updated)
                    VALUES %s
                """, records)
                
                total_loaded += len(records)
                logger.info(f"  Loaded {len(records):,} nonprofit officers from {state}")
    
    conn.commit()
    logger.success(f"✅ Loaded {total_loaded:,} contacts into search table")
    record_sync(conn, 'contact', total_loaded)
    return True


def load_bills_search(conn, limit_states=None):
    """Load bills from states"""
    logger.info("📜 Loading bills search data...")
    
    states_to_load = limit_states or []
    
    # If no limit, scan all states
    if not limit_states:
        states_dir = GOLD_DIR / "states"
        if states_dir.exists():
            states_to_load = [d.name for d in states_dir.iterdir() if d.is_dir()]
    
    total_loaded = 0
    cursor = conn.cursor()
    
    for state in states_to_load:
        bills_file = GOLD_DIR / "states" / state / "bills_bills.parquet"
        if bills_file.exists():
            df = pd.read_parquet(bills_file)
            
            # Extract state code from jurisdiction_ocd_id
            # ocd-jurisdiction/country:us/state:ma/government -> MA
            state_code = state.upper()
            state_name = STATE_NAMES.get(state_code, state_code)
            
            records = []
            for _, row in df.iterrows():
                # Convert values to Python native types to avoid numpy array issues
                def safe_str(val):
                    """Convert value to string, handling None and arrays"""
                    if pd.isna(val):
                        return ''
                    if isinstance(val, (list, tuple)):
                        return str(val[0]) if len(val) > 0 else ''
                    return str(val)
                
                def safe_date(val):
                    """Convert value to date, handling None and NaT"""
                    if pd.isna(val):
                        return None
                    # Check for NaT string representation
                    if str(val) == 'NaT':
                        return None
                    try:
                        dt = pd.to_datetime(val)
                        if pd.isna(dt):
                            return None
                        return dt.date()
                    except:
                        return None
                
                def safe_datetime(val):
                    """Convert value to datetime, handling None and NaT"""
                    if pd.isna(val):
                        return None
                    # Check for NaT string representation  
                    if str(val) == 'NaT':
                        return None
                    try:
                        dt = pd.to_datetime(val)
                        if pd.isna(dt):
                            return None
                        return dt
                    except:
                        return None
                
                record = (
                    safe_str(row.get('bill_id', '')),
                    safe_str(row.get('bill_number', '')),
                    safe_str(row.get('title', '')),
                    safe_str(row.get('classification', '')),
                    safe_str(row.get('session', '')),
                    safe_str(row.get('session_name', '')),
                    safe_str(row.get('jurisdiction_name', '')),
                    state_code,  # state_code
                    state_name,  # state (full name)
                    safe_date(row.get('first_action_date')),
                    safe_date(row.get('latest_action_date')),
                    safe_str(row.get('latest_action_description', '')),
                    safe_str(row.get('abstract', '')),
                    safe_str(row.get('source_url', '')),
                    safe_datetime(row.get('created_at')),
                    safe_datetime(row.get('updated_at')),
                    datetime.now()
                )
                records.append(record)
            
            if records:
                # Insert in batches to handle large datasets
                batch_size = 1000
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    execute_values(cursor, """
                        INSERT INTO bills_search 
                        (bill_id, bill_number, title, classification, session, session_name,
                         jurisdiction_name, state_code, state, first_action_date, latest_action_date,
                         latest_action_description, abstract, source_url, created_at, updated_at,
                         last_synced)
                        VALUES %s
                        ON CONFLICT (bill_id) DO NOTHING
                    """, batch)
                
                total_loaded += len(records)
                logger.info(f"  Loaded {len(records):,} bills from {state}")
    
    conn.commit()
    logger.success(f"✅ Loaded {total_loaded:,} bills into search table")
    record_sync(conn, 'bills_search', total_loaded)
    return True



def record_sync(conn, table_name: str, records_synced: int, status: str = 'success', error: Optional[str] = None):
    """Record sync status"""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO log_last_sync (table_name, last_sync_time, records_synced, sync_status, error_message)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (table_name) DO UPDATE SET
            last_sync_time = EXCLUDED.last_sync_time,
            records_synced = EXCLUDED.records_synced,
            sync_status = EXCLUDED.sync_status,
            error_message = EXCLUDED.error_message
    """, (table_name, datetime.now(), records_synced, status, error))
    conn.commit()


def main():
    """Main migration function"""
    logger.info("🚀 Starting Neon migration...")
    logger.info(f"📁 Gold directory: {GOLD_DIR.absolute()}")
    
    try:
        conn = get_db_connection()
        logger.success("✅ Connected to Neon database")
        
        # Step 1: Create schema
        if not execute_schema(conn):
            return 1
        
        # Step 2: Load aggregates (critical for dashboard)
        if not load_jurisdiction_state_aggregate(conn):
            return 1
        
        # Step 3: Load reference data
        if not load_reference_data(conn):
            return 1
        
        # Step 4: Load nonprofit search data (start with MA as example)
        logger.info("⚠️  Loading only MA nonprofits (full load would be 3M+ records)")
        logger.info("   To load all states, modify limit_states parameter")
        if not load_organization_nonprofit(conn, limit_states=['MA']):
            return 1
        
        # Step 5: Load jurisdictions (all jurisdictions - reference data)
        if not load_jurisdiction(conn):
            return 1
        
        # Step 6: Load events (MA only, same as nonprofits)
        if not load_event(conn, limit_states=['MA']):
            return 1
        
        # Step 7: Load contacts (MA only, same as nonprofits)
        if not load_contact(conn, limit_states=['MA']):
            return 1
        
        # Step 8: Load bills (MA only to start)
        logger.info("⚠️  Loading only MA bills (~75K records)")
        logger.info("   To load all states, modify limit_states parameter")
        if not load_bills_search(conn, limit_states=['MA']):
            return 1
        
        # Show summary
        cursor = conn.cursor()
        cursor.execute("SELECT table_name, records_synced, last_sync_time FROM log_last_sync ORDER BY table_name")
        logger.info("\n📊 Migration Summary:")
        logger.info("=" * 60)
        for row in cursor.fetchall():
            logger.info(f"  {row[0]:<30} {row[1]:>10,} records  ({row[2]})")
        logger.info("=" * 60)
        
        conn.close()
        logger.success("\n🎉 Migration completed successfully!")
        logger.info("\n💡 Next steps:")
        logger.info("  1. Test queries: SELECT * FROM jurisdiction_state_aggregate LIMIT 5;")
        logger.info("  2. Update API routes to use Neon")
        logger.info("  3. Add NEON_DATABASE_URL to HuggingFace Secrets")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
