# Bronze Migration for Events Data

## Overview

This migration creates bronze tables for `events_search` and `events_text_search` (renamed to `events_text_ai`), following the bronze → staging → marts dbt architecture pattern.

## Architecture

```
Bronze Layer (open_navigator_bronze)
    ↓
Staging Layer (dbt views with cleaning/validation)
    ↓
Marts Layer (dbt tables - production-ready)
```

## Files Created

### Database Migrations

1. **003_create_bronze_events_search.sql**
   - Creates `bronze_events_search` table in `open_navigator_bronze` database
   - Stores raw meeting events from LocalView, YouTube, Legistar, etc.
   - Includes all fields from current production `events_search`
   - Tracks data source (`source`, `datasource_id` columns)

2. **004_create_bronze_events_text_ai.sql**
   - Creates `bronze_events_text_ai` table in `open_navigator_bronze` database
   - Stores video transcripts and AI-extracted text
   - Replaces production `events_text_search` table
   - Includes quality flags and AI model tracking

### dbt Staging Models

3. **stg_bronze_events_search.sql**
   - Staging view applying basic cleaning to bronze events
   - Normalizes state codes (UPPER), cities (INITCAP)
   - Adds quality flags: `missing_title`, `missing_date`, `missing_state`, `video_missing_channel`
   - Filters out events without title or date

4. **stg_bronze_events_text_ai.sql**
   - Staging view cleaning video transcripts
   - Calculates `word_count` and `transcript_length`
   - Adds quality flags: `missing_transcript`, `very_short_transcript`, `missing_segments`
   - Filters out transcripts &lt;100 characters

### dbt Mart Models (Production)

5. **events_search.sql**
   - Production-ready events table (replaces current `events_search`)
   - **Deduplicates by video_url** (keeps most recent)
   - Applies quality filters
   - Compatible with current API schema

6. **events_text_search.sql**
   - Production-ready transcripts table (replaces current `events_text_search`)
   - Joins to `events_search` to get `event_id`
   - **Deduplicates by video_id** (keeps highest quality)
   - Quality scoring: prefers manual transcripts, then by word count

### Configuration Files

7. **dbt_project/models/staging/_staging.yml**
   - Added `bronze_events_search` source definition
   - Added `bronze_events_text_ai` source definition
   - Added `stg_bronze_events_search` model documentation
   - Added `stg_bronze_events_text_ai` model documentation

8. **dbt_project/models/marts/_marts.yml**
   - Added `events_search` model documentation
   - Added `events_text_search` model documentation

## Migration Steps

### Step 1: Create Bronze Tables

```bash
# Create bronze_events_search table
psql -h localhost -p 5433 -U postgres -d open_navigator_bronze \
  -f scripts/deployment/neon/migrations/003_create_bronze_events_search.sql

# Create bronze_events_text_ai table
psql -h localhost -p 5433 -U postgres -d open_navigator_bronze \
  -f scripts/deployment/neon/migrations/004_create_bronze_events_text_ai.sql
```

### Step 2: Import Foreign Tables

```bash
# In open_navigator database, import bronze tables via FDW
psql -h localhost -p 5433 -U postgres -d open_navigator -c "
IMPORT FOREIGN SCHEMA public
    LIMIT TO (bronze_events_search, bronze_events_text_ai)
    FROM SERVER bronze_server INTO bronze;
"
```

### Step 3: Load Sample Data (Testing)

```bash
# Copy 100 sample events from production to bronze for testing
psql -h localhost -p 5433 -U postgres -d open_navigator_bronze -c "
INSERT INTO bronze_events_search (
    title, description, event_date, event_time,
    jurisdiction_id, jurisdiction_name, jurisdiction_type,
    state_code, state, city, location, meeting_type, status,
    agenda_url, minutes_url, video_url,
    channel_id, channel_url, channel_type,
    view_count, duration_minutes, like_count, language,
    source, datasource_id
)
SELECT 
    title, description, event_date, event_time,
    jurisdiction_id, jurisdiction_name, jurisdiction_type,
    state_code, state, city, location, meeting_type, status,
    agenda_url, minutes_url, video_url,
    channel_id, channel_url, channel_type,
    view_count, duration_minutes, like_count, language,
    COALESCE(source, 'unknown') AS source,
    CAST(id AS VARCHAR) AS datasource_id
FROM open_navigator.public.events_search
ORDER BY event_date DESC
LIMIT 100;
"

# Copy sample transcripts
psql -h localhost -p 5433 -U postgres -d open_navigator_bronze -c "
INSERT INTO bronze_events_text_ai (
    event_id, video_id, raw_text, segments,
    language, is_auto_generated, transcript_source,
    has_transcript, created_at
)
SELECT 
    event_id, video_id, raw_text, segments,
    language, is_auto_generated, transcript_source,
    TRUE AS has_transcript, created_at
FROM open_navigator.public.events_text_search
LIMIT 100;
"
```

### Step 4: Run dbt Models

```bash
cd dbt_project

# Test staging models
dbt run --select stg_bronze_events_search stg_bronze_events_text_ai

# Build production marts
dbt run --select events_search events_text_search

# Run tests
dbt test --select events_search events_text_search
```

### Step 5: Verify Results

```sql
-- Check events count
SELECT 
    'bronze_events_search' AS table_name, 
    COUNT(*) 
FROM bronze.bronze_events_search
UNION ALL
SELECT 
    'events_search (dbt mart)', 
    COUNT(*) 
FROM events_search;

-- Check transcripts count
SELECT 
    'bronze_events_text_ai' AS table_name, 
    COUNT(*) 
FROM bronze.bronze_events_text_ai
UNION ALL
SELECT 
    'events_text_search (dbt mart)', 
    COUNT(*) 
FROM events_text_search;

-- Verify deduplication worked
SELECT 
    COUNT(*) AS total_bronze_events,
    COUNT(DISTINCT video_url) AS unique_video_urls
FROM bronze.bronze_events_search
WHERE video_url IS NOT NULL;
```

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
├────────────┬────────────┬────────────┬──────────────────────────┤
│  LocalView │  YouTube   │  Legistar  │  Other (Granicus, etc.)  │
└──────┬─────┴──────┬─────┴──────┬─────┴──────┬──────────────────┘
       │            │            │            │
       ↓            ↓            ↓            ↓
┌──────────────────────────────────────────────────────────────────┐
│             BRONZE LAYER (open_navigator_bronze)                 │
├──────────────────────────────┬───────────────────────────────────┤
│  bronze_events_search        │  bronze_events_text_ai            │
│  - Raw events from all       │  - Raw transcripts                │
│    sources                   │  - AI extraction metadata         │
│  - May contain duplicates    │  - Quality flags                  │
│  - Tracks source system      │                                   │
└──────────────┬───────────────┴──────────────┬────────────────────┘
               │                              │
               ↓ (FDW)                        ↓ (FDW)
┌──────────────────────────────────────────────────────────────────┐
│           STAGING LAYER (dbt views - open_navigator)             │
├──────────────────────────────┬───────────────────────────────────┤
│  stg_bronze_events_search    │  stg_bronze_events_text_ai        │
│  - Clean & normalize         │  - Calculate word count           │
│  - Quality flags             │  - Filter &lt;100 chars              │
│  - No deduplication          │  - Quality scoring                │
└──────────────┬───────────────┴──────────────┬────────────────────┘
               │                              │
               ↓                              ↓
┌──────────────────────────────────────────────────────────────────┐
│           MARTS LAYER (dbt tables - open_navigator)              │
├──────────────────────────────┬───────────────────────────────────┤
│  events_search               │  events_text_search               │
│  - Deduplicate by video_url  │  - Join to get event_id           │
│  - Production-ready          │  - Deduplicate by video_id        │
│  - API-compatible schema     │  - Production-ready               │
└──────────────┬───────────────┴──────────────┬────────────────────┘
               │                              │
               ↓                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                   API & FRONTEND                                 │
│         (api/routes/search_postgres.py)                          │
└──────────────────────────────────────────────────────────────────┘
```

## Quality Improvements

### Events Deduplication

**Before:** Direct loading to production could create duplicates
**After:** 
- Bronze layer tracks all raw events
- Staging adds quality flags
- Marts deduplicate by `video_url` (keeps most recent)

### Transcript Quality Scoring

**Before:** No quality ranking for multiple transcripts
**After:**
- Quality score based on: manual > auto-generated, word count
- Keeps only highest quality transcript per video
- Filters transcripts &lt;100 characters

### Data Lineage

**Before:** Unclear where events came from
**After:**
- `source` field tracks origin (localview, youtube, legistar)
- `datasource_id` stores original system ID
- Full history in bronze layer

## Updating Data Loading Scripts

### Current Scripts to Update

1. **scripts/datasources/youtube/load_youtube_events_to_postgres.py**
   - Change: Insert to `bronze_events_search` instead of `events_search`
   - Change: Insert to `bronze_events_text_ai` instead of `events_text_search`

2. **scripts/datasources/localview/load_to_postgres.py**
   - Change: Insert to `bronze_events_search` instead of `events_search`

3. **Any other scripts inserting to events_search**
   - Search: `grep -r "INSERT INTO events_search" scripts/`
   - Update to insert to `bronze_events_search`

### After Updating Scripts

```bash
# Run updated loader script
python scripts/datasources/youtube/load_youtube_events_to_postgres.py --states AL,MA

# Run dbt to update production tables
cd dbt_project
dbt run --select events_search events_text_search

# Production tables are now up to date!
```

## Benefits

✅ **Version Control** - All transformations in SQL tracked by git
✅ **Testable** - dbt tests ensure data quality
✅ **Deduplication** - Automatic deduplication in marts layer
✅ **Quality Filters** - Consistent quality rules applied
✅ **Data Lineage** - Clear path from source to production
✅ **Rollback-able** - Can rebuild from bronze at any time

## Next Steps

1. **Update loading scripts** - Change insert targets to bronze tables
2. **Test full pipeline** - Load → dbt run → API query
3. **Schedule dbt runs** - Add to cron/Airflow for daily updates
4. **Monitor quality** - Review dbt test results regularly
5. **Backfill bronze** - Load historical data from production to bronze

## Questions?

See also:
- [YouTube Channels Bronze Migration](youtube-channels-bronze-migration.md)
- [dbt Quick Reference](../dbt_project/QUICK_REFERENCE.md)
