-- Gold: decision analysis shaped to the event_decision writeback contract —
-- column names matching the event_decision serving mart, keyed by
-- (video_id, decision_id). Handoff table pulled back into the warehouse; the UC
-- serving event_decision is a Neon-overwritten mirror and is NOT written here.

select
    video_id,
    decision_id,
    headline,
    decision_statement,
    primary_theme,
    outcome,
    vote_tally,
    human_element,
    competing_views,
    smart_brevity,
    source_ai_model,
    extracted_at
from {{ ref('silver_decision_analysis') }}
