#!/bin/bash
# Quick-start script to load and update meeting data for priority states
# States: AL, GA, IN, MA, MT, WA, WI

set -e  # Exit on error

STATES="AL,GA,IN,MA,MT,WA,WI"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=========================================================================="
echo "🏛️  MEETING DATA LOADER FOR PRIORITY STATES"
echo "=========================================================================="
echo ""
echo "States: $STATES"
echo "Project: $PROJECT_ROOT"
echo ""

# Check virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Virtual environment not activated. Activating..."
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Step 1: Check current data status
echo "=========================================================================="
echo "Step 1: Checking Current Data Status"
echo "=========================================================================="
python "$PROJECT_ROOT/scripts/localview/check_meeting_data.py" --states "$STATES"

echo ""
echo "=========================================================================="
echo "Next Steps"
echo "=========================================================================="
echo ""
echo "Choose what you want to do:"
echo ""
echo "1. Download LocalView Historical Data (2006-2023)"
echo "   - Visit: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM"
echo "   - Download CSV files to: $PROJECT_ROOT/data/cache/localview/"
echo "   - Then run: python scripts/datasources/localview/localview_ingestion.py"
echo ""
echo "2. Scrape Recent Meetings from YouTube (2024-2026)"
echo "   - Get YouTube API key: https://console.cloud.google.com/apis/credentials"
echo "   - Add to .env: YOUTUBE_API_KEY=your_key_here"
echo "   - Run this script with --scrape flag (scrapes last 850 days)"
echo ""
echo "3. Use Existing OpenStates Legislative Events"
echo "   - Already loaded for all 7 states"
echo "   - Contains committee hearings, sessions, participants"
echo "   - See: data/gold/states/{STATE}/events_events.parquet"
echo ""

# Check for scrape flag
if [[ "$1" == "--scrape" ]]; then
    echo "=========================================================================="
    echo "Starting YouTube Scraping (Recent Meetings 2024-2026)"
    echo "=========================================================================="
    
    # Check for YouTube API key
    if ! grep -q "YOUTUBE_API_KEY=" "$PROJECT_ROOT/.env" 2>/dev/null; then
        echo "❌ YOUTUBE_API_KEY not found in .env"
        echo ""
        echo "To get an API key:"
        echo "1. Go to: https://console.cloud.google.com/apis/credentials"
        echo "2. Create project (if needed)"
        echo "3. Enable YouTube Data API v3"
        echo "4. Create credentials -> API Key"
        echo "5. Add to .env: YOUTUBE_API_KEY=your_key_here"
        echo ""
        exit 1
    fi
    
    echo "✅ YouTube API key found"
    echo ""
    
    # Scrape YouTube channels
    echo "Scraping municipal YouTube channels..."
    # --since-days 850 covers from Jan 1, 2024 to now (May 2026)
    python "$PROJECT_ROOT/scripts/localview/scrape_youtube_channels.py" \
        --states "$STATES" \
        --since-days 850
    
    echo ""
    echo "✅ Scraping complete!"
    echo ""
    
    # Extract transcripts
    echo "=========================================================================="
    echo "Extracting Transcripts"
    echo "=========================================================================="
    python "$PROJECT_ROOT/scripts/localview/extract_transcripts.py" \
        --states "$STATES"
    
    echo ""
    echo "✅ Transcript extraction complete!"
    echo ""
    
    # Extract contacts
    echo "=========================================================================="
    echo "Extracting Contacts from Meeting Transcripts"
    echo "=========================================================================="
    python "$PROJECT_ROOT/scripts/manage_contacts.py" extract \
        --states "$STATES" \
        --batch-size 1000
    
    echo ""
    echo "✅ Contact extraction complete!"
    echo ""
    
    # Final status
    echo "=========================================================================="
    echo "Final Data Status"
    echo "=========================================================================="
    python "$PROJECT_ROOT/scripts/localview/check_meeting_data.py" --states "$STATES"
fi

if [[ "$1" == "--localview" ]]; then
    echo "=========================================================================="
    echo "Loading LocalView Historical Data"
    echo "=========================================================================="
    
    # Check for LocalView files
    if [[ ! -f "$PROJECT_ROOT/data/cache/localview/municipalities.csv" ]] && \
       [[ ! -f "$PROJECT_ROOT/data/cache/localview/meetings.csv" ]]; then
        echo "❌ LocalView CSV files not found in data/cache/localview/"
        echo ""
        echo "Download files from:"
        echo "https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM"
        echo ""
        echo "Expected files:"
        echo "  - municipalities.csv (or municipalities.tab)"
        echo "  - meetings.csv (or meetings.tab)"
        echo "  - videos.csv (or videos.tab)"
        echo ""
        exit 1
    fi
    
    echo "✅ LocalView files found"
    echo ""
    
    # Run ingestion
    python "$PROJECT_ROOT/scripts/datasources/localview/localview_ingestion.py"
    
    echo ""
    echo "✅ LocalView ingestion complete!"
    echo ""
    
    # Filter for priority states
    echo "Filtering for priority states ($STATES)..."
    python "$PROJECT_ROOT/scripts/data/organize_meetings_by_state.py" \
        --states "$STATES"
    
    echo ""
    echo "✅ Data organized by state!"
    echo ""
    
    # Final status
    echo "=========================================================================="
    echo "Final Data Status"
    echo "=========================================================================="
    python "$PROJECT_ROOT/scripts/localview/check_meeting_data.py" --states "$STATES"
fi

echo ""
echo "=========================================================================="
echo "📚 Documentation"
echo "=========================================================================="
echo ""
echo "For more details, see:"
echo "  - website/docs/guides/loading-meeting-data.md"
echo "  - docs/LOCALVIEW_INTEGRATION_GUIDE.md"
echo "  - docs/CONTACTS_MEETINGS_WORKFLOW.md"
echo ""
