{{
  config(
    materialized='table',
    tags=['marts', 'ai-extraction', 'provenance', 'production'],
    unique_key='analysis_id',
    indexes=[
      {'columns': ['legacy_event_id'], 'type': 'btree'},
      {'columns': ['video_id'], 'type': 'btree'}
    ]
  )
}}

/*
How each AI analysis was made (#798): one row per analysis in bronze_events_analysis_ai.

The decision page's "how this summary was made" panel reads this by analysis_id
(= event_decision.analysis_id). It carries only facts the analysis run recorded:

  * ai_model, generated_at   - bronze ai_model, created_at
  * analysis_tier            - light | full, from the run metadata (NULL before migration 115)
  * prompt_name, prompt_sha  - split from prompt_version ("<name>@<sha12>"). The old constant
                               "v1.0" and "<name>@unrecorded" give NULL, never a made-up version
  * transcript_source        - where the transcript text came from (NULL when not recorded)
  * is_preferred             - this is the analysis int_preferred_event_analysis chose to show
  * analyses_for_meeting     - how many publishable analyses exist for the meeting, so the page can
                               say when it chose between several

Same candidate filter as int_preferred_event_analysis, so is_preferred is true for exactly one row
per meeting video.
*/

select
    a.id                                              as analysis_id,
    a.event_id                                        as legacy_event_id,
    a.video_id::text                                  as video_id,
    e.state                                           as state_code,
    a.ai_model::text                                  as ai_model,
    a.created_at                                      as generated_at,
    a.analysis_tier::text                             as analysis_tier,
    case when position('@' in coalesce(a.prompt_version, '')) > 0
         then nullif(split_part(a.prompt_version, '@', 1), '') end::text as prompt_name,
    case when position('@' in coalesce(a.prompt_version, '')) > 0
         then nullif(nullif(split_part(a.prompt_version, '@', 2), ''), 'unrecorded') end::text as prompt_sha,
    a.transcript_source::text                         as transcript_source,
    (p.analysis_id is not null)                       as is_preferred,
    (count(*) over (partition by a.event_id))::int    as analyses_for_meeting
from {{ source('bronze', 'bronze_events_analysis_ai') }} a
left join {{ ref('int_preferred_event_analysis') }} p
    on p.analysis_id = a.id
left join {{ source('civic_core', 'civic_event') }} e
    on e.legacy_id = a.event_id
where a.structured_analysis is not null
  and {{ is_publishable_governance_analysis('a.structured_analysis') }}
