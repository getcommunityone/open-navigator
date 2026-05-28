#!/bin/bash
set -e  # Exit on error

# Setup OpenStates PostgreSQL Database
# Loads the 9.8GB legislative data dump from Open States
# Contains: 50+ tables with bills, legislators, votes, committees for all 50 states

# ✅ REQUIRES TWO FILES:
# 1. Schema file: Creates tables, indexes, constraints (~50 MB)
# 2. Data file: Contains all the actual data (~10 GB)
#
# Download both with:
#   python scripts/bulk_legislative_download.py --postgres --month 2026-04
#
# This script restores schema first, then data.

echo "🏛️  OpenStates Database Setup"
echo "===================================="
echo ""

# Load credentials from .env
ENV_FILE="$(dirname "$0")/../../../.env"
if [ -f "$ENV_FILE" ]; then
    export $(grep -E "^POSTGRES_USER=|^POSTGRES_PASSWORD=" "$ENV_FILE" | xargs)
fi

# Configuration
DB_NAME="openstates"
DB_USER="${POSTGRES_USER:-postgres}"
DB_PASSWORD="${POSTGRES_PASSWORD:-password}"
DB_HOST="localhost"
DB_PORT="5433"  # PostgreSQL container (charming_mestorf)
SCHEMA_FILE="data/cache/openstates/2026-05-schema.pgdump"
DATA_FILE="data/cache/openstates/2026-05-public.pgdump"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if schema file exists
if [ ! -f "$SCHEMA_FILE" ]; then
    echo -e "${RED}❌ Error: Schema file not found at $SCHEMA_FILE${NC}"
    echo ""
    echo "Download both schema and data files with:"
    echo "  python scripts/bulk_legislative_download.py --postgres --month 2026-04"
    exit 1
fi

echo -e "${GREEN}✓${NC} Found schema file: $SCHEMA_FILE"
SCHEMA_SIZE=$(du -h "$SCHEMA_FILE" | cut -f1)
echo -e "  Size: $SCHEMA_SIZE"
echo ""

# Check if data file exists
if [ ! -f "$DATA_FILE" ]; then
    echo -e "${RED}❌ Error: Data file not found at $DATA_FILE${NC}"
    echo ""
    echo "Download both schema and data files with:"
    echo "  python scripts/bulk_legislative_download.py --postgres --month 2026-04"
    exit 1
fi

echo -e "${GREEN}✓${NC} Found data file: $DATA_FILE"
DATA_SIZE=$(du -h "$DATA_FILE" | cut -f1)
echo -e "  Size: $DATA_SIZE"
echo ""

# Check if PostgreSQL is running
if ! pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER > /dev/null 2>&1; then
    echo -e "${RED}❌ Error: PostgreSQL 17 is not running on port $DB_PORT${NC}"
    echo ""
    echo "Start PostgreSQL 17 container:"
    echo "  docker start openstates-db"
    exit 1
fi

echo -e "${GREEN}✓${NC} PostgreSQL is running"
echo ""

# Check if database already exists
if PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
    echo -e "${YELLOW}⚠️  Database '$DB_NAME' already exists${NC}"
    echo ""
    read -p "Drop and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Dropping existing database..."
        PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -c "DROP DATABASE $DB_NAME;"
        echo -e "${GREEN}✓${NC} Database dropped"
    else
        echo "Skipping database creation. Will attempt restore into existing database."
        echo ""
    fi
fi

# Create database if it doesn't exist
if ! PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
    echo "Creating database '$DB_NAME'..."
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -c "CREATE DATABASE $DB_NAME;"
    echo -e "${GREEN}✓${NC} Database created"
    echo ""
fi

# Restore the schema and data
echo "🔄 Restoring OpenStates database (2-step process)..."
echo ""

# Use pg_restore with verbose output
# --clean: Drop existing objects before recreating
# --if-exists: Don't error if objects don't exist
# --no-owner: Don't set ownership
# --no-acl: Don't set access privileges
export PGPASSWORD=$DB_PASSWORD

# Step 1: Restore schema (creates tables, indexes, constraints)
echo "📋 Step 1/2: Restoring schema (creates all tables)..."
echo "Started at $(date)..."
pg_restore \
    -h $DB_HOST \
    -p $DB_PORT \
    -U $DB_USER \
    -d $DB_NAME \
    --clean \
    --if-exists \
    --no-owner \
    --no-acl \
    --verbose \
    "$SCHEMA_FILE" 2>&1 | while read line; do
        # Only show important messages
        if echo "$line" | grep -qE "^processing|^creating|^ERROR|^WARNING"; then
            echo "  $line"
        fi
    done

echo ""
echo -e "${GREEN}✓${NC} Schema restored at $(date)"
echo ""

# Step 2: Restore data (this takes longer, ~10-15 minutes)
echo "📊 Step 2/2: Restoring data (this will take 10-15 minutes for 9.8GB)..."
echo "Started at $(date)..."
pg_restore \
    -h $DB_HOST \
    -p $DB_PORT \
    -U $DB_USER \
    -d $DB_NAME \
    --data-only \
    --no-owner \
    --no-acl \
    --disable-triggers \
    --verbose \
    "$DATA_FILE" 2>&1 | while read line; do
        # Only show important messages
        if echo "$line" | grep -qE "^processing|^restoring data|^ERROR|^WARNING"; then
            echo "  $line"
        fi
    done

echo ""
echo "Data restore completed at $(date)"
echo ""

# Verify the restore
echo "📊 Verifying database contents..."
echo ""

TABLE_COUNT=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")

echo -e "${GREEN}✓${NC} Database restored successfully"
echo -e "  Tables created: $TABLE_COUNT"
echo ""

# Show sample table counts
echo "Sample table contents:"
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << 'SQL'
SELECT 
    tablename,
    (xpath('//row/cnt/text()', query_to_xml(format('SELECT COUNT(*) as cnt FROM %I', tablename), false, true, '')))[1]::text::int AS row_count
FROM pg_tables 
WHERE schemaname = 'public' 
    AND tablename IN ('opencivicdata_person', 'opencivicdata_bill', 'opencivicdata_voteevent', 'opencivicdata_organization')
ORDER BY row_count DESC;
SQL

echo ""
echo "======================================"
echo -e "${GREEN}✅ OpenStates database setup complete!${NC}"
echo "======================================"
echo ""
echo "Database: $DB_NAME"
echo "Host: $DB_HOST:$DB_PORT (PostgreSQL 17)"
echo ""
echo "Connect with:"
echo "  PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"
echo ""
echo "Or from Python:"
echo "  import psycopg2"
echo "  conn = psycopg2.connect(host='$DB_HOST', port=$DB_PORT, database='$DB_NAME', user='$DB_USER', password='$DB_PASSWORD')"
echo ""
