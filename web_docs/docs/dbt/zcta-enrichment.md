---
sidebar_position: 7
---

# ZCTA Enrichment for Nonprofits

This guide explains how to use the ZCTA (ZIP Code Tabulation Area) enrichment in the nonprofit data models.

## What is ZCTA?

**ZCTA (ZIP Code Tabulation Area)** is a Census Bureau geographic area that approximates USPS ZIP code boundaries:

- **ZIP codes** = postal delivery routes (can change frequently)
- **ZCTAs** = stable census geographic boundaries (updated every 10 years)

ZCTAs provide:
- Statistical boundaries for geographic analysis
- Centroid coordinates (latitude/longitude)
- Land and water area measurements
- Consistent geography for data aggregation

**Coverage:** ~33,791 ZCTAs cover the United States

## Data Sources

### Bronze Tables

1. **bronze_organizations_nonprofits_irs** (1.95M nonprofits)
   - Source: IRS Business Master File (BMF)
   - ZIP field: `zip_code` (may include ZIP+4)

2. **bronze_organizations_nonprofits_nccs** (1.8M nonprofits)
   - Source: NCCS Core Files
   - ZIP field: `f990_org_addr_zip` (may include ZIP+4)

3. **bronze_jurisdictions_postal_codes** (33,791 ZCTAs)
   - Source: Census Bureau Gazetteer Files
   - Loading script: `scripts/datasources/census/load_census_postal_codes.py`

4. **bronze_jurisdictions_zip_place** (~29,000 ZCTA-place relationships)
   - Source: Census 2020 ZCTA-Place Relationship File
   - Maps ZCTAs to Census Places (cities/towns)
   - Many-to-many: 41% of ZCTAs span multiple places

5. **bronze_jurisdictions_zip_county** (~33,800 ZCTA-county relationships)
   - Source: Census 2020 ZCTA-County Relationship File
   - Maps ZCTAs to Counties
   - Many-to-many: 30% of ZCTAs span multiple counties

## dbt Models with ZCTA

### Recommended: bronze_organizations_nonprofits (Marts)

**Location:** `dbt_project/models/marts/bronze_organizations_nonprofits.sql`

This model combines IRS + NCCS + ZCTA data in a single table:

```sql
-- Run the model
dbt run --select bronze_organizations_nonprofits
```

**ZCTA Columns Added:**

| Column | Type | Description |
|--------|------|-------------|
| `zcta_5` | VARCHAR(5) | 5-digit ZCTA code |
| `zcta_latitude` | NUMERIC | ZCTA centroid latitude |
| `zcta_longitude` | NUMERIC | ZCTA centroid longitude |
| `zcta_land_area_sqmi` | NUMERIC | Land area in square miles |
| `zcta_water_area_sqmi` | NUMERIC | Water area in square miles |
| `place_geoid` | VARCHAR(7) | Census Place GEOID (7-digit) |
| `zcta_place_name` | VARCHAR | Place name (city/town) |
| `county_fips` | VARCHAR(5) | County GEOID/FIPS (5-digit) |
| `zcta_county_name` | VARCHAR | County name |
| `best_latitude` | NUMERIC | Best available lat (NCCS geocoded > ZCTA) |
| `best_longitude` | NUMERIC | Best available lon (NCCS geocoded > ZCTA) |
| `has_zcta_match` | BOOLEAN | True if ZIP matched to ZCTA (~95%) |

**Important Notes:**

- **Many-to-Many Relationships:** Some ZCTAs span multiple places (41%) or counties (30%)
- **Primary Selection:** We select the place/county with the largest land area overlap
- **Place GEOID:** 7-digit Census Place identifier (state FIPS + place code)
- **County FIPS:** 5-digit County GEOID (state FIPS + county code)

**Coordinate Priority:**
1. **NCCS geocoded coordinates** (if available) - most accurate, address-level
2. **IRS ZCTA centroid** - from IRS zip_code
3. **NCCS ZCTA centroid** - from NCCS f990_org_addr_zip

### Alternative: Intermediate Models (Disabled by Default)

**Files:**
- `int_nonprofits_irs_with_zcta.sql` - IRS only with ZCTA
- `int_nonprofits_nccs_with_zcta.sql` - NCCS only with ZCTA

⚠️ **These are disabled by default** due to PostgreSQL cross-database limitations.

To enable for bronze-only usage:
1. Set `enabled=true` in the model config
2. Run with bronze target: `dbt run --target bronze --select int_nonprofits_irs_with_zcta`

## ZCTA Join Logic

The models extract 5-digit ZIP codes and join to ZCTA lookup tables:

```sql
-- Step 1: Normalize ZIP+4 to ZIP5
LEFT(TRIM(zip_code), 5) AS zip_code_5

-- Step 2: Join to ZCTA centroid and area
LEFT JOIN bronze_jurisdictions_postal_codes
    ON zip_code_5 = zcta

-- Step 3: Join to primary place (largest by land area)
LEFT JOIN (
    SELECT DISTINCT ON (zcta) zcta, place_geoid, place_name
    FROM bronze_jurisdictions_zip_place
    ORDER BY zcta, arealand_part DESC
) AS zcta_place_primary
    ON zip_code_5 = zcta_place_primary.zcta

-- Step 4: Join to primary county (largest by land area)
LEFT JOIN (
    SELECT DISTINCT ON (zcta) zcta, county_geoid, county_name
    FROM bronze_jurisdictions_zip_county
    ORDER BY zcta, arealand_part DESC
) AS zcta_county_primary
    ON zip_code_5 = zcta_county_primary.zcta
```

**Match Rate:** ~95% of nonprofits have valid ZCTA matches

**Why 5% don't match:**
- PO Box addresses (not in ZCTA)
- Invalid/missing ZIP codes
- Foreign addresses
- Very new ZIP codes not yet in Census ZCTA

## Example Queries

### Find nonprofits in a specific place or county

```sql
-- By Place GEOID
SELECT 
    ein,
    org_name,
    city,
    state_code,
    place_geoid,
    zcta_place_name,
    irs_revenue_amt
FROM bronze_organizations_nonprofits
WHERE place_geoid = '2507000'  -- Boston, MA
ORDER BY irs_revenue_amt DESC NULLS LAST
LIMIT 10;
place or county

```sql
-- By Place
SELECT 
    place_geoid,
    zcta_place_name,
    COUNT(*) as nonprofit_count,
    AVG(irs_revenue_amt) as avg_revenue
FROM bronze_organizations_nonprofits
WHERE place_geoid IS NOT NULL
GROUP BY place_geoid, zcta_place_name
ORDER BY nonprofit_count DESC
LIMIT 20;

-- By County
SELECT 
    county_fips,
    zcta_county_name,
    COUNT(*) as nonprofit_count,
    SUM(irs_revenue_amt) as total_revenue
FROM bronze_organizations_nonprofits
WHERE county_fips IS NOT NULL
GROUP BY county_fips, zcta_county_nameps = '25025'  -- Suffolk County, MA
ORDER BY irs_revenue_amt DESC NULLS LAST
LIMIT 10;
```

### Count nonprofits by ZCTA

```sql
SELECT 
    zcta_5,
    COUNT(*) as nonprofit_count,
    AVG(irs_revenue_amt) as avg_revenue
FROM bronze_organizations_nonprofits
WHERE has_zcta_match = true
GROUP BY zcta_5
ORDER BY nonprofit_count DESC
LIMIT 20;
```

### Find nonprofits near a point using ZCTA centroids

```sql
-- Nonprofits within ~10 miles of a location (approximate)
SELECT 
    ein,
    org_name,
    zcta_5,
    zcta_latitude,
    zcta_longitude,
    -- Haversine distance approximation
    3959 * acos(
        cos(radians(42.3736)) * cos(radians(zcta_latitude)) * 
        cos(radians(zcta_longitude) - radians(-71.1097)) + 
        sin(radians(42.3736)) * sin(radians(zcta_latitude))
    ) as distance_miles
FROM bronze_organizations_nonprofits
WHERE has_zcta_match = true
HAVING distance_miles < 10
ORDER BY distance_miles
LIMIT 50;
```

### Geographic coverage analysis

```sql
SELECT 
    state_code,
    COUNT(*) as total_nonprofits,
    SUM(CASE WHEN has_zcta_match THEN 1 ELSE 0 END) as with_zcta,
    ROUND(100.0 * SUM(CASE WHEN has_zcta_match THEN 1 ELSE 0 END) / COUNT(*), 2) as match_rate_pct
FROM bronze_organizations_nonprofits
GROUP BY state_code
ORDER BY total_nonprofits DESC;
```

## Data Quality Flags

| Flag | Description |
|------|-------------|
| `has_nccs_data` | Organization exists in NCCS dataset |
| `has_geocoding` | Has precise lat/lon from NCCS address geocoding |
| `has_zcta_match` | ZIP code matched to a Census ZCTA |

**Best coordinates strategy:**
- If `has_geocoding = true`: Use `latitude`/`longitude` (most accurate)
- Else: Use `best_latitude`/`best_longitude` (ZCTA centroid fallback)

## Loading ZCTA Data

If the bronze_jurisdictions_postal_codes table is empty, run:

```bash
cd /home/developer/projects/open-navigator
source .venv/bin/activate
python scripts/datasources/census/load_census_postal_codes.py
```

This downloads the latest Census Gazetteer ZCTA file (~33,791 records).

### ⚠️ Known Issue: Missing Longitude Data

**Current Status (as of last check):**
- ✅ Latitude (`intptlat`) is populated correctly
- ❌ Longitude (`intptlong`) is **NULL** for all records

This is a data loading issue in the `load_census_postal_codes.py` script. The dbt models are correct and will work properly once the source data is fixed.

**To verify ZCTA data quality:**

```sql
-- Check for NULL longitude values
SELECT 
    COUNT(*) as total_zctas,
    SUM(CASE WHEN intptlong IS NULL THEN 1 ELSE 0 END) as missing_longitude,
    SUM(CASE WHEN intptlat IS NULL THEN 1 ELSE 0 END) as missing_latitude
FROM bronze_jurisdictions_postal_codes;
```

**Expected result:**
- All ZCTAs should have both latitude AND longitude
- If longitude is NULL, the Census data file may need to be reloaded with corrected column mapping

## Troubleshooting

### ZCTA Match Rate Lower Than Expected

If less than 90% of nonprofits match to ZCTAs:

1. **Check if ZCTA table is loaded:**
   ```sql
   SELECT COUNT(*) FROM bronze_jurisdictions_postal_codes;
   ```
   Expected: ~33,791 records

2. **Check for NULL coordinates:**
   ```sql
   SELECT 
       COUNT(*) FILTER (WHERE intptlat IS NULL) as null_lat,
       COUNT(*) FILTER (WHERE intptlong IS NULL) as null_lon
   FROM bronze_jurisdictions_postal_codes;
   ```
   Expected: 0 NULL values for both

3. **Check ZIP code format in nonprofits:**
   ```sql
   -- Sample ZIP codes that don't match
   SELECT DISTINCT 
       LEFT(TRIM(zip_code), 5) as zip_5,
       COUNT(*) as org_count
   FROM bronze_organizations_nonprofits_irs
   WHERE LEFT(TRIM(zip_code), 5) NOT IN (
       SELECT zcta FROM bronze_jurisdictions_postal_codes
   )
   GROUP BY LEFT(TRIM(zip_code), 5)
   ORDER BY org_count DESC
   LIMIT 10;
   ```

### Fixing Missing Longitude Data

If longitude is missing, check the `load_census_postal_codes.py` script:

1. Verify the Census Gazetteer file format
2. Check the column mapping in the Pandas DataFrame
3. Ensure `INTPTLONG` column is correctly mapped to `intptlong`
4. Re-run the loading script with corrected mapping

## See Also

- [Census ZCTA Documentation](https://www.census.gov/programs-surveys/geography/guidance/geo-areas/zctas.html)
- [Census Gazetteer Files](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html)
- dbt model: [organizations_nonprofits.sql](https://github.com/getcommunityone/open-navigator/blob/main/dbt_project/models/marts/organizations_nonprofits.sql)
- Loading script: [census/postal_codes.py](https://github.com/getcommunityone/open-navigator/blob/main/packages/ingestion/src/ingestion/census/postal_codes.py)
