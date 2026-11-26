{{ config(materialized='table', tags=['marts', 'topics', 'serving']) }}

/*
    Jev's reading of each topic meeting (#1126): how the members of the public and the elected officials who spoke
    leaned on a curated topic. Grain: one row per (video_id, topic_id), for meetings linked to the topic
    (topic_transcript_link) that have a reading under the topic's current Jev question version.

    Jev is a classifier (probabilities only, no text): every lean here is an AI reading of the transcript, never a
    count of speakers, and nothing is tied to a person. "For" and "against" point the way the topic's wording fixes
    them (llm.typesafe.topic_lean.TOPICS: for pickleball, the courts or venue; for water fluoridation, fluoride in the
    water). Flags use the data-center thresholds (data_center_meeting_lean, #1117):
      public_against                  public_lean = 'mostly_opposed' with P >= 0.7;
      public_for                      public_lean = 'mostly_supportive' with P >= 0.7;
      officials_sided_against_public  the public mostly opposed AND officials mostly supportive AND the outcome is
                                      not a denial or a moratorium.
    Which labels are reliable enough to show is decided by the hand check in
    web_docs/docs/development/topic-meeting-lean.md, after the first run.
*/

with screen as (
    select *
    from {{ ref('stg_jev__transcript_topic_lean') }}
    where is_current_question_version
),

link as (
    select topic_id, video_id, state_code, state, jurisdiction_name, event_date
    from {{ ref('topic_transcript_link') }}
),

video as (
    select distinct on (video_id) video_id, nullif(trim(jurisdiction_id), '') as jurisdiction_id
    from {{ ref('event_youtube_with_jurisdiction') }}
    order by video_id
)

select
    s.video_id::text                                                    as video_id,
    s.topic_id::integer                                                 as topic_id,
    l.state_code::text                                                  as state_code,
    l.state::text                                                       as state,
    v.jurisdiction_id::text                                             as jurisdiction_id,
    l.jurisdiction_name::text                                           as jurisdiction_name,
    l.event_date::date                                                  as meeting_date,
    s.public_lean::text                                                 as public_lean,
    s.public_lean_p::numeric                                            as public_lean_p,
    s.official_lean::text                                               as official_lean,
    s.official_lean_p::numeric                                          as official_lean_p,
    s.outcome::text                                                     as outcome,
    (s.public_lean = 'mostly_opposed' and coalesce(s.public_lean_p, 0) >= 0.7)::boolean    as public_against,
    (s.public_lean = 'mostly_supportive' and coalesce(s.public_lean_p, 0) >= 0.7)::boolean as public_for,
    (
        s.public_lean = 'mostly_opposed'
        and s.official_lean = 'mostly_supportive'
        and coalesce(s.outcome, '') not in ('denied', 'moratorium')
    )::boolean                                                          as officials_sided_against_public,
    s.question_version::text                                            as question_version,
    s.screened_at::timestamptz                                          as screened_at
from screen as s
inner join link as l on l.topic_id = s.topic_id and l.video_id = s.video_id
left join video as v on v.video_id = s.video_id
