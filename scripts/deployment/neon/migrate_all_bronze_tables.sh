#!/bin/bash
# Migrate ALL bronze tables from open_navigator_bronze to open_navigator.bronze schema
# This consolidates to a single database with schemas (no FDW needed)

set -e

PGHOST=localhost
PGPORT=5433
PGUSER=postgres
SOURCE_DB=open_navigator_bronze
TARGET_DB=open_navigator

echo "🔄 Migrating all bronze tables to single database..."
echo "   Source: $SOURCE_DB.public.*"
echo "   Target: $TARGET_DB.bronze.*"
echo ""

# Get list of all bronze tables
TABLES=$(psql -h $PGHOST -p $PGPORT -U $PGUSER -d $SOURCE_DB -t -c \
    "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'bronze_%' ORDER BY tablename;")

echo "Found $(echo "$TABLES" | wc -l) tables to migrate"
echo ""

# Migrate each table
for TABLE in $TABLES; do
    TABLE=$(echo $TABLE | xargs)  # Trim whitespace
    
    SIZE=$(psql -h $PGHOST -p $PGPORT -U $PGUSER -d $SOURCE_DB -t -c \
        "SELECT pg_size_pretty(pg_total_relation_size('public.$TABLE'));")
    
    echo "📦 Migrating: $TABLE ($SIZE)"
    
    # Drop table in target if exists
    psql -h $PGHOST -p $PGPORT -U $PGUSER -d $TARGET_DB -q -c \
        "DROP TABLE IF EXISTS bronze.$TABLE CASCADE;" 2>/dev/null || true
    
    # Dump schema and data, pipe to target with schema rename
    pg_dump -h $PGHOST -p $PGPORT -U $PGUSER -d $SOURCE_DB \
        --table=public.$TABLE \
        --no-owner --no-acl \
        | sed "s/public\.$TABLE/bronze.$TABLE/g" \
        | sed "s/SET search_path = public/SET search_path = bronze/g" \
        | psql -h $PGHOST -p $PGPORT -U $PGUSER -d $TARGET_DB -q > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo "   ✓ Migrated successfully"
    else
        echo "   ✗ Migration failed"
    fi
done

echo ""
echo "✅ Migration complete!"
echo ""
echo "📊 Verifying bronze schema tables:"
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $TARGET_DB -c \
    "SELECT tablename, pg_size_pretty(pg_total_relation_size('bronze.' || tablename)) as size
     FROM pg_tables 
     WHERE schemaname = 'bronze'
     ORDER BY tablename;"

echo ""
echo "🎯 Next steps:"
echo "  1. Update dbt sources to use bronze schema (already done)"
echo "  2. Drop old open_navigator_bronze database (after verification):"
echo "     dropdb -h localhost -p 5433 -U postgres open_navigator_bronze"
echo "  3. Remove Foreign Data Wrapper server (optional):"
echo "     psql -d open_navigator -c 'DROP SERVER IF EXISTS bronze_server CASCADE;'"
