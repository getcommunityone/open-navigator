# Gemini One-Time Scripts & Migrations

This directory contains one-time migration scripts, backfill utilities, and cleanup tools that were used during development but are not part of the regular data processing workflow.

## Migration Scripts

### Database Schema Migrations

- **`migrate_multimodel_support.py`** - Adds multi-model support to bronze tables
  - Drops old UNIQUE constraints
  - Adds new constraints with `source_ai_model` column
  - Enables storing multiple AI model extractions of same decision
  - Status: ✅ Applied (May 5, 2026)

- **`migrate_add_ntee_to_topics.py`** - Adds NTEE columns to bronze_topics table
  - Adds `ntee_code`, `ntee_major_group`, `ntee_category_label` columns
  - Adds `primary_org_ids` to bronze_decisions
  - Status: ✅ Applied

- **`migrate_add_secondary_ntee.py`** - Adds secondary NTEE fields
  - Adds secondary NTEE code support for topics spanning multiple domains
  - Status: ✅ Applied

## Backfill Scripts

### Data Population & Enrichment

- **`backfill_ntee_from_arguments.py`** - Backfills NTEE codes from arguments
  - Extracts organization IDs from decision arguments
  - Populates `primary_org_ids` in bronze_decisions
  - Enriches topics with NTEE codes from linked organizations
  - Status: ✅ Run once

- **`backfill_ntee_to_topics.py`** - Backfills NTEE to bronze_topics
  - Populates NTEE fields in topics table from organizations
  - Status: ✅ Run once

- **`repopulate_ntee_codes.py`** - Repopulates all NTEE codes
  - Comprehensive repopulation of NTEE fields across bronze tables
  - Uses organization mappings and topic analysis
  - Status: ✅ Run once

- **`infer_ntee_from_topics.py`** - Infers NTEE codes using LLM
  - For topics where organizations don't have NTEE codes
  - Uses Gemini to classify topics into NTEE categories
  - Status: ✅ Run once

## Cleanup Utilities

- **`cleanup_null_records.py`** - Cleans up null records
  - Removes records with null `raw_response` (failed API calls)
  - Helps maintain data quality
  - Status: Run as needed

## Usage

These scripts are **not part of the regular workflow**. They were used during specific development phases and should only be re-run if:

1. Database schema needs to be migrated again (e.g., fresh install)
2. Historical data needs to be backfilled after a schema change
3. Data cleanup is required

## Regular Workflow Scripts

For regular data processing, use the scripts in the parent directory:
- `analyze_meeting_transcripts.py` - Main analysis pipeline
- `extract_to_bronze.py` - Extract to bronze tables
- `compare_model_extractions.py` - Compare model outputs
- `moa_synthesize.py` - Mixture-of-Agents synthesis

## Re-Running Migrations

If you need to apply migrations to a fresh database:

```bash
# 1. Apply multi-model support
python migrations/migrate_multimodel_support.py

# 2. Add NTEE columns
python migrations/migrate_add_ntee_to_topics.py

# 3. Add secondary NTEE
python migrations/migrate_add_secondary_ntee.py

# 4. Backfill data (if historical data exists)
python migrations/backfill_ntee_from_arguments.py
python migrations/repopulate_ntee_codes.py
```

## Warning

⚠️ **Do not run these scripts on production data without understanding their impact.** Some scripts modify or delete data. Always test on a development database first.
