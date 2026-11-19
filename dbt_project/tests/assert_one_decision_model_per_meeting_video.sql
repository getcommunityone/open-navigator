-- #519: event_decision must not serve two source_ai_model values for one video.
-- Joins analysis rows so the grain is the meeting video (event_id), not analysis_id.

select
    ba.event_id as legacy_event_id,
    count(distinct ed.source_ai_model) as n_models
from {{ ref('event_decision') }} ed
inner join {{ source('bronze', 'bronze_events_analysis_ai') }} ba
    on ba.id = ed.analysis_id
group by ba.event_id
having count(distinct ed.source_ai_model) > 1
