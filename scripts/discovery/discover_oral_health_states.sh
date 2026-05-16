#!/bin/bash
# Discover all jurisdictions in oral health focus states
# States: AL, GA, IN, MA, WA, WI

set -e

cd /home/developer/projects/open-navigator
source .venv/bin/activate

# Load environment variables from .env
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

echo "=========================================="
echo "DISCOVERING ORAL HEALTH FOCUS STATES"
echo "=========================================="
echo ""

STATES=("AL" "GA" "IN" "MA" "WA" "WI")

for STATE in "${STATES[@]}"; do
    echo "=========================================="
    echo "Discovering ${STATE}..."
    echo "=========================================="
    
    # Build command with optional YouTube API key
    CMD="python scripts/discovery/archive/comprehensive_discovery_pipeline.py --state ${STATE} --all --max-concurrent 5"
    
    if [ ! -z "${YOUTUBE_API_KEY}" ]; then
        CMD="${CMD} --youtube-api-key ${YOUTUBE_API_KEY}"
    fi
    
    eval $CMD
    
    echo ""
    echo "✅ ${STATE} complete!"
    echo ""
    
    # Small delay between states to avoid rate limits
    sleep 5
done

echo "=========================================="
echo "ALL ORAL HEALTH STATES DISCOVERED!"
echo "=========================================="
echo ""
echo "Results saved to:"
echo "  - data/gold/jurisdictions_details.parquet (gold layer)"
echo "  - data/bronze/discovered_sources/ (detailed JSON)"
echo ""
