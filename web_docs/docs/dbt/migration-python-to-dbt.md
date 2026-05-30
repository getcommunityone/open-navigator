---
sidebar_position: 5
---

# Migrating JSONB Extraction from Python to dbt

## Overview

This guide shows how to replace `scripts/datasources/gemini/load_meeting_transcripts_bronze.py` with dbt incremental models.

## Why Migrate to dbt?

**Current approach (Python):**
- ❌ Separate tool/language from main transformation pipeline
- ❌ Manual UPSERT logic with psycopg2
- ❌ Harder to track lineage
- ❌ No built-in testing framework

**dbt approach:**
- ✅ Single tool for all transformations
- ✅ SQL-based JSONB extraction (simpler to maintain)
- ✅ Incremental processing built-in
- ✅ Automatic lineage tracking
- ✅ Built-in testing and documentation
- ✅ Version control friendly

## What CAN Be Migrated

✅ **`load_meeting_transcripts_bronze.py`** - JSONB extraction to bronze tables
   - bronze_contacts
   - bronze_decisions
   - bronze_topics
   - bronze_organizations_meetings
   - bronze_bills
   - bronze_causes
   - bronze_financial_items

## What CANNOT Be Migrated

❌ **`load_meeting_transcripts.py`** - Calls Gemini API (data loading, not transformation)
❌ **`check_models_used.py`** - Reporting script
❌ **`analyze_with_multi_models.py`** - Calls Gemini API
❌ **`migrations/cleanup_null_records.py`** - One-time migration

## Migration Steps

### 1. Create dbt Bronze Models

Created example models (see `models/bronze/`):
- `bronze_contacts_from_ai.sql` - Extract people from JSONB
- `bronze_decisions_from_ai.sql` - Extract decisions from JSONB

Pattern for other tables:
```sql
{{
  config(
    materialized='incremental',
    unique_key='source_event_id_<entity>_id',
    schema='bronze',
    tags=['bronze', 'incremental', 'ai-extraction']
  )
}}

WITH source_events AS (
    SELECT 
        id as event_id,
        structured_analysis,
        ai_model,
        created_at
    FROM {{ source('bronze', 'bronze_events_analysis_ai') }}
    WHERE structured_analysis IS NOT NULL
    
    {% if is_incremental() %}
        AND created_at > (SELECT MAX(extracted_at) FROM {{ this }})
    {% endif %}
),

entities_unnested AS (
    SELECT 
        event_id,
        ai_model,
        jsonb_array_elements(structured_analysis->'<entity_key>') as entity_data,
        created_at as extracted_at
    FROM source_events
    WHERE structured_analysis ? '<entity_key>'
)

SELECT
    -- Extract fields from JSONB...
FROM entities_unnested
```

### 2. Update Staging Models

**OLD (reads from bronze tables created by Python):**
```sql
SELECT * FROM {{ source('bronze', 'bronze_contacts') }}
```

**NEW (reads from dbt bronze models):**
```sql
SELECT * FROM {{ ref('bronze_contacts_from_ai') }}
```

### 3. Update Workflow

**OLD:**
```bash
# Step 1: Run Gemini API analysis
python scripts/datasources/gemini/load_meeting_transcripts.py

# Step 2: Extract JSONB to bronze tables (Python)
python scripts/datasources/gemini/load_meeting_transcripts_bronze.py

# Step 3: Transform with dbt
cd dbt_project
dbt run --select stg_bronze_contacts+
```

**NEW:**
```bash
# Step 1: Run Gemini API analysis (still Python)
python scripts/datasources/gemini/load_meeting_transcripts.py

# Step 2: Extract JSONB with dbt (incremental)
cd dbt_project
dbt run --select bronze_contacts_from_ai+

# Or run all bronze extractions:
dbt run --select tag:ai-extraction+
```

### 4. First-Time Setup

**Initial load (one time):**
```bash
# Let Python script create initial bronze tables
python scripts/datasources/gemini/load_meeting_transcripts_bronze.py

# OR let dbt create them fresh:
cd dbt_project
dbt run --select tag:ai-extraction --full-refresh
```

**Going forward (incremental):**
```bash
cd dbt_project
dbt run --select tag:ai-extraction
# Only processes new records added since last run
```

## JSONB Extraction Patterns

### Simple Array Extraction

```sql
-- Extract people array
jsonb_array_elements(structured_analysis->'people') as person_data

-- Get fields
person_data->>'full_name' as full_name  -- Text
person_data->>'is_lobbyist' as is_lobbyist  -- Still text, cast later
(person_data->>'is_lobbyist')::boolean  -- Cast to boolean
```

### Nested JSONB (Keep as JSONB)

```sql
-- Keep complex structures as JSONB
person_data->'lobbyist_clients' as lobbyist_clients,  -- JSONB
decision_data->'vote_tally' as vote_tally,  -- JSONB
decision_data->'frame_analysis' as frame_analysis  -- JSONB
```

### Date/Numeric Casting

```sql
(decision_data->>'decision_date')::date as decision_date,
(decision_data->>'year')::integer as year,
(financial_data->>'amount')::numeric as amount
```

### Handling NULL/Missing Fields

```sql
-- Use COALESCE for defaults
COALESCE((person_data->>'is_lobbyist')::boolean, FALSE) as is_lobbyist,

-- Check if key exists
WHERE structured_analysis ? 'people'
```

## Incremental Model Strategy

dbt will:
1. Check if target table exists
2. If first run → create full table
3. If subsequent run → only process new source records
4. Use `unique_key` to deduplicate (UPSERT behavior)

```sql
{% if is_incremental() %}
    AND created_at > (SELECT MAX(extracted_at) FROM {{ this }})
{% endif %}
```

## Testing

Add tests in `_bronze.yml`:

```yaml
models:
  - name: bronze_contacts_from_ai
    description: "Contacts extracted from Gemini AI analysis JSONB"
    tests:
      - dbt_utils.recency:
          datepart: day
          field: extracted_at
          interval: 7
    columns:
      - name: person_id
        tests:
          - not_null
      - name: full_name
        tests:
          - not_null
```

## Performance

**Python script:**
- Loads entire events_text_ai table into memory
- Processes all rows every run
- Manual batching required

**dbt incremental:**
- Only processes new records
- SQL-based (database does the work)
- No memory constraints
- Parallel execution possible

## Rollback Plan

If needed, can run both in parallel:
```bash
# Old way (Python)
python scripts/datasources/gemini/load_meeting_transcripts_bronze.py \
  --table bronze_contacts_python

# New way (dbt)
dbt run --select bronze_contacts_from_ai

# Compare results
psql -c "SELECT COUNT(*) FROM bronze.bronze_contacts_python"
psql -c "SELECT COUNT(*) FROM bronze.bronze_contacts_from_ai"
```

## Next Steps

1. ✅ Review example models (`bronze_contacts_from_ai.sql`, `bronze_decisions_from_ai.sql`)
2. Create remaining bronze models:
   - `bronze_topics_from_ai.sql`
   - `bronze_organizations_meetings_from_ai.sql`
   - `bronze_bills_from_ai.sql`
   - `bronze_causes_from_ai.sql`
   - `bronze_financial_items_from_ai.sql`
3. Update staging models to reference new dbt models
4. Test incremental runs
5. Deprecate Python extraction script
6. Update documentation

## Questions?

- How do I handle deduplication? → Use `unique_key` config
- What if JSONB structure changes? → Update the model SQL
- Can I still use Python for initial load? → Yes, for backward compatibility
- How do I backfill? → Use `dbt run --select <model> --full-refresh`
