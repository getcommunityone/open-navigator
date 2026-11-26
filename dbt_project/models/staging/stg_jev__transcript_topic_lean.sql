/*
    Staging (#1126): Jev's reading of how the public and elected officials leaned on each curated topic, per meeting.
    Grain: one row per (video_id, topic_id, question_version). Jev is a classifier: probabilities only, no text.

    is_current_question_version: the topic's most recently screened question version (per topic, since each topic's
    wording is versioned on its own). Consumers keep only current rows: older wordings aren't comparable.

    Builds as an empty, typed relation until the first `python -m llm.typesafe.screen_transcripts --topic ...` run
    creates the bronze table, so dbt runs keep passing: an honest "not read yet".
*/

{%- set src = source('bronze', 'bronze_transcript_topic_lean_jev') -%}
{%- set bronze_exists = execute and adapter.get_relation(
        database=src.database, schema=src.schema, identifier=src.identifier) is not none -%}

{% if bronze_exists %}

with current_version as (
    select distinct on (topic_id) topic_id, question_version
    from (
        select topic_id, question_version, max(screened_at) as last_screened
        from {{ src }}
        group by topic_id, question_version
    ) as v
    order by topic_id, last_screened desc
)

select
    b.video_id::text                                                      as video_id,
    b.topic_id::integer                                                   as topic_id,
    b.question_version::text                                              as question_version,
    b.model::text                                                         as model,
    nullif(b.public_lean, '')::text                                       as public_lean,
    (b.public_lean_probabilities ->> nullif(b.public_lean, ''))::numeric  as public_lean_p,
    nullif(b.official_lean, '')::text                                     as official_lean,
    (b.official_lean_probabilities ->> nullif(b.official_lean, ''))::numeric as official_lean_p,
    nullif(b.outcome, '')::text                                           as outcome,
    (b.outcome_probabilities ->> nullif(b.outcome, ''))::numeric          as outcome_p,
    (cv.question_version is not null)::boolean                            as is_current_question_version,
    b.screened_at::timestamptz                                            as screened_at
from {{ src }} as b
left join current_version as cv
    on cv.topic_id = b.topic_id and cv.question_version = b.question_version

{% else %}

select
    cast(null as text)        as video_id,
    cast(null as integer)     as topic_id,
    cast(null as text)        as question_version,
    cast(null as text)        as model,
    cast(null as text)        as public_lean,
    cast(null as numeric)     as public_lean_p,
    cast(null as text)        as official_lean,
    cast(null as numeric)     as official_lean_p,
    cast(null as text)        as outcome,
    cast(null as numeric)     as outcome_p,
    cast(null as boolean)     as is_current_question_version,
    cast(null as timestamptz) as screened_at
where false

{% endif %}
