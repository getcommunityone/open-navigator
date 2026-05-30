-- Migration: bronze.bronze_contacts_scraped — jurisdiction directory / board / council contact scrape rows
--
-- Apply from repo root (uses OPEN_NAVIGATOR_DATABASE_URL / NEON_* / DATABASE_URL from .env like the app):
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/035_create_bronze_contacts_scraped.sql
--
-- If you use raw psql, pass a full libpq URL; an empty DATABASE_URL makes psql connect via local socket.

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.bronze_contacts_scraped (
    id                   BIGSERIAL PRIMARY KEY,
    scrape_batch_id      UUID NOT NULL,
    jurisdiction_id      TEXT NOT NULL,
    state_code           CHAR(2) NOT NULL,
    source_page_url      TEXT NOT NULL,
    page_classification  TEXT NOT NULL DEFAULT 'unknown',
    directory_score      INTEGER NOT NULL DEFAULT 0,
    person_name          TEXT,
    title_or_role        TEXT,
    department           TEXT,
    email                TEXT,
    phone                TEXT,
    mailing_address      TEXT,
    profile_url          TEXT,
    extraction_method    TEXT,
    raw_row              JSONB NOT NULL DEFAULT '{}'::JSONB,
    scraped_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    loaded_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bronze_contacts_scraped_jurisdiction
    ON bronze.bronze_contacts_scraped (jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_bronze_contacts_scraped_batch
    ON bronze.bronze_contacts_scraped (scrape_batch_id);
CREATE INDEX IF NOT EXISTS idx_bronze_contacts_scraped_scraped_at
    ON bronze.bronze_contacts_scraped (scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_bronze_contacts_scraped_source_page
    ON bronze.bronze_contacts_scraped (source_page_url);

COMMENT ON TABLE bronze.bronze_contacts_scraped IS
    'Best-effort structured contacts from HTML directory pages (board/council/officials); linked to legacy jurisdiction_id (e.g. county_01125). Not verified CRM data.';

COMMIT;
