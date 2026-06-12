{{
    config(
        materialized='table',
        on_schema_change='fail',
        tags=['marts', 'browse', 'transcripts'],
        contract={'enforced': true}
    )
}}

/*
public.browse_directory_summary — category-grain rollup powering the homepage
"Browse" cards (one card per entity_type, with national + per-state totals).

GRAIN: one row per (entity_type, state_code) where state_code IS NULL is the
NATIONAL rollup and a non-null state_code is that state's rollup. Built with
GROUPING SETS over int_browse_entity_transcripts so:
  * the national COUNT(DISTINCT video_id) is the GENUINE distinct count — a
    place/topic/question video is counted ONCE nationally even if it spans
    multiple states.
  * entity_count = COUNT(DISTINCT entity_id) at each grain.

CAUSES: a single NATIONAL row (state_code NULL) with transcript_count = 0 and
entity_count = the NTEE tag universe — no cause->transcript linkage exists, so
0 transcripts is honest (no fabricated data). No per-state cause rows.

PK: declared on the surrogate state_code_key = COALESCE(state_code, '_ALL_')
because Postgres PK columns must be NOT NULL and the national rollup carries a
NULL state_code. state_code itself stays NULL for the national row (the API
filters on state_code IS NULL); state_code_key exists ONLY to give the contract
a non-null composite key.

SOURCE : ref('int_browse_entity_transcripts') + ref('tag').
TARGET : public.browse_directory_summary (served via publish_public_serving).
*/

with

bridge as (
    select * from {{ ref('int_browse_entity_transcripts') }}
),

rollup_raw as (
    select
        entity_type,
        state_code,
        grouping(state_code)                as is_national,
        count(distinct video_id)::integer   as transcript_count,
        count(distinct entity_id)::integer  as entity_count
    from bridge
    group by grouping sets (
        (entity_type),
        (entity_type, state_code)
    )
),

-- Drop the per-state grouping-set row whose state_code is NULL: a video with a
-- NULL state_code would otherwise emit a second "national-looking" row
-- (state_code NULL, is_national=0) that collides with the true national rollup
-- (is_national=1) on the COALESCE(state_code,'_ALL_') PK surrogate. Those rows
-- are already counted in the national row, so we simply exclude them per-state.
rollup as (
    select
        entity_type,
        case when is_national = 1 then null else state_code end as state_code,
        transcript_count,
        entity_count
    from rollup_raw
    where is_national = 1
       or state_code is not null
),

cause_national as (
    select
        'cause'::text                       as entity_type,
        cast(null as text)                  as state_code,
        0::integer                          as transcript_count,
        count(*)::integer                   as entity_count
    from {{ ref('tag') }}
    where vocabulary = 'ntee'
),

unioned as (
    select entity_type, state_code, transcript_count, entity_count from rollup
    union all
    select entity_type, state_code, transcript_count, entity_count from cause_national
),

-- Dense-rank entity_types by national transcript volume for default card order.
national_rank as (
    select
        entity_type,
        dense_rank() over (order by transcript_count desc)::integer as sort_rank
    from unioned
    where state_code is null
)

select
    u.entity_type::text                             as entity_type,
    u.state_code::text                              as state_code,
    coalesce(u.state_code, '_ALL_')::text           as state_code_key,
    u.transcript_count::integer                     as transcript_count,
    u.entity_count::integer                         as entity_count,
    nr.sort_rank::integer                           as sort_rank
from unioned u
left join national_rank nr
    on nr.entity_type = u.entity_type
