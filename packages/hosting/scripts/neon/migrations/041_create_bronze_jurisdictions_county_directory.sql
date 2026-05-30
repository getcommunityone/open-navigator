-- Migration: bronze.bronze_jurisdictions_county_directory — per-office records-access
-- entries scraped from publicrecords.netronline.com.
--
-- One row per (state_code, county_slug, office_name) within a scrape_batch_id.
-- A county typically has 3–7 offices (Assessor / Probate / Recorder / Treasurer / GIS / etc.).
-- The same county appears under one row per office for the same batch.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/041_create_bronze_jurisdictions_county_directory.sql

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_county_directory (
    id                   BIGSERIAL PRIMARY KEY,
    scrape_batch_id      UUID NOT NULL,
    state_code           CHAR(2) NOT NULL,
    county_slug          TEXT NOT NULL,        -- netronline path slug, e.g. "jefferson_birmingham"
    county_name          TEXT NOT NULL,        -- human-readable, e.g. "Jefferson - Birmingham"
    jurisdiction_id      TEXT,                 -- best-effort FK to int_jurisdictions (county_<FIPS>)
    fips_code            CHAR(5),              -- 2-digit state + 3-digit county; null when unmapped
    source_page_url      TEXT NOT NULL,        -- /state/XX/county/<slug>
    office_name          TEXT NOT NULL,        -- "Tax Assessor", "Judge of Probate", …
    office_url           TEXT,                 -- outbound URL the office maintains
    office_phone         TEXT,
    data_type            TEXT,                 -- "Property Tax Data", "Document Search", …
    access_type          TEXT,                 -- "Online Access", "By Subscription Only", …
    raw_row              JSONB NOT NULL DEFAULT '{}'::JSONB,
    scraped_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    loaded_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bronze_jcd_state
    ON bronze.bronze_jurisdictions_county_directory (state_code);
CREATE INDEX IF NOT EXISTS idx_bronze_jcd_state_county
    ON bronze.bronze_jurisdictions_county_directory (state_code, county_slug);
CREATE INDEX IF NOT EXISTS idx_bronze_jcd_jurisdiction
    ON bronze.bronze_jurisdictions_county_directory (jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_bronze_jcd_batch
    ON bronze.bronze_jurisdictions_county_directory (scrape_batch_id);
CREATE INDEX IF NOT EXISTS idx_bronze_jcd_office
    ON bronze.bronze_jurisdictions_county_directory (office_name);

COMMENT ON TABLE bronze.bronze_jurisdictions_county_directory IS
    'Per-office public-records access entries scraped from publicrecords.netronline.com. One row per (county × office). Source is human-curated directory; treat as best-effort, not authoritative.';

COMMIT;
