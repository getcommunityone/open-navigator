-- Migration 063: drop misleading discovery_confidence on bronze_jurisdiction_youtube.
--
-- Filtering and primary-channel selection use official_meeting_confidence only
-- (see migration 040). discovery_confidence duplicated an older "confidence" name
-- and was confused with the official-channel score.

BEGIN;

ALTER TABLE bronze.bronze_jurisdiction_youtube
    DROP COLUMN IF EXISTS discovery_confidence;

COMMIT;
