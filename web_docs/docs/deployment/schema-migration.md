---
sidebar_position: 7
---

# Schema Migration Guide

## Overview

CommunityOne has migrated from a domain-specific oral health schema to a **generic community engagement data platform**. This enables broader civic tech applications beyond health policy.

## What Changed

### File Rename
- **Old:** `databricks/oral_health_schema.sql`
- **New:** `databricks/communityone_schema.sql`
- **Status:** Legacy file renamed to `.deprecated` suffix

### Table Renames

| Old Name | New Name | Purpose |
|----------|----------|---------|
| `fact_oral_health_observation` | `fact_communityone_observation` | Generic community outcome measurements |
| *(no oral health prefix in other tables)* | All dimensions remain the same | Geography, date, measure, etc. |

### Dimension Table Updates

#### New: `dim_jurisdiction`
Replaces inline jurisdiction data with proper dimension table:
```sql
CREATE TABLE dim_jurisdiction (
    jurisdiction_key         string NOT NULL,
    jurisdiction_id          string,  -- OCD-ID format
    jurisdiction_name        string,
    jurisdiction_type        string,  -- city, county, state, district
    geography_key            string,
    ocd_id                   string,
    website_url              string,
    population               int,
    ...
)
```

#### New: `dim_organization`
Nonprofit and foundation master dimension (IRS EO-BMF):
```sql
CREATE TABLE dim_organization (
    organization_key         string NOT NULL,
    ein                      string,
    organization_name        string,
    ntee_code                string,
    foundation_code          string,  -- 10-13=Foundation, 15=Public Charity
    is_private_foundation    boolean, -- 990-PF filers
    asset_amount             decimal(18, 2),
    income_amount            decimal(18, 2),
    ...
)
```

### New Fact Tables (Previously Missing)

#### 1. `fact_grant` - Grant Transactions
**Purpose:** Track individual grants between funders and recipients

**Data Sources:**
- IRS Form 990 Schedule I (grants paid by nonprofits)
- IRS Form 990-PF (private foundation giving)
- USASpending.gov API (federal grants)
- State grant databases

```sql
CREATE TABLE fact_grant (
    grant_key                    string NOT NULL,
    recipient_org_key            string,  -- FK to dim_organization
    recipient_jurisdiction_key   string,  -- FK to dim_jurisdiction
    funder_org_key               string,  -- FK to dim_organization
    funder_jurisdiction_key      string,  -- FK to dim_jurisdiction
    grant_amount                 decimal(18, 2),
    grant_purpose                string,
    program_area                 string,
    award_date_key               int,
    start_date_key               int,
    end_date_key                 int,
    is_multi_year                boolean,
    funding_source               string,  -- federal, state, foundation, corporate
    ...
)
```

**Example Queries:**
```sql
-- Find all federal grants to dental nonprofits in Alabama
SELECT 
    g.grant_amount,
    g.grant_purpose,
    o.organization_name,
    j.jurisdiction_name
FROM fact_grant g
JOIN dim_organization o ON g.recipient_org_key = o.organization_key
JOIN dim_jurisdiction j ON j.jurisdiction_key = g.recipient_jurisdiction_key
WHERE o.ntee_code LIKE 'E%'  -- Health services
  AND j.state_code = 'AL'
  AND g.funding_source = 'federal'
  AND g.grant_purpose LIKE '%dental%';

-- Track foundation giving patterns (990-PF data)
SELECT 
    funder.organization_name,
    COUNT(*) as grant_count,
    SUM(g.grant_amount) as total_giving,
    AVG(g.grant_amount) as avg_grant_size
FROM fact_grant g
JOIN dim_organization funder ON g.funder_org_key = funder.organization_key
WHERE funder.is_private_foundation = TRUE
GROUP BY funder.organization_name
ORDER BY total_giving DESC;
```

#### 2. `fact_nonprofit_finance` - Annual 990 Filings
**Purpose:** Detailed nonprofit financial health and revenue sources

```sql
CREATE TABLE fact_nonprofit_finance (
    filing_key                   string NOT NULL,
    organization_key             string,
    ein                          string,
    tax_year                     int,
    total_revenue                decimal(18, 2),
    total_expenses               decimal(18, 2),
    grants_paid                  decimal(18, 2),
    government_grants            decimal(18, 2),  -- Revenue source
    foundation_grants            decimal(18, 2),  -- Revenue source
    corporate_donations          decimal(18, 2),  -- Revenue source
    individual_donations         decimal(18, 2),  -- Revenue source
    program_service_revenue      decimal(18, 2),  -- Earned income
    overhead_ratio               decimal(8, 4),   -- Calculated metric
    fundraising_efficiency       decimal(8, 4),   -- Calculated metric
    ...
)
```

**Example Queries:**
```sql
-- Compare revenue sources for health vs education nonprofits
SELECT 
    SUBSTR(o.ntee_code, 1, 1) as sector,
    AVG(f.government_grants / f.total_revenue * 100) as govt_pct,
    AVG(f.foundation_grants / f.total_revenue * 100) as foundation_pct,
    AVG(f.individual_donations / f.total_revenue * 100) as individual_pct
FROM fact_nonprofit_finance f
JOIN dim_organization o ON f.organization_key = o.organization_key
WHERE o.ntee_code IN ('E', 'B')  -- Health, Education
  AND f.total_revenue > 0
GROUP BY SUBSTR(o.ntee_code, 1, 1);

-- Find most efficient nonprofits
SELECT 
    o.organization_name,
    f.total_revenue,
    f.overhead_ratio,
    f.fundraising_efficiency
FROM fact_nonprofit_finance f
JOIN dim_organization o ON f.organization_key = o.organization_key
WHERE f.tax_year = 2023
  AND f.overhead_ratio < 0.25  -- Less than 25% overhead
  AND f.fundraising_efficiency > 4.0  -- $4+ raised per $1 spent
ORDER BY f.total_revenue DESC;
```

#### 3. `fact_jurisdiction_budget` - Government Finances
**Purpose:** Track government budgets and spending priorities

```sql
CREATE TABLE fact_jurisdiction_budget (
    budget_key                   string NOT NULL,
    jurisdiction_key             string,
    fiscal_year                  int,
    total_revenue                decimal(18, 2),
    total_expenditures           decimal(18, 2),
    federal_grants               decimal(18, 2),
    state_grants                 decimal(18, 2),
    property_tax_revenue         decimal(18, 2),
    ...
)
```

#### 4. `fact_meeting` - Meetings & Public Hearings
**Purpose:** Track government transparency and public engagement

```sql
CREATE TABLE fact_meeting (
    meeting_key                  string NOT NULL,
    jurisdiction_key             string,
    meeting_date_key             int,
    meeting_type                 string,
    has_agenda                   boolean,
    has_minutes                  boolean,
    has_video                    boolean,
    topic_tags                   array<string>,
    ...
)
```

#### 5. `bridge_grant_program_area` - Grant Multi-Purpose Support
**Purpose:** Handle grants supporting multiple program areas

```sql
CREATE TABLE bridge_grant_program_area (
    grant_key                    string NOT NULL,
    program_area_code            string NOT NULL,
    program_area_desc            string,
    allocation_pct               decimal(5, 2),  -- % of grant to this area
    ...
)
```

## Migration Steps

### 1. For Databricks Users

Update your Unity Catalog schema creation scripts:

```sql
-- Old approach (DEPRECATED)
-- CREATE TABLE catalog.schema.fact_oral_health_observation ...

-- New approach
CREATE TABLE catalog.schema.fact_communityone_observation ...;
CREATE TABLE catalog.schema.fact_grant ...;
CREATE TABLE catalog.schema.fact_nonprofit_finance ...;
CREATE TABLE catalog.schema.dim_organization ...;
CREATE TABLE catalog.schema.dim_jurisdiction ...;
```

### 2. For Existing Data

If you have data in `fact_oral_health_observation`:

```sql
-- Rename table
ALTER TABLE catalog.schema.fact_oral_health_observation 
RENAME TO fact_communityone_observation;

-- Or migrate data
INSERT INTO fact_communityone_observation
SELECT 
    observation_key,
    measure_key,
    geography_key,
    NULL as jurisdiction_key,  -- NEW column
    stratification_key,
    ...
FROM fact_oral_health_observation;
```

### 3. Update Application Code

**Python/SQL queries:**
```python
# Old
df = spark.table("fact_oral_health_observation")

# New
df = spark.table("fact_communityone_observation")
```

**Documentation references:**
- Update ERD diagrams
- Update API documentation
- Update data dictionary

## New Capabilities Enabled

### 1. Grant Flow Analysis
Track money flow from funders to recipients:
```sql
SELECT 
    funder.organization_name as funder,
    recipient.organization_name as recipient,
    SUM(g.grant_amount) as total_grants,
    COUNT(*) as grant_count
FROM fact_grant g
JOIN dim_organization funder ON g.funder_org_key = funder.organization_key
JOIN dim_organization recipient ON g.recipient_org_key = recipient.organization_key
WHERE funder.is_private_foundation = TRUE
GROUP BY funder.organization_name, recipient.organization_name;
```

### 2. Nonprofit-Government Relationships
Which nonprofits receive the most government funding?
```sql
SELECT 
    o.organization_name,
    SUM(CASE WHEN g.funding_source IN ('federal', 'state') 
        THEN g.grant_amount ELSE 0 END) as govt_grants,
    COUNT(CASE WHEN g.funding_source IN ('federal', 'state') 
        THEN 1 END) as govt_grant_count
FROM dim_organization o
LEFT JOIN fact_grant g ON o.organization_key = g.recipient_org_key
GROUP BY o.organization_name
HAVING govt_grants > 0
ORDER BY govt_grants DESC;
```

### 3. Foundation Investment Patterns
990-PF Schedule I analysis:
```sql
-- Where are private foundations investing?
SELECT 
    g.program_area,
    COUNT(DISTINCT funder.organization_key) as foundation_count,
    SUM(g.grant_amount) as total_investment,
    AVG(g.grant_amount) as avg_grant_size
FROM fact_grant g
JOIN dim_organization funder ON g.funder_org_key = funder.organization_key
WHERE funder.is_private_foundation = TRUE
  AND g.program_area IS NOT NULL
GROUP BY g.program_area
ORDER BY total_investment DESC;
```

### 4. Financial Health Benchmarking
```sql
-- Compare your nonprofit to sector averages
WITH sector_avg AS (
    SELECT 
        SUBSTR(o.ntee_code, 1, 1) as sector,
        AVG(f.overhead_ratio) as avg_overhead,
        AVG(f.fundraising_efficiency) as avg_efficiency
    FROM fact_nonprofit_finance f
    JOIN dim_organization o ON f.organization_key = o.organization_key
    WHERE f.tax_year = 2023
    GROUP BY SUBSTR(o.ntee_code, 1, 1)
)
SELECT 
    o.organization_name,
    f.overhead_ratio,
    s.avg_overhead as sector_avg_overhead,
    f.fundraising_efficiency,
    s.avg_efficiency as sector_avg_efficiency
FROM fact_nonprofit_finance f
JOIN dim_organization o ON f.organization_key = o.organization_key
JOIN sector_avg s ON SUBSTR(o.ntee_code, 1, 1) = s.sector
WHERE f.tax_year = 2023
  AND o.ein = 'YOUR-EIN-HERE';
```

## Backward Compatibility

### Deprecated Fields
The following fields in `dim_measure` are renamed for generic use:

| Old Field | New Field | Notes |
|-----------|-----------|-------|
| `nohss_indicator_nbr` | `indicator_nbr` | Generic indicator number |
| `nohss_indicator_group_type` | `indicator_group_type` | Generic grouping |
| `nohss_indicator_desc` | `indicator_desc` | Generic description |

### Views for Compatibility
Create views to maintain old query compatibility:
```sql
CREATE VIEW fact_oral_health_observation AS
SELECT * FROM fact_communityone_observation
WHERE measure_key IN (
    SELECT measure_key FROM dim_measure 
    WHERE indicator_group_type = 'oral_health'
);
```

## Questions?

- **Schema issues:** See [Data Model ERD](/docs/data-sources/data-model-erd)
- **Grant data sources:** See [Nonprofit Data Sources](/docs/data-sources/nonprofit-sources)
- **990-PF parsing:** See [Form 990 XML Guide](/docs/data-sources/form-990-xml)
