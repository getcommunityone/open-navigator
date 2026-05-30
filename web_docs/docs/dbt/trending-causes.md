---
sidebar_position: 2
---

# DBT Models for Stats Aggregates with Trending Causes

## Overview

The dbt project includes models to load `jurisdiction_state_aggregate` table with **location-specific trending causes** based on decisions from the last 90 days.

✨ **NEW:** The frontend now displays trending causes dynamically based on the selected geography (national, state, county, or city level).

## Quick Start

```bash
# Update trending causes data (runs all required dbt models)
./scripts/data/update_trending_causes.sh

# Or manually:
cd dbt_project
dbt run --select stg_bronze_decisions int_trending_causes_by_jurisdiction jurisdiction_state_aggregate
```

## How It Works

1. **User selects a location** in the frontend (e.g., "Mobile, AL")
2. **Frontend queries** `/api/stats?state=AL&city=Mobile`
3. **API returns** stats with `trending_causes` JSONB field
4. **Frontend displays** the top trending causes for that location in the last 90 days
5. **Fallback:** If no location-specific causes exist, shows global trending causes from `/api/trending`

## Models Created

### 1. Staging Layer

**`stg_bronze_decisions.sql`**
- Cleans and normalizes bronze_decisions data
- Adds `is_recent` flag for decisions in last 90 days
- Calculates `days_since_decision` for trending analysis
- Filters out decisions without dates

### 2. Intermediate Layer

**`int_trending_causes_by_jurisdiction.sql`**
- Aggregates decisions by cause (NTEE major group) and jurisdiction
- Ranks causes by decision count and recency
- Includes top 10 trending causes per jurisdiction
- Generates JSON structure with:
  - Cause category and code
  - Decision count and unique topics
  - Most recent decision date
  - Sample headlines (up to 3)

### 3. Marts Layer

**`jurisdiction_state_aggregate.sql`**
- Builds the final jurisdiction_state_aggregate table
- Supports multiple levels: national, state, county, city, jurisdiction
- Includes `trending_causes` as JSONB column
- Joins trending causes data from intermediate model

## Schema Changes

Added `trending_causes` JSONB column to `jurisdiction_state_aggregate` table:

```sql
ALTER TABLE jurisdiction_state_aggregate ADD COLUMN IF NOT EXISTS trending_causes JSONB;
```

## Trending Causes JSON Structure

The `trending_causes` JSONB column contains different structures depending on the aggregation level:

### City Level (Jurisdiction-Specific)
```json
[
  {
    "cause": "Education and Workforce",
    "code": "COFOG-09",
    "decision_count": 5,
    "topics": 3,
    "most_recent": "2024-05-22",
    "rank": 1,
    "sample_headlines": [
      "MPS highlights literacy strategies...",
      "Board approves new curriculum...",
      "Teacher hiring approved..."
    ]
  },
  {
    "cause": "Health",
    "code": "COFOG-07",
    "decision_count": 3,
    "topics": 2,
    "most_recent": "2024-05-20",
    "rank": 2,
    "sample_headlines": [...]
  }
]
```

### State Level (Aggregated Across State)
```json
[
  {
    "cause": "Education and Workforce",
    "decision_count": 127,
    "jurisdictions": 15
  },
  {
    "cause": "Health",
    "decision_count": 89,
    "jurisdictions": 12
  }
]
```

### National Level (Aggregated Across Nation)
```json
[
  {
    "cause": "Education and Workforce",
    "decision_count": 1543,
    "states": 42
  },
  {
    "cause": "Infrastructure",
    "decision_count": 1201,
    "states": 38
  }
]
```

## Usage

### Running the Models

```bash
# Quick update (recommended)
./scripts/data/update_trending_causes.sh

# Or step-by-step:
cd dbt_project

# Install dependencies
dbt deps

# Run staging and intermediate models
dbt run --select stg_bronze_decisions int_trending_causes_by_jurisdiction

# Run marts layer (jurisdiction_state_aggregate)
dbt run --select jurisdiction_state_aggregate

# Run all models
dbt run

# Test data quality
dbt test
```

### Verifying the Data

After running the models, verify trending causes are populated:

```sql
-- Check city-level trending causes
SELECT 
  city,
  state_code,
  jsonb_array_length(trending_causes) as cause_count,
  trending_causes
FROM jurisdiction_state_aggregate
WHERE level = 'city' 
  AND trending_causes IS NOT NULL
  AND city ILIKE '%Mobile%'
LIMIT 1;

-- See top causes for a state
SELECT 
  state_code,
  jsonb_pretty(trending_causes) as causes
FROM jurisdiction_state_aggregate
WHERE level = 'state' 
  AND state_code = 'AL';

-- National trending causes
SELECT jsonb_pretty(trending_causes) 
FROM jurisdiction_state_aggregate 
WHERE level = 'national';
```

### Testing in the Frontend

1. Start the application:
   ```bash
   ./start-all.sh
   ```

2. Open http://localhost:5173

3. Search for a location (e.g., "Mobile, AL")

4. Observe the trending topics bar at the top - it should show location-specific causes

5. Switch to different locations and see the trending causes update dynamically

## Integration with Python Scripts

The existing Python migration scripts in `scripts/deployment/neon/` can now:
1. Use dbt to generate jurisdiction_state_aggregate
2. OR continue using Python aggregation
3. Merge both approaches (Python for counts, dbt for trending causes)

### Recommended Workflow

```python
# In migrate.py or update_stats.py
import subprocess

# Run dbt models first to calculate trending causes
subprocess.run(['dbt', 'run', '--select', 'jurisdiction_state_aggregate'], 
               cwd='/path/to/dbt_project')

# Then update counts using Python (jurisdictions, nonprofits, etc.)
# The trending_causes column will be preserved
```

## Dependencies

### Bronze Tables Required
- `bronze_decisions` - Policy decisions with dates and themes
- `bronze_events` - Meeting events with jurisdiction info

### Source Configuration

Sources are defined in `models/staging/_staging.yml`:
- Database: `open_navigator`
- Schema: `bronze`

## Data Quality Tests

The models include data quality tests:

```yaml
# stg_bronze_decisions
- decision_date: not_null
- bronze_decision_id: unique, not_null

# int_trending_causes_by_jurisdiction  
- state_code: not_null
- jurisdiction_name: not_null
- cause_category: not_null
- decision_count: not_null

# jurisdiction_state_aggregate
- level: not_null, accepted_values
- last_updated: not_null
```

Run tests with:
```bash
dbt test
```

## Maintenance

### Incremental Updates

The models currently use full refresh. For incremental updates:

1. Change materialization to `incremental`
2. Add `is_incremental()` logic
3. Filter by `extracted_at > max(last_updated)`

```sql
{% if is_incremental() %}
  WHERE extracted_at > (SELECT MAX(last_updated) FROM {{ this }})
{% endif %}
```

### Refreshing Trending Causes

Trending causes should be refreshed daily:

```bash
# Cron job example
0 2 * * * cd /path/to/dbt_project && dbt run --select jurisdiction_state_aggregate
```

## Next Steps

1. **Populate counts**: Update Python scripts or create dbt models to load actual jurisdiction/nonprofit counts
2. **Add indexes**: Create GIN index on `trending_causes` JSONB column for faster queries
3. **API integration**: Update `/api/stats` endpoint to return `trending_causes`
4. **Frontend**: Display trending causes in dashboard/stats pages
