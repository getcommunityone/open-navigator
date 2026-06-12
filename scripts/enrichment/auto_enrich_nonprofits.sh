#!/bin/bash
# Automated nonprofit enrichment with BigQuery data

# Load environment variables
set -a
source .env
set +a

# Run enrichment for all states
for state in MA AL GA WA WI; do
    echo "🔄 Enriching $state nonprofits..."
    python -m scrapers.irs.enrich_nonprofits_bigquery \
        --input data/gold/states/$state/nonprofits_organizations.parquet \
        --update-in-place \
        --project ${GCP_PROJECT_ID:-998485965463}
    
    if [ $? -eq 0 ]; then
        echo "✅ $state enrichment complete"
    else
        echo "❌ $state enrichment failed"
        exit 1
    fi
done

echo "🎉 All states enriched successfully!"
