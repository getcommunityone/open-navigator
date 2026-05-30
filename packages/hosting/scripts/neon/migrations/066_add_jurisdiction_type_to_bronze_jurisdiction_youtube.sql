-- Migration 066: add jurisdiction_type to YouTube channel bronze tables.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/066_add_jurisdiction_type_to_bronze_jurisdiction_youtube.sql

BEGIN;

ALTER TABLE bronze.bronze_jurisdiction_youtube_candidates
    ADD COLUMN IF NOT EXISTS jurisdiction_type TEXT;

ALTER TABLE bronze.bronze_jurisdiction_youtube
    ADD COLUMN IF NOT EXISTS jurisdiction_type TEXT;

COMMENT ON COLUMN bronze.bronze_jurisdiction_youtube_candidates.jurisdiction_type IS
    'Jurisdiction category: county, municipality, school_district, … (matches int_jurisdictions.jurisdiction_type).';

COMMENT ON COLUMN bronze.bronze_jurisdiction_youtube.jurisdiction_type IS
    'Jurisdiction category: county, municipality, school_district, … (matches int_jurisdictions.jurisdiction_type).';

-- Backfill from int_jurisdictions where available.
UPDATE bronze.bronze_jurisdiction_youtube_candidates c
SET jurisdiction_type = j.jurisdiction_type::text
FROM intermediate.int_jurisdictions j
WHERE j.jurisdiction_id = c.jurisdiction_id
  AND c.jurisdiction_type IS NULL;

UPDATE bronze.bronze_jurisdiction_youtube y
SET jurisdiction_type = j.jurisdiction_type::text
FROM intermediate.int_jurisdictions j
WHERE j.jurisdiction_id = y.jurisdiction_id
  AND y.jurisdiction_type IS NULL;

-- Fallback: infer from canonical {slug}_{geoid} suffix length.
UPDATE bronze.bronze_jurisdiction_youtube_candidates c
SET jurisdiction_type = CASE
    WHEN LENGTH(SPLIT_PART(c.jurisdiction_id, '_', -1)) = 5 THEN 'county'
    WHEN LENGTH(SPLIT_PART(c.jurisdiction_id, '_', -1)) = 7 THEN 'municipality'
    WHEN c.jurisdiction_id LIKE 'county_%' THEN 'county'
    WHEN c.jurisdiction_id LIKE 'municipality_%' THEN 'municipality'
    ELSE 'unknown'
END
WHERE c.jurisdiction_type IS NULL;

UPDATE bronze.bronze_jurisdiction_youtube y
SET jurisdiction_type = CASE
    WHEN LENGTH(SPLIT_PART(y.jurisdiction_id, '_', -1)) = 5 THEN 'county'
    WHEN LENGTH(SPLIT_PART(y.jurisdiction_id, '_', -1)) = 7 THEN 'municipality'
    WHEN y.jurisdiction_id LIKE 'county_%' THEN 'county'
    WHEN y.jurisdiction_id LIKE 'municipality_%' THEN 'municipality'
    ELSE 'unknown'
END
WHERE y.jurisdiction_type IS NULL;

CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_youtube_candidates_type
    ON bronze.bronze_jurisdiction_youtube_candidates (jurisdiction_type);

CREATE INDEX IF NOT EXISTS idx_bronze_jurisdiction_youtube_type
    ON bronze.bronze_jurisdiction_youtube (jurisdiction_type);

COMMIT;
