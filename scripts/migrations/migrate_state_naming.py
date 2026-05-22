#!/usr/bin/env python3
"""
Migrate state field naming to standard convention

This script migrates all database tables and parquet files from legacy naming:
  - state (2-letter code) → state_code
  - state_name (full name) → state
  - state_abbr (2-letter code) → state_code

To standard naming:
  - state_code (2-letter code)  
  - state (full name)

Usage:
    python scripts/migrations/migrate_state_naming.py --dry-run
    python scripts/migrations/migrate_state_naming.py --tables
    python scripts/migrations/migrate_state_naming.py --parquets
    python scripts/migrations/migrate_state_naming.py --all
"""
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List
import pandas as pd
import psycopg2
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')

# State code to full name mapping
STATE_CODE_TO_NAME = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia',
    'PR': 'Puerto Rico', 'VI': 'U.S. Virgin Islands', 'GU': 'Guam',
    'AS': 'American Samoa', 'MP': 'Northern Mariana Islands'
}


class StateFieldMigrator:
    """Migrate state field naming across database and parquet files."""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.changes_made = []
        
    def migrate_database_tables(self):
        """Migrate all database tables to new naming convention."""
        
        logger.info("=" * 80)
        logger.info("MIGRATING DATABASE TABLES")
        logger.info("=" * 80)
        
        if self.dry_run:
            logger.warning("🔍 DRY RUN MODE - No changes will be made")
        
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        try:
            # Get all tables with state columns
            cursor.execute("""
                SELECT DISTINCT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND column_name IN ('state', 'state_abbr', 'state_code', 'state_name')
                ORDER BY table_name, column_name
            """)
            
            tables_columns = {}
            for table_name, column_name in cursor.fetchall():
                if table_name not in tables_columns:
                    tables_columns[table_name] = []
                tables_columns[table_name].append(column_name)
            
            logger.info(f"Found {len(tables_columns)} tables with state columns")
            
            # Migrate each table
            for table_name, columns in tables_columns.items():
                self._migrate_table(conn, cursor, table_name, columns)
            
            if not self.dry_run:
                conn.commit()
                logger.success("✓ All database migrations committed")
            else:
                conn.rollback()
                logger.info("🔍 Dry run complete - no changes committed")
                
        except Exception as e:
            conn.rollback()
            logger.error(f"✗ Migration failed: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def _migrate_table(self, conn, cursor, table_name: str, columns: List[str]):
        """Migrate a single table."""
        
        logger.info(f"\n📋 Table: {table_name}")
        logger.info(f"   Current columns: {columns}")
        
        # Skip system tables
        if table_name in ['contact_oauth_state', 'user', 'zip_county_mapping']:
            logger.info(f"   ⏭️  Skipping system table")
            return
        
        # Determine migration strategy
        has_state = 'state' in columns
        has_state_code = 'state_code' in columns
        has_state_name = 'state_name' in columns
        has_state_abbr = 'state_abbr' in columns
        
        # Check if state contains 2-letter codes or full names
        if has_state:
            cursor.execute(f"SELECT state FROM {table_name} WHERE state IS NOT NULL LIMIT 1")
            row = cursor.fetchone()
            if row and row[0]:
                state_is_code = len(row[0]) == 2
            else:
                state_is_code = False
        else:
            state_is_code = False
        
        # Migration strategy
        steps = []
        
        # CASE 1: state contains 2-letter codes (most common legacy pattern)
        if has_state and state_is_code and not has_state_code:
            steps.append(f"ALTER TABLE {table_name} RENAME COLUMN state TO state_code")
            steps.append(f"ALTER TABLE {table_name} ADD COLUMN state VARCHAR(50)")
            steps.append(self._generate_state_update_query(table_name))
            
        # CASE 2: has state_abbr instead of state_code  
        elif has_state_abbr and not has_state_code:
            steps.append(f"ALTER TABLE {table_name} RENAME COLUMN state_abbr TO state_code")
            if not has_state and not has_state_name:
                steps.append(f"ALTER TABLE {table_name} ADD COLUMN state VARCHAR(50)")
                steps.append(self._generate_state_update_query(table_name))
        
        # CASE 3: has state_name but needs to rename to state
        if has_state_name and (has_state_code or steps):
            # If we renamed state → state_code, now rename state_name → state
            steps.append(f"ALTER TABLE {table_name} RENAME COLUMN state_name TO state")
        
        # CASE 4: has state_code but missing state column
        if has_state_code and not has_state and not has_state_name:
            steps.append(f"ALTER TABLE {table_name} ADD COLUMN state VARCHAR(50)")
            steps.append(self._generate_state_update_query(table_name))
        
        # Execute migration
        if steps:
            for step in steps:
                logger.info(f"   → {step}")
                if not self.dry_run:
                    cursor.execute(step)
            self.changes_made.append({
                'table': table_name,
                'steps': steps
            })
        else:
            logger.info(f"   ✓ Already uses correct naming")
    
    def _generate_state_update_query(self, table_name: str) -> str:
        """Generate CASE statement to populate state from state_code."""
        
        cases = []
        for code, name in STATE_CODE_TO_NAME.items():
            cases.append(f"        WHEN '{code}' THEN '{name}'")
        
        case_stmt = "\n".join(cases)
        
        return f"""UPDATE {table_name} 
    SET state = CASE state_code
{case_stmt}
        ELSE state_code
    END
    WHERE state IS NULL"""
    
    def migrate_parquet_files(self, base_dir: Path = None):
        """Migrate all parquet files to new naming convention."""
        
        logger.info("\n" + "=" * 80)
        logger.info("MIGRATING PARQUET FILES")
        logger.info("=" * 80)
        
        if self.dry_run:
            logger.warning("🔍 DRY RUN MODE - No files will be modified")
        
        base_dir = base_dir or Path('data/gold')
        
        # Find all parquet files
        parquet_files = list(base_dir.rglob('*.parquet'))
        logger.info(f"Found {len(parquet_files)} parquet files")
        
        for file_path in parquet_files:
            self._migrate_parquet_file(file_path)
        
        if not self.dry_run:
            logger.success(f"✓ Migrated {len(self.changes_made)} parquet files")
        else:
            logger.info(f"🔍 Dry run complete - would modify {len([c for c in self.changes_made if c.get('file')])} files")
    
    def _migrate_parquet_file(self, file_path: Path):
        """Migrate a single parquet file."""
        
        try:
            df = pd.read_parquet(file_path)
            
            # Check for state columns
            state_cols = [col for col in df.columns if 'state' in col.lower()]
            if not state_cols:
                return
            
            logger.info(f"\n📄 {file_path.relative_to('data')}")
            logger.info(f"   Current columns: {state_cols}")
            
            original_df = df.copy()
            modified = False
            
            # CASE 1: state contains 2-letter codes
            if 'state' in df.columns and df['state'].str.len().max() <= 2:
                df.rename(columns={'state': 'state_code'}, inplace=True)
                df['state'] = df['state_code'].map(STATE_CODE_TO_NAME)
                modified = True
                logger.info(f"   → Renamed 'state' → 'state_code', added full 'state' names")
            
            # CASE 2: state_name exists, rename to state
            if 'state_name' in df.columns:
                df.rename(columns={'state_name': 'state'}, inplace=True)
                modified = True
                logger.info(f"   → Renamed 'state_name' → 'state'")
            
            # CASE 3: state_abbr exists, rename to state_code
            if 'state_abbr' in df.columns:
                df.rename(columns={'state_abbr': 'state_code'}, inplace=True)
                modified = True
                logger.info(f"   → Renamed 'state_abbr' → 'state_code'")
            
            # CASE 4: has state_code but missing state
            if 'state_code' in df.columns and 'state' not in df.columns:
                df['state'] = df['state_code'].map(STATE_CODE_TO_NAME)
                modified = True
                logger.info(f"   → Added 'state' column from state_code")
            
            # Save if modified
            if modified:
                if not self.dry_run:
                    # Create backup
                    backup_path = file_path.with_suffix('.parquet.backup')
                    original_df.to_parquet(backup_path)
                    logger.info(f"   💾 Backup: {backup_path.name}")
                    
                    # Save migrated file
                    df.to_parquet(file_path)
                    logger.success(f"   ✓ Migrated")
                else:
                    logger.info(f"   🔍 Would migrate (dry run)")
                
                self.changes_made.append({
                    'file': str(file_path),
                    'columns_before': state_cols,
                    'columns_after': [col for col in df.columns if 'state' in col.lower()]
                })
            else:
                logger.info(f"   ✓ Already uses correct naming")
                
        except Exception as e:
            logger.error(f"   ✗ Failed to migrate {file_path}: {e}")
    
    def print_summary(self):
        """Print migration summary."""
        
        logger.info("\n" + "=" * 80)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 80)
        
        table_changes = [c for c in self.changes_made if 'table' in c]
        file_changes = [c for c in self.changes_made if 'file' in c]
        
        logger.info(f"Database tables: {len(table_changes)} migrated")
        logger.info(f"Parquet files: {len(file_changes)} migrated")
        
        if self.dry_run:
            logger.warning("\n⚠️  DRY RUN - No actual changes were made")
            logger.info("Run without --dry-run to apply changes")


def main():
    parser = argparse.ArgumentParser(description='Migrate state field naming to standard')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')
    parser.add_argument('--tables', action='store_true', help='Migrate database tables')
    parser.add_argument('--parquets', action='store_true', help='Migrate parquet files')
    parser.add_argument('--all', action='store_true', help='Migrate both tables and parquets')
    
    args = parser.parse_args()
    
    # Default to dry run if no action specified
    if not (args.tables or args.parquets or args.all):
        logger.warning("No migration target specified. Running in dry-run mode for all targets.")
        args.dry_run = True
        args.all = True
    
    migrator = StateFieldMigrator(dry_run=args.dry_run)
    
    try:
        if args.tables or args.all:
            migrator.migrate_database_tables()
        
        if args.parquets or args.all:
            migrator.migrate_parquet_files()
        
        migrator.print_summary()
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
