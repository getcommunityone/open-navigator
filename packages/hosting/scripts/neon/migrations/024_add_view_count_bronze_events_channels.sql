-- Total lifetime channel views from public /about scrape (view_count).
-- channel_about_links.py also ALTERs this column.

BEGIN;

ALTER TABLE bronze.bronze_events_channels
    ADD COLUMN IF NOT EXISTS view_count BIGINT;

COMMIT;
