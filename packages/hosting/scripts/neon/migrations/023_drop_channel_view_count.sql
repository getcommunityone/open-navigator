-- Remove redundant channel_view_count; total views are not stored separately.
-- Subscriber and video counts remain on subscriber_count / video_count.

BEGIN;

ALTER TABLE bronze.bronze_events_channels
    DROP COLUMN IF EXISTS channel_view_count;

COMMIT;
