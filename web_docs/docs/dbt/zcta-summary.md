---
sidebar_position: 8
---

# ZCTA Enrichment Summary

## ✅ What Was Created

Created dbt models to add 5-digit ZCTA (ZIP Code Tabulation Area) to nonprofit organizations:

### 1. Main Model: bronze_organizations_nonprofits

**Location:** `dbt_project/models/marts/bronze_organizations_nonprofits.sql`

**What it does:**
- Combines IRS + NCCS + ZCTA + Place + County data in one table
- Adds `zcta_5`, `zcta_latitude`, `zcta_longitude` columns
- Adds `place_geoid`, `zcta_place_name` columns (Census Place/city)
- Adds `county_fips`, `zcta_county_name` columns (County GEOID)
- Provides `best_latitude`/`best_longitude` (prioritizes NCCS geocoded > ZCTA centroid)
- Adds `has_zcta_match` flag

**Run it:**
```bash
cd dbt_project
source ../.venv/bin/activate
dbt run --select bronze_organizations_nonprofits
```

### 2. Supporting Models (Disabled by Default)

- `int_nonprofits_irs_with_zcta.sql` - IRS only with ZCTA
- `int_nonprofits_nccs_with_zcta.sql` - NCCS only with ZCTA

These are disabled due to PostgreSQL cross-database limitations. Use the marts model instead.

### 3. Documentation

**Location:** `website/docs/dbt/zcta-enrichment.md`

Includes:
- ZCTA explanation and use cases
- Column definitions
- Example queries
- Troubleshooting guide
- Data quality checks

## 🎯 How It Works

### ZCTA Join Logic

```sql
-- 1. Extract 5-digit ZIP from nonprofit address
LEFT(TRIM(zip_code), 5) AS zip_code_5

-- 2. Join to Census ZCTA lookup table
LEFT JOIN bronze_jurisdictions_postal_codes 
    ON zip_code_5 = zcta

-- 3. Join to primary place (largest by land area)
LEFT JOIN (
    SELECT DISTINCT ON (zcta) zcta, place_geoid, place_name
    FROM bronze_jurisdictions_zip_place
    ORDER BY zcta, arealand_part DESC
) AS zcta_place_primary ON zip_code_5 = zcta

-- 4. Join to primary county (largest by land area)
LEFT JOIN (
    SELECT DISTINCT ON (zcta) zcta, county_geoid, county_name
    FROM bronze_jurisdictions_zip_county
    ORDER BY zcta, arealand_part DESC
) AS zcta_county_primary ON zip_code_5 = zcta

-- 5. Add ZCTA columns + place + county
COALESCE(irs_zcta.zcta, nccs_zcta.zcta) as zcta_5,
COALESCE(irs_place.place_geoid, nccs_place.place_geoid) as place_geoid,
COALESCE(irs_county.county_geoid, nccs_county.county_geoid) as county_fips
```

### Coordinate Priority

Best available coordinates for each nonprofit:
1. **NCCS geocoded** (most accurate) - from address geocoding
2. **IRS ZCTA centroid** - from IRS zip_code
3. **NCCS ZCTA centroid** - from NCCS f990_org_addr_zip

## 📊 Data Sources

| Table | Records | Purpose |
|-------|---------|---------|
| `bronze_organizations_nonprofits_irs` | 1.95M | IRS Business Master File |
| `bronze_organizations_nonprofits_nccs` | 1.8M | NCCS Core Files |
| `bronze_jurisdictions_postal_codes` | 33,791 | Census ZCTA lookup |
| `bronze_jurisdictions_zip_place` | ~29,000 | ZCTA → Place mapping |
| `bronze_jurisdictions_zip_county` | ~33,800 | ZCTA → County mapping |

**Expected ZCTA match rate:** ~95% of nonprofits

**Many-to-Many:** 41% of ZCTAs span multiple places, 30% span multiple counties
- **Solution:** We select the place/county with the largest land area overlap

## ⚠️ Known Issues

### Missing Longitude Data

The `bronze_jurisdictions_postal_codes` table currently has **NULL longitude values** for all ZCTAs.

**Impact:**
- ZCTA latitude works correctly ✅
- ZCTA longitude is NULL ❌
- Geographic queries using ZCTA coordinates won't work until fixed

**Fix:**
- Check `scripts/datasources/census/load_census_postal_codes.py`
- Verify Census Gazetteer column mapping includes `INTPTLONG`
- Re-run the loading script

## 🔍 Quick Verification

```sql
-- Test ZCTA + Place + County enrichment
SELECT 
    ein,
    LEFT(name, 40) as org_name,
    city,
    state_code,
    zip_code,
    zcta_5,
    place_geoid,
    zcta_place_name,
    county_fips,
    zcta_county_name,
    has_zcta_match
FROM bronze_organizations_nonprofits
WHERE state_code = 'CA'
LIMIT 10;
```

## 📁 Files Modified/Created

### dbt Models
- ✅ `dbt_project/models/marts/bronze_organizations_nonprofits.sql` - Updated with ZCTA joins
- ✅ `dbt_project/models/intermediate/int_nonprofits_irs_with_zcta.sql` - Created (disabled)
- ✅ `dbt_project/models/intermediate/int_nonprofits_nccs_with_zcta.sql` - Created (disabled)
- ✅ `dbt_project/models/intermediate/_intermediate.yml` - Updated with ZCTA model definitions
- ✅ `dbt_project/models/staging/_staging.yml` - Added bronze_jurisdictions_postal_codes source

### Documentation
- ✅ `website/docs/dbt/zcta-enrichment.md` - Complete ZCTA guide
- ✅ `website/docs/dbt/zcta-summary.md` - This summary (quick reference)

## 🚀 Next Steps

1. **Fix longitude data** in bronze_jurisdictions_postal_codes table
2. **Run the dbt model** to create the enriched nonprofits table
3. **Test ZCTA queries** with sample data
4. **Update downstream models** (silver, gold) to use ZCTA data if needed

## 💡 Use Cases

**Geographic Analysis:**
- Count nonprofits by ZCTA/place/county
- Find organizations near a location
- Map nonprofit density by ZIP area
- Aggregate by Census Place (city/town)
- Roll up statistics by county

**Data Quality:**
- Validate addresses with ZCTA centroids
- Fill missing coordinates with ZCTA fallback
- Identify invalid ZIP codes (no ZCTA match)
- Cross-reference city names with Census Places

**Spatial Joins:**
- Join with Census demographic data by ZCTA/Place/County
- Connect with other geographic datasets
- Aggregate metrics by postal area
- Link to county-level government data

## See Also

- Full documentation: [ZCTA Enrichment Guide](./zcta-enrichment.md)
- Census ZCTA docs: https://www.census.gov/programs-surveys/geography/guidance/geo-areas/zctas.html
- Loading script: `scripts/datasources/census/load_census_postal_codes.py`
