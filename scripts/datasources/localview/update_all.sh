#!/bin/bash
# Update All LocalView Data Sources
#
# Runs all LocalView scraper scripts to update the dataset

set -e

echo "🏛️  LocalView Data Update Pipeline"
echo "===================================="
echo ""

cd "$(dirname "$0")/../.."

# Activate virtual environment
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
elif [ -f venv/bin/activate ]; then
    source venv/bin/activate
fi

# Check for API key
if [ -z "$YOUTUBE_API_KEY" ]; then
    echo "⚠️  YOUTUBE_API_KEY not set"
    echo ""
    echo "Add to .env file:"
    echo "  YOUTUBE_API_KEY=your_api_key_here"
    echo ""
    echo "Get an API key at: https://console.cloud.google.com/apis/credentials"
    exit 1
fi

echo "✅ YouTube API key found"
echo ""

# Step 1: Scrape YouTube channels
echo "📹 Step 1: Scraping YouTube channels..."
python scripts/localview/scrape_youtube_channels.py --update --since-days 60

# Step 2: Extract transcripts
echo ""
echo "📝 Step 2: Extracting transcripts..."
python scripts/localview/extract_transcripts.py --year $(date +%Y)

# Step 3: Load into database
echo ""
echo "💾 Step 3: Loading into database..."
if [ -f discovery/localview_ingestion.py ]; then
    python discovery/localview_ingestion.py
else
    echo "⚠️  Ingestion script not found, skipping database load"
fi

echo ""
echo "✅ LocalView update complete!"
echo ""
echo "Data saved to:"
echo "  - data/cache/localview/videos_$(date +%Y).csv"
echo "  - data/cache/localview/transcripts/*.txt"
