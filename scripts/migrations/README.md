# Database & Data Migrations

This directory contains migration scripts for schema changes and data transformations.

## Available Migrations

### migrate_state_naming.py

**Purpose:** Standardize state field naming across all database tables and parquet files

**What it does:**
- Renames `state` (2-char codes) → `state_code`
- Renames `state_name` (full names) → `state`
- Renames `state_abbr` → `state_code`
- Adds missing `state` (full name) columns where needed
- Populates full state names from codes using lookup table

**Usage:**
```bash
# Dry run (recommended first)
python scripts/migrations/migrate_state_naming.py --dry-run --all

# Migrate database tables only
python scripts/migrations/migrate_state_naming.py --tables

# Migrate parquet files only
python scripts/migrations/migrate_state_naming.py --parquets

# Migrate everything
python scripts/migrations/migrate_state_naming.py --all
```

**Safety:**
- Always runs in dry-run mode by default if no target specified
- Creates `.parquet.backup` files before modifying parquet files
- Shows all changes before applying them
- Can be run multiple times safely (idempotent)

**Affected Tables:**
- `jurisdiction`
- `contact`
- `event`
- `organization_nonprofit`
- `bills_search`
- `bill_map_aggregate`
- `jurisdictions_details_search`
- `zip_county_mapping`
- + 8 more tables with state columns

**Affected Files:**
- `data/gold/states/{STATE}/*.parquet` (all state-specific parquets)
- `data/gold/jurisdictions_details.parquet`

## Best Practices

### Before Running Migrations

1. **Backup your database:**
   ```bash
   pg_dump -h localhost -p 5433 -U postgres open_navigator > backup_$(date +%Y%m%d).sql
   ```

2. **Test in dry-run mode:**
   ```bash
   python scripts/migrations/migrate_state_naming.py --dry-run --all
   ```

3. **Review the changes:**
   - Check the migration plan
   - Verify table/file identification
   - Confirm backup locations

### After Running Migrations

1. **Verify the migration:**
   ```sql
   -- Check table structure
   \d+ jurisdiction
   
   -- Verify data
   SELECT state_code, state, COUNT(*) 
   FROM jurisdiction 
   GROUP BY state_code, state 
   LIMIT 10;
   ```

2. **Test parquet files:**
   ```python
   import pandas as pd
   df = pd.read_parquet('data/gold/states/AL/contact_official.parquet')
   print(df.columns.tolist())
   print(df[['state_code', 'state']].drop_duplicates())
   ```

3. **Update dependent code:**
   - Search for: `WHERE state =`
   - Update API endpoints
   - Update frontend filters
   - Update data loading scripts

## Creating New Migrations

### Template

```python
#!/usr/bin/env python3
"""
Migration: [Brief description]

Changes:
- [Change 1]
- [Change 2]

Usage:
    python scripts/migrations/migrate_xxx.py --dry-run
    python scripts/migrations/migrate_xxx.py --apply
"""
import os
import sys
from pathlib import Path
import psycopg2
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 
                         'postgresql://postgres:password@localhost:5433/open_navigator')

class XXXMigrator:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        
    def migrate(self):
        logger.info("Starting migration...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        try:
            # Migration logic here
            if not self.dry_run:
                conn.commit()
            else:
                conn.rollback()
        finally:
            cursor.close()
            conn.close()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    
    migrator = XXXMigrator(dry_run=not args.apply)
    migrator.migrate()
```

### Naming Convention

- Use descriptive names: `migrate_{what}_{when}.py`
- Include date for tracking: `migrate_state_naming_20260503.py`
- Keep migrations in order: `001_`, `002_`, etc.

## Migration History

| Date | Script | Description | Status |
|------|--------|-------------|--------|
| 2026-05-03 | `migrate_state_naming.py` | Standardize state field naming | ✅ Ready |

## Troubleshooting

### Migration failed mid-way

1. Check the error message
2. Restore from backup:
   ```bash
   psql -h localhost -p 5433 -U postgres open_navigator < backup_20260503.sql
   ```
3. Fix the issue
4. Run migration again

### Parquet file corruption

1. Backups are created as `.parquet.backup`
2. Restore:
   ```bash
   mv file.parquet file.parquet.failed
   mv file.parquet.backup file.parquet
   ```

### Dependent code breaking

1. Search for state field references:
   ```bash
   grep -r "WHERE state = " api/ scripts/ neon/
   ```

2. Update to use `state_code`:
   ```python
   # Before
   query = "SELECT * FROM jurisdictions WHERE state = 'AL'"
   
   # After
   query = "SELECT * FROM jurisdictions WHERE state_code = 'AL'"
   ```

## See Also

- [State Field Naming Standard](../../website/docs/development/state-field-naming-standard.md)
- [GitHub Copilot Instructions](../../.github/copilot-instructions.md)
- [Database Schema](../../packages/hosting/src/hosting/neon/schema.sql)
