---
sidebar_position: 6
---

# dbt Stats & Data Pipeline

## Overview

This directory contains scripts for building and syncing statistics and enriched data tables using dbt models.

## Models

### 1. `bronze_organizations_nonprofits` (Marts)

**Combined nonprofit data:** IRS Business Master File + NCCS enrichment

- **Base**: 1.95M organizations from IRS BMF
- **Enrichment**: Geographic coordinates, CBSA, detailed financials from NCCS
- **Join**: LEFT JOIN on EIN (794k organizations have both IRS + NCCS data)

**Key columns:**
- IRS base: `ein`, `org_name`, `city`, `state_code`, `ntee_cd`, `irs_revenue_amt`
- Geographic: `latitude`, `longitude`, `census_cbsa_name`, `census_county_name`
- Financials: `f990_total_revenue_recent`, `f990_total_assets_recent`
- Flags: `has_nccs_data`, `has_geocoding`

**Build:**
```bash
cd dbt_project
dbt run --target bronze --select bronze_organizations_nonprofits
```

**Output:** `open_navigator.bronze.bronze_organizations_nonprofits` (756 MB, 70 columns)

### 2. `jurisdiction_state_aggregate` (Marts)

**Multi-level jurisdiction statistics with trending causes**

- **Levels**: national, state, **county** (NEW!), city, jurisdiction
- **Nonprofit data**: Uses `bronze_organizations_nonprofits` (1.95M orgs with NCCS enrichment)
- **Geographic coverage**: 8,561 counties, 62 states/territories, 147 cities
- **Metrics**: Nonprofit counts, revenue, assets, event counts, contact counts, bill counts

**Build and sync to production - see workflow below.**

**Output:** `open_navigator.bronze.jurisdiction_state_aggregate` (8,779 records)

## Pipeline Architecture

```
Bronze schema (dev)  →  Public schema (queries)  →  Neon Cloud (website)
open_navigator.bronze  →  open_navigator.public  →  Neon PostgreSQL
```

### Database Roles

- **`open_navigator.bronze`**: Development schema for raw data and dbt transformations
  - Contains `bronze_*` tables from data loading scripts
  - dbt models run here (staging, intermediate, marts)
  - NOT deployed to production servers

- **`open_navigator`**: Production-ready local PostgreSQL database
  - Fast queries for API endpoints
  - Synced from bronze via export scripts
  - Source for Neon cloud deployment

- **Neon Cloud**: Production database for deployed website
  - Synced via `packages/hosting/src/hosting/neon/migrate.py`
  - Optimized for HuggingFace Spaces deployment

## Workflow: Building Stats

### 1. Run dbt models

Build the stats in the bronze schema:

```bash
cd dbt_project
source ../.venv/bin/activate
dbt run --target bronze --select stg_bronze_decisions+
```

**What this does:**
- `stg_bronze_decisions`: Cleans and filters recent decisions (last 90 days)
- `int_trending_causes_by_jurisdiction`: Aggregates decisions by NTEE cause category
- `jurisdiction_state_aggregate`: Final stats table with trending causes JSON

**Output:** `open_navigator.bronze.jurisdiction_state_aggregate`

### 2. Export to production database

Sync stats from bronze to production:

```bash
cd /home/developer/projects/open-navigator
source .venv/bin/activate
python dbt_project/scripts/export_stats_to_open_navigator.py
```

**What this does:**
- Reads from `open_navigator.bronze.jurisdiction_state_aggregate`
- Deletes old data from `open_navigator.jurisdiction_state_aggregate`
- Inserts updated stats (3 records: national, state, jurisdiction levels)
- Handles JSONB serialization for trending_causes column

**Output:** `open_navigator.jurisdiction_state_aggregate` (ready for API queries)

### 3. Deploy to Neon Cloud (optional)

For production deployment:

```bash
python packages/hosting/src/hosting/neon/migrate.py
```

## Data Schema

### jurisdiction_state_aggregate Table

**8,779 records across 5 aggregation levels**

| Column | Type | Description |
|--------|------|-------------|
| `level` | VARCHAR(20) | Aggregation level: `national`, `state`, `county`, `city`, `jurisdiction` |
| `state_code` | VARCHAR(2) | Two-letter state code (e.g., 'AL', 'MA') |
| `state` | VARCHAR(50) | Full state name (e.g., 'Alabama', 'Massachusetts') |
| `county` | VARCHAR(100) | County name (populated for `county` level) |
| `city` | VARCHAR(100) | City name (populated for `city` and `jurisdiction` levels) |
| `jurisdictions_count` | INTEGER | Number of jurisdictions (currently 0 - placeholder) |
| `school_districts_count` | INTEGER | Number of school districts (currently 0 - placeholder) |
| `nonprofits_count` | INTEGER | **Number of nonprofits** (from `bronze_organizations_nonprofits`) |
| `events_count` | INTEGER | **Number of events/meetings** (from `bronze_events`) |
| `bills_count` | INTEGER | **Number of bills** (from `bronze_bills`) |
| `contacts_count` | INTEGER | Number of contacts (from `bronze_contacts`) |
| `total_revenue` | BIGINT | **Total nonprofit revenue** (IRS data) |
| `total_assets` | BIGINT | **Total nonprofit assets** (IRS data) |
| `trending_causes` | JSONB | **Array of trending policy causes** (jurisdiction/city levels only) |
| `last_updated` | TIMESTAMP | Last update timestamp |

**Data Coverage by Level:**

| Level | Records | Nonprofits | Events | Revenue | Assets | Trending Causes |
|-------|---------|------------|--------|---------|--------|-----------------|
| **national** | 1 | 1.95M | 31.8k | $3.8T | $9.7T | ❌ |
| **state** | 62 | 1.95M total | 31.8k total | $3.8T total | $9.7T total | ✅ (aggregated) |
| **county** | 8,561 | 793k (with NCCS) | ❌ | $1.8T | $4.5T | ❌ |
| **city** | 147 | 5.2M (rollup) | 31.8k | ❌ | ❌ | ✅ |
| **jurisdiction** | 8 | ❌ | 5.1k | ❌ | ❌ | ✅ |

**Notes:**
- County stats only include nonprofits with NCCS enrichment (geographic data available)
- Events don't have county mapping, so county-level event counts are 0
- City and jurisdiction levels focus on trending causes from meeting analysis

### bronze_organizations_nonprofits Table

**Combined IRS + NCCS nonprofit data (1.95M organizations)**

| Column | Type | Description |
|--------|------|-------------|
| `ein` | VARCHAR(20) | Employer Identification Number (primary key) |
| `org_name` | TEXT | Organization name from IRS BMF |
| `city` | VARCHAR(100) | City |
| `state_code` | VARCHAR(2) | Two-letter state code |
| `zip_code` | VARCHAR(10) | ZIP code |
| `ntee_cd` | VARCHAR(10) | IRS NTEE classification code |
| `irs_revenue_amt` | BIGINT | Revenue from IRS BMF |
| `irs_asset_amt` | BIGINT | Assets from IRS BMF |
| `irs_income_amt` | BIGINT | Income from IRS BMF |
| **NCCS Enrichment** | | **Available for 794k orgs (40.7%)** |
| `latitude` | DOUBLE | Geographic latitude |
| `longitude` | DOUBLE | Geographic longitude |
| `census_cbsa_name` | VARCHAR(200) | Census Core Based Statistical Area |
| `census_county_name` | VARCHAR(100) | County name |
| `f990_total_revenue_recent` | BIGINT | Most recent Form 990 revenue |
| `f990_total_assets_recent` | BIGINT | Most recent Form 990 assets |
| `f990_total_expenses_recent` | BIGINT | Most recent Form 990 expenses |
| `ntee_nccs` | VARCHAR(20) | NCCS NTEE classification |
| `nteev2` | VARCHAR(20) | NTEE version 2 code |
| `org_year_first` | INTEGER | First year in NCCS data |
| `org_year_last` | INTEGER | Most recent year in NCCS data |
| **Data Quality Flags** | | |
| `has_nccs_data` | BOOLEAN | TRUE if NCCS enrichment available |
| `has_geocoding` | BOOLEAN | TRUE if lat/lon coordinates available |
| `last_updated` | TIMESTAMP | Most recent load timestamp |

**Enrichment Coverage:**
- 40.7% (794,072 orgs) have NCCS enrichment data
- 40.7% (794,072 orgs) have geocoding (lat/lon)
- 20.8% (406,385 orgs) have Form 990 revenue data
- 37.5% (732,660 orgs) have CBSA (metro area) data

**Source Tables:**
- `bronze_organizations_nonprofits_irs`: IRS Business Master File (1.95M orgs)
- `bronze_organizations_nonprofits_nccs`: NCCS Core data (1.8M orgs)

### Trending Causes JSON Structure

```json
[
  {
    "causes": [
      {
        "code": "COFOG-01",
        "rank": 1,
        "cause": "Governance and Administrative Policy",
        "topics": 9,
        "most_recent": "2026-04-20",
        "decision_count": 9,
        "sample_headlines": [
          "Council approves appointment of new City Clerk",
          "Previous meeting minutes approved",
          "Meeting called to order"
        ]
      },
      {
        "code": "COFOG-04",
        "rank": 2,
        "cause": "Infrastructure and Capital Projects",
        "topics": 4,
        "most_recent": "2026-04-21",
        "decision_count": 4,
        "sample_headlines": [
          "Council discusses City Hall renovation project.",
          "Council Reviews City Hall Renovation Options"
        ]
      }
    ]
  }
]
```

## API Usage

Query stats from the production database:

```python
# In FastAPI endpoint
from api.database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# Get trending causes for a state
cursor.execute("""
    SELECT trending_causes 
    FROM jurisdiction_state_aggregate 
    WHERE level = 'state' AND state_code = %s
""", ('AL',))

causes = cursor.fetchone()[0]  # Returns JSONB as Python dict

# Get county-level nonprofit stats (NEW!)
cursor.execute("""
    SELECT 
        county,
        nonprofits_count,
        total_revenue,
        total_assets
    FROM jurisdiction_state_aggregate 
    WHERE level = 'county' 
      AND state_code = %s
    ORDER BY nonprofits_count DESC
    LIMIT 10
""", ('CA',))

top_counties = cursor.fetchall()

# Get national summary
cursor.execute("""
    SELECT 
        nonprofits_count,
        events_count,
        total_revenue,
        total_assets
    FROM jurisdiction_state_aggregate 
    WHERE level = 'national'
""")

national_stats = cursor.fetchone()
```

## dbt Profile Configuration

The `~/.dbt/profiles.yml` file defines three targets:

- **`dev`**: Default target, uses `open_navigator` database
- **`bronze`**: Uses `open_navigator` database with `bronze` schema
- **`prod`**: Neon cloud database (requires env vars)

To switch targets:
```bash
dbt run --target bronze  # For stats pipeline
dbt run --target dev     # For other models
```

## Common Tasks

### Rebuild all stats from scratch

```bash
# 1. Run dbt models
cd dbt_project && dbt run --target bronze --select stg_bronze_decisions+

# 2. Export to production
cd .. && python dbt_project/scripts/export_stats_to_open_navigator.py

# 3. Verify
psql -h localhost -p 5433 -U postgres -d open_navigator -c \
  "SELECT level, jsonb_array_length(trending_causes) FROM jurisdiction_state_aggregate WHERE trending_causes IS NOT NULL;"
```

### Add new dbt models

1. Create model in `dbt_project/models/`
2. Update `_staging.yml`, `_intermediate.yml`, or `_marts.yml`
3. Run: `dbt run --target bronze --select your_model+`
4. Export if needed: `python dbt_project/scripts/export_stats_to_open_navigator.py`

## Troubleshooting

### "cross-database references are not implemented"

This error occurs when dbt tries to query across databases. Make sure you're using the correct target:

```bash
dbt run --target bronze  # NOT --target dev
```

### "relation does not exist"

The staging model needs to be built before intermediate/mart models:

```bash
dbt run --target bronze --select stg_bronze_decisions+  # The + builds downstream
```

### "can't adapt type 'dict'"

The export script handles JSONB serialization automatically. If you see this error, check that you're using `psycopg2.extras.Json()` wrapper.

## Files in this Directory

- `export_stats_to_open_navigator.py` - Sync script (bronze → production)
- `README.md` - This file

## Related Documentation

- [dbt Project README](../../dbt_project/README.md)
- [Trending Causes Guide](../../dbt_project/README_TRENDING_CAUSES.md)
- [Neon Deployment](../deployment/neon/README.md)
