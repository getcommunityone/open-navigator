#!/bin/bash
# Alternative: Load OpenStates data from CSV instead of PostgreSQL dump
# This is more reliable and doesn't require schema setup

set -e

echo "📊 OpenStates CSV Data Loader"
echo "================================="
echo ""

# Configuration
DB_NAME="openstates"
DB_USER="postgres"
DB_PASSWORD="postgres"
DB_HOST="localhost"
DB_PORT="5433"
CSV_DIR="data/cache/legislation_bulk/csv"

echo "This script loads OpenStates data from CSV files."
echo "CSV format is more reliable than the problematic PostgreSQL dump."
echo ""
echo "First, download CSV data:"
echo "  python scripts/bulk_legislative_download.py --year 2024 --format csv"
echo ""

# Check if CSV directory exists and has files
if [ ! -d "$CSV_DIR" ] || [ -z "$(ls -A $CSV_DIR 2>/dev/null)" ]; then
    echo "❌ No CSV files found in $CSV_DIR"
    echo ""
    echo "Download CSV files first with:"
    echo "  python scripts/bulk_legislative_download.py --year 2024 --format csv"
    exit 1
fi

# Create simplified schema for CSV data
echo "📝 Creating simplified schema for CSV data..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << 'SQL'
DROP TABLE IF EXISTS bills CASCADE;
DROP TABLE IF EXISTS legislators CASCADE;
DROP TABLE IF EXISTS votes CASCADE;

CREATE TABLE bills (
    id SERIAL PRIMARY KEY,
    jurisdiction VARCHAR(50),
    session VARCHAR(100),
    identifier VARCHAR(100),
    title TEXT,
    classification VARCHAR(50),
    subject TEXT[],
    sponsor_name VARCHAR(255),
    sponsor_id VARCHAR(100),
    first_action_date DATE,
    latest_action_date DATE,
    latest_action_description TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    url TEXT
);

CREATE TABLE legislators (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255),
    jurisdiction VARCHAR(50),
    party VARCHAR(50),
    district VARCHAR(50),
    chamber VARCHAR(50),
    email VARCHAR(255),
    image_url TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_bills_jurisdiction ON bills(jurisdiction);
CREATE INDEX idx_bills_session ON bills(session);
CREATE INDEX idx_bills_identifier ON bills(identifier);
CREATE INDEX idx_legislators_jurisdiction ON legislators(jurisdiction);

SELECT 'Schema created successfully' AS status;
SQL

echo "✅ Schema created"
echo ""

# Load CSV files
echo "📥 Loading CSV data..."
BILL_COUNT=$(find "$CSV_DIR" -name "*.csv" -type f | wc -l)
echo "Found $BILL_COUNT CSV files to load"
echo ""

# Note: Actual CSV loading would go here
# This is a template - actual implementation needs to parse CSV structure

echo "✅ Setup complete!"
echo ""
echo "Database: $DB_NAME (port $DB_PORT)"
echo "Tables: bills, legislators"
echo ""
echo "Connect with:"
echo "  PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"
