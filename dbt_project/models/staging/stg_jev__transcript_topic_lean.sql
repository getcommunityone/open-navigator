{{ config(materialized='view') }}

/*
    Staging (#1126): Jev's per-meeting reading of a topic, typed. One row per (video_id, topic_id, question_version).
    Jev is a classifier: probabilities only, no text, and every row is an aggregate reading of one meeting.

    chunk_selection / passages_covered (#1145): keyword_passages = the chunks holding the topic's keyword passages were
    sent (passages_covered of keyword_chunks); evenly_spaced = no keyword in the caption text, so spread chunks were.

    is_current_question_version: per topic, the version screened most recently. Not hardcoded, so a reworded topic
    question takes over as soon as its first rows land; older versions asked differently and aren't comparable.

    The bronze columns are the ones llm.typesafe.topic_lean.CREATE_SQL creates (a test keeps them in step, #1201).
    Builds as an empty, typed relation until the first `python -m llm.typesafe.screen_transcripts --topic ...` run
    creates the bronze table, so dbt runs keep passing: an honest "not read yet".
*/

{%- set bronze = source('bronze', 'bronze_transcript_topic_lean_jev') -%}
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
    s.video_id::text                                                  as video_id,
    s.topic_id::integer                                               as topic_id,
    s.topic_slug::text                                                as topic_slug,
    s.question_version::text                                          as question_version,
    s.model::text                                                     as model,
    nullif(s.public_lean, '')::text                                   as public_lean_label,
    s.public_lean_probabilities                                       as public_lean_probabilities,
    nullif(s.official_lean, '')::text                                 as official_lean_label,
    s.official_lean_probabilities                                     as official_lean_probabilities,
    nullif(s.outcome, '')::text                                       as outcome,
    s.outcome_probabilities                                           as outcome_probabilities,
    (s.outcome_probabilities ->> nullif(s.outcome, ''))::numeric      as outcome_p,
    s.chunk_count::integer                                            as chunk_count,
    s.chunks_screened::integer                                        as chunks_screened,
    s.keyword_chunks::integer                                         as keyword_chunks,
    s.chunk_selection::text                                           as chunk_selection,
    s.passages_covered::integer                                       as passages_covered,
    s.input_tokens::integer                                           as input_tokens,
    s.screened_at                                                     as screened_at,
    (c.question_version is not null)                                  as is_current_question_version
from src as s
left join current_version as c
    on c.topic_id = s.topic_id and c.question_version = s.question_version

{% else %}

select
    cast(null as text)        as video_id,
    cast(null as integer)     as topic_id,
    cast(null as text)        as topic_slug,
    cast(null as text)        as question_version,
    cast(null as text)        as model,
    cast(null as text)        as public_lean_label,
    cast(null as jsonb)       as public_lean_probabilities,
    cast(null as text)        as official_lean_label,
    cast(null as jsonb)       as official_lean_probabilities,
    cast(null as text)        as outcome,
    cast(null as jsonb)       as outcome_probabilities,
    cast(null as numeric)     as outcome_p,
    cast(null as integer)     as chunk_count,
    cast(null as integer)     as chunks_screened,
    cast(null as integer)     as keyword_chunks,
    cast(null as text)        as chunk_selection,
    cast(null as integer)     as passages_covered,
    cast(null as integer)     as input_tokens,
    cast(null as timestamptz) as screened_at,
    cast(null as boolean)     as is_current_question_version
where false

{% endif %}
