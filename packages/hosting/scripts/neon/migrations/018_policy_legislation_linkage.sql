-- Policy analysis legislation linkage: meeting-level leg_ids, per-item FK rows, bronze bills.
-- Apply: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/018_policy_legislation_linkage.sql

BEGIN;

-- Meeting-level rollup on YouTube catalog rows
ALTER TABLE bronze.bronze_events_youtube
    ADD COLUMN IF NOT EXISTS primary_leg_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS legislation_validated_at TIMESTAMPTZ;

COMMENT ON COLUMN bronze.bronze_events_youtube.primary_leg_ids IS
    'Distinct leg_id slugs from latest policy analysis for this video';

-- Canonical legislation rows per meeting (parallel to dbt bronze_bills_from_ai)
CREATE TABLE IF NOT EXISTS bronze.bronze_bills (
    source_event_id_leg_id TEXT PRIMARY KEY,
    source_event_id INTEGER NOT NULL,
    video_id VARCHAR(64),
    source_ai_model VARCHAR(100) NOT NULL DEFAULT 'gemini-2.5-flash-lite',
    leg_id VARCHAR(255) NOT NULL,
    leg_type VARCHAR(100),
    official_number VARCHAR(64),
    title TEXT,
    jurisdiction VARCHAR(200),
    year VARCHAR(4),
    status VARCHAR(100),
    relevance TEXT,
    url TEXT,
    agenda_labels JSONB NOT NULL DEFAULT '[]'::jsonb,
    analysis_cache_path TEXT,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_event_id, leg_id, source_ai_model)
);

CREATE INDEX IF NOT EXISTS idx_bronze_bills_video_id
    ON bronze.bronze_bills (video_id);
CREATE INDEX IF NOT EXISTS idx_bronze_bills_leg_id
    ON bronze.bronze_bills (leg_id);
CREATE INDEX IF NOT EXISTS idx_bronze_bills_event_id
    ON bronze.bronze_bills (source_event_id);

-- Agenda item / decision → leg_id (many-to-many per meeting item)
CREATE TABLE IF NOT EXISTS bronze.bronze_meeting_item_legislation (
    id SERIAL PRIMARY KEY,
    source_event_id INTEGER NOT NULL,
    video_id VARCHAR(64) NOT NULL,
    source_ai_model VARCHAR(100) NOT NULL DEFAULT 'gemini-2.5-flash-lite',
    item_id VARCHAR(32) NOT NULL,
    item_kind VARCHAR(16) NOT NULL CHECK (item_kind IN ('uncontested', 'decision')),
    leg_id VARCHAR(255) NOT NULL,
    agenda_labels JSONB NOT NULL DEFAULT '[]'::jsonb,
    headline TEXT,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_event_id, item_id, leg_id, source_ai_model)
);

CREATE INDEX IF NOT EXISTS idx_bronze_meeting_item_leg_video
    ON bronze.bronze_meeting_item_legislation (video_id);
CREATE INDEX IF NOT EXISTS idx_bronze_meeting_item_leg_leg
    ON bronze.bronze_meeting_item_legislation (leg_id);

-- Policy decisions with leg_id array (extends legacy bronze_decisions pattern)
CREATE TABLE IF NOT EXISTS bronze.bronze_policy_decisions (
    id SERIAL PRIMARY KEY,
    source_event_id INTEGER NOT NULL,
    video_id VARCHAR(64) NOT NULL,
    source_ai_model VARCHAR(100) NOT NULL DEFAULT 'gemini-2.5-flash-lite',
    decision_id VARCHAR(32) NOT NULL,
    subject_id VARCHAR(255),
    headline TEXT,
    outcome VARCHAR(100),
    legislation_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    vote_tally JSONB,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_event_id, decision_id, source_ai_model)
);

CREATE INDEX IF NOT EXISTS idx_bronze_policy_decisions_video
    ON bronze.bronze_policy_decisions (video_id);

-- Extend dbt-created bronze.bronze_bills when table already exists
ALTER TABLE bronze.bronze_bills
    ADD COLUMN IF NOT EXISTS video_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS agenda_labels JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS analysis_cache_path TEXT;

COMMIT;
