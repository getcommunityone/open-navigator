#!/usr/bin/env python3
"""
Load NTEE codes from parquet file into PostgreSQL

This script loads the National Taxonomy of Exempt Entities (NTEE) codes
used to classify nonprofit organizations by their mission and activities.

Data source: IRS Publication 557 + NCCS (National Center for Charitable Statistics)
Input: data/gold/causes_ntee_codes.parquet (196 codes)
Output: cause_ntee table in PostgreSQL (cause_type='ntee')

Usage:
    # Load to local database
    python scripts/datasources/ntee/load_to_postgres.py
    
    # Load to Neon (production)
    python scripts/datasources/ntee/load_to_postgres.py --neon
    
    # Load to custom database
    python scripts/datasources/ntee/load_to_postgres.py --db-url postgresql://user:pass@host:port/dbname
    
    # Show what would be loaded without loading
    python scripts/datasources/ntee/load_to_postgres.py --dry-run
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import psycopg2
from psycopg2.extras import execute_values
import pandas as pd
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Default database URLs
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
LOCAL_DATABASE_URL = os.getenv('LOCAL_DATABASE_URL', f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator')
NEON_DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', os.getenv('NEON_DATABASE_URL'))

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
GOLD_DIR = PROJECT_ROOT / "data" / "gold"
NTEE_FILE = GOLD_DIR / "causes_ntee_codes.parquet"


def create_table(conn):
    """Create cause_ntee table if it doesn't exist"""
    
    logger.info("Creating cause_ntee table if needed...")
    
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cause_ntee (
                code VARCHAR(100) PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                cause_type VARCHAR(20) NOT NULL,
                parent_code VARCHAR(100),
                category VARCHAR(100),
                subcategory VARCHAR(100),
                cause_breadcrumb TEXT,
                source VARCHAR(50) NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cause_ntee_type 
            ON cause_ntee(cause_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cause_ntee_name_search 
            ON cause_ntee USING gin(to_tsvector('english', name))
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cause_ntee_description_search 
            ON cause_ntee USING gin(to_tsvector('english', description))
        """)
    
    conn.commit()
    logger.success("✅ Table created/verified")


def load_ntee_codes(cursor, dry_run=False):
    """Load NTEE codes from parquet file"""
    
    if not NTEE_FILE.exists():
        logger.error(f"❌ NTEE codes file not found: {NTEE_FILE}")
        logger.info("\n💡 To generate NTEE codes data, run:")
        logger.info("   python scripts/datasources/ntee/generate_ntee_codes.py")
        return 0
    
    logger.info(f"Reading NTEE codes from {NTEE_FILE}...")
    df = pd.read_parquet(NTEE_FILE)
    
    logger.info(f"Found {len(df)} NTEE codes")
    logger.info(f"Columns: {df.columns.tolist()}")
    
    # Show sample data
    logger.info("\nSample codes:")
    for idx, row in df.head(5).iterrows():
        logger.info(f"  {row['ntee_code']:5} - {row['description']}")
    
    if dry_run:
        logger.info(f"\n[DRY RUN] Would load {len(df)} NTEE codes")
        return len(df)
    
    # Build lookup dictionary for breadcrumb creation
    code_lookup = {row['ntee_code']: row['description'] for _, row in df.iterrows()}
    
    def build_breadcrumb(code, parent_code):
        """Build hierarchical breadcrumb path"""
        if pd.isna(parent_code) or not parent_code:
            # Top level - just the name
            return code_lookup.get(code, code)
        
        # Build path: traverse up the parent chain
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
        
        # Add current code's name
        path.append(code_lookup.get(code, code))
        
        return ' > '.join(path)
    
    # Prepare records for insertion
    records = [
        (
            row['ntee_code'],                                                    # code
            row.get('description', ''),                                         # name
            row.get('description', ''),                                         # description
            'ntee',                                                             # cause_type
            row.get('parent_code'),                                             # parent_code
            row.get('ntee_type'),                                               # category
            None,                                                               # subcategory
            build_breadcrumb(row['ntee_code'], row.get('parent_code')),        # cause_breadcrumb
            'irs',                                                              # source
            datetime.now()                                                      # last_updated
        ) 
        for _, row in df.iterrows()
    ]
    
    logger.info(f"Loading {len(records)} NTEE codes into database...")
    
    execute_values(cursor, """
        INSERT INTO cause_ntee (code, name, description, cause_type, parent_code, category, subcategory, cause_breadcrumb, source, last_updated)
        VALUES %s
        ON CONFLICT (code) DO UPDATE SET 
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            cause_breadcrumb = EXCLUDED.cause_breadcrumb,
            last_updated = EXCLUDED.last_updated
    """, records)
    
    logger.success(f"✅ Loaded {len(records)} NTEE codes")
    return len(records)


def verify_data(conn):
    """Verify loaded data"""
    
    cursor = conn.cursor()
    
    # Count total records
    cursor.execute("SELECT COUNT(*) FROM cause_ntee WHERE cause_type = 'ntee'")
    total = cursor.fetchone()[0]
    
    # Get sample records
    cursor.execute("SELECT code, name FROM cause_ntee WHERE cause_type = 'ntee' ORDER BY code LIMIT 5")
    samples = cursor.fetchall()
    
    logger.info("\n" + "=" * 70)
    logger.info("VERIFICATION")
    logger.info("=" * 70)
    logger.info(f"Total NTEE codes in database: {total}")
    logger.info("\nSample records:")
    for code, desc in samples:
        logger.info(f"  {code:5} - {desc}")
    logger.info("=" * 70)
    
    return total


def main():
    parser = argparse.ArgumentParser(
        description='Load NTEE codes into PostgreSQL'
    )
    
    parser.add_argument(
        '--neon',
        action='store_true',
        help='Load to Neon cloud database instead of local'
    )
    
    parser.add_argument(
        '--db-url',
        type=str,
        help='Custom database URL'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be loaded without actually loading'
    )
    
    args = parser.parse_args()
    
    # Determine database URL
    if args.db_url:
        db_url = args.db_url
    elif args.neon:
        if not NEON_DATABASE_URL:
            logger.error("❌ NEON_DATABASE_URL not set in environment")
            return 1
        db_url = NEON_DATABASE_URL
    else:
        db_url = LOCAL_DATABASE_URL
    
    logger.info("=" * 70)
    logger.info("LOAD NTEE CODES TO POSTGRESQL")
    logger.info("=" * 70)
    if not args.dry_run:
        logger.info(f"Database: {db_url[:60]}...")
    logger.info(f"NTEE file: {NTEE_FILE}")
    logger.info("")
    
    try:
        if args.dry_run:
            # Just read and show data
            cursor = None
            load_ntee_codes(cursor, dry_run=True)
            return 0
        
        # Connect to database
        conn = psycopg2.connect(db_url)
        logger.success("✅ Connected to database")
        
        # Create table
        create_table(conn)
        
        # Load data
        cursor = conn.cursor()
        count = load_ntee_codes(cursor)
        conn.commit()
        
        # Verify
        verify_data(conn)
        
        conn.close()
        logger.success("\n🎉 NTEE codes loaded successfully!")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ Load failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == '__main__':
    sys.exit(main())
