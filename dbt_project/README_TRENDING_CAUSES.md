# DBT Models for Stats Aggregates with Trending Causes

## Overview

The dbt project now includes models to load `stats_aggregates` table with trending causes based on decisions from the last 90 days.

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

**`stats_aggregates.sql`**
- Builds the final stats_aggregates table
- Supports multiple levels: national, state, county, city, jurisdiction
- Includes `trending_causes` as JSONB column
- Joins trending causes data from intermediate model

## Schema Changes

Added `trending_causes` JSONB column to `stats_aggregates` table:

```sql
ALTER TABLE stats_aggregates ADD COLUMN IF NOT EXISTS trending_causes JSONB;
```

## Trending Causes JSON Structure

```json
{
  "jurisdiction": "Mobile",
  "causes": [
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
    }
  ]
}
```

## Usage

### Running the Models

```bash
# Navigate to dbt directory
cd dbt_project

# Install dependencies
dbt deps

# Run staging and intermediate models
dbt run --select stg_bronze_decisions int_trending_causes_by_jurisdiction

# Run marts layer (stats_aggregates)
dbt run --select stats_aggregates

# Run all models
dbt run

# Test data quality
dbt test
```

### Querying Results

```sql
-- Get trending causes for a state
SELECT 
  state,
  trending_causes
FROM stats_aggregates
WHERE level = 'state' 
  AND state_code = 'AL';

-- Get top causes across all jurisdictions
SELECT 
  city,
  jsonb_array_elements(trending_causes) as cause
FROM stats_aggregates
WHERE level = 'jurisdiction'
  AND trending_causes IS NOT NULL;
  
-- Extract specific cause details
SELECT 
  city,
  cause_data->>'cause' as cause_name,
  (cause_data->>'decision_count')::int as decisions,
  cause_data->>'most_recent' as latest_decision
FROM stats_aggregates,
  jsonb_array_elements(trending_causes) as cause_data
WHERE level = 'jurisdiction'
  AND state_code = 'AL'
ORDER BY (cause_data->>'decision_count')::int DESC;
```

## Integration with Python Scripts

The existing Python migration scripts in `scripts/deployment/neon/` can now:
1. Use dbt to generate stats_aggregates
2. OR continue using Python aggregation
3. Merge both approaches (Python for counts, dbt for trending causes)

### Recommended Workflow

```python
# In migrate.py or update_stats.py
import subprocess

# Run dbt models first to calculate trending causes
subprocess.run(['dbt', 'run', '--select', 'stats_aggregates'], 
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
- Database: `open_navigator_bronze`
- Schema: `public`

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

# stats_aggregates
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
0 2 * * * cd /path/to/dbt_project && dbt run --select stats_aggregates
```

## Next Steps

1. **Populate counts**: Update Python scripts or create dbt models to load actual jurisdiction/nonprofit counts
2. **Add indexes**: Create GIN index on `trending_causes` JSONB column for faster queries
3. **API integration**: Update `/api/stats` endpoint to return `trending_causes`
4. **Frontend**: Display trending causes in dashboard/stats pages
