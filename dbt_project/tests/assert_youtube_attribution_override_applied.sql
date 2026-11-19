{{ config(tags=['data_quality', 'youtube', 'event_meeting']) }}

-- Every video on a hand-reviewed channel (seed youtube_channel_attribution_override) must be served with the
-- reviewed jurisdiction and state, never the one discovery guessed (#484, #514, #515). A row here means the mart
-- is not reading int_youtube__attribution_override for that video, or a re-crawl brought the old attribution back.

select
    o.video_id,
    o.channel_id,
    o.state_code    as reviewed_state_code,
    y.state_code    as served_state_code,
    o.jurisdiction_id as reviewed_jurisdiction_id,
    y.jurisdiction_id as served_jurisdiction_id
from {{ ref('int_youtube__attribution_override') }} o
join {{ ref('event_youtube_with_jurisdiction') }} y on y.video_id = o.video_id
where y.jurisdiction_id is distinct from o.jurisdiction_id
   or y.state_code is distinct from o.state_code
