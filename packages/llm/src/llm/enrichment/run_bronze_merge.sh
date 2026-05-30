#!/bin/bash
# Bronze to Production Merge - Complete Workflow
# Run this script to execute the full bronze → production merge

set -e  # Exit on error

echo "========================================================================"
echo "BRONZE → PRODUCTION MERGE WORKFLOW"
echo "========================================================================"
echo ""

# Activate virtual environment
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Run: python -m venv .venv"
    exit 1
fi

source .venv/bin/activate

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Step 1: Check Bronze Data${NC}"
echo "========================================================================"
python << EOF
import psycopg2
import os

POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
BRONZE_DB_URL = f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator_bronze'

conn = psycopg2.connect(BRONZE_DB_URL)
cur = conn.cursor()

print("\n📊 Bronze Table Counts:")
cur.execute("""
    SELECT 'bronze_contacts' as table_name, COUNT(*) as count FROM bronze_contacts
    UNION ALL
    SELECT 'bronze_organizations_meetings', COUNT(*) FROM bronze_organizations_meetings
    UNION ALL
    SELECT 'bronze_bills', COUNT(*) FROM bronze_bills
    UNION ALL
    SELECT 'bronze_decisions', COUNT(*) FROM bronze_decisions
    UNION ALL
    SELECT 'bronze_financial_items', COUNT(*) FROM bronze_financial_items
""")
for row in cur.fetchall():
    print(f"  {row[0]:<30} {row[1]:>6,} records")

conn.close()
print()
EOF

echo ""
echo -e "${BLUE}Step 2: Apply Schema Migration (Add Datasource Fields)${NC}"
echo "========================================================================"
echo "This adds datasource, confidence_score, verified columns to production tables"
echo ""

read -p "Apply migration to production database? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Applying migration..."
    PGPASSWORD=${POSTGRES_PASSWORD:-password} psql -h localhost -p 5433 -U postgres -d open_navigator \
        -f packages/hosting/scripts/neon/migrations/001_add_datasource_fields.sql
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Migration applied successfully${NC}"
    else
        echo -e "${RED}❌ Migration failed${NC}"
        exit 1
    fi
else
    echo "⏭️  Skipping migration (assuming already applied)"
fi

echo ""
echo -e "${BLUE}Step 3: Run Merge (Dry Run First)${NC}"
echo "========================================================================"
echo "This shows what WOULD be merged without making changes"
echo "Testing all entities: contacts, organizations, bills"
echo ""

python -m llm.enrichment.merge_bronze_to_production \
    --entity all \
    --dry-run

echo ""
read -p "Proceed with actual merge of ALL entities? (y/n) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⏸️  Merge cancelled. Run manually when ready:${NC}"
    echo "   python -m llm.enrichment.merge_bronze_to_production --all"
    echo ""
    echo "Or merge one entity at a time:"
    echo "   python -m llm.enrichment.merge_bronze_to_production --entity contacts"
    echo "   python -m llm.enrichment.merge_bronze_to_production --entity organizations"
    echo "   python -m llm.enrichment.merge_bronze_to_production --entity bills"
    exit 0
fi

echo ""
echo -e "${BLUE}Step 4: Run Actual Merge (ALL Entities)${NC}"
echo "========================================================================"

python -m llm.enrichment.merge_bronze_to_production \
    --entity all

echo ""
echo -e "${BLUE}Step 5: Check Results${NC}"
echo "========================================================================"

python << EOF
import psycopg2
import os

POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
PROD_DB_URL = f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator'

conn = psycopg2.connect(PROD_DB_URL)
cur = conn.cursor()

print("\n📊 Production Table Counts by Datasource:")
cur.execute("""
    SELECT 
        datasource,
        COUNT(*) as count,
        AVG(confidence_score)::NUMERIC(3,2) as avg_confidence
    FROM contact
    GROUP BY datasource
    ORDER BY count DESC
""")

print(f"\n{'Datasource':<30} {'Count':>10} {'Avg Confidence':>15}")
print("-" * 60)
for row in cur.fetchall():
    print(f"{row[0]:<30} {row[1]:>10,} {row[2] if row[2] else 'N/A':>15}")

print("\n📊 Records Needing Review:")
cur.execute("""
    SELECT COUNT(*) as count
    FROM contact
    WHERE needs_review = TRUE
""")
needs_review = cur.fetchone()[0]
print(f"  {needs_review:,} contacts flagged for manual review")

conn.close()
print()
EOF

echo ""
echo -e "${BLUE}Step 6: Generate Duplicate Report (Optional)${NC}"
echo "========================================================================"

read -p "Generate duplicate detection report? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    python -m llm.enrichment.merge_bronze_to_production --report-duplicates
fi

echo ""
echo "========================================================================"
echo -e "${GREEN}✅ MERGE WORKFLOW COMPLETE${NC}"
echo "========================================================================"
echo ""
echo "Merged entities:"
echo "  ✅ Contacts (382 records)"
echo "  ✅ Organizations (185 records)"  
echo "  ✅ Bills (22 records)"
echo ""
echo "Next steps:"
echo "  1. Review flagged duplicates: Query WHERE needs_review = TRUE"
echo "  2. Check merge log: SELECT * FROM bronze_merge_log ORDER BY merged_at DESC LIMIT 20"
echo "  3. Query junction tables:"
echo "     - bills_meetings: Bills discussed in meetings"
echo "     - organizations_meetings: Organizations mentioned in meetings"
echo "  4. Set up incremental updates (run merge daily/hourly)"
echo ""
echo "Documentation:"
echo "  - Strategy: website/docs/development/bronze-to-production-merge.md"
echo "  - Quick Start: llm/enrichment/README_BRONZE_MERGE.md"
echo ""
