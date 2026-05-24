-- Migration: bronze.bronze_ballotpedia_external_links — captures every outbound link
-- discovered on a Ballotpedia article page so downstream enrichment (jurisdiction-website
-- discovery, leader-bio links, source citations) has a typed bronze surface to query.
--
-- One row per (source_page_url, target_url, anchor_text). The same target URL may appear
-- under multiple source pages; that's intentional — provenance is the point of bronze.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/055_bronze_ballotpedia_external_links.sql

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.bronze_ballotpedia_external_links (
    id              BIGSERIAL PRIMARY KEY,
    scrape_batch_id UUID NOT NULL,

    -- The Ballotpedia article URL the link was found on.
    source_page_url TEXT NOT NULL,
    -- The Ballotpedia article kind: 'city', 'county', 'parish', 'ballot_measures', 'leader', …
    source_page_kind TEXT,

    -- The actual outbound link.
    target_url      TEXT NOT NULL,
    target_host     TEXT,                       -- parsed host for cheap filtering
    target_kind     TEXT,                       -- 'gov', 'social', 'news', 'wikipedia', 'other'
    anchor_text     TEXT,
    rel             TEXT,                       -- rel attribute (nofollow, etc.)

    -- Jurisdiction context (best-effort; populated by the loader when the
    -- source page corresponds to a known jurisdiction in our system).
    state_code      CHAR(2),
    jurisdiction_id TEXT,
    ocd_id          TEXT,

    raw_row         JSONB NOT NULL DEFAULT '{}'::jsonb,
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    loaded_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bronze_bp_links_source_page
    ON bronze.bronze_ballotpedia_external_links (source_page_url);
CREATE INDEX IF NOT EXISTS idx_bronze_bp_links_target_host
    ON bronze.bronze_ballotpedia_external_links (target_host);
CREATE INDEX IF NOT EXISTS idx_bronze_bp_links_state
    ON bronze.bronze_ballotpedia_external_links (state_code);
CREATE INDEX IF NOT EXISTS idx_bronze_bp_links_jurisdiction
    ON bronze.bronze_ballotpedia_external_links (jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_bronze_bp_links_batch
    ON bronze.bronze_ballotpedia_external_links (scrape_batch_id);
CREATE INDEX IF NOT EXISTS idx_bronze_bp_links_target_kind
    ON bronze.bronze_ballotpedia_external_links (target_kind);

COMMENT ON TABLE bronze.bronze_ballotpedia_external_links IS
    'Outbound links discovered on Ballotpedia article pages. Loader records every external '
    '<a href> from each fetched page so downstream models can identify official websites, '
    'social media, news mentions, and other authoritative URLs per jurisdiction.';

COMMIT;
