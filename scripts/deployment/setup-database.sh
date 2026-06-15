#!/bin/bash
# End-to-End Database Setup Script
# Sets up local PostgreSQL, syncs data to Neon, and verifies stats are available

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Open Navigator - Database Setup${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT" || exit 1

# Check for virtual environment
if [ ! -f ".venv/bin/python" ]; then
    echo -e "${RED}❌ Virtual environment not found at .venv/${NC}"
    echo -e "${YELLOW}💡 Run: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt${NC}"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env file not found${NC}"
    echo -e "${YELLOW}💡 Copy .env.example to .env and add your NEON_DATABASE_URL${NC}"
    exit 1
fi

# Load environment variables
set -a
source .env
set +a

# Verify NEON_DATABASE_URL is set
if [ -z "$NEON_DATABASE_URL" ]; then
    echo -e "${RED}❌ NEON_DATABASE_URL not set in .env${NC}"
    echo -e "${YELLOW}💡 Add NEON_DATABASE_URL=postgresql://user:pass@host/db to .env${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Environment configured${NC}"
echo ""

# Step 1: Check if local PostgreSQL is running (optional - for local dev)
echo -e "${BLUE}📊 Step 1: Checking local PostgreSQL (optional)${NC}"
if docker ps | grep -q postgres; then
    LOCAL_PG_RUNNING=true
    echo -e "${GREEN}✅ Local PostgreSQL is running${NC}"
else
    LOCAL_PG_RUNNING=false
    echo -e "${YELLOW}⚠️  Local PostgreSQL not running (OK for production)${NC}"
fi
echo ""

# Step 2: Sync data to Neon database
echo -e "${BLUE}📤 Step 2: Syncing data to Neon database${NC}"
echo -e "${YELLOW}This will:${NC}"
echo -e "${YELLOW}  - Create tables if they don't exist${NC}"
echo -e "${YELLOW}  - Sync data from data/gold/ parquet files${NC}"
echo -e "${YELLOW}  - Skip unchanged data (smart sync)${NC}"
echo ""

read -p "$(echo -e ${YELLOW}"Continue with sync? (y/N): "${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⏭️  Skipping sync${NC}"
else
    echo -e "${BLUE}🔄 Running smart sync...${NC}"
    ./scripts/data/sync-smart.sh
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Data sync completed${NC}"
    else
        echo -e "${RED}❌ Data sync failed${NC}"
        exit 1
    fi
fi
echo ""

# Step 3: Verify stats are available
echo -e "${BLUE}🔍 Step 3: Verifying stats are available${NC}"

# Test stats endpoint via Python
VERIFICATION_RESULT=$(.venv/bin/python -c "
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv('NEON_DATABASE_URL')
if not DATABASE_URL:
    print('ERROR: NEON_DATABASE_URL not set')
    sys.exit(1)

try:
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    # Check key tables exist
    tables = ['nonprofits_organizations', 'contacts_local_officials', 'events_meetings', 'jurisdictions']
    missing = []
    
    for table in tables:
        cur.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            )
        ''', (table,))
        exists = cur.fetchone()['exists']
        if not exists:
            missing.append(table)
    
    if missing:
        print(f'MISSING_TABLES:{','.join(missing)}')
        sys.exit(1)
    
    # Get sample counts
    stats = {}
    
    # Nonprofits count
    cur.execute('SELECT COUNT(*) as count FROM nonprofits_organizations LIMIT 1')
    stats['nonprofits'] = cur.fetchone()['count']
    
    # Events count
    cur.execute('SELECT COUNT(*) as count FROM events_meetings LIMIT 1')
    stats['events'] = cur.fetchone()['count']
    
    # Contacts count
    cur.execute('SELECT COUNT(*) as count FROM contacts_local_officials LIMIT 1')
    stats['contacts'] = cur.fetchone()['count']
    
    # Jurisdictions count
    cur.execute('SELECT COUNT(*) as count FROM jurisdictions LIMIT 1')
    stats['jurisdictions'] = cur.fetchone()['count']
    
    # Print stats
    print(f'nonprofits:{stats['nonprofits']}')
    print(f'events:{stats['events']}')
    print(f'contacts:{stats['contacts']}')
    print(f'jurisdictions:{stats['jurisdictions']}')
    
    # Check if we have reasonable data
    if stats['nonprofits'] == 0 and stats['events'] == 0 and stats['contacts'] == 0:
        print('WARNING:All counts are zero - database may be empty')
        sys.exit(1)
    
    print('SUCCESS')
    conn.close()
    
except Exception as e:
    print(f'ERROR:{str(e)}')
    sys.exit(1)
" 2>&1)

# Parse verification results
if echo "$VERIFICATION_RESULT" | grep -q "ERROR:"; then
    ERROR_MSG=$(echo "$VERIFICATION_RESULT" | grep "ERROR:" | cut -d: -f2-)
    echo -e "${RED}❌ Database verification failed: $ERROR_MSG${NC}"
    exit 1
elif echo "$VERIFICATION_RESULT" | grep -q "MISSING_TABLES:"; then
    MISSING=$(echo "$VERIFICATION_RESULT" | grep "MISSING_TABLES:" | cut -d: -f2-)
    echo -e "${RED}❌ Missing tables: $MISSING${NC}"
    echo -e "${YELLOW}💡 Run the sync step to create tables${NC}"
    exit 1
elif echo "$VERIFICATION_RESULT" | grep -q "WARNING:"; then
    echo -e "${YELLOW}⚠️  Database tables exist but are empty${NC}"
    echo -e "${YELLOW}💡 Run the sync step to load data${NC}"
    exit 1
elif echo "$VERIFICATION_RESULT" | grep -q "SUCCESS"; then
    # Parse and display stats
    NONPROFITS=$(echo "$VERIFICATION_RESULT" | grep "nonprofits:" | cut -d: -f2)
    EVENTS=$(echo "$VERIFICATION_RESULT" | grep "events:" | cut -d: -f2)
    CONTACTS=$(echo "$VERIFICATION_RESULT" | grep "contacts:" | cut -d: -f2)
    JURISDICTIONS=$(echo "$VERIFICATION_RESULT" | grep "jurisdictions:" | cut -d: -f2)
    
    echo -e "${GREEN}✅ Database verified successfully!${NC}"
    echo ""
    echo -e "${GREEN}📊 Current Stats:${NC}"
    echo -e "  ${BLUE}Nonprofits:${NC}    $(printf "%'d" $NONPROFITS 2>/dev/null || echo $NONPROFITS)"
    echo -e "  ${BLUE}Events:${NC}        $(printf "%'d" $EVENTS 2>/dev/null || echo $EVENTS)"
    echo -e "  ${BLUE}Contacts:${NC}      $(printf "%'d" $CONTACTS 2>/dev/null || echo $CONTACTS)"
    echo -e "  ${BLUE}Jurisdictions:${NC} $(printf "%'d" $JURISDICTIONS 2>/dev/null || echo $JURISDICTIONS)"
else
    echo -e "${RED}❌ Unexpected verification result${NC}"
    echo "$VERIFICATION_RESULT"
    exit 1
fi
echo ""

# Step 4: Test API endpoint (if server is running)
echo -e "${BLUE}🔍 Step 4: Testing API endpoint (optional)${NC}"
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API server is running${NC}"
    
    # Test stats endpoint
    STATS_RESPONSE=$(curl -s http://localhost:8001/api/stats?state=MA)
    if echo "$STATS_RESPONSE" | grep -q "nonprofits"; then
        echo -e "${GREEN}✅ Stats API is working${NC}"
        echo -e "${BLUE}Sample response:${NC}"
        echo "$STATS_RESPONSE" | python3 -m json.tool 2>/dev/null | head -20 || echo "$STATS_RESPONSE"
    else
        echo -e "${YELLOW}⚠️  Stats API returned unexpected response${NC}"
        echo "$STATS_RESPONSE"
    fi
else
    echo -e "${YELLOW}⚠️  API server not running (start with ./start-all.sh)${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo -e "  1. Start the application: ${BLUE}./start-all.sh${NC}"
echo -e "  2. Open frontend: ${BLUE}http://localhost:5173${NC}"
echo -e "  3. Check stats: ${BLUE}http://localhost:8001/api/stats${NC}"
echo ""
echo -e "${YELLOW}Troubleshooting:${NC}"
echo -e "  - Check logs in ${BLUE}logs/${NC} directory"
echo -e "  - Verify .env has correct NEON_DATABASE_URL"
echo -e "  - Run ${BLUE}./scripts/data/sync-smart.sh${NC} to refresh data"
echo ""
