# NCES School District Jurisdiction Enrichment - Quick Reference

## Overview

Update `jurisdiction` and `jurisdictions_details_search` with NCES school district data including websites, phone numbers, district types, and school counts.

## The Problem We Solved

- **jurisdiction** had 13,326 school districts with **NULL `state_code`**
- NCES has 19,630 school districts with **websites, phones, district metadata**
- Couldn't match them without state information

## The Solution (3 Scripts)

### 1. **fix_and_enrich_school_districts.py** (RECOMMENDED - All-in-One)

```bash
# Complete workflow: Fix state codes + Match + Enrich
python scripts/datasources/nces/fix_and_enrich_school_districts.py

# Specific states only
python scripts/datasources/nces/fix_and_enrich_school_districts.py --states MA,CA,TX

# Dry run to preview changes
python scripts/datasources/nces/fix_and_enrich_school_districts.py --dry-run

# Skip state code fix (if already done)
python scripts/datasources/nces/fix_and_enrich_school_districts.py --skip-fix
```

**What it does:**
1. Fixes NULL state_code in jurisdiction (extracts from geoid FIPS code)
2. Matches NCES districts to jurisdictions by name + state
3. Updates jurisdictions_details_search with:
   - `website_url` - District website from NCES
   - `social_media->nces_metadata` - JSON with NCES ID, district type, num schools, phone, address

### 2. **update_jurisdictions_from_nces_simple.py** (Simple Version)

```bash
# Simple version - just adds websites
python scripts/datasources/nces/update_jurisdictions_from_nces_simple.py --states MA --dry-run
python scripts/datasources/nces/update_jurisdictions_from_nces_simple.py --states MA
```

**What it does:**
- Simpler logic, fewer features
- Good for understanding the concept
- Only updates website_url and basic metadata

### 3. **enrich_jurisdictions_from_nces.py** (Advanced - Not Needed Now)

Full-featured version with jurisdiction creation. Use fix_and_enrich_school_districts.py instead.

## Results

### Massachusetts Example (419 NCES districts with websites)

- ✅ **Matched: 287 (68%)** - Found in jurisdiction
- ⚠️  **Unmatched: 132 (32%)** - Mostly charter schools with different names
- ✅ **Updated: 287** - jurisdictions_details_search records enriched

### Sample Enriched Data

```sql
SELECT 
    jurisdiction_name,
    website_url,
    social_media->'nces_metadata'->>'nces_id' as nces_id,
    social_media->'nces_metadata'->>'num_schools' as schools,
    social_media->'nces_metadata'->>'phone' as phone
FROM jurisdictions_details_search
WHERE state_code = 'MA'
AND social_media ? 'nces_metadata'
LIMIT 5;
```

| jurisdiction_name | website_url | nces_id | schools | phone |
|---|---|---|---|---|
| Abington | http://www.abingtonps.org | 2501650 | 5 | (781)982-2150 |
| Acton-Boxborough | http://www.abschools.org/ | 2501710 | 9 | (978)264-4700 |
| Boston | http://bostonpublicschools.org | 2502790 | 125 | (617)635-9000 |

## Data Structure

### jurisdiction (Basic Info)

- Fixed `state_code` for all 13,326 school districts
- State codes extracted from `geoid` (first 2 digits = state FIPS code)

### jurisdictions_details_search (Enrichment)

New/updated fields:
- `website_url` - District website
- `social_media` - JSON with nces_metadata:
  ```json
  {
    "nces_metadata": {
      "nces_id": "2502790",
      "district_type": "Local School District",
      "num_schools": 125,
      "phone": "(617)635-9000",
      "school_year": "2024-25",
      "source": "nces_ccd",
      "address": {
        "street": "2300 Washington St",
        "city": "Boston",
        "zip": "02119"
      }
    }
  }
  ```

## How Matching Works

The script tries multiple strategies:

1. **Exact match**: `Abington` (jurisdictions) = `Abington` (NCES)
2. **Normalized match**: `Abington School District` = `Abington Public Schools` (removes suffixes)
3. **geoid match**: Some jurisdictions have geoid = nces_id

**Match rate varies by state:**
- MA: 68% (287/419)
- Nationwide estimate: ~70% (charter schools often don't match)

## Running for All States

```bash
# Dry run first to see stats
python scripts/datasources/nces/fix_and_enrich_school_districts.py --dry-run

# Run for real
python scripts/datasources/nces/fix_and_enrich_school_districts.py

# This will:
# - Fix 13,326 school district state codes
# - Match ~12,000-14,000 NCES districts (70% match rate)
# - Update jurisdictions_details_search with websites + metadata
```

## Verification Queries

### Check state code fix
```sql
SELECT 
    state_code, 
    COUNT(*) 
FROM jurisdiction 
WHERE type = 'school_district' 
GROUP BY state_code 
ORDER BY count DESC 
LIMIT 10;
```

### Check enrichment progress
```sql
SELECT 
    state_code,
    COUNT(*) as total_districts,
    COUNT(CASE WHEN social_media ? 'nces_metadata' THEN 1 END) as enriched
FROM jurisdictions_details_search
WHERE jurisdiction_type = 'school_district'
GROUP BY state_code
ORDER BY total_districts DESC
LIMIT 10;
```

### Find districts with websites
```sql
SELECT 
    jurisdiction_name,
    state_code,
    website_url,
    social_media->'nces_metadata'->>'num_schools' as schools
FROM jurisdictions_details_search
WHERE social_media ? 'nces_metadata'
AND state_code = 'CA'
ORDER BY (social_media->'nces_metadata'->>'num_schools')::int DESC
LIMIT 20;
```

## Troubleshooting

**Q: No matches found?**  
A: Make sure you ran the state code fix first. Check:
```sql
SELECT COUNT(*) FROM jurisdiction 
WHERE type = 'school_district' AND state_code IS NOT NULL;
```

**Q: Low match rate?**  
A: Charter schools and special districts often have different names in Census vs NCES data. 68% is normal.

**Q: Want to match the unmatched 32%?**  
A: You'd need fuzzy matching or manual mapping. For now, 70% coverage is good.

## Next Steps

1. **Run for all states** to get nationwide coverage
2. **Use enriched data** in the dashboard:
   - Show school district websites on jurisdiction pages
   - Add district phone numbers to contact info
   - Display "125 schools" in district metadata
   - Link to NCES IDs for detailed data
3. **Update frontend** to display nces_metadata in jurisdiction detail pages
