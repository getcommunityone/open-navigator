-- Silver: decisions[] exploded to one row per decision, fields extracted from
-- JSON. posexplode gives a stable per-meeting index so a synthetic decision_id
-- is reproducible when the model didn't supply one. Only rows with a real
-- decision_statement survive — No Fabricated Data (no placeholder decisions).

with valid as (
    select *
    from {{ ref('bronze_transcript_analysis') }}
    where error_message is null
      and get_json_object(analysis_json, '$.decisions') is not null
),

exploded as (
    select
        v.video_id,
        v.source_ai_model,
        v.analyzed_at,
        d.pos as decision_idx,
        d.col as decision_json
    from valid v
    lateral view posexplode(
        from_json(get_json_object(v.analysis_json, '$.decisions'), 'array<string>')
    ) d as pos, col
)

select
    video_id,
    coalesce(
        nullif(get_json_object(decision_json, '$.decision_id'), ''),
        concat(video_id, '_d', decision_idx)
    )                                                                  as decision_id,
    nullif(get_json_object(decision_json, '$.headline'), '')           as headline,
    nullif(get_json_object(decision_json, '$.decision_statement'), '') as decision_statement,
    nullif(get_json_object(decision_json, '$.primary_theme'), '')      as primary_theme,
    nullif(get_json_object(decision_json, '$.outcome'), '')            as outcome,
    nullif(get_json_object(decision_json, '$.vote_tally'), '')         as vote_tally,
    nullif(get_json_object(decision_json, '$.human_element'), '')      as human_element,
    get_json_object(decision_json, '$.competing_views')                as competing_views,
    nullif(get_json_object(decision_json, '$.smart_brevity'), '')      as smart_brevity,
    source_ai_model,
    analyzed_at                                                        as extracted_at
from exploded
where nullif(get_json_object(decision_json, '$.decision_statement'), '') is not null
