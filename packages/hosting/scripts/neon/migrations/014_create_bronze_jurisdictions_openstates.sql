-- Mirror of Open Civic Data `opencivicdata_jurisdiction` (Open States Postgres dump).
-- DDL aligned with openstates-core Jurisdiction model (OCDBase + division FK).
--
-- Apply:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/014_create_bronze_jurisdictions_openstates.sql
--
-- Load data:
--   python scripts/datasources/openstates/map_openstates_jurisdiction_ids.py

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_openstates (
    id                      VARCHAR(300) PRIMARY KEY,
    name                    VARCHAR(300) NOT NULL,
    url                     VARCHAR(2000) NOT NULL DEFAULT '',
    classification          VARCHAR(50) NOT NULL DEFAULT 'government',
    division_id             VARCHAR(300),
    latest_bill_update      TIMESTAMPTZ NOT NULL,
    latest_people_update    TIMESTAMPTZ NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    extras                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    loaded_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bjos_division_id
    ON bronze.bronze_jurisdictions_openstates (division_id)
    WHERE division_id IS NOT NULL;

COMMENT ON TABLE bronze.bronze_jurisdictions_openstates IS
    'Snapshot of Open States opencivicdata_jurisdiction; use map_openstates_jurisdiction_ids.py to refresh.';
COMMENT ON COLUMN bronze.bronze_jurisdictions_openstates.division_id IS
    'OCD division id (opencivicdata_division.id); used with Census GEOIDs in int_jurisdictions.';
