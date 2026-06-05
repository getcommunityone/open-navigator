-- Policy analysis legislation linkage: meeting-level leg_ids, per-item FK rows, bronze bills.
-- Apply: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/018_policy_legislation_linkage.sql

BEGIN;

-- Meeting-level rollup on YouTube catalog rows
ALTER TABLE bronze.bronze_event_youtube
    ADD COLUMN IF NOT EXISTS primary_leg_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS legislation_validated_at TIMESTAMPTZ;

COMMENT ON COLUMN bronze.bronze_event_youtube.primary_leg_ids IS
    'Distinct leg_id slugs from latest policy analysis for this video';

-- Canonical legislation rows per meeting (parallel to dbt bronze_bills_from_ai)
CREATE TABLE IF NOT EXISTS bronze.bronze_bills (
    source_event_id_leg_id TEXT PRIMARY KEY,
    source_event_id INTEGER NOT NULL,
    video_id VARCHAR(64),
    source_ai_model VARCHAR(100) NOT NULL DEFAULT 'gemini-2.5-flash-lite',
    leg_id TEXT NOT NULL,
    leg_type TEXT,
    official_number TEXT,
    title TEXT,
    jurisdiction TEXT,
    year TEXT,
    status TEXT,
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
    item_id TEXT NOT NULL,
    item_kind VARCHAR(16) NOT NULL CHECK (item_kind IN ('uncontested', 'decision')),
    leg_id TEXT NOT NULL,
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
    decision_id TEXT NOT NULL,
    subject_id TEXT,
    headline TEXT,
    outcome TEXT,
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

-- Widen AI-derived text columns to TEXT on already-existing tables.
-- These hold free-form model output and overflowed their original VARCHAR bounds
-- (e.g. a decision `outcome` > 100 chars aborted the whole backlog run). The dbt
-- staging views stg_policy_bill / stg_policy_decisions reference some of these columns,
-- so an ALTER COLUMN TYPE is blocked until they are dropped — we capture their
-- definitions, drop, widen, and recreate them verbatim within this transaction.
-- Guarded so it runs (and churns the views) at most once: this migration is re-run
-- idempotently on every persist call, but does nothing once every column is already TEXT.
DO $$
DECLARE
    rec record;
    need_widen boolean;
    def_bill text;
    def_dec text;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'bronze'
          AND data_type <> 'text'
          AND (
            (table_name = 'bronze_bills'
                AND column_name IN ('leg_id','leg_type','official_number','jurisdiction','year','status'))
         OR (table_name = 'bronze_meeting_item_legislation'
                AND column_name IN ('item_id','leg_id'))
         OR (table_name = 'bronze_policy_decisions'
                AND column_name IN ('decision_id','subject_id','outcome'))
          )
    ) INTO need_widen;

    IF NOT need_widen THEN
        RETURN;
    END IF;

    -- Capture dependent view definitions (NULL if the view does not exist yet).
    def_bill := pg_get_viewdef(to_regclass('staging.stg_policy_bill'), true);
    def_dec  := pg_get_viewdef(to_regclass('staging.stg_policy_decisions'), true);
    DROP VIEW IF EXISTS staging.stg_policy_bill;
    DROP VIEW IF EXISTS staging.stg_policy_decisions;

    FOR rec IN
        SELECT * FROM (VALUES
            ('bronze_bills', 'leg_id'),
            ('bronze_bills', 'leg_type'),
            ('bronze_bills', 'official_number'),
            ('bronze_bills', 'jurisdiction'),
            ('bronze_bills', 'year'),
            ('bronze_bills', 'status'),
            ('bronze_meeting_item_legislation', 'item_id'),
            ('bronze_meeting_item_legislation', 'leg_id'),
            ('bronze_policy_decisions', 'decision_id'),
            ('bronze_policy_decisions', 'subject_id'),
            ('bronze_policy_decisions', 'outcome')
        ) AS t(tbl, col)
    LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'bronze'
              AND table_name = rec.tbl
              AND column_name = rec.col
              AND data_type <> 'text'
        ) THEN
            EXECUTE format(
                'ALTER TABLE bronze.%I ALTER COLUMN %I TYPE TEXT', rec.tbl, rec.col
            );
        END IF;
    END LOOP;

    IF def_bill IS NOT NULL THEN
        EXECUTE 'CREATE VIEW staging.stg_policy_bill AS ' || def_bill;
    END IF;
    IF def_dec IS NOT NULL THEN
        EXECUTE 'CREATE VIEW staging.stg_policy_decisions AS ' || def_dec;
    END IF;
END $$;

COMMIT;
