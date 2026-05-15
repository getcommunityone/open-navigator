-- Accessibility scan results (Pa11y-CI / axe-core on int_jurisdiction_websites URLs).
--
-- Apply:
--   psql "$OPEN_NAVIGATOR_DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f scripts/deployment/neon/migrations/032_create_bronze_jurisdiction_website_accessibility.sql
--
-- Load results:
--   python -m scripts.accessibility.persist_results --ensure-ddl

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdiction_website_accessibility (
    scan_key            TEXT          PRIMARY KEY,
    batch_id            TEXT          NOT NULL,
    scanner             TEXT          NOT NULL,
    jurisdiction_id     TEXT          NOT NULL,
    website_record_key  TEXT,
    website_url         TEXT          NOT NULL,
    website_source      TEXT,
    state_code          VARCHAR(2),
    organization_name   TEXT,
    scanned_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    status              TEXT          NOT NULL,
    http_status         INTEGER,
    final_url           TEXT,
    page_title          TEXT,
    violation_count     INTEGER       NOT NULL DEFAULT 0,
    pass_count          INTEGER       NOT NULL DEFAULT 0,
    incomplete_count    INTEGER       NOT NULL DEFAULT 0,
    scan_duration_ms    INTEGER,
    error_message       TEXT,
    results             JSONB         NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_bjwa_batch_id
    ON bronze.bronze_jurisdiction_website_accessibility (batch_id);

CREATE INDEX IF NOT EXISTS idx_bjwa_jurisdiction_id
    ON bronze.bronze_jurisdiction_website_accessibility (jurisdiction_id);

CREATE INDEX IF NOT EXISTS idx_bjwa_scanned_at
    ON bronze.bronze_jurisdiction_website_accessibility (scanned_at DESC);

CREATE INDEX IF NOT EXISTS idx_bjwa_scanner_state
    ON bronze.bronze_jurisdiction_website_accessibility (scanner, state_code);
