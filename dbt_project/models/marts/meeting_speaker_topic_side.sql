{{ config(materialized='table', tags=['meeting_comments', 'serving'],
          indexes=[{'columns': ['topic_id', 'state_code']}, {'columns': ['video_id']}]) }}

/*
    One row per meeting x public speaker x topic (#1391): the side the speaker's OWN words took on the topic, read by a
    classifier (TypeSafe Jev) from the passages of their turn text that name it, at the topic's current question
    version. A speaker is read only for the topics their own words match (llm.typesafe.speaker_stance).

    side is served only at side_confidence >= var('speaker_side_min_confidence') (calibrated on the hand-labelled gold
    set, web_docs/docs/development/speaker-stance-classifier.md); below it the row says 'not_sure', so a low-confidence
    reading never counts for either side. off_topic readings (a passing mention) are dropped: the speaker did not
    speak on the topic. Heat (1-5) is the same reading's ladder, served at heat_confidence >= var('speaker_heat_min_confidence').
    Provenance: side_method / heat_method = 'classifier', with confidence and version (the question hash).
    No text and no name: join meeting_speaker_position for the speaker's label, which keeps its own privacy rules.
*/

{%- set floor = var('speaker_side_min_confidence') %}
{%- set heat_floor = var('speaker_heat_min_confidence') %}

with r as (
    select *
    from {{ ref('stg_jev__speaker_topic_stance') }}
    where is_current_question_version and side is not null and side <> 'off_topic'
)

select
    r.meeting_speaker_id::text                                            as meeting_speaker_id,
    r.topic_id::int                                                       as topic_id,
    p.video_id::text                                                      as video_id,
    p.meeting_date::date                                                  as meeting_date,
    p.jurisdiction_id::text                                               as jurisdiction_id,
    p.jurisdiction_name::text                                             as jurisdiction_name,
    p.state_code::text                                                    as state_code,
    (case when r.side_confidence >= {{ floor }} then r.side else 'not_sure' end)::text as side,
    r.side_confidence::numeric(4, 3)                                      as side_confidence,
    'classifier'::text                                                    as side_method,
    ('jev:' || r.question_version)::text                                  as side_version,
    (case when r.heat_confidence >= {{ heat_floor }} then r.heat end)::smallint as heat,
    r.heat_confidence::numeric(4, 3)                                      as heat_confidence
from r
inner join {{ ref('meeting_speaker_position') }} as p on p.meeting_speaker_id = r.meeting_speaker_id
where p.is_public_comment and not p.possible_minor
