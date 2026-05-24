-- Migration: create bronze.bronze_jurisdiction_openstates — a Neon-local mirror of
-- ``openstates.public.opencivicdata_person`` (plus collapsed ``personlink`` and
-- ``personidentifier`` arrays). Refreshed by
-- ``scripts/datasources/openstates/sync_persons_to_bronze.py``.
--
-- Mirroring rather than cross-database joining because Postgres can't FDW-join the
-- two databases directly without extra setup, and the OpenStates DB connection is
-- read-only / external; we want a local copy we can join against in dbt.
--
-- One row per ``openstates_person_id`` per ``sync_batch_id``. Re-syncs append new
-- batches; downstream models pick the latest batch.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/046_create_bronze_jurisdiction_openstates.sql

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdiction_openstates (
    id                          BIGSERIAL PRIMARY KEY,
    sync_batch_id               UUID NOT NULL,
    openstates_person_id        TEXT NOT NULL,        -- ocd-person/<UUID>
    name                        TEXT NOT NULL,
    given_name                  TEXT,
    family_name                 TEXT,
    gender                      TEXT,
    biography                   TEXT,
    birth_date                  TEXT,
    death_date                  TEXT,
    image                       TEXT,
    primary_party               TEXT,
    email                       TEXT,
    current_jurisdiction_id     TEXT,                 -- ocd-jurisdiction/country:us/state:XX/...
    state_code                  CHAR(2),              -- denormalized from current_jurisdiction_id
    "current_role"              JSONB NOT NULL DEFAULT '{}'::JSONB,
    extras                      JSONB NOT NULL DEFAULT '{}'::JSONB,
    links                       JSONB NOT NULL DEFAULT '[]'::JSONB,
    identifiers                 JSONB NOT NULL DEFAULT '[]'::JSONB,
    source_created_at           TIMESTAMPTZ,
    source_updated_at           TIMESTAMPTZ,
    synced_at                   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_openstates_person
    ON bronze.bronze_jurisdiction_openstates (openstates_person_id);
CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_openstates_state
    ON bronze.bronze_jurisdiction_openstates (state_code);
CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_openstates_juris
    ON bronze.bronze_jurisdiction_openstates (current_jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_openstates_batch
    ON bronze.bronze_jurisdiction_openstates (sync_batch_id);
CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_openstates_email
    ON bronze.bronze_jurisdiction_openstates (lower(email));

COMMENT ON TABLE bronze.bronze_jurisdiction_openstates IS
    'Neon-local mirror of openstates.public.opencivicdata_person (+ personlink, +personidentifier) for cross-database enrichment. Refresh with scripts/datasources/openstates/sync_persons_to_bronze.py.';

COMMIT;
