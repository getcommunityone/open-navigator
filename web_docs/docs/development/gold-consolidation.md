---
sidebar_position: 6
---

# Gold Tables Consolidation

## Overview

The gold data directory has been consolidated from **86 files to 21 files** (75% reduction) to simplify HuggingFace deployment and make the codebase easier to manage.

## Changes Made

### Before (86 files)
```
data/gold/
├── national/
│   ├── bill_map_aggregate.parquet
│   ├── events.parquet
│   ├── nonprofits_financials.parquet
│   ├── nonprofits_locations.parquet
│   ├── nonprofits_organizations.parquet
│   └── nonprofits_programs.parquet
├── reference/
│   ├── causes_everyorg_causes.parquet
│   ├── causes_ntee_codes
│   ├── domains_gsa_domains.parquet
│   ├── jurisdictions_cities.parquet
│   ├── jurisdictions_counties.parquet
│   ├── jurisdictions_school_districts.parquet
│   ├── jurisdictions_townships.parquet
│   └── zip_county_mapping.parquet
└── states/
    ├── AL/  (16 files)
    ├── GA/  (16 files)
    ├── IN/  (partial)
    ├── MA/  (17 files)
    ├── WA/  (16 files)
    └── WI/  (6 files)
```

### After (21 files)
```
data/gold/
├── bills_bill_actions.parquet          (52 MB)
├── bills_bill_sponsorships.parquet     (39 MB)
├── bills_bills.parquet                 (15 MB)
├── bill_map_aggregate.parquet        (142 KB)
├── causes_everyorg_causes.parquet      (11 KB)
├── causes_ntee_codes           (11 KB)
├── contacts_local_officials.parquet    (15 KB)
├── contact_official.parquet          (461 KB)
├── domains_gsa_domains.parquet         (596 KB)
├── events_documents.parquet             (366 MB)
├── events_participants.parquet          (808 KB)
├── events.parquet                      (1.8 MB)
├── jurisdictions_cities.parquet        (2.0 MB)
├── jurisdictions_counties.parquet      (244 KB)
├── jurisdictions_school_districts.parquet (926 KB)
├── jurisdictions_townships.parquet     (2.4 MB)
├── nonprofits_financials.parquet       (77 MB)
├── nonprofits_locations.parquet        (86 MB)
├── nonprofits_organizations.parquet    (134 MB)
├── nonprofits_programs.parquet         (65 MB)
└── zip_county_mapping.parquet          (323 KB)
```

## Key Changes

### 1. State Data Consolidation

**Before:**
- Separate files per state: `data/gold/states/AL/bills_bills.parquet`, `data/gold/states/GA/bills_bills.parquet`, etc.
- Difficult to query across states
- Many small duplicate files

**After:**
- Single consolidated file: `data/gold/bills_bills.parquet`
- Contains `state` column for filtering
- Easy to query across all states

### 2. API Code Updates

**Old pattern:**
```python
for st in states:
    parquet_path = Path(f"data/gold/states/{st}/bills_bills.parquet")
    df = pd.read_parquet(parquet_path)
    # process...
```

**New pattern:**
```python
parquet_path = Path("data/gold/bills_bills.parquet")
df = pd.read_parquet(parquet_path)
if state:
    df = df[df['state'] == state]
```

**Files updated:**
- `api/main.py` - Updated opportunities endpoint to use consolidated bills
- `api/routes/stats.py` - Updated stats endpoints for nonprofits, events, contacts

### 3. File Size Compliance

All files are under HuggingFace's 500MB recommended limit:
- Largest file: `events_documents.parquet` at 366 MB
- Total data size: ~840 MB

## Benefits

1. **Simpler deployment** - Fewer files to upload to HuggingFace
2. **Better queries** - Can query across all states in single operation
3. **Easier maintenance** - One file per table type instead of 5+ copies
4. **Cleaner codebase** - Less path juggling in API code
5. **Faster reads** - Read once instead of multiple times for multi-state queries

## Scripts

### Consolidation Script
```bash
# Consolidate state-partitioned files (already done)
python scripts/data/rebuild_consolidated_gold.py

# Dry run to preview
python scripts/data/rebuild_consolidated_gold.py --dry-run
```

### Upload to HuggingFace
```bash
# Upload all consolidated files
python scripts/huggingface/upload_consolidated_gold.py

# Upload specific file
python scripts/huggingface/upload_consolidated_gold.py --file bills_bills.parquet

# Test with row limit
python scripts/huggingface/upload_consolidated_gold.py --max-rows 1000

# Skip large files
python scripts/huggingface/upload_consolidated_gold.py --skip-large
```

## Querying Consolidated Data

### Python
```python
import pandas as pd

# Load consolidated bills data
df = pd.read_parquet('data/gold/bills_bills.parquet')

# Filter by state
ma_bills = df[df['state'] == 'MA']

# Query across multiple states
southern_bills = df[df['state'].isin(['AL', 'GA'])]
```

### DuckDB
```sql
-- Query all bills
SELECT * FROM read_parquet('data/gold/bills_bills.parquet');

-- Filter by state
SELECT * FROM read_parquet('data/gold/bills_bills.parquet')
WHERE state = 'MA';

-- Aggregate across states
SELECT state, COUNT(*) as bill_count
FROM read_parquet('data/gold/bills_bills.parquet')
GROUP BY state;
```

## Backup

The original state-partitioned structure is backed up in `data/gold_old/` (not committed to git).

To restore if needed:
```bash
mv data/gold data/gold_consolidated
mv data/gold_old data/gold
```

## Migration Notes

- ✅ All files include `state` column where applicable
- ✅ National and reference tables copied as-is
- ✅ API code updated to use consolidated files
- ⚠️ Example scripts in `examples/` and `scripts/enrichment/` still reference old paths (low priority - for local dev only)
- ⚠️ Documentation files still show old paths (needs update)

## Next Steps

1. ✅ Test API endpoints with consolidated data
2. ⏳ Upload consolidated files to HuggingFace
3. ⏳ Update documentation to reflect new structure
4. ⏳ Update example scripts to use consolidated files
5. ⏳ Deploy to production and verify
