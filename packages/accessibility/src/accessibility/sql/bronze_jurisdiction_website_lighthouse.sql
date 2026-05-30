-- Lighthouse navigation audits for jurisdiction homepages (paired with axe via batch_id).
-- Applied by: python -m accessibility.persist_lighthouse_results --ensure-ddl
-- Neon mirror: packages/hosting/scripts/neon/migrations/034_create_bronze_jurisdiction_website_lighthouse.sql

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdiction_website_lighthouse (
    scan_key                 TEXT          PRIMARY KEY,
    batch_id                 TEXT          NOT NULL,
    jurisdiction_id          TEXT          NOT NULL,
    website_record_key       TEXT,
    website_url              TEXT          NOT NULL,
    website_source           TEXT,
    state_code               VARCHAR(2),
    organization_name        TEXT,
    scanned_at               TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    status                   TEXT          NOT NULL,
    final_url                TEXT,
    lighthouse_version       TEXT,
    score_accessibility      INTEGER,
    score_performance       INTEGER,
    score_best_practices     INTEGER,
    scan_duration_ms         INTEGER,
    error_message            TEXT,
    results                  JSONB         NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_bjwl_batch_id
    ON bronze.bronze_jurisdiction_website_lighthouse (batch_id);

CREATE INDEX IF NOT EXISTS idx_bjwl_jurisdiction_id
    ON bronze.bronze_jurisdiction_website_lighthouse (jurisdiction_id);

CREATE INDEX IF NOT EXISTS idx_bjwl_scanned_at
    ON bronze.bronze_jurisdiction_website_lighthouse (scanned_at DESC);

CREATE INDEX IF NOT EXISTS idx_bjwl_a11y_score
    ON bronze.bronze_jurisdiction_website_lighthouse (score_accessibility);

-- Join axe + LH for the same canonical batch export (reuse urls.json batch_id for both scanners).
CREATE OR REPLACE VIEW public.v_jurisdiction_audits_axe_lighthouse AS
SELECT
    ax.scan_key           AS axe_scan_key,
    lh.scan_key           AS lighthouse_scan_key,
    COALESCE(ax.jurisdiction_id, lh.jurisdiction_id) AS jurisdiction_id,
    COALESCE(ax.batch_id, lh.batch_id) AS batch_id,
    COALESCE(ax.website_url, lh.website_url) AS website_url,
    ax.organization_name AS organization_name,
    ax.state_code         AS state_code,
    ax.scanner             AS axe_scanner,
    ax.violation_count     AS axe_violation_count,
    ax.pass_count          AS axe_pass_count,
    ax.incomplete_count   AS axe_incomplete_count,
    ax.status             AS axe_status,
    ax.error_message       AS axe_error_message,
    ax.final_url           AS axe_final_url,
    ax.http_status         AS axe_http_status,
    lh.score_accessibility AS lighthouse_accessibility_score,
    lh.score_performance   AS lighthouse_performance_score,
    lh.score_best_practices AS lighthouse_best_practices_score,
    lh.status              AS lighthouse_status,
    lh.error_message       AS lighthouse_error_message,
    lh.final_url           AS lighthouse_final_url,
    lh.lighthouse_version  AS lighthouse_version,
    ax.scanned_at         AS axe_scanned_at,
    lh.scanned_at         AS lighthouse_scanned_at,
    ax.results            AS axe_results,
    lh.results            AS lighthouse_results
FROM (
    SELECT *
    FROM bronze.bronze_jurisdiction_website_accessibility
    WHERE scanner = 'axe'
) ax
FULL OUTER JOIN bronze.bronze_jurisdiction_website_lighthouse lh
    ON ax.jurisdiction_id = lh.jurisdiction_id
    AND ax.batch_id = lh.batch_id
    AND ax.website_url = lh.website_url;
