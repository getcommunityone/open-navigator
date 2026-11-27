-- Migration: bronze inventory of meeting audio we already hold (#1255)
-- Purpose: one row per (video_id, location) so audio downloads never fetch a file twice.
-- Written by `python -m scrapers.youtube.download_meeting_audio` (it also creates the table if missing).
-- Grain: one row per YouTube video_id per storage location (OneDrive path, local path, or a bronze
-- tracking path whose file wasn't found). Bronze, not served: no FK (bronze_event_youtube.video_id
-- has no unique constraint).
--
-- Usage:
-- psql $OPEN_NAVIGATOR_DATABASE_URL -f 116_create_meeting_audio_inventory.sql

BEGIN;

CREATE TABLE IF NOT EXISTS bronze.bronze_meeting_audio_inventory (
    video_id       text        NOT NULL,
    location_kind  text        NOT NULL,  -- target | local | tracked
    location       text        NOT NULL,  -- e.g. onedrive:CommunityOne/youtube_audio/va/.../x.opus
    size_bytes     bigint,
    seen_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (video_id, location)
);

COMMENT ON TABLE bronze.bronze_meeting_audio_inventory IS
    'Meeting audio already held, by YouTube video_id and location (#1255). Checked before any download.';

COMMIT;
