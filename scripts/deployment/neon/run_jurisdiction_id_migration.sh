#!/usr/bin/env bash
# Apply jurisdiction_id to all bronze jurisdiction tables and verify the results.
#
# What this does:
#   1. Runs migration 010 (ALTER TABLE — safe on existing data, idempotent)
#   2. Re-materializes _wikidata tables so they get the FK constraints
#   3. Prints a verification report
#
# Usage:
#   ./scripts/deployment/neon/run_jurisdiction_id_migration.sh
#
# Prereqs:
#   - .env contains NEON_DATABASE_URL_DEV (or NEON_DATABASE_URL / OPEN_NAVIGATOR_DATABASE_URL)
#   - Bronze base tables already populated (run load_census_gazetteer.py first if not)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || { echo "ERROR: venv not found at ${PY}"; exit 1; }

# Load .env so DATABASE_URL vars are available
if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

# Resolve DB URL using the same priority as the Python loaders
DB_URL="${OPEN_NAVIGATOR_DATABASE_URL:-${NEON_DATABASE_URL_DEV:-${NEON_DATABASE_URL:-${DATABASE_URL:-}}}}"
if [[ -z "$DB_URL" ]]; then
  PGPASSWORD="${POSTGRES_PASSWORD:-password}"
  DB_URL="postgresql://postgres:${PGPASSWORD}@localhost:5433/open_navigator"
fi

echo "==> Database: ${DB_URL%%@*}@…"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Apply migration 010
# ─────────────────────────────────────────────────────────────────────────────
echo "==> [1/3] Running migrations …"
psql "$DB_URL" -v ON_ERROR_STOP=1 -f "${ROOT}/scripts/deployment/neon/migrations/010_add_jurisdiction_id.sql"
echo "    ✓ 010_add_jurisdiction_id applied"
psql "$DB_URL" -v ON_ERROR_STOP=1 -f "${ROOT}/scripts/deployment/neon/migrations/011_add_jurisdiction_type_and_source.sql"
echo "    ✓ 011_add_jurisdiction_type_and_source applied"
psql "$DB_URL" -v ON_ERROR_STOP=1 -f "${ROOT}/scripts/deployment/neon/migrations/012_convert_jurisdiction_columns_to_enum.sql"
echo "    ✓ 012_convert_jurisdiction_columns_to_enum applied"
psql "$DB_URL" -v ON_ERROR_STOP=1 -f "${ROOT}/scripts/deployment/neon/migrations/013_add_jurisdiction_id_prefix.sql"
echo "    ✓ 013_add_jurisdiction_id_prefix applied"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Re-materialize _wikidata tables.
#         DROP + CREATE TABLE AS SELECT base.* picks up the new enum columns.
#         Works even without jurisdictions_wikidata loaded — wikidata columns
#         will simply be NULL until that data is loaded.
# ─────────────────────────────────────────────────────────────────────────────
WIKIDATA_SCRIPT="${ROOT}/packages/scrapers/src/scrapers/wikidata/materialize_bronze_jurisdictions_wikidata_tables.py"
echo "==> [2/3] Re-materializing _wikidata tables (picks up new prefixed jurisdiction_id values) …"
WIKIDATA_EXISTS=$(psql "$DB_URL" -tAc "SELECT to_regclass('public.jurisdictions_wikidata')")
if [[ "$WIKIDATA_EXISTS" == "jurisdictions_wikidata" ]]; then
  "$PY" "$WIKIDATA_SCRIPT"
  echo "    ✓ Wikidata tables rebuilt"
else
  echo "    ⚠ jurisdictions_wikidata not loaded yet — skipping wikidata materialization"
fi
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Verification report
# ─────────────────────────────────────────────────────────────────────────────
echo "==> [3/3] Verification report"
echo ""

psql "$DB_URL" -v ON_ERROR_STOP=1 <<'SQL'

\echo '--- jurisdiction_id column coverage (total should equal with_jid) ---'
SELECT
    'states'          AS table_name,
    COUNT(*)          AS total_rows,
    COUNT(jurisdiction_id) AS with_jid,
    MIN(jurisdiction_id)   AS sample_min,
    MAX(jurisdiction_id)   AS sample_max
FROM bronze.bronze_jurisdictions_states
UNION ALL
SELECT 'counties', COUNT(*), COUNT(jurisdiction_id),
    MIN(jurisdiction_id), MAX(jurisdiction_id)
FROM bronze.bronze_jurisdictions_counties
UNION ALL
SELECT 'municipalities', COUNT(*), COUNT(jurisdiction_id),
    MIN(jurisdiction_id), MAX(jurisdiction_id)
FROM bronze.bronze_jurisdictions_municipalities
UNION ALL
SELECT 'school_districts', COUNT(*), COUNT(jurisdiction_id),
    MIN(jurisdiction_id), MAX(jurisdiction_id)
FROM bronze.bronze_jurisdictions_school_districts
UNION ALL
SELECT 'place_zcta', COUNT(*), COUNT(jurisdiction_id),
    MIN(jurisdiction_id), MAX(jurisdiction_id)
FROM bronze.bronze_jurisdictions_place_zcta
ORDER BY 1;

\echo ''
\echo '--- UNIQUE constraints on base tables ---'
SELECT table_name, constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_schema = 'bronze'
  AND constraint_name LIKE '%jurisdiction_id%'
  AND constraint_type IN ('UNIQUE', 'FOREIGN KEY')
ORDER BY constraint_type DESC, table_name;

\echo ''
\echo '--- Sample values ---'
SELECT 'state'  AS type, jurisdiction_id FROM bronze.bronze_jurisdictions_states        LIMIT 3;
SELECT 'county' AS type, jurisdiction_id FROM bronze.bronze_jurisdictions_counties       LIMIT 3;
SELECT 'muni'   AS type, jurisdiction_id FROM bronze.bronze_jurisdictions_municipalities LIMIT 3;
SELECT 'zcta'   AS type, jurisdiction_id FROM bronze.bronze_jurisdictions_place_zcta     LIMIT 3;
SQL

echo ""
echo "==> Done."
