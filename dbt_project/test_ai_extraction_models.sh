#!/bin/bash
# Test dbt AI extraction models

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║       Testing dbt AI Extraction Models (Bronze Layer)         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -f "../.venv/bin/activate" ]; then
    source ../.venv/bin/activate
fi

echo "📊 Source table (input):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
psql -h localhost -p 5433 -U postgres -d open_navigator -c "
SELECT 
    'bronze_events_analysis_ai' as table_name,
    COUNT(*) as row_count,
    pg_size_pretty(pg_total_relation_size('bronze.bronze_events_analysis_ai')) as size
FROM bronze.bronze_events_analysis_ai;
"

echo ""
echo "🔨 Running dbt models (full refresh)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
dbt run --select tag:ai-extraction --full-refresh

echo ""
echo "✅ Results (output tables):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
psql -h localhost -p 5433 -U postgres -d open_navigator -c "
SELECT 'bronze_contacts_from_ai' as table_name, COUNT(*) as row_count FROM bronze.bronze_contacts_from_ai
UNION ALL
SELECT 'bronze_decisions_from_ai', COUNT(*) FROM bronze.bronze_decisions_from_ai
UNION ALL
SELECT 'bronze_topics_from_ai', COUNT(*) FROM bronze.bronze_topics_from_ai
UNION ALL
SELECT 'bronze_organizations_from_ai', COUNT(*) FROM bronze.bronze_organizations_from_ai
UNION ALL
SELECT 'bronze_bills_from_ai', COUNT(*) FROM bronze.bronze_bills_from_ai
UNION ALL
SELECT 'bronze_causes_from_ai', COUNT(*) FROM bronze.bronze_causes_from_ai
UNION ALL
SELECT 'bronze_financial_items_from_ai', COUNT(*) FROM bronze.bronze_financial_items_from_ai
ORDER BY table_name;
"

echo ""
echo "📊 Compare with old Python-generated tables:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
psql -h localhost -p 5433 -U postgres -d open_navigator -c "
SELECT 
    'bronze_contacts (Python)' as table_name, 
    COUNT(*) as row_count,
    MAX(extracted_at) as last_updated
FROM bronze.bronze_contacts
UNION ALL
SELECT 
    'bronze_contacts_from_ai (dbt)', 
    COUNT(*),
    MAX(extracted_at)
FROM bronze.bronze_contacts_from_ai
ORDER BY table_name;
"

echo ""
echo "✅ Test complete!"
echo ""
echo "Next steps:"
echo "  1. Verify row counts match between Python and dbt versions"
echo "  2. Test incremental run: dbt run --select tag:ai-extraction"
echo "  3. Update staging models to use dbt bronze models"
echo "  4. Deprecate Python script: mv load_meeting_transcripts_bronze.py{,.deprecated}"
