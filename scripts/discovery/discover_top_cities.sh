#!/bin/bash
# Discover top N largest jurisdictions nationwide

set -e

cd /home/developer/projects/open-navigator
source .venv/bin/activate

# Load environment variables from .env
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Default to top 100, can override with argument
TOP_N=${1:-100}

echo "=========================================="
echo "DISCOVERING TOP ${TOP_N} JURISDICTIONS"
echo "=========================================="
echo ""

# Build command with optional YouTube API key
CMD="python scripts/discovery/archive/comprehensive_discovery_pipeline.py --top ${TOP_N} --max-concurrent 5"

if [ ! -z "${YOUTUBE_API_KEY}" ]; then
    CMD="${CMD} --youtube-api-key ${YOUTUBE_API_KEY}"
fi

eval $CMD

echo ""
echo "=========================================="
echo "TOP ${TOP_N} JURISDICTIONS DISCOVERED!"
echo "=========================================="
echo ""
echo "Results saved to:"
echo "  - data/gold/jurisdictions_details.parquet (gold layer)"
echo "  - data/bronze/discovered_sources/ (detailed JSON)"
echo ""
