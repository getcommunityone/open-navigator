{{ config(materialized='view') }}

/*
    Staging (#1391): Jev's reading of ONE public speaker's own words on one topic, typed. One row per
    (meeting_speaker_id, topic_id, question_version). side: for / against / concerns_only / no_position / off_topic,
    with its probability (side_confidence); heat 1-5 from a ladder of yes/no thresholds (P(heat >= k), k = 2..5), with
    the weakest decision's margin as heat_confidence. Probabilities only; Jev writes no text and nothing here names a
    person (meeting_speaker_id is a hash of meeting + name key, never linked across meetings).

    is_current_question_version: per topic, the version read most recently (a reworded topic takes over as its rows
    land). Builds as an empty, typed relation until `python -m llm.typesafe.speaker_stance` first creates the table.
    The bronze columns are llm.typesafe.speaker_stance.CREATE_SQL's (a test keeps them in step).
*/

{%- set bronze = source('bronze', 'bronze_speaker_topic_stance_jev') -%}
{%- set bronze_exists = execute and adapter.get_relation(
        database=bronze.database, schema=bronze.schema, identifier=bronze.identifier) is not none -%}

{% if bronze_exists %}

with src as (
    select * from {{ bronze }}
),

current_version as (
    select distinct on (topic_id) topic_id, question_version
    from (
        select topic_id, question_version, max(screened_at) as last_screened_at
        from src
        group by topic_id, question_version
    ) as v
    order by topic_id, last_screened_at desc
)

select
    s.meeting_speaker_id::text                   as meeting_speaker_id,
    s.topic_id::integer                          as topic_id,
    s.topic_slug::text                           as topic_slug,
    s.question_version::text                     as question_version,
    s.video_id::text                             as video_id,
    s.model::text                                as model,
    s.state_version::text                        as state_version,
    nullif(s.side, '')::text                     as side,
    s.side_confidence::numeric(6, 4)             as side_confidence,
    s.heat::integer                              as heat,
    s.heat_confidence::numeric(6, 4)             as heat_confidence,
    s.input_tokens::integer                      as input_tokens,
    s.screened_at                                as screened_at,
    (c.question_version is not null)             as is_current_question_version
from src as s
left join current_version as c
    on c.topic_id = s.topic_id and c.question_version = s.question_version

{% else %}

select
    cast(null as text)          as meeting_speaker_id,
    cast(null as integer)       as topic_id,
    cast(null as text)          as topic_slug,
    cast(null as text)          as question_version,
    cast(null as text)          as video_id,
    cast(null as text)          as model,
    cast(null as text)          as state_version,
    cast(null as text)          as side,
    cast(null as numeric(6, 4)) as side_confidence,
    cast(null as integer)       as heat,
    cast(null as numeric(6, 4)) as heat_confidence,
    cast(null as integer)       as input_tokens,
    cast(null as timestamptz)   as screened_at,
    cast(null as boolean)       as is_current_question_version
where false

{% endif %}
