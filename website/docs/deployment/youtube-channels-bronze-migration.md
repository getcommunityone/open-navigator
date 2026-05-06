---
sidebar_position: 7
---

# YouTube Channels Bronze Migration

Guide for migrating `events_channels_search` from direct production loading to the bronze + dbt pattern.

## Overview

**What:** Move YouTube channel loading from direct production writes to bronze database with dbt transformations

**Why:**
- ✅ Separation of concerns (loading vs. transformation)
- ✅ Testable data quality via dbt tests
- ✅ Version-controlled transformations
- ✅ Reusable intermediate models
- ✅ Clear data lineage (bronze → staging → intermediate → mart)

## Architecture

### Before (Current)

```
scripts/datasources/youtube/load_channels.py
    ↓ (direct write)
events_channels_search (production table)
```

### After (New)

```
scripts/datasources/youtube/load_youtube_channels_bronze.py
    ↓ (write to bronze)
bronze_events_channels (bronze table)
    ↓ (Foreign Data Wrapper)
bronze.bronze_events_channels (foreign table in production)
    ↓ (dbt staging)
stg_bronze_events_channels (view)
    ↓ (dbt intermediate)
int_events_channels_enriched (view with stats)
    ↓ (dbt mart)
events_channels_search (production table)
```

## Migration Steps

### 1. Create Bronze Table

Run the migration in the bronze database:

```bash
psql -h localhost -p 5433 -U postgres -d open_navigator_bronze \
  -f scripts/deployment/neon/migrations/002_create_bronze_events_channels.sql
```

### 2. Import Foreign Table

Run in the production database to make bronze table accessible:

```sql
-- In open_navigator database
BEGIN;

IMPORT FOREIGN SCHEMA public 
    LIMIT TO (bronze_events_channels)
    FROM SERVER bronze_server 
    INTO bronze;

COMMIT;
```

Verify the import:

```sql
\d bronze.bronze_events_channels
```

### 3. Load Data to Bronze

Use the new bronze loading script:

```bash
# Load channels for specific states
python scripts/datasources/youtube/load_youtube_channels_bronze.py \
  --states AL,GA,IN,MA,WA,WI \
  --auto-flag

# Or all states
python scripts/datasources/youtube/load_youtube_channels_bronze.py --auto-flag
```

**Flags:**
- `--states`: Comma-separated state codes to process
- `--validate`: Validate against WikiData (slower)
- `--auto-flag`: Automatically flag junk channels (news, entertainment)

### 4. Run dbt Models

```bash
cd dbt_project

# Test staging model
dbt run --select stg_bronze_events_channels

# Test intermediate model
dbt run --select int_events_channels_enriched

# Build production table
dbt run --select events_channels_search

# Verify counts
dbt run --select events_channels_search && \
  psql -h localhost -p 5433 -U postgres -d open_navigator \
    -c "SELECT COUNT(*), 
        COUNT(*) FILTER (WHERE is_government) as govt_channels,
        COUNT(*) FILTER (WHERE in_localview) as localview_channels
        FROM events_channels_search;"
```

### 5. Update Dependent Processes

Update any scripts that reference `events_channels_search`:

**API Routes:**
- No changes needed - table name stays the same
- Data structure is identical

**Loading Scripts:**
- Use `load_youtube_channels_bronze.py` instead of `load_channels.py`
- Run dbt after loading to update production table

## Data Flow

### Bronze Layer

**Source:** `load_youtube_channels_bronze.py`
- Reads from: `jurisdictions_details_search.youtube_channels` (production)
- Writes to: `bronze_events_channels` (bronze database)
- Purpose: Raw channel data with basic validation

### Staging Layer

**Model:** `stg_bronze_events_channels.sql`
- Input: `bronze.bronze_events_channels` (via FDW)
- Output: View with clean data
- Filters: Basic data quality (non-null channel_id, valid URLs)

### Intermediate Layer

**Model:** `int_events_channels_enriched.sql`
- Input: `stg_bronze_events_channels`
- Output: View with enrichments
- Adds:
  - Event statistics (count, date ranges)
  - Quality scoring (based on validation sources)
  - Government likelihood assessment
  - Activity status (active/stale/inactive)

### Mart Layer

**Model:** `events_channels_search.sql`
- Input: `int_events_channels_enriched`
- Output: Production table
- Filters:
  - Excludes junk channels (unless in LocalView)
  - Only validated channels (quality_score >= 0.7)
- Indexes: channel_id, in_localview, is_government, etc.

## Quality Scoring

Channels are scored based on validation sources:

| Validation | Quality Score | Meaning |
|------------|---------------|---------|
| WikiData verified | 1.0 | Highest - official government channel |
| LocalView + jurisdictions | 0.9 | High - multiple validations |
| LocalView only | 0.85 | High - validated by LocalView dataset |
| jurisdictions only | 0.7 | Medium - found in jurisdiction data |
| Unknown source | 0.5 | Low - needs validation |

## Junk Channel Detection

Auto-flagging patterns (conservative to avoid false positives):

**Flagged:**
- Major news networks: CNN, Fox News, MSNBC, NBC News, ABC News, CBS News
- YouTube auto-generated: "- Topic" channels
- Music platforms: VEVO
- Entertainment shows: Last Week Tonight, Daily Show, etc.

**Not Flagged:**
- Local news stations (might cover government meetings)
- Political commentary (unless clearly entertainment)
- Citizen journalism

**False Positive Protection:**
- Channels in LocalView dataset are kept even if flagged
- Manual review recommended for borderline cases

## Validation

### Data Quality Tests

Add to `dbt_project/tests/`:

```sql
-- tests/assert_channels_have_validation.sql
-- Every channel must have at least one validation source
SELECT *
FROM {{ ref('events_channels_search') }}
WHERE NOT (
    in_localview 
    OR in_wikidata 
    OR in_jurisdictions_details
    OR quality_score >= 0.7
)
```

```sql
-- tests/assert_no_flagged_junk_unless_localview.sql  
-- Flagged junk should only be in table if also in LocalView
SELECT *
FROM {{ ref('events_channels_search') }}
WHERE flagged_as_junk = TRUE
  AND in_localview = FALSE
```

Run tests:

```bash
dbt test --select events_channels_search
```

### Manual Verification

Compare old vs. new tables:

```sql
-- Count comparison
SELECT 
    'OLD' as source, COUNT(*) as total,
    COUNT(*) FILTER (WHERE is_government) as govt,
    COUNT(*) FILTER (WHERE flagged_as_junk) as flagged
FROM events_channels_search_old
UNION ALL
SELECT 
    'NEW' as source, COUNT(*) as total,
    COUNT(*) FILTER (WHERE is_government) as govt,
    COUNT(*) FILTER (WHERE flagged_as_junk) as flagged
FROM events_channels_search;

-- Sample records
SELECT channel_id, channel_title, is_government, quality_score, activity_status
FROM events_channels_search
ORDER BY quality_score DESC
LIMIT 20;
```

## Rollback Plan

If issues arise, rollback to old process:

```bash
# 1. Stop using new loading script
# Use old script: scripts/datasources/youtube/load_channels.py

# 2. Drop dbt-generated table
psql -h localhost -p 5433 -U postgres -d open_navigator \
  -c "DROP TABLE IF EXISTS events_channels_search;"

# 3. Rename old table back
psql -h localhost -p 5433 -U postgres -d open_navigator \
  -c "ALTER TABLE events_channels_search_backup RENAME TO events_channels_search;"
```

## Maintenance

### Regular Updates

Run bronze loading + dbt weekly:

```bash
#!/bin/bash
# scripts/datasources/youtube/update_channels_weekly.sh

# Load new channels to bronze
python scripts/datasources/youtube/load_youtube_channels_bronze.py --auto-flag

# Refresh production table via dbt
cd dbt_project
dbt run --select +events_channels_search
```

### Monitoring

Check for issues:

```sql
-- Channels with no recent videos
SELECT channel_id, channel_title, days_since_last_video, activity_status
FROM events_channels_search
WHERE activity_status = 'inactive'
  AND is_government = TRUE
ORDER BY days_since_last_video DESC
LIMIT 20;

-- Channels needing validation
SELECT channel_id, channel_title, quality_score, 
       in_localview, in_wikidata, in_jurisdictions_details
FROM events_channels_search
WHERE quality_score < 0.8
  AND is_government IS NULL
ORDER BY event_count DESC
LIMIT 20;
```

## Benefits

✅ **Testable:** dbt tests ensure data quality  
✅ **Auditable:** All transformations versioned in SQL  
✅ **Flexible:** Easy to add new enrichments in intermediate layer  
✅ **Performant:** Indexed mart table for fast queries  
✅ **Maintainable:** Clear separation between loading and transformation  
✅ **Incremental:** Can make mart incremental for large datasets

## Next Steps

Once this pattern works well:

1. Migrate `events_search` to bronze pattern
2. Migrate `jurisdictions_details_search` to bronze pattern  
3. Create unified dbt documentation
4. Add more data quality tests
5. Implement incremental materializations for large tables
