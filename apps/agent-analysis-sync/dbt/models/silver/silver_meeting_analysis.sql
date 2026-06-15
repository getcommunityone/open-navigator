-- Silver: meeting-level fields extracted from the analysis JSON, one row per
-- transcript. nullif(...,'') turns empty strings into NULL (an honest "no
-- summary" rather than blank text). A row survives only if the model produced a
-- real meeting_summary — No Fabricated Data.

with valid as (
    select *
    from {{ ref('bronze_transcript_analysis') }}
    where error_message is null
      and get_json_object(analysis_json, '$.meeting') is not null
)

select
    video_id,
    nullif(get_json_object(analysis_json, '$.meeting.meeting_summary'), '') as meeting_summary,
    nullif(get_json_object(analysis_json, '$.meeting.agenda_summary'), '')  as agenda_summary,
    get_json_object(analysis_json, '$.meeting.session_info')                as session_info,
    source_ai_model,
    analyzed_at                                                             as extracted_at
from valid
where nullif(get_json_object(analysis_json, '$.meeting.meeting_summary'), '') is not null
