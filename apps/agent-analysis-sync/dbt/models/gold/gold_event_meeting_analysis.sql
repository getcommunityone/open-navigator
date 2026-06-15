-- Gold: meeting analysis shaped to the event_meeting writeback contract — exact
-- column names the local `gold` mart / promote path expects, keyed by video_id.
-- This is the handoff table pulled back into the warehouse (the UC serving
-- event_meeting is a Neon-overwritten mirror and is NOT written here).

select
    video_id,
    meeting_summary,
    agenda_summary,
    session_info,
    source_ai_model,
    extracted_at
from {{ ref('silver_meeting_analysis') }}
