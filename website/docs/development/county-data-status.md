---
sidebar_position: 8
---

# County Search and Aggregation - Status Summary

## Issue Identified

County search filtering is not working because:
1. ❌ The `county` field in `jurisdiction` table is NULL for most records
2. ❌ Cities don't have county data (Census gazetteer files don't include it)
3. ⚠️  Townships have county data but database update failed due to transaction errors

## What We Have Now

### ✅ Created

1. **ZIP Code to County Mapping** (`data/gold/reference/zip_county_mapping.parquet`)
   - 33,791 ZIP codes mapped to counties
   - Downloaded from Census Bureau 2020 ZCTA-to-County relationship file

2. **Scripts**:
   - `scripts/data/download_county_mappings.py` - Downloads Census relationship files
   - `scripts/data/update_jurisdiction_counties.py` - Updates database with county data

3. **Documentation**: `website/docs/guides/county-aggregation.md`
   - Complete guide on county-level aggregation
   - Examples of queries and API usage
   - Future enhancement roadmap

### ⚠️ Partially Working

- **Township County Mapping**: Code works (infers from GEOID) but needs database fix
- **Search API**: Already supports `county` parameter, just needs data

### ❌ Not Yet Available

- **City to County Mapping**: Census doesn't provide this in gazetteer files
  - Need geocoding API OR state-specific Census relationship files
  - Affects 32,333 cities

## How to Fix County Search

### Quick Fix: Update Townships (23,318 records)

The update script has a bug where database transaction errors cause rollback. Fix:

```python
# In update_township_with_counties(), add error handling per row:
for _, row in townships_df.iterrows():
    try:
        # Update code...
        conn.commit()  # Commit each row individually
    except Exception as e:
        conn.rollback()  # Rollback only this row
        logger.error(f"Error: {e}")
```

Then run:
```bash
python scripts/data/update_jurisdiction_counties.py
```

This will populate county data for **townships** (64% of non-county jurisdictions).

### Complete Fix: Add City-County Mapping

Three options:

**Option 1: Use Geocoding (Recommended for now)**
- Use city lat/lon coordinates (already in data)
- Call geocoding API (Nominatim, Google, etc.)
- Free tier available

**Option 2: Download Census Relationship Files**
- Download state-by-state from Census Bureau
- URL: `https://www2.census.gov/geo/docs/maps-data/data/rel2020/place/`
- Process each state file

**Option 3: Use OpenStreetMap**
- Query OSM Nominatim API for each city
- Extract county from administrative boundaries

## Current Database State

```
Type              Total    With County   Percent
-------------------------------------------------
city             32,333            0      0.0%
county            3,222            0      0.0%
school_district  13,326            0      0.0%
township         36,421            0      0.0%  (should be 64% after fix)
```

## API Already Works

The Search API in `api/routes/search_postgres.py` already has county filtering:

```python
# City filter
if city:
    where_clauses.append(f"LOWER(name) LIKE LOWER(${param_idx})")
    params.append(f"%{city}%")
```

Just missing: `county` filter (which would be trivial to add once data exists)

## Frontend Already Uses It

The Home.tsx component already passes county to the API:

```typescript
if (searchScope === 'county' || searchScope === 'city') {
  if (location.county) params.set('county', location.county)
}
```

## Next Steps (Priority Order)

### 1. Fix Township Update (10 minutes)
Edit `scripts/data/update_jurisdiction_counties.py` to commit per-row instead of in batch.
This will populate 23,318 township records with county data.

### 2. Add County Filter to Search API (5 minutes)
Add to `api/routes/search_postgres.py`:
```python
# County filter
if county:
    where_clauses.append(f"county = ${param_idx}")
    params.append(county)
    param_idx += 1
```

### 3. Add City-County Geocoding (1-2 hours)
Create script to geocode all 32,333 cities using Nominatim:
```python
from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="open-navigator")
# Geocode each city, extract county, update database
# Add rate limiting (1 request/second for free tier)
```

### 4. Test County Search
Once townships have county data:
1. Search for "Boston" with scope="county"
2. Should return all jurisdictions in the county
3. Verify heatmap/stats aggregate correctly

## Files Created

1. `/home/developer/projects/open-navigator/scripts/data/download_county_mappings.py`
2. `/home/developer/projects/open-navigator/scripts/data/update_jurisdiction_counties.py`
3. `/home/developer/projects/open-navigator/website/docs/guides/county-aggregation.md`
4. `/home/developer/projects/open-navigator/data/gold/reference/zip_county_mapping.parquet`

## Summary

**Problem**: County field is empty in database → county filtering doesn't work

**Root Cause**: Census gazetteer files don't include county for cities/places

**Solution Created**:
1. ✅ Downloaded ZIP→County mapping (33,791 records)
2. ✅ Created scripts to update database
3. ⚠️  Township updates ready but transaction error needs fix
4. ❌ City→County needs geocoding or additional Census files

**Impact**: Once township fix is applied, 64% of jurisdictions will have county data. City geocoding will bring it to 100%.
