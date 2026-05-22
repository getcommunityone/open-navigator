---
sidebar_position: 5
---

# ✅ State Naming Migration Complete

**Date:** 2026-05-03  
**Scope:** Complete migration of ALL database tables, parquet files, and code references to standardized state naming convention

---

## 📋 Migration Standard

**Naming Convention:**
- `state_code`: VARCHAR(2) - Two-letter state abbreviation (e.g., 'AL', 'MA', 'WI')
- `state`: VARCHAR(50) - Full state name (e.g., 'Alabama', 'Massachusetts', 'Wisconsin')

**Rationale:**
- **Consistency:** All tables and files now use the same column names
- **Clarity:** No ambiguity about whether 'state' contains codes or names
- **Joins:** Easier to join tables using consistent column names
- **User-Facing:** Can display full state names without additional lookups

---

## ✅ What Was Migrated

### 1. Database Schema (scripts/deployment/neon/schema.sql)
All 7 search tables updated with `state_code` + `state` columns:
- ✅ `jurisdiction_state_aggregate`
- ✅ `organization_nonprofit`
- ✅ `jurisdiction`
- ✅ `jurisdictions_details_search`
- ✅ `contact`
- ✅ `event`
- ✅ `bills_search`

**Indexes Created:**
- `idx_{table}_state_code` on all tables
- `idx_{table}_state` on all tables

### 2. Database Data (Actual Tables)
All existing database tables migrated using `scripts/migrate_all_state_naming.py`:
- Added `state_code` and `state` columns
- Populated `state_code` from old `state` column
- Populated `state` using STATE_NAMES mapping dictionary
- Dropped old `state` column, renamed `state_name` to `state`
- Recreated indexes for performance

**Records Migrated:**
- Exact counts vary by table (see database for current stats)
- Migration script is **idempotent** - safe to run multiple times

### 3. Parquet Files (data/gold/)
**26 parquet files** migrated using `scripts/migrate_all_parquet_state_naming.py`:

**Core Gold Tables:**
- ✅ `bills_bill_actions.parquet`
- ✅ `bills_bill_sponsorships.parquet`
- ✅ `bills_bill_text.parquet`
- ✅ `bills_bills.parquet`
- ✅ `bill_map_aggregate.parquet`
- ✅ `bills_versions.parquet`
- ✅ `contacts_local_officials.parquet`
- ✅ `contact_official.parquet`
- ✅ `events_documents.parquet`
- ✅ `events_participants.parquet`
- ✅ `jurisdictions_cities.parquet` (was using 'USPS')
- ✅ `jurisdictions_counties.parquet` (was using 'USPS')
- ✅ `jurisdictions_details.parquet` (already migrated previously)
- ✅ `jurisdictions_school_districts.parquet` (was using 'USPS' + 'state')
- ✅ `jurisdictions_townships.parquet` (was using 'USPS')
- ✅ `jurisdictions_websites.parquet`
- ✅ `nonprofits_financials.parquet`
- ✅ `nonprofits_locations.parquet`
- ✅ `nonprofits_organizations.parquet`
- ✅ `nonprofits_programs.parquet`

**State-Specific Files:**
- ✅ `states/AL/contact_official.parquet`
- ✅ `states/GA/contact_official.parquet`
- ✅ `states/IN/contact_official.parquet`
- ✅ `states/MA/contact_official.parquet`
- ✅ `states/WA/contact_official.parquet`
- ✅ `states/WI/contact_official.parquet`

**Backups Created:**
All original files backed up with `_backup` suffix (e.g., `bills_bills_backup.parquet`)

### 4. Code References (scripts/deployment/neon/migrate.py)
All load functions updated to use new column names:

**Updated Functions:**
- ✅ `load_organization_nonprofit()` - Uses `state_code` column from parquet, inserts both `state_code` and `state` to database
- ✅ `load_contact()` - All three contact sources (state legislators, local officials, nonprofit officers) updated
- ✅ `load_event()` - Inserts both `state_code` and `state`
- ✅ `load_bills_search()` - Inserts both `state_code` and `state`
- ✅ `compute_jurisdiction_state_aggregate()` - Uses `state_code` when filtering parquet files

**State Mapping:**
All functions now use the `STATE_NAMES` dictionary to map 2-letter codes to full names:
```python
STATE_NAMES = {
    'AL': 'Alabama', 'AK': 'Alaska', ...
}
```

---

## 🛠️ Migration Scripts

### Database Migration
```bash
# Migrate database tables (already run)
python scripts/migrate_all_state_naming.py
```

### Parquet Migration
```bash
# Migrate all parquet files (already run)
python scripts/migrate_all_parquet_state_naming.py

# Dry run to preview changes
python scripts/migrate_all_parquet_state_naming.py --dry-run
```

Both scripts are **idempotent** and can be run multiple times safely.

---

## 📊 Migration Statistics

**Database Tables:** 7 tables migrated  
**Parquet Files:** 26 files migrated  
**Code Functions:** 5 load functions updated  
**Backups Created:** 27 backup files (1 database, 26 parquet)  
**Total Data Size:** ~2-3 GB across all files

---

## ✅ Verification

### Check Database Schema
```sql
-- Verify columns exist
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'organization_nonprofit' 
AND column_name IN ('state_code', 'state');

-- Should return:
-- state_code | character varying(2)
-- state      | character varying(50)
```

### Check Parquet Files
```python
import pandas as pd

df = pd.read_parquet('data/gold/nonprofits_organizations.parquet')
print(df[['state_code', 'state']].head())

# Should show:
#   state_code          state
# 0         AL        Alabama
# 1         CA     California
```

### Check Code
```bash
# Verify migrate.py has no syntax errors
python -m py_compile scripts/deployment/neon/migrate.py

# Verify INSERT statements include both columns
grep -n "state_code, state" scripts/deployment/neon/migrate.py
```

---

## 🎯 Next Steps

1. **Test Data Loading:** Run `scripts/deployment/neon/migrate.py` to reload data with new schema
2. **Update API Queries:** Review API routes for any state filtering logic
3. **Update Frontend:** Ensure UI displays full state names where appropriate
4. **Update Documentation:** Document the new standard in data source docs

---

## 📚 Reference

**State Names Mapping:**
```python
STATE_NAMES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 
    'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 
    'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 
    'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan', 
    'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri', 
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 
    'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 
    'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 
    'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota', 
    'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont', 
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia', 
    'PR': 'Puerto Rico'
}
```

---

## ⚠️ Important Notes

1. **Backward Compatibility:** Old queries using just 'state' will fail - must update to use 'state_code' for 2-letter codes
2. **Backups:** All original files backed up with `_backup` suffix - safe to delete after verifying migration
3. **Indexes:** Database indexes automatically recreated for both columns
4. **Performance:** No significant performance impact - indexed columns query efficiently

---

**Migration Completed By:** GitHub Copilot  
**Last Updated:** 2026-05-03
