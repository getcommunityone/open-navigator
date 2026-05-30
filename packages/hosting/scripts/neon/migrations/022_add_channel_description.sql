-- Add channel About-tab description (subs/video use existing INTEGER columns).
-- channel_about_links.py ALTERs this too; migration is for ops / fresh DBs.

BEGIN;

ALTER TABLE bronze.bronze_events_channels
    ADD COLUMN IF NOT EXISTS channel_description TEXT;

COMMIT;
