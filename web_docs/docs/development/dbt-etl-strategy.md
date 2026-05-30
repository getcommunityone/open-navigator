---
sidebar_position: 11
---

# dbt + Python Hybrid ETL Strategy

## Overview

Open Navigator uses a **hybrid approach** for ETL:
- **Python scripts** for data ingestion, API calls, AI analysis, and file generation
- **dbt (data build tool)** for SQL-based transformations in the warehouse

This combines the flexibility of Python with the testing, documentation, and dependency management of dbt.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ PYTHON ETL (Data Ingestion)                                 │
├─────────────────────────────────────────────────────────────┤
│ • scripts/datasources/*/load_*.py                           │
│ • API calls (OpenStates, IRS, Census, YouTube)              │
│ • AI analysis (Gemini extraction from transcripts)          │
│ • File processing (990 XML, PDFs, videos)                   │
│ • Parquet generation (gold tables)                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ BRONZE TABLES (PostgreSQL - Raw Extractions)                │
├─────────────────────────────────────────────────────────────┤
│ • bronze_contacts, bronze_organizations, bronze_bills       │
│ • bronze_decisions, bronze_financial_items                  │
│ • Direct AI output, not yet deduplicated                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ dbt TRANSFORMATIONS (SQL-based)                             │
├─────────────────────────────────────────────────────────────┤
│ • Entity resolution & deduplication                         │
│ • Data quality tests                                        │
│ • Incremental materializations                              │
│ • Stats aggregation                                         │
│ • Junction table creation                                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ PRODUCTION TABLES (Neon PostgreSQL - API-ready)             │
├─────────────────────────────────────────────────────────────┤
│ • contact, bills_search, event              │
│ • organization_nonprofit                            │
│ • Junction tables (bills_meetings, attendance)              │
│ • jurisdiction_state_aggregate                                          │
└─────────────────────────────────────────────────────────────┘
```

## Why Hybrid?

### Use Python When You Need To:

✅ **Make external API calls**
- OpenStates Bulk API
- IRS Data Retrieval
- Census API
- YouTube Data API

✅ **Process files**
- Download 990 XML files
- Parse PDF documents
- Extract video transcripts

✅ **Run AI/ML workloads**
- Gemini API for transcript analysis
- Sentiment analysis
- Topic classification

✅ **Generate files for distribution**
- Parquet files for HuggingFace
- State-level gold tables
- Export to Delta Lake

### Use dbt When You Need To:

✅ **Transform data IN the warehouse**
- Bronze → Production transformations
- Entity resolution (fuzzy matching in SQL)
- Deduplication logic

✅ **Maintain data quality**
- Uniqueness tests
- Not-null constraints
- Relationship validation
- Custom business logic tests

✅ **Document transformations**
- Column-level descriptions
- Data lineage graphs
- Transformation logic

✅ **Incremental updates**
- Process only new records
- Efficient full refreshes
- Dependency management

## dbt Project Structure

```
dbt_project/
├── dbt_project.yml               # Project configuration
├── profiles.yml                  # Database connections
├── models/
│   ├── staging/                  # Stage bronze data
│   │   ├── _staging.yml
│   │   ├── stg_bronze_contacts.sql
│   │   ├── stg_bronze_organizations.sql
│   │   ├── stg_bronze_bills.sql
│   │   └── stg_bronze_decisions.sql
│   │
│   ├── intermediate/             # Clean and deduplicate
│   │   ├── _intermediate.yml
│   │   ├── int_contacts_deduped.sql
│   │   ├── int_bills_matched.sql
│   │   └── int_orgs_resolved.sql
│   │
│   └── marts/                    # Production-ready tables
│       ├── _marts.yml
│       ├── contact.sql
│       ├── bills_search.sql
│       ├── bills_meetings.sql        # Junction table
│       ├── contacts_meeting_attendance.sql
│       └── jurisdiction_state_aggregate.sql
│
├── tests/                        # Custom tests
│   ├── assert_no_duplicate_contacts.sql
│   ├── assert_valid_datasources.sql
│   └── assert_confidence_scores.sql
│
├── macros/                       # Reusable SQL functions
│   ├── fuzzy_match_name.sql
│   ├── normalize_bill_number.sql
│   └── calculate_confidence.sql
│
├── snapshots/                    # Track changes over time
│   └── contacts_snapshot.sql
│
└── analyses/                     # Ad-hoc queries
    └── duplicate_analysis.sql
```

## Example dbt Models

### Staging: Clean Bronze Data

```sql
-- models/staging/stg_bronze_contacts.sql
{{ config(
    materialized='view'
) }}

SELECT
    id as bronze_contact_id,
    source_event_id,
    source_ai_model,
    person_id,
    TRIM(full_name) as full_name,
    LOWER(TRIM(full_name)) as full_name_normalized,
    role,
    org_id,
    party_affiliation,
    is_lobbyist,
    lobbyist_registration_number,
    wikidata_qid,
    appeared_as,
    extracted_at
FROM {{ source('bronze', 'bronze_contacts') }}
WHERE full_name IS NOT NULL
  AND LENGTH(TRIM(full_name)) > 3
```

### Intermediate: Deduplicate

```sql
-- models/intermediate/int_contacts_deduped.sql
{{ config(
    materialized='table'
) }}

WITH ranked_contacts AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY full_name_normalized, org_id 
            ORDER BY extracted_at DESC
        ) as rn
    FROM {{ ref('stg_bronze_contacts') }}
)

SELECT * FROM ranked_contacts
WHERE rn = 1
```

### Marts: Production Table

```sql
-- models/marts/contact.sql
{{ config(
    materialized='incremental',
    unique_key='id',
    on_schema_change='sync_all_columns'
) }}

WITH bronze_contacts AS (
    SELECT * FROM {{ ref('int_contacts_deduped') }}
),

existing_contacts AS (
    SELECT 
        id,
        name,
        datasource,
        datasource_id,
        confidence_score,
        last_updated
    FROM {{ ref('contact') }}
    WHERE datasource != 'gemini_ai_extraction'  -- Keep authoritative sources
),

new_ai_contacts AS (
    SELECT
        bc.full_name as name,
        bc.role as title,
        bc.org_id as organization_name,
        NULL as organization_ein,
        NULL as email,
        NULL as phone,
        NULL as street_address,
        NULL as city,
        NULL as state_code,
        NULL as state,
        NULL as zip_code,
        CASE 
            WHEN bc.is_lobbyist THEN 'lobbyist'
            ELSE 'government_official'
        END as role_type,
        NULL::BIGINT as compensation,
        NULL::DECIMAL as hours_per_week,
        'gemini_ai_extraction' as datasource,
        COALESCE(bc.wikidata_qid, bc.person_id) as datasource_id,
        {{ calculate_confidence('gemini_ai_extraction') }} as confidence_score,
        FALSE as verified,
        FALSE as needs_review,
        NULL as verification_date,
        NULL as review_notes,
        CURRENT_TIMESTAMP as last_updated
    FROM bronze_contacts bc
    LEFT JOIN existing_contacts ec 
        ON LOWER(TRIM(bc.full_name)) = LOWER(TRIM(ec.name))
        AND ec.datasource IN ('openstates_api', 'irs_990')
    WHERE ec.id IS NULL  -- Don't override authoritative sources
    
    {% if is_incremental() %}
    AND bc.extracted_at > (SELECT MAX(last_updated) FROM {{ this }})
    {% endif %}
)

SELECT * FROM new_ai_contacts
```

## Data Quality Tests

### Schema Tests

```yaml
# models/marts/_marts.yml
version: 2

models:
  - name: contact
    description: "Searchable contacts from all data sources"
    columns:
      - name: id
        description: "Primary key"
        tests:
          - unique
          - not_null

      - name: name
        description: "Contact full name"
        tests:
          - not_null

      - name: datasource
        description: "Origin system"
        tests:
          - accepted_values:
              values: 
                - 'openstates_api'
                - 'irs_990'
                - 'gemini_ai_extraction'
                - 'localview'
                - 'manual_entry'

      - name: confidence_score
        description: "Data quality score (0.0-1.0)"
        tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: ">= 0.0 AND <= 1.0"
```

### Custom Tests

```sql
-- tests/assert_no_ai_overrides_authoritative.sql
-- Check that AI extractions didn't override authoritative sources

WITH ai_duplicates AS (
    SELECT 
        c1.id as ai_id,
        c1.name as ai_name,
        c1.datasource as ai_source,
        c2.id as auth_id,
        c2.name as auth_name,
        c2.datasource as auth_source
    FROM {{ ref('contact') }} c1
    JOIN {{ ref('contact') }} c2
        ON LOWER(TRIM(c1.name)) = LOWER(TRIM(c2.name))
        AND c1.datasource = 'gemini_ai_extraction'
        AND c2.datasource IN ('openstates_api', 'irs_990')
    WHERE c1.last_updated > c2.last_updated
)

SELECT * FROM ai_duplicates
```

## Macros for Reusable Logic

```sql
-- macros/calculate_confidence.sql
{% macro calculate_confidence(datasource) %}
    CASE 
        WHEN {{ datasource }} IN ('openstates_api', 'irs_bmf', 'irs_990') THEN 1.0
        WHEN {{ datasource }} IN ('localview', 'youtube_api') THEN 0.90
        WHEN {{ datasource }} = 'gemini_ai_extraction' THEN 0.60
        ELSE 0.50
    END
{% endmacro %}
```

```sql
-- macros/fuzzy_match_name.sql
{% macro fuzzy_match_name(name1, name2, threshold=0.85) %}
    -- PostgreSQL similarity extension
    similarity(
        LOWER(TRIM({{ name1 }})),
        LOWER(TRIM({{ name2 }}))
    ) >= {{ threshold }}
{% endmacro %}
```

## Running dbt

### Development

```bash
# Install dbt
pip install dbt-postgres

# Set up profiles (connection to Neon)
dbt debug

# Run all models
dbt run

# Run specific model
dbt run --select contact

# Run tests
dbt test

# Generate documentation
dbt docs generate
dbt docs serve
```

### Production

```bash
# Full refresh (rebuild everything)
dbt run --full-refresh

# Incremental only (process new records)
dbt run

# Run and test
dbt build

# Run specific tag
dbt run --select tag:daily
```

## Workflow Integration

### Combined Python + dbt Pipeline

```bash
#!/bin/bash
# scripts/run_full_etl.sh

set -e  # Exit on error

echo "🔄 Starting full ETL pipeline..."

# Step 1: Python ingestion
echo "📥 Step 1: Data ingestion (Python)"
python scripts/datasources/openstates/load_openstates_bulk.py
python scripts/datasources/irs/load_irs_bmf.py
python scripts/datasources/gemini/load_meeting_transcripts_bronze.py

# Step 2: dbt transformations
echo "🔧 Step 2: Transformations (dbt)"
cd dbt_project
dbt run --select staging+
dbt run --select intermediate+
dbt run --select marts+
dbt test

# Step 3: Python post-processing (if needed)
echo "📤 Step 3: Export to parquet (Python)"
cd ..
python scripts/data/export_to_gold_parquet.py

echo "✅ ETL pipeline complete!"
```

## Migration Strategy

### Phase 1: Core Transformations (Week 1)
- [ ] Set up dbt project
- [ ] Create staging models for bronze tables
- [ ] Implement contact transformation
- [ ] Add basic tests

### Phase 2: Entity Resolution (Week 2)
- [ ] Implement fuzzy matching in SQL
- [ ] Create intermediate deduplication models
- [ ] Add relationship tests
- [ ] Document lineage

### Phase 3: Full Production (Week 3)
- [ ] Migrate all bronze → production transformations
- [ ] Set up incremental models
- [ ] Create snapshots for change tracking
- [ ] Generate documentation site

### Phase 4: Optimization (Week 4)
- [ ] Performance tuning
- [ ] Add data quality alerts
- [ ] Set up CI/CD with dbt Cloud or GitHub Actions
- [ ] Train team on dbt workflows

## Best Practices

### 1. Keep Python for What It Does Best
- API calls
- File I/O
- AI/ML
- Complex business logic that's easier in Python

### 2. Use dbt for Warehouse Transformations
- SQL-first transformations
- Incremental processing
- Data quality testing
- Documentation generation

### 3. Clear Handoff Points
- Python loads → Bronze tables
- dbt transforms → Production tables
- Python exports → Parquet files

### 4. Test Everything
```yaml
# Every model should have tests
tests:
  - unique
  - not_null
  - relationships
  - custom_sql_test
```

### 5. Document As You Go
```yaml
description: |
  This model deduplicates contacts from AI extraction,
  prioritizing authoritative sources like OpenStates and IRS.
```

## Monitoring and Alerts

### dbt Cloud (Optional)
- Automatic scheduling
- Email alerts on test failures
- Web UI for documentation
- Lineage visualization

### Custom Alerts
```sql
-- models/quality/contacts_quality_check.sql
{{ config(
    severity='error'
) }}

SELECT 
    'AI extraction has low confidence records' as issue,
    COUNT(*) as affected_rows
FROM {{ ref('contact') }}
WHERE datasource = 'gemini_ai_extraction'
  AND confidence_score < 0.50
HAVING COUNT(*) > 100
```

## Resources

- [dbt Documentation](https://docs.getdbt.com/)
- [dbt Best Practices](https://docs.getdbt.com/guides/best-practices)
- [dbt Discourse Community](https://discourse.getdbt.com/)
- [Open Navigator Bronze Merge Strategy](./bronze-to-production-merge.md)

## Next Steps

1. **Initialize dbt project**: `dbt init open_navigator_dbt`
2. **Configure profiles.yml**: Add Neon PostgreSQL connection
3. **Create first model**: Start with `stg_bronze_contacts.sql`
4. **Run and test**: `dbt run && dbt test`
5. **Iterate**: Add more models incrementally
