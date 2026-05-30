# YouTube Channels Bronze Migration - File Summary

## Files Created

### 1. Database Migration
**File:** `packages/hosting/scripts/neon/migrations/002_create_bronze_events_channels.sql`
- Creates `bronze_events_channels` table in bronze database
- Adds indexes for performance
- Includes instructions for importing foreign table

### 2. Bronze Loading Script
**File:** `packages/scrapers/src/scrapers/youtube/load_youtube_channels_bronze.py`
- Loads channels from `jurisdictions_details_search` to bronze
- Validates against LocalView and WikiData
- Auto-flags junk channels (news, entertainment)
- **Key difference:** Writes to `open_navigator_bronze.bronze_events_channels` instead of production

### 3. dbt Staging Model
**File:** `dbt_project/models/staging/stg_bronze_events_channels.sql`
- Reads from `bronze.bronze_events_channels` (via FDW)
- Basic data quality filters
- Materialized as view

### 4. dbt Intermediate Model
**File:** `dbt_project/models/intermediate/int_events_channels_enriched.sql`
- Adds event statistics (count, date ranges)
- Calculates quality scores (0-1) based on validation
- Determines government likelihood
- Adds activity status (active/stale/inactive)
- Materialized as view

### 5. dbt Mart Model
**File:** `dbt_project/models/marts/events_channels_search.sql`
- Production-ready table replacing direct-loaded version
- Filters out junk (unless in LocalView)
- Adds indexes for API performance
- Materialized as table

### 6. dbt Configuration
**File:** `dbt_project/models/staging/_staging.yml`
- Added `bronze_events_channels` source definition
- Documented all columns

**File:** `dbt_project/models/intermediate/_intermediate.yml`
- Added `int_events_channels_enriched` model definition
- Added data quality tests

### 7. Documentation
**File:** `website/docs/deployment/youtube-channels-bronze-migration.md`
- Complete migration guide
- Step-by-step instructions
- Quality scoring explanation
- Validation procedures
- Rollback plan

### 8. Setup Script
**File:** `packages/scrapers/src/scrapers/youtube/setup_channels_bronze.sh`
- Automated setup script
- Runs all migration steps
- Loads sample data
- Verifies results

## Quick Start

```bash
# Run complete migration
./packages/scrapers/src/scrapers/youtube/setup_channels_bronze.sh

# Or manually:

# 1. Create bronze table
psql -h localhost -p 5433 -U postgres -d open_navigator_bronze \
  -f packages/hosting/scripts/neon/migrations/002_create_bronze_events_channels.sql

# 2. Import foreign table
psql -h localhost -p 5433 -U postgres -d open_navigator <<EOF
IMPORT FOREIGN SCHEMA public 
    LIMIT TO (bronze_events_channels)
    FROM SERVER bronze_server 
    INTO bronze;
EOF

# 3. Load data
python packages/scrapers/src/scrapers/youtube/load_youtube_channels_bronze.py \
  --states AL,MA \
  --auto-flag

# 4. Run dbt
cd dbt_project
dbt run --select +events_channels_search
```

## Data Flow

```
jurisdictions_details_search (production)
    ↓ (read by load_youtube_channels_bronze.py)
bronze_events_channels (bronze database)
    ↓ (Foreign Data Wrapper)
bronze.bronze_events_channels (production, foreign table)
    ↓ (dbt source)
stg_bronze_events_channels (view)
    ↓ (dbt ref)
int_events_channels_enriched (view + enrichments)
    ↓ (dbt ref + filters)
events_channels_search (table, indexed)
```

## Key Improvements

✅ **Bronze separation:** Raw data isolated from production  
✅ **dbt transformations:** All logic in version-controlled SQL  
✅ **Quality scoring:** 0-1 score based on validation sources  
✅ **Activity tracking:** Know which channels are active/stale  
✅ **Junk filtering:** Auto-flag non-government channels  
✅ **Testable:** dbt tests ensure data quality  
✅ **Auditable:** Clear lineage from bronze to mart  

## Validation Sources

| Source | Quality Score | Description |
|--------|---------------|-------------|
| WikiData | 1.0 | Official government channel |
| LocalView + jurisdictions | 0.9 | Multiple validations |
| LocalView only | 0.85 | Validated by LocalView |
| jurisdictions only | 0.7 | Found in jurisdiction data |
| Unknown | 0.5 | Needs validation |

## Next Steps

1. Test with sample states (AL, MA)
2. Verify data quality
3. Load all states
4. Add dbt tests
5. Update API documentation
6. Schedule weekly updates

## Rollback

If issues occur:

```bash
# Restore old process
python packages/scrapers/src/scrapers/youtube/load_channels.py

# Drop new table
psql -h localhost -p 5433 -U postgres -d open_navigator \
  -c "DROP TABLE IF EXISTS events_channels_search;"
```

## Support

See full documentation:
- [Migration Guide](../website/docs/deployment/youtube-channels-bronze-migration.md)
- [dbt README](../dbt_project/README.md)
- [Bronze Strategy](../website/docs/development/dbt-etl-strategy.md)
