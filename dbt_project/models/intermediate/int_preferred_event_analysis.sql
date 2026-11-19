{{
  config(
    materialized='view',
    tags=['intermediate', 'ai-extraction']
  )
}}

/*
One preferred analysis row per meeting video (#519).

bronze_events_analysis_ai is keyed on (event_id, analysis_type, ai_model), so a
Gemma load for a video that already has Gemini adds a second analysis. Downstream
marts (event_meeting, event_decision, …) would otherwise surface two decision
sets for the same meeting.

Selection rule (documented in
web_docs/docs/development/analysis-model-preference.md):
  1. Prefer Gemini-family models over Gemma over anything else
  2. Tie-break: newest created_at, then highest analysis id
*/

select
    analysis_id,
    legacy_event_id,
    source_ai_model,
    created_at
from (
    select
        id as analysis_id,
        event_id as legacy_event_id,
        ai_model as source_ai_model,
        created_at,
        row_number() over (
            partition by event_id
            order by
                case
                    when lower(coalesce(ai_model, '')) like '%gemini%' then 1
                    when lower(coalesce(ai_model, '')) like '%gemma%' then 2
                    else 3
                end,
                created_at desc nulls last,
                id desc
        ) as _rn
    from {{ source('bronze', 'bronze_events_analysis_ai') }}
    where structured_analysis is not null
      and {{ is_publishable_governance_analysis('structured_analysis') }}
) ranked
where _rn = 1
