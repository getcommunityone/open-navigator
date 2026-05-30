-- Normalized DOT public-involvement events (list pages + detail links + collateral metadata).
-- Populated by scripts/datasources/dot/load_dot_unified_events_to_postgres.py from unified_events.jsonl.

CREATE TABLE IF NOT EXISTS bronze.bronze_dot_public_events (
    id BIGSERIAL PRIMARY KEY,
    state_usps CHAR(2) NOT NULL,
    event_fingerprint TEXT NOT NULL,
    adapter TEXT NOT NULL,
    title TEXT NOT NULL,
    summary_text TEXT,
    list_page_url TEXT NOT NULL,
    detail_url TEXT,
    meeting_date DATE,
    meeting_date_raw TEXT,
    collateral JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_record JSONB NOT NULL,
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    CONSTRAINT bronze_dot_public_events_fingerprint_unique UNIQUE (event_fingerprint)
);

CREATE INDEX IF NOT EXISTS bronze_dot_public_events_state_idx
    ON bronze.bronze_dot_public_events (state_usps);

CREATE INDEX IF NOT EXISTS bronze_dot_public_events_detail_url_idx
    ON bronze.bronze_dot_public_events ((LOWER(detail_url)))
    WHERE detail_url IS NOT NULL;

COMMENT ON TABLE bronze.bronze_dot_public_events IS
    'State DOT public meeting / hearing rows extracted by per-state adapters (see scripts/datasources/dot/build_dot_unified_events.py).';
