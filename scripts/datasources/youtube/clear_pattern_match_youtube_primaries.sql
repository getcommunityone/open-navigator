-- Bulk clear pattern_match YouTube primaries on scraped jurisdiction tables.
-- Prefer the repair script (restores verified channels from gemini cache + bronze events):
--   .venv/bin/python scripts/datasources/youtube/repair_scraped_youtube_channels.py --apply
--
-- Use this SQL only for a blunt reset (no restore).

BEGIN;

UPDATE bronze.bronze_jurisdictions_counties_scraped
SET youtube_channel_url = NULL,
    youtube_channel_id = NULL,
    youtube_channel_selection_method = NULL,
    youtube_channel_selection_confidence = NULL
WHERE youtube_channel_selection_method = 'pattern_match'
   OR youtube_channel_url ILIKE '%@CalhounCounty'
   OR youtube_channel_url ~* 'youtube\.com/@[A-Za-z0-9_]+County/?$';

UPDATE bronze.bronze_jurisdictions_municipalities_scraped
SET youtube_channel_url = NULL,
    youtube_channel_id = NULL,
    youtube_channel_selection_method = NULL,
    youtube_channel_selection_confidence = NULL
WHERE youtube_channel_selection_method = 'pattern_match'
   OR youtube_channel_url ~* 'youtube\.com/@[A-Za-z0-9_]+County/?$';

COMMIT;
