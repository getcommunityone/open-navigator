---
sidebar_position: 5
---

# County-Level Data Aggregation

This guide explains how to aggregate Open Navigator statistics by county.

## Overview

County-level aggregation allows you to:
- Filter search results by county
- Analyze legislation impact at the county level
- Track nonprofit activity within counties
- Monitor civic engagement metrics by county

## Current Status

### Data Available

✅ **ZIP Code to County Mapping** - We have a complete mapping of ZIP codes (ZCTAs) to counties:
- File: `data/gold/reference/zip_county_mapping.parquet`
- Coverage: 33,791 ZIP codes mapped to counties
- Source: Census Bureau 2020 ZCTA-to-County relationship file

✅ **Township to County Mapping** - Townships encode their county in the GEOID:
- Coverage: 36,421 townships  
- Method: First 5 digits of township GEOID = state FIPS + county FIPS

✅ **All Counties** - Complete list of U.S. counties:
- File: `data/gold/reference/jurisdictions_counties.parquet`
- Coverage: 3,222 counties
- Includes: Population, area, coordinates

### Data Not Yet Available

⚠️ **City to County Mapping** - Cities don't include county in Census gazetteer files:
- Cities: 32,333 records
- Current county data: None
- Needed: Census place-to-county relationship files or geocoding

⚠️ **School District to County** - School districts often span multiple counties:
- School districts: 13,326 records
- Current county data: None  
- Needed: Census school district-to-county relationship files

## Using County Data

### Query by County

```sql
-- Find all jurisdictions in a county
SELECT name, type, state, county, population
FROM jurisdiction
WHERE county = 'Los Angeles County'
  AND state = 'CA';

-- Find all townships in a county
SELECT name, type, county, area_sq_miles
FROM jurisdiction
WHERE type = 'township'
  AND county = 'Cook County'
  AND state = 'IL';
```

### API Filtering

The `/api/search/` endpoint supports county filtering:

```typescript
// Search for jurisdictions in a county
const response = await api.get('/search/', {
  params: {
    q: 'city council',
    types: 'jurisdictions',
    state: 'CA',
    county: 'Los Angeles County',
    limit: 20
  }
});
```

### ZIP Code to County Lookup

```python
import pandas as pd

# Load ZIP to county mapping
zip_county = pd.read_parquet('data/gold/reference/zip_county_mapping.parquet')

# Look up county for a ZIP code
zip_code = '90210'
county = zip_county[zip_county['zcta'] == zip_code]['county_name'].values[0]
print(f"ZIP {zip_code} is in {county}")
# Output: ZIP 90210 is in Los Angeles County
```

### County Statistics

```sql
-- Count jurisdictions per county
SELECT county, state, COUNT(*) as jurisdiction_count
FROM jurisdiction
WHERE county IS NOT NULL
GROUP BY county, state
ORDER BY jurisdiction_count DESC
LIMIT 20;

-- Aggregate nonprofits by county (when county data is available)
-- This requires joining with nonprofit location data
SELECT 
  z.county_name,
  z.state_fips,
  COUNT(DISTINCT n.ein) as nonprofit_count,
  SUM(n.revenue) as total_revenue
FROM organization_nonprofit n
JOIN zip_county_mapping z ON n.zip_code = z.zcta
GROUP BY z.county_name, z.state_fips
ORDER BY nonprofit_count DESC;
```

## Adding County Data to Cities

To add county information for cities, you have several options:

### Option 1: Geocoding API

Use a geocoding service to look up county from city coordinates:

```python
import pandas as pd
from geopy.geocoders import Nominatim

cities_df = pd.read_parquet('data/gold/reference/jurisdictions_cities.parquet')

geolocator = Nominatim(user_agent="open-navigator")

for _, row in cities_df.iterrows():
    lat = row['INTPTLAT']
    lon = row['INTPTLONG']
    
    location = geolocator.reverse(f"{lat}, {lon}")
    county = location.raw['address'].get('county', '')
    
    # Update database with county
```

### Option 2: Census Relationship Files

Download state-specific place-to-county crosswalk files:

1. Visit: https://www2.census.gov/geo/docs/maps-data/data/rel2020/place/
2. Download state files (e.g., `tab20_place20_county20_01.txt` for Alabama)
3. Process each state file to extract place-to-county mappings

### Option 3: OpenStreetMap

Use OpenStreetMap data which includes county (administrative level) information:

```python
from OSMPythonTools.nominatim import Nominatim
nominatim = Nominatim()

result = nominatim.query('Los Angeles, CA', params={'addressdetails': 1})
county = result.toJSON()[0]['address']['county']
```

## County-Based Aggregation Examples

### Legislative Activity by County

```python
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine('postgresql://postgres:password@localhost:5433/open_navigator')

# Aggregate bills by county (requires joining with sponsor locations)
query = """
SELECT 
    s.county,
    s.state,
    COUNT(DISTINCT b.id) as bill_count,
    COUNT(DISTINCT CASE WHEN b.classification = 'bill' THEN b.id END) as regular_bills,
    COUNT(DISTINCT CASE WHEN b.classification = 'resolution' THEN b.id END) as resolutions
FROM bills b
JOIN sponsors sp ON b.id = sp.bill_id
JOIN legislators l ON sp.person_id = l.id
JOIN jurisdiction s ON l.district_id = s.geoid
WHERE s.county IS NOT NULL
GROUP BY s.county, s.state
ORDER BY bill_count DESC
LIMIT 20;
"""

df = pd.read_sql(query, engine)
print(df)
```

### Nonprofit Density by County

```python
# Requires ZIP code to county mapping
query = """
SELECT 
    z.county_name,
    COUNT(DISTINCT n.ein) as nonprofit_count,
    ROUND(COUNT(DISTINCT n.ein)::numeric / c.population * 100000, 2) as nonprofits_per_100k
FROM organization_nonprofit n
JOIN zip_county_mapping z ON n.zip_code = z.zcta
JOIN (
    SELECT county, state, SUM(population) as population
    FROM jurisdiction
    WHERE type = 'county'
    GROUP BY county, state
) c ON z.county_name = c.county
GROUP BY z.county_name, c.population
HAVING c.population > 100000
ORDER BY nonprofits_per_100k DESC
LIMIT 20;
"""
```

## Future Enhancements

1. **Automated Geocoding**: Add a pipeline to geocode all cities and assign counties
2. **County Profiles**: Create dedicated county profile pages showing:
   - All jurisdictions within the county
   - Legislative activity
   - Nonprofit statistics
   - Meeting calendar
3. **County Comparison Tool**: Side-by-side comparison of county metrics
4. **County-Level Maps**: Interactive maps showing county-level heatmaps

## Data Files

All county-related mapping files are stored in `data/gold/reference/`:

| File | Description | Records |
|------|-------------|---------|
| `jurisdictions_counties.parquet` | All U.S. counties | 3,222 |
| `zip_county_mapping.parquet` | ZIP/ZCTA to county | 33,791 |
| `jurisdictions_cities.parquet` | All cities (no county yet) | 32,333 |
| `jurisdictions_townships.parquet` | Townships (county in GEOID) | 36,421 |
| `jurisdictions_school_districts.parquet` | School districts | 13,326 |

## Scripts

### Download County Mappings

```bash
# Download Census relationship files and create mappings
python scripts/data/download_county_mappings.py
```

This script:
- Downloads ZCTA-to-county relationship file from Census Bureau
- Processes it into a clean parquet file
- Shows instructions for additional manual downloads

### Update Database

```bash
# Update jurisdiction table with county data
python scripts/data/update_jurisdiction_counties.py
```

This script:
- Updates townships with county information (from GEOID)
- Reports on coverage statistics
- Identifies gaps in county data

## Troubleshooting

### County Field is NULL

If the `county` field is NULL for jurisdictions:

1. **Check if data exists**: 
   ```sql
   SELECT type, COUNT(*), COUNT(county) 
   FROM jurisdiction 
   GROUP BY type;
   ```

2. **Run the update script**:
   ```bash
   python scripts/data/update_jurisdiction_counties.py
   ```

3. **For cities**: County data requires additional Census files or geocoding

### ZIP Code Not Found

If a ZIP code isn't in the mapping:

1. Check if it's a valid ZIP: Some ZIP codes are for PO boxes or specific buildings
2. Use the ZCTA (ZIP Code Tabulation Area) instead - it's the Census approximation
3. Fall back to city/state lookup

### Search Filtering Not Working

If county filtering isn't working in the search API:

1. Verify the API endpoint supports the `county` parameter
2. Check that the county name is exact (include "County" suffix)
3. Use URL encoding for county names with spaces

## Related Documentation

- [Data Sources](../data-sources/census-data.md) - Census Bureau data sources
- [Search API](./unified-search.md) - Search API documentation  
- [Database Schema](../data-sources/data-model-erd.md) - Database structure
