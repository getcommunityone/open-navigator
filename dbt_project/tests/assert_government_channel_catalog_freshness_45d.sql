-- #562: government YouTube channels should not go 45+ days without a catalog
-- video when they are marked government in events_channels_search.
-- Warn-only for now: many channels are still catching up after discovery gaps;
-- severity can be raised to error once national crawls are current.
{{ config(severity='warn') }}

select
    channel_id,
    channel_title,
    state_code,
    days_since_last_video,
    latest_video_date
from {{ ref('events_channels_search') }}
where coalesce(is_government, false)
  and days_since_last_video is not null
  and days_since_last_video > 45
