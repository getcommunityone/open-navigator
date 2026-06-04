-- Migration: create bronze.bronze_bills_openstates — a dev-warehouse-local mirror
-- of ``openstates.public.opencivicdata_bill`` joined to its legislative session,
-- with sponsorships / abstracts / titles / identifiers collapsed into JSONB arrays
-- on the bill row. Refreshed by ``ingestion.openstates.bills``
-- (``python -m ingestion.openstates.bills``).
--
-- Mirroring rather than cross-database joining because Postgres can't FDW-join the
-- openstates source DB and the warehouse without extra setup; we want a local copy
-- to join against in dbt for the bill -> jurisdiction / person pipeline.
--
-- One row per ``ocd_bill_id`` (unique). Re-running the loader UPSERTs in place and
-- bumps ``synced_at``; each run still stamps a fresh ``sync_batch_id`` for audit.
--
-- The loader also creates this table if missing (mirroring the persons loader);
-- this migration is the durable record.
--
-- Apply:
--   ./scripts/neon/psql_resolved.sh -f scripts/neon/migrations/104_create_bronze_bills_openstates.sql

BEGIN;

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_bills_openstates (
    id                          BIGSERIAL PRIMARY KEY,
    sync_batch_id               UUID NOT NULL,
    ocd_bill_id                 TEXT NOT NULL,        -- ocd-bill/<UUID> (source bill id, unique)
    identifier                  TEXT,                 -- e.g. "HB 123"
    title                       TEXT,
    classification              JSONB NOT NULL DEFAULT '[]'::JSONB,  -- source text[] -> jsonb array
    subject                     JSONB NOT NULL DEFAULT '[]'::JSONB,  -- source text[] -> jsonb array
    from_organization_id        TEXT,                 -- ocd-organization/<UUID>
    legislative_session_id      TEXT,                 -- legislativesession.id (uuid as text)
    session_identifier          TEXT,                 -- e.g. "2023rs"
    session_name                TEXT,
    ocd_jurisdiction_id         TEXT,                 -- ocd-jurisdiction/country:us/state:XX/government
    state_code                  CHAR(2),              -- denormalized from ocd_jurisdiction_id
    first_action_date           TEXT,
    latest_action_date          TEXT,
    latest_action_description   TEXT,
    latest_passage_date         TEXT,
    citations                   JSONB NOT NULL DEFAULT '[]'::JSONB,
    extras                      JSONB NOT NULL DEFAULT '{}'::JSONB,
    sponsorships                JSONB NOT NULL DEFAULT '[]'::JSONB,  -- [{id,name,entity_type,primary,classification,person_id,organization_id}]
    abstracts                   JSONB NOT NULL DEFAULT '[]'::JSONB,  -- [{abstract,note}]
    titles                      JSONB NOT NULL DEFAULT '[]'::JSONB,  -- [{title,note}]
    identifiers                 JSONB NOT NULL DEFAULT '[]'::JSONB,  -- [{identifier}]
    source_created_at           TIMESTAMPTZ,
    source_updated_at           TIMESTAMPTZ,
    synced_at                   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_bronze_bills_openstates_ocd_bill_id
    ON bronze.bronze_bills_openstates (ocd_bill_id);
CREATE INDEX IF NOT EXISTS idx_bronze_bills_openstates_juris
    ON bronze.bronze_bills_openstates (ocd_jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_bronze_bills_openstates_session
    ON bronze.bronze_bills_openstates (legislative_session_id);
CREATE INDEX IF NOT EXISTS idx_bronze_bills_openstates_state
    ON bronze.bronze_bills_openstates (state_code);
CREATE INDEX IF NOT EXISTS idx_bronze_bills_openstates_batch
    ON bronze.bronze_bills_openstates (sync_batch_id);

COMMENT ON TABLE bronze.bronze_bills_openstates IS
    'Dev-warehouse-local mirror of openstates.public.opencivicdata_bill (+ session, +sponsorships/abstracts/titles/identifiers JSONB arrays) for the bill -> jurisdiction/person pipeline. Refresh with python -m ingestion.openstates.bills.';

COMMIT;
