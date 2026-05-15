-- veraPDF validation results (PDF/UA, PDF/A) for jurisdiction-linked PDFs.
-- Applied by: python -m scripts.accessibility.persist_verapdf_results --ensure-ddl

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdiction_pdf_verapdf (
    scan_key            TEXT          PRIMARY KEY,
    batch_id            TEXT          NOT NULL,
    jurisdiction_id     TEXT          NOT NULL,
    pdf_url             TEXT          NOT NULL,
    homepage_url        TEXT,
    website_record_key  TEXT,
    website_source      TEXT,
    state_code          VARCHAR(2),
    organization_name   TEXT,
    profile_flavour     VARCHAR(8)    NOT NULL,
    scanned_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    status              TEXT          NOT NULL,
    is_compliant        BOOLEAN,
    failed_rules        INTEGER,
    failed_checks       INTEGER,
    passed_rules        INTEGER,
    passed_checks       INTEGER,
    pdf_bytes           INTEGER,
    scan_duration_ms    INTEGER,
    error_message       TEXT,
    results             JSONB         NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_bjpv_batch_id
    ON bronze.bronze_jurisdiction_pdf_verapdf (batch_id);

CREATE INDEX IF NOT EXISTS idx_bjpv_jurisdiction_id
    ON bronze.bronze_jurisdiction_pdf_verapdf (jurisdiction_id);

CREATE INDEX IF NOT EXISTS idx_bjpv_scanned_at
    ON bronze.bronze_jurisdiction_pdf_verapdf (scanned_at DESC);

CREATE INDEX IF NOT EXISTS idx_bjpv_compliant
    ON bronze.bronze_jurisdiction_pdf_verapdf (is_compliant, profile_flavour);
