{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'event-extraction', 'ai', 'serving'],
        contract={'enforced': true}
    )
}}

/*
public.event_uncontested_item — the actions a meeting took without debate (#932).

GRAIN  : one row per uncontested item of an analysis that is a row in event_meeting
         (the preferred analysis of one recording).
SOURCE : bronze.bronze_uncontested_items_from_ai (structured_analysis->'uncontested_items').
WHY    : event_decision holds only CONTESTED decisions (the analysis's decisions[]). Consent
         and routine items, including real decisions such as "Approve Data Center Ordinance"
         or a data center moratorium passed on a voice vote, live only in uncontested_items[]
         and were in no table. This mart is their sibling of event_decision.
VOTE   : the extraction's text, as said ("voice vote", "5-0", "unanimous"); not parsed into
         a tally, because it is often not a count. Null when not stated.
KEYS   : PK event_uncontested_item_id = md5(analysis id || '_' || item_id), the same shape
         as event_decision_id, so a public comment's (meeting, item_id) finds it.
         FK event_meeting_id -> event_meeting is an enforced constraint.
PREFERRED: only the recording's preferred analysis (int_preferred_event_analysis, as
         event_decision uses). event_meeting is append-only and still holds rows for analyses
         that were later superseded, so joining it alone would keep two analyses' items for
         one recording. The join to event_meeting is then the parent guard for the FK.
Design : web_docs/docs/development/data-center-who-spoke-up.md
*/

with preferred as (
    select analysis_id from {{ ref('int_preferred_event_analysis') }}
),

meetings as (
    select event_meeting_id, state_code, state, jurisdiction_name, video_id
    from (
        select
            *,
            row_number() over (partition by event_meeting_id order by extracted_at desc) as _rn
        from {{ ref('event_meeting') }}
    ) as m
    where _rn = 1
)

select
    md5(u.source_event_id || '_' || u.item_id)::text   as event_uncontested_item_id,
    m.event_meeting_id::integer                         as event_meeting_id,
    u.item_id::text                                     as item_id,
    u.headline::text                                    as headline,
    u.outcome::text                                     as outcome,
    u.vote::text                                        as vote,
    u.primary_theme::text                               as primary_theme,
    u.primary_cause_ntee::text                          as primary_cause_ntee,
    u.primary_cause_label::text                         as primary_cause_label,
    m.state_code::varchar(2)                            as state_code,
    m.state::text                                       as state,
    m.jurisdiction_name::varchar(200)                   as jurisdiction_name,
    m.video_id::varchar(64)                             as video_id,
    u.source_ai_model::text                             as source_ai_model,
    u.extracted_at::timestamp                           as extracted_at
from {{ ref('bronze_uncontested_items_from_ai') }} as u
inner join preferred as p on p.analysis_id = u.source_event_id
inner join meetings as m on m.event_meeting_id = u.source_event_id
