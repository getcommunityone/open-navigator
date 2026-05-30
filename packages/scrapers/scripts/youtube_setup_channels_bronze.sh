#!/bin/bash
# Quick setup script for YouTube channels bronze migration
# Run this to set up the complete pipeline

set -e

echo "=================================="
echo "YouTube Channels Bronze Migration"
echo "=================================="
echo ""

# 1. Create bronze table
echo "Step 1: Creating bronze table..."
psql -h localhost -p 5433 -U postgres -d open_navigator_bronze \
  -f packages/hosting/scripts/neon/migrations/002_create_bronze_events_channels.sql

# 2. Import foreign table
echo ""
echo "Step 2: Importing foreign table to production..."
psql -h localhost -p 5433 -U postgres -d open_navigator <<EOF
BEGIN;
IMPORT FOREIGN SCHEMA public 
    LIMIT TO (bronze_events_channels)
    FROM SERVER bronze_server 
    INTO bronze;
COMMIT;
EOF

# 3. Load sample data (just a few states for testing)
echo ""
echo "Step 3: Loading sample data to bronze..."
python packages/scrapers/src/scrapers/youtube/load_youtube_channels_bronze.py \
  --states AL,MA \
  --auto-flag

# 4. Run dbt pipeline
echo ""
echo "Step 4: Running dbt pipeline..."
cd dbt_project
dbt run --select stg_bronze_events_channels
dbt run --select int_events_channels_enriched
dbt run --select events_channels_search

# 5. Verify results
echo ""
echo "Step 5: Verifying results..."
cd ..
psql -h localhost -p 5433 -U postgres -d open_navigator <<EOF
SELECT 
    COUNT(*) as total_channels,
    COUNT(*) FILTER (WHERE is_government = TRUE) as govt_channels,
    COUNT(*) FILTER (WHERE in_localview = TRUE) as localview_channels,
    COUNT(*) FILTER (WHERE flagged_as_junk = TRUE) as flagged_junk,
    ROUND(AVG(quality_score)::numeric, 2) as avg_quality_score
FROM events_channels_search;
EOF

echo ""
echo "✓ Migration complete!"
echo ""
echo "Next steps:"
echo "  1. Review sample data in events_channels_search"
echo "  2. Load more states: python packages/scrapers/src/scrapers/youtube/load_youtube_channels_bronze.py --states GA,IN,WA,WI --auto-flag"
echo "  3. Run dbt after each load: cd dbt_project && dbt run --select events_channels_search"
echo "  4. Add dbt tests: dbt test --select events_channels_search"
