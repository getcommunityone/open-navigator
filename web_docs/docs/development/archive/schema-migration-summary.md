---
sidebar_position: 5
---

# Schema Migration Summary

**Date:** April 28, 2026  
**Migration:** Oral Health → Generic CommunityOne Platform

## ✅ Completed Changes

### 1. New Comprehensive Schema Created
**File:** `databricks/communityone_schema.sql` (641 lines)

**Previous:** `databricks/oral_health_schema.sql.deprecated` (285 lines - 125% expansion)

### 2. Core Renamings

| Component | Old Name | New Name |
|-----------|----------|----------|
| Schema file | `oral_health_schema.sql` | `communityone_schema.sql` |
| Primary fact table | `fact_oral_health_observation` | `fact_communityone_observation` |
| Project scope | Oral health-specific | Generic civic engagement |
| Measure fields | `nohss_indicator_*` | `indicator_*` (generic) |

### 3. New Dimension Tables Added ✨

Previously missing, now implemented:

#### `dim_jurisdiction` 
Government jurisdictions (cities, counties, states, districts)
- 🔑 Primary Key: `jurisdiction_key`
- 📍 Links to: `dim_geography`
- 🌐 Supports: OCD-ID format for Open Civic Data compliance

#### `dim_organization`
Nonprofits, churches, private foundations (IRS EO-BMF)
- 🔑 Primary Key: `organization_key`
- 💰 Fields: EIN, NTEE code, foundation_code, asset/income amounts
- 🏦 Flags: `is_private_foundation` for 990-PF filers
- 📍 Links to: `dim_geography`

### 4. New Fact Tables Added ✨

Previously missing from schema but documented in ERD - **NOW IMPLEMENTED:**

#### `fact_grant` 
**Individual grant transactions** - The missing piece!
- 💵 Tracks grants between funders and recipients
- 🔗 Links organizations via `dim_organization`
- 🏛️ Links jurisdictions via `dim_jurisdiction`
- 📊 Sources: 990 Schedule I, 990-PF, USASpending.gov
- 🔑 Fields: grant_amount, grant_purpose, program_area, dates, restrictions

**Example Use Cases:**
- Foundation giving patterns (990-PF analysis)
- Government grants to nonprofits
- Federal funding flows (USASpending.gov)
- Multi-year grant tracking

#### `fact_nonprofit_finance`
**Annual Form 990 financials**
- 📈 Revenue breakdown (10 sources: govt grants, foundation grants, donations, earned income)
- 📊 Calculated metrics: overhead_ratio, fundraising_efficiency
- 🔗 Links to: `dim_organization`, `dim_date`
- 🎯 Enables: Financial health benchmarking, sector comparisons

#### `fact_jurisdiction_budget`
**Government budgets and spending**
- 💰 Revenue and expenditure tracking
- 📊 Federal/state grants received by governments
- 🔗 Links to: `dim_jurisdiction`, `dim_date`
- 🎯 Enables: Budget trend analysis, fiscal health monitoring

#### `fact_meeting`
**Government meetings and public hearings**
- 📅 Meeting metadata (date, type, body, status)
- 📄 Flags: has_agenda, has_minutes, has_video
- 🏷️ Topic tags (array field)
- 🔗 Links to: `dim_jurisdiction`, `dim_date`

### 5. New Bridge Table Added ✨

#### `bridge_grant_program_area`
**Multi-purpose grant support**
- Handles grants supporting multiple program areas
- Tracks allocation percentages per program area
- Enables accurate program area aggregations

### 6. Updated Relationships

**Total Foreign Keys:** 30+ constraints added

**Key Relationship Patterns:**
```
ORGANIZATION ──grants→ ORGANIZATION  (foundation → nonprofit)
ORGANIZATION ──grants→ JURISDICTION  (nonprofit → government)
JURISDICTION ──grants→ ORGANIZATION  (government → nonprofit)
JURISDICTION ──budget→ BUDGET        (fiscal tracking)
JURISDICTION ──meetings→ MEETING     (transparency)
ORGANIZATION ──finances→ FINANCE     (annual 990s)
```

### 7. Documentation Updates

**New Files:**
- ✅ `databricks/communityone_schema.sql` - Complete schema (641 lines)
- ✅ `website/docs/deployment/schema-migration.md` - Migration guide
- ✅ `databricks/README.md` - Updated with schema documentation

**Updated References:**
- ✅ Databricks README now explains schema differences
- ✅ Migration guide provides SQL examples
- ✅ Deprecated old schema file with `.deprecated` suffix

## Schema Comparison

### Before (oral_health_schema.sql)
```
Dimension Tables: 9
  ├── dim_data_source
  ├── dim_date
  ├── dim_geography
  ├── dim_measure
  ├── dim_postal
  ├── dim_state
  ├── dim_statistic_type
  ├── dim_stratification
  └── dim_survey_period

Fact Tables: 1
  └── fact_oral_health_observation

Bridge Tables: 0

Total Tables: 10
Total Lines: 285
Foreign Keys: 9
```

### After (communityone_schema.sql)
```
Dimension Tables: 11 (+2)
  ├── dim_data_source
  ├── dim_date
  ├── dim_geography
  ├── dim_jurisdiction          ✨ NEW
  ├── dim_organization          ✨ NEW
  ├── dim_measure
  ├── dim_postal
  ├── dim_state
  ├── dim_statistic_type
  ├── dim_stratification
  └── dim_survey_period

Fact Tables: 5 (+4)
  ├── fact_communityone_observation (renamed)
  ├── fact_grant                ✨ NEW
  ├── fact_nonprofit_finance    ✨ NEW
  ├── fact_jurisdiction_budget  ✨ NEW
  └── fact_meeting              ✨ NEW

Bridge Tables: 1 (+1)
  └── bridge_grant_program_area ✨ NEW

Total Tables: 17 (+70%)
Total Lines: 641 (+125%)
Foreign Keys: 30+ (+233%)
```

## Data Model Alignment Status

### ✅ Previously Documented, NOW IMPLEMENTED:

**From data-model-erd.md Line 894:**
```mermaid
ORGANIZATION ||--o{ GRANT : receives
JURISDICTION ||--o{ GRANT : awards
```
**Status:** ✅ **FIXED** - `fact_grant` table created with foreign keys

**From data-model-erd.md Lines 87-90:**
```
├── grants/
│   ├── nonprofit_grants   # Grants to nonprofits (from 990 Schedule I)
│   ├── government_grants  # Government grants to orgs/jurisdictions
│   ├── foundation_grants  # Private foundation grants
│   └── federal_grants     # Federal funding programs
```
**Status:** ✅ **FIXED** - `fact_grant` supports all grant types via `funding_source` field

**From data-model-erd.md Lines 871-872:**
```
float government_grants
float foundation_grants
```
**Status:** ✅ **FIXED** - `fact_nonprofit_finance` tracks revenue sources

## Query Examples Enabled

### 1. Foundation Giving Patterns (990-PF)
```sql
SELECT 
    funder.organization_name,
    COUNT(*) as grants_made,
    SUM(g.grant_amount) as total_giving
FROM fact_grant g
JOIN dim_organization funder ON g.funder_org_key = funder.organization_key
WHERE funder.is_private_foundation = TRUE
GROUP BY funder.organization_name;
```

### 2. Nonprofit Financial Health
```sql
SELECT 
    o.organization_name,
    f.total_revenue,
    f.overhead_ratio,
    f.government_grants / f.total_revenue as govt_dependency_pct
FROM fact_nonprofit_finance f
JOIN dim_organization o ON f.organization_key = o.organization_key
WHERE f.tax_year = 2023
ORDER BY f.total_revenue DESC;
```

### 3. Grant Flow Analysis
```sql
SELECT 
    funder.organization_name as funder,
    recipient.organization_name as recipient,
    g.grant_amount,
    g.program_area
FROM fact_grant g
JOIN dim_organization funder ON g.funder_org_key = funder.organization_key
JOIN dim_organization recipient ON g.recipient_org_key = recipient.organization_key
WHERE g.program_area LIKE '%health%';
```

## Migration Required?

### For New Deployments
✅ No migration needed - use `communityone_schema.sql` directly

### For Existing Databricks Catalogs
```sql
-- Rename existing table
ALTER TABLE fact_oral_health_observation 
RENAME TO fact_communityone_observation;

-- Create new tables
CREATE TABLE fact_grant ...;
CREATE TABLE fact_nonprofit_finance ...;
CREATE TABLE dim_organization ...;
CREATE TABLE dim_jurisdiction ...;
```

See: [Schema Migration Guide](../deployment/schema-migration.md) for complete migration steps

## Impact Summary

**Schema Completeness:** 60% → 100%  
**ERD Alignment:** Partial → Full  
**Grant Support:** None → Complete  
**Foundation Data:** Missing → 990-PF ready  
**Nonprofit Finances:** None → Full revenue breakdown  
**Government Budgets:** None → Added  
**Meetings:** None → Added  

**Bottom Line:** The gap between ERD documentation and actual schema implementation is **CLOSED** ✅

## 🔗 Related Documentation

- [Schema Migration Guide](../deployment/schema-migration.md)
- [Databricks Deployment](../deployment/databricks.md)
- [Data Model ERD](../../databricks/README.md)
- [Database Schema Files](../../databricks/)

## 📝 Next Steps

1. **Review New Schema:**
   - Examine `databricks/communityone_schema.sql`
   - Understand new table relationships
   - Review foreign key constraints

2. **Plan Data Migration:**
   - If migrating from old schema
   - Test migration scripts
   - Backup existing data

3. **Update Queries:**
   - Update references from `fact_oral_health_observation`
   - Use new dimension tables (`dim_organization`, `dim_jurisdiction`)
   - Leverage new fact tables for enhanced analytics

4. **Deploy:**
   - Create new tables in Databricks
   - Load initial data
   - Verify relationships and constraints
