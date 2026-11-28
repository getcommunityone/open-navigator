{{ config(
    post_hook=["analyze {{ this }}"],materialized='table', tags=['intermediate', 'trending_terms'],
          indexes=[{'columns': ['word'], 'unique': true}]) }}

/*
    Name words (#1399): one row per lower-case word used as a person's first or last name anywhere in our name data,
    with how many distinct names use it in each position. Feeds the privacy filter on candidate trending terms
    (int_trending_term__candidate), so a private person's name can't surface as a trend.

    Sources: the self-introductions in meeting comments (residents, staff: int_meeting_comment__flags.intro_name),
    elected officials (person_government) and state legislators (legislator). Private (gold only, never published):
    it only ever drops terms.
*/

with names as (
    select distinct lower(btrim(intro_name)) as full_name
    from {{ ref('int_meeting_comment__flags') }}
    where intro_name is not null
    union
    select distinct lower(btrim(full_name)) from {{ ref('person_government') }} where full_name is not null
    union
    select distinct lower(btrim(full_name)) from {{ ref('legislator') }} where full_name is not null
),

parts as (
    select full_name, regexp_split_to_array(regexp_replace(full_name, '[^a-z'' -]', '', 'g'), '[ -]+') as a
    from names
),

pos as (
    select a[1] as word, 'given' as position, full_name from parts where array_length(a, 1) >= 1
    union all
    select a[array_length(a, 1)], 'surname', full_name from parts where array_length(a, 1) >= 2
)

select
    word::text                                                              as word,
    count(distinct full_name) filter (where position = 'given')::int        as n_given,
    count(distinct full_name) filter (where position = 'surname')::int      as n_surname
from pos
where word ~ '^[a-z][a-z'']+$'
group by word
