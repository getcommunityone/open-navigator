#!/bin/bash
#
# Enrich nonprofits with BigQuery officer data - NO AUTHENTICATION REQUIRED
#
# This script uses the web-based approach that doesn't need gcloud auth:
# 1. Export SQL query
# 2. Run in BigQuery web console
# 3. Merge CSV results back into parquet files
#

set -e

echo "=========================================="
echo "BigQuery Nonprofit Enrichment (No Auth)"
echo "=========================================="
echo ""

# Check if input file exists
if [ ! -f "data/gold/states/MA/nonprofits_organizations.parquet" ]; then
    echo "❌ Error: Massachusetts nonprofit data not found"
    echo "   Expected: data/gold/states/MA/nonprofits_organizations.parquet"
    exit 1
fi

echo "✅ Found nonprofit data file"
echo ""

# Step 1: Export SQL query
echo "📝 Step 1: Exporting SQL query..."
python scripts/enrich_nonprofits_bigquery.py \
    --input data/gold/states/MA/nonprofits_organizations.parquet \
    --export-sql data/cache/bigquery_ma_officers.sql

if [ $? -eq 0 ]; then
    echo "✅ SQL query exported to: data/cache/bigquery_ma_officers.sql"
else
    echo "❌ Failed to export SQL query"
    exit 1
fi

echo ""
echo "=========================================="
echo "⚠️  MANUAL STEP REQUIRED"
echo "=========================================="
echo ""
echo "1. Open BigQuery Console:"
echo "   https://console.cloud.google.com/bigquery"
echo ""
echo "2. Click 'Compose New Query'"
echo ""
echo "3. Copy the SQL from:"
echo "   data/cache/bigquery_ma_officers.sql"
echo ""
echo "4. Run the query (it's free - public dataset)"
echo ""
echo "5. Click 'Save Results' → 'CSV (local file)'"
echo ""
echo "6. Save to:"
echo "   data/cache/bigquery_ma_results.csv"
echo ""
echo "7. Come back here and press ENTER to continue..."
echo ""

read -p "Press ENTER when you've downloaded the CSV..."

# Step 2: Check if CSV exists
if [ ! -f "data/cache/bigquery_ma_results.csv" ]; then
    echo "❌ Error: CSV file not found at data/cache/bigquery_ma_results.csv"
    echo "   Please download the query results and try again"
    exit 1
fi

echo ""
echo "✅ CSV file found!"
echo ""

# Step 3: Merge CSV results
echo "📊 Step 3: Merging BigQuery results into parquet file..."
python scripts/enrich_nonprofits_bigquery.py \
    --input data/gold/states/MA/nonprofits_organizations.parquet \
    --from-csv data/cache/bigquery_ma_results.csv \
    --update-in-place

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ SUCCESS!"
    echo "=========================================="
    echo ""
    echo "Massachusetts nonprofits enriched with officer data!"
    echo ""
    echo "Next steps:"
    echo "1. Create contact tables:"
    echo "   python -c \"from ingestion.publication.gold.create_contacts_gold_tables import ContactsGoldTableCreator; ContactsGoldTableCreator().create_contacts_nonprofit_officers()\""
    echo ""
    echo "2. Search officers:"
    echo "   curl 'http://localhost:8000/api/search/?q=CEO&state=MA'"
    echo ""
else
    echo "❌ Failed to merge CSV results"
    exit 1
fi
