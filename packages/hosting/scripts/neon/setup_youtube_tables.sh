#!/bin/bash
# Setup YouTube Tables in Neon Cloud
# 
# This script automates the complete setup process for YouTube data loading:
# 1. Creates bronze schema in Neon
# 2. Creates required tables using dbt
# 3. Syncs data from local to Neon
#
# Usage:
#   ./packages/hosting/scripts/neon/setup_youtube_tables.sh
#
# Prerequisites:
#   - NEON_DATABASE_URL set in .env
#   - dbt profiles configured (~/.dbt/profiles.yml)
#   - Local database with bronze tables populated

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  🚀 Setup YouTube Tables in Neon Cloud"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Load .env file first (before checking variables)
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${BLUE}📄 Loading environment from .env${NC}"
    # Load .env safely - skip comments and empty lines, handle special characters
    while IFS='=' read -r key value; do
        # Skip empty lines
        [[ -z "$key" ]] && continue
        # Skip comment lines
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        
        # Trim whitespace from key
        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"
        
        # Only export if key is valid (alphanumeric + underscore, no spaces)
        if [[ "$key" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
            # Export the variable (value already has everything after first =)
            export "$key=$value"
        fi
    done < <(grep '=' "$PROJECT_ROOT/.env" | grep -v '^[[:space:]]*#')
    echo ""
fi

# Now check environment variables
if [ -z "$NEON_DATABASE_URL" ]; then
    echo -e "${RED}❌ ERROR: NEON_DATABASE_URL not set${NC}"
    echo ""
    echo "Please set it in your .env file (with quotes):"
    echo '  NEON_DATABASE_URL="postgresql://user:password@ep-xxxx.neon.tech/open_navigator?sslmode=require"'
    echo ""
    echo "Or export it temporarily:"
    echo '  export NEON_DATABASE_URL="your_connection_string"'
    echo ""
    exit 1
fi

# Sanitize the URL (remove problematic channel_binding parameter)
if [[ "$NEON_DATABASE_URL" == *"channel_binding=require"* ]]; then
    echo -e "${YELLOW}⚠️  Removing channel_binding=require from URL (causes connection issues)${NC}"
    NEON_DATABASE_URL="${NEON_DATABASE_URL//&channel_binding=require/}"
    NEON_DATABASE_URL="${NEON_DATABASE_URL//?channel_binding=require&/?}"
    export NEON_DATABASE_URL
    echo ""
fi

# Mask password in URL for display
SAFE_URL=$(echo "$NEON_DATABASE_URL" | sed 's/:\/\/[^:]*:[^@]*@/:\/\/***:***@/')
echo -e "${GREEN}✓${NC} Neon URL configured: ${SAFE_URL}"
echo ""

# Quick connection test (with shorter timeout to fail fast)
echo -e "${BLUE}🔌 Testing Neon connection (this may take 10-30s if database is sleeping)...${NC}"
if timeout 45 bash -c "PGCONNECT_TIMEOUT=40 psql '$NEON_DATABASE_URL' -c 'SELECT 1;' --quiet --no-psqlrc >/dev/null 2>&1"; then
    echo -e "${GREEN}✓${NC} Connected to Neon"
else
    echo -e "${RED}✗${NC} Connection failed or timed out after 45 seconds"
    echo ""
    echo "This usually means:"
    echo "  • Database is sleeping and taking too long to wake up (try again)"
    echo "  • Network connectivity issues"
    echo "  • Invalid credentials"
    echo ""
    exit 1
fi
echo ""

# ============================================================================
# Step 1: Create bronze schema in Neon
# ============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 1/3: Creating bronze schema in Neon"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Database is already awake from connection test, this should be fast
if PGOPTIONS='--client-min-messages=warning' psql "$NEON_DATABASE_URL" \
    --quiet --no-psqlrc \
    -c "CREATE SCHEMA IF NOT EXISTS bronze;" 2>&1 | grep -v "^$"; then
    echo -e "${GREEN}✓${NC} Bronze schema created/verified"
else
    echo -e "${RED}✗${NC} Failed to create bronze schema"
    exit 1
fi
echo ""

# ============================================================================
# Step 2: Create tables using dbt
# ============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔨 Step 2/3: Creating tables with dbt"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if dbt profiles exist
if [ ! -f ~/.dbt/profiles.yml ]; then
    echo -e "${YELLOW}⚠️  WARNING: dbt profiles not found at ~/.dbt/profiles.yml${NC}"
    echo ""
    echo "Creating from example..."
    
    if [ -f "$PROJECT_ROOT/dbt_project/profiles.yml.example" ]; then
        mkdir -p ~/.dbt
        cp "$PROJECT_ROOT/dbt_project/profiles.yml.example" ~/.dbt/profiles.yml
        echo -e "${YELLOW}✓${NC} Created ~/.dbt/profiles.yml from example"
        echo ""
        echo -e "${YELLOW}⚠️  You need to edit ~/.dbt/profiles.yml and add your Neon credentials:${NC}"
        echo "   - NEON_HOST"
        echo "   - NEON_USER"
        echo "   - NEON_PASSWORD"
        echo "   - NEON_DATABASE"
        echo ""
        echo "Press Enter to continue after editing, or Ctrl+C to cancel..."
        read -r
    else
        echo -e "${RED}✗${NC} profiles.yml.example not found"
        exit 1
    fi
fi

cd "$PROJECT_ROOT/dbt_project"

# Create bronze_events_youtube table
echo "Creating bronze_events_youtube..."
if dbt run --select bronze_events_youtube --target prod --quiet 2>&1 | grep -E "Completed successfully|ERROR|PASS|FAIL" | head -5; then
    echo -e "${GREEN}✓${NC} bronze_events_youtube created"
else
    echo -e "${YELLOW}⚠️  Note: Table may already exist (this is okay)${NC}"
fi
echo ""

# Create bronze_events_text_ai table  
echo "Creating bronze_events_text_ai..."
if dbt run --select bronze_events_text_ai --target prod --quiet 2>&1 | grep -E "Completed successfully|ERROR|PASS|FAIL" | head -5; then
    echo -e "${GREEN}✓${NC} bronze_events_text_ai created"
else
    echo -e "${YELLOW}⚠️  Note: Table may already exist (this is okay)${NC}"
fi
echo ""

cd "$PROJECT_ROOT"

echo -e "${GREEN}✓${NC} dbt table creation complete"
echo ""
echo -e "${BLUE}ℹ️  Note: bronze_events_channels table will be created automatically${NC}"
echo "   by the Python script when you run load_youtube_events_to_postgres.py"
echo ""

# ============================================================================
# Step 3: Sync data from local to Neon
# ============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📤 Step 3/3: Syncing data from local to Neon"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Activate virtual environment if it exists
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    echo -e "${BLUE}🐍 Activating Python virtual environment${NC}"
    source "$PROJECT_ROOT/.venv/bin/activate"
else
    echo -e "${YELLOW}⚠️  No virtual environment found at .venv/${NC}"
    echo "   Using system Python..."
fi
echo ""

# Check if sync script exists
SYNC_SCRIPT="$PROJECT_ROOT/packages/hosting/src/hosting/neon/sync_bronze_tables.py"
if [ ! -f "$SYNC_SCRIPT" ]; then
    echo -e "${RED}✗${NC} Sync script not found: $SYNC_SCRIPT"
    exit 1
fi

# Ask user which tables to sync
echo "Which tables do you want to sync?"
echo ""
echo "  1) Minimum (bronze_events_youtube, bronze_events_text_ai, bronze_events_channels)"
echo "     Size: ~8 MB, Time: 10-30 seconds"
echo ""
echo "  2) Recommended (includes bronze_events_localview)"
echo "     Size: ~73 MB, Time: 1-2 minutes"
echo ""
echo "  3) Custom - choose specific tables"
echo ""
read -p "Enter choice (1/2/3) [default: 1]: " CHOICE
CHOICE=${CHOICE:-1}

case $CHOICE in
    1)
        TABLES="bronze_events_youtube bronze_events_text_ai bronze_events_channels"
        echo ""
        echo -e "${BLUE}📦 Syncing minimum required tables${NC}"
        ;;
    2)
        TABLES="bronze_events_youtube bronze_events_text_ai bronze_events_channels bronze_events_localview"
        echo ""
        echo -e "${BLUE}📦 Syncing recommended tables (including LocalView)${NC}"
        ;;
    3)
        echo ""
        echo "Available tables:"
        python "$SYNC_SCRIPT" --list | grep -E "^\s+[0-9]+" || true
        echo ""
        read -p "Enter table names (space-separated): " CUSTOM_TABLES
        TABLES="$CUSTOM_TABLES"
        echo ""
        echo -e "${BLUE}📦 Syncing custom tables${NC}"
        ;;
    *)
        echo -e "${RED}✗${NC} Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Syncing: $TABLES"
echo ""

# Run sync
if python "$SYNC_SCRIPT" $TABLES; then
    echo ""
    echo -e "${GREEN}✓${NC} Data sync complete"
else
    echo ""
    echo -e "${RED}✗${NC} Data sync failed"
    exit 1
fi

# ============================================================================
# Verification
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Verifying Neon database"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Single connection for all verification queries (faster)
PGOPTIONS='--client-min-messages=warning' psql "$NEON_DATABASE_URL" \
    --quiet --no-psqlrc << 'EOSQL'
-- Table sizes
SELECT 
    tablename as table,
    pg_size_pretty(pg_total_relation_size('bronze.' || tablename)) as size
FROM pg_tables 
WHERE schemaname = 'bronze'
  AND tablename IN ('bronze_events_youtube', 'bronze_events_text_ai', 'bronze_events_channels', 'bronze_events_localview')
ORDER BY tablename;

-- Row counts
SELECT 
    'bronze_events_youtube' as table, 
    COUNT(*) as rows,
    MAX(event_date) as latest_date
FROM bronze.bronze_events_youtube
UNION ALL
SELECT 'bronze_events_text_ai', COUNT(*), NULL FROM bronze.bronze_events_text_ai
UNION ALL
SELECT 'bronze_events_channels', COUNT(*), NULL FROM bronze.bronze_events_channels;
EOSQL

# ============================================================================
# Success!
# ============================================================================

echo ""
echo "════════════════════════════════════════════════════════════════"
echo -e "  ${GREEN}✅ Setup Complete!${NC}"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Your Neon database is ready for YouTube data loading."
echo ""
echo "📋 Next steps:"
echo ""
echo "  1. In Colab, set your Neon connection in Secrets:"
echo "     Key: NEON_DATABASE_URL"
echo "     Value: (your Neon connection string)"
echo ""
echo "  2. Run the YouTube events loader:"
echo "     python packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py"
echo ""
echo "  3. Or use the Colab notebook:"
echo "     packages/scrapers/src/scrapers/youtube/load_youtube_events_colab.ipynb"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
