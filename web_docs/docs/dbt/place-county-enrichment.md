---
sidebar_position: 9
---

# Place and County Enrichment via ZCTA

This document describes the Census Place (city/town) and County enrichments added to nonprofit organizations via ZCTA lookup.

## Overview

In addition to ZCTA centroid coordinates, we now enrich nonprofits with:
- **Place GEOID** - 7-digit Census Place identifier (city/town)
- **County FIPS** - 5-digit County GEOID

These are derived from the nonprofit's ZIP code → ZCTA mapping.

## Data Coverage

Based on analysis of 1.95M nonprofits in the IRS dataset:

| Enrichment | Coverage | Description |
|------------|----------|-------------|
| ZIP Code | 100.0% | All nonprofits have a ZIP code |
| ZCTA Match | 92.5% | ZIP matches to Census ZCTA |
| Place Match | 90.3% | ZCTA maps to a Census Place |
| County Match | 92.5% | ZCTA maps to a County |

**Why not 100%?**
- Some ZIP codes are PO Boxes (not in ZCTA)
- Foreign addresses
- Invalid/missing ZIP codes
- Very new ZIP codes

## Census Place vs City Field

**Important Distinction:**

```
org.city              → Self-reported city name from IRS/990 filing
zcta_place_name       → Official Census Place name from ZCTA
place_geoid           → Unique 7-digit identifier for the Census Place
```

**Example:**
- `org.city` = "LA" (user-entered abbreviation)
- `zcta_place_name` = "Los Angeles city" (official Census name)
- `place_geoid` = "0644000" (unique identifier)

**Why Census Places are better:**
- Standardized names (no abbreviations)
- Unique identifiers (handles duplicate city names)
- Statistical boundaries for analysis
- Consistent across Census datasets

## Place GEOID Format

**7-digit format:** `SSCCCCC`
- `SS` = State FIPS code (2 digits)
- `CCCCC` = Place code (5 digits)

**Examples:**
- `0644000` = Los Angeles city, CA (state 06, place 44000)
- `2507000` = Boston city, MA (state 25, place 07000)
- `3651000` = New York city, NY (state 36, place 51000)

## County FIPS Format

**5-digit format:** `SSCCC`
- `SS` = State FIPS code (2 digits)
- `CCC` = County code (3 digits)

**Examples:**
- `06037` = Los Angeles County, CA (state 06, county 037)
- `25025` = Suffolk County, MA (state 25, county 025)
- `36061` = New York County, NY (state 36, county 061)

## Handling Many-to-Many Relationships

**Problem:** Some ZCTAs span multiple places or counties

**Statistics:**
- 41% of ZCTAs overlap with multiple Census Places
- 30% of ZCTAs overlap with multiple Counties

**Solution:** Select PRIMARY place/county by **largest land area overlap**

```sql
-- Get primary place for each ZCTA
SELECT DISTINCT ON (zcta)
    zcta,
    place_geoid,
    place_name
FROM bronze_jurisdictions_zip_place
ORDER BY zcta, arealand_part DESC NULLS LAST
```

This ensures each nonprofit gets exactly ONE place and ONE county.

## Example Queries

### Find nonprofits in a specific city (by Place GEOID)

```sql
SELECT 
    ein,
    org_name,
    city,
    state_code,
    place_geoid,
    zcta_place_name,
    irs_revenue_amt
FROM bronze_organizations_nonprofits
WHERE place_geoid = '0644000'  -- Los Angeles city
ORDER BY irs_revenue_amt DESC NULLS LAST
LIMIT 20;
```

### Find nonprofits in a specific county

```sql
SELECT 
    ein,
    org_name,
    county_fips,
    zcta_county_name,
    irs_revenue_amt
FROM bronze_organizations_nonprofits
WHERE county_fips = '06037'  -- Los Angeles County
ORDER BY irs_revenue_amt DESC NULLS LAST
LIMIT 20;
```

### Count nonprofits by city (Top 20)

```sql
SELECT 
    place_geoid,
    zcta_place_name,
    state_code,
    COUNT(*) as nonprofit_count,
    SUM(irs_revenue_amt) as total_revenue,
    AVG(irs_revenue_amt) as avg_revenue
FROM bronze_organizations_nonprofits
WHERE place_geoid IS NOT NULL
GROUP BY place_geoid, zcta_place_name, state_code
ORDER BY nonprofit_count DESC
LIMIT 20;
```

### Count nonprofits by county

```sql
SELECT 
    county_fips,
    zcta_county_name,
    COUNT(*) as nonprofit_count,
    SUM(irs_revenue_amt) as total_revenue
FROM bronze_organizations_nonprofits
WHERE county_fips IS NOT NULL
GROUP BY county_fips, zcta_county_name
ORDER BY nonprofit_count DESC
LIMIT 20;
```

### Compare user-entered city vs Census Place

```sql
-- Find mismatches between org.city and zcta_place_name
SELECT 
    ein,
    org_name,
    city as user_city,
    zcta_place_name as census_place,
    state_code
FROM bronze_organizations_nonprofits
WHERE 
    city IS NOT NULL 
    AND zcta_place_name IS NOT NULL
    AND LOWER(city) != LOWER(REPLACE(zcta_place_name, ' city', ''))
    AND LOWER(city) != LOWER(REPLACE(zcta_place_name, ' town', ''))
    AND LOWER(city) != LOWER(REPLACE(zcta_place_name, ' CDP', ''))
LIMIT 20;
```

## Join with Census Data

### Join to Census Population Data

```sql
-- Example: Nonprofits per capita by place
SELECT 
    n.place_geoid,
    n.zcta_place_name,
    COUNT(*) as nonprofit_count,
    p.population,
    ROUND(COUNT(*)::numeric / p.population * 1000, 2) as nonprofits_per_1000_people
FROM bronze_organizations_nonprofits n
INNER JOIN census_place_population p 
    ON n.place_geoid = p.place_geoid
WHERE n.place_geoid IS NOT NULL
GROUP BY n.place_geoid, n.zcta_place_name, p.population
ORDER BY nonprofits_per_1000_people DESC
LIMIT 20;
```

### Join to County Demographics

```sql
-- Example: Nonprofits with county median income
SELECT 
    n.county_fips,
    n.zcta_county_name,
    COUNT(*) as nonprofit_count,
    SUM(n.irs_revenue_amt) as total_revenue,
    c.median_household_income,
    c.population
FROM bronze_organizations_nonprofits n
INNER JOIN census_county_demographics c
    ON n.county_fips = c.county_fips
WHERE n.county_fips IS NOT NULL
GROUP BY n.county_fips, n.zcta_county_name, 
         c.median_household_income, c.population
ORDER BY nonprofit_count DESC
LIMIT 20;
```

## Data Quality Checks

### Check Place/County match rates by state

```sql
SELECT 
    state_code,
    COUNT(*) as total_orgs,
    SUM(CASE WHEN place_geoid IS NOT NULL THEN 1 ELSE 0 END) as with_place,
    SUM(CASE WHEN county_fips IS NOT NULL THEN 1 ELSE 0 END) as with_county,
    ROUND(100.0 * SUM(CASE WHEN place_geoid IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as place_pct,
    ROUND(100.0 * SUM(CASE WHEN county_fips IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as county_pct
FROM bronze_organizations_nonprofits
GROUP BY state_code
ORDER BY total_orgs DESC
LIMIT 20;
```

### Find ZCTAs with no place match

```sql
-- Nonprofits in ZCTAs without a Census Place
SELECT 
    zcta_5,
    state_code,
    COUNT(*) as org_count,
    ARRAY_AGG(DISTINCT city ORDER BY city) as cities
FROM bronze_organizations_nonprofits
WHERE zcta_5 IS NOT NULL AND place_geoid IS NULL
GROUP BY zcta_5, state_code
ORDER BY org_count DESC
LIMIT 20;
```

## Use Cases

### Policy Analysis
- Aggregate nonprofits by city/county for policy reports
- Calculate nonprofit density by jurisdiction
- Compare nonprofit activity across similar-sized cities

### Grant Programs
- Target grant programs to specific counties
- Identify underserved Census Places
- Calculate per-capita nonprofit presence

### Geographic Studies
- Join with Census demographic data
- Analyze nonprofit distribution patterns
- Study urban vs rural nonprofit ecosystems

### Data Validation
- Verify user-entered city names
- Standardize city names to Census Places
- Detect address errors

## See Also

- [ZCTA Enrichment Guide](./zcta-enrichment.md) - Full ZCTA documentation
- [Census Place Documentation](https://www.census.gov/programs-surveys/geography/guidance/geo-areas/places.html)
- [Census FIPS Codes](https://www.census.gov/library/reference/code-lists/ansi.html)
- dbt model: [bronze_organizations_nonprofits.sql](../../dbt_project/models/marts/bronze_organizations_nonprofits.sql)
