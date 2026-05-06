#!/bin/bash
# Migrate bronze tables from open_navigator_bronze database to open_navigator.bronze schema

set -e

PGHOST=localhost
PGPORT=5433
PGUSER=postgres
SOURCE_DB=open_navigator_bronze
TARGET_DB=open_navigator

echo "🔄 Migrating bronze tables to single database with schemas..."

# List of bronze tables to migrate
TABLES=(
    "bronze_bills"
    "bronze_causes"
    "bronze_contacts"
    "bronze_decisions"
    "bronze_events"
    "bronze_events_search"
    "bronze_events_text_ai"
    "bronze_financial_items"
    "bronze_jurisdictions"
    "bronze_jurisdictions_postal_codes"
    "bronze_jurisdictions_zip_county"
    "bronze_jurisdictions_zip_place"
    "bronze_organizations_meetings"
    "bronze_organizations_nonprofits"
    "bronze_organizations_nonprofits_irs"
    "bronze_organizations_nonprofits_nccs"
    "bronze_organizations_nonprofits_nccs_history"
    "bronze_topics"
)

for TABLE in "${TABLES[@]}"; do
    echo "  Migrating $TABLE..."
    
    # Drop if exists in target
    psql -h $PGHOST -p $PGPORT -U $PGUSER -d $TARGET_DB -c \
        "DROP TABLE IF EXISTS bronze.$TABLE CASCADE;" > /dev/null 2>&1
    
    # Dump schema and data, restore to bronze schema
    pg_dump -h $PGHOST -p $PGPORT -U $PGUSER -d $SOURCE_DB \
        --table=public.$TABLE \
        --schema-only \
        | sed "s/public\.$TABLE/bronze.$TABLE/g" \
        | psql -h $PGHOST -p $PGPORT -U $PGUSER -d $TARGET_DB > /dev/null 2>&1
    
    # Copy data
    psql -h $PGHOST -p $PGPORT -U $PGUSER -d $TARGET_DB -c \
        "INSERT INTO bronze.$TABLE SELECT * FROM dblink('dbname=$SOURCE_DB', 'SELECT * FROM public.$TABLE')
         AS t($(psql -h $PGHOST -p $PGPORT -U $PGUSER -d $SOURCE_DB -t -c \
            "SELECT string_agg(column_name || ' ' || data_type, ', ') 
             FROM information_schema.columns 
             WHERE table_schema='public' AND table_name='$TABLE'"));" 2>/dev/null || {
        
        # Fallback: Use COPY through file
        echo "    Using COPY method for $TABLE..."
        psql -h $PGHOST -p $PGPORT -U $PGUSER -d $SOURCE_DB -c \
            "COPY public.$TABLE TO '/tmp/${TABLE}.csv' WITH CSV HEADER;" > /dev/null
        
        psql -h $PGHOST -p $PGPORT -U $PGUSER -d $TARGET_DB -c \
            "COPY bronze.$TABLE FROM '/tmp/${TABLE}.csv' WITH CSV HEADER;" > /dev/null
        
        rm -f "/tmp/${TABLE}.csv"
    }
    
    echo "  ✓ Migrated $TABLE"
done

echo ""
echo "✅ Migration complete! All bronze tables are now in open_navigator.bronze schema"
echo ""
echo "Next steps:"
echo "  1. Update dbt sources to use bronze schema (no FDW needed)"
echo "  2. Drop open_navigator_bronze database (optional, after verification)"
echo "  3. Remove FDW server configuration (optional)"
