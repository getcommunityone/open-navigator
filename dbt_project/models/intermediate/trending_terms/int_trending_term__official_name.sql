{{ config(materialized='table', tags=['intermediate', 'trending_terms'],
          indexes=[{'columns': ['name_key'], 'unique': true}]) }}

/*
    Public officials' names as "first last" (#1399): one row per lower-case first+last name of an elected official
    (person_government) or state legislator (legislator). A candidate term shaped like a person's name may surface
    only when it is one of these (or on the reviewed public-figure seed). Gold only.
*/

with names as (
    select lower(btrim(full_name)) as full_name from {{ ref('person_government') }} where full_name is not null
    union
    select lower(btrim(full_name)) from {{ ref('legislator') }} where full_name is not null
),

parts as (
    select regexp_split_to_array(regexp_replace(full_name, '[^a-z'' -]', '', 'g'), '[ -]+') as a from names
)

select distinct (a[1] || ' ' || a[array_length(a, 1)])::text as name_key
from parts
where array_length(a, 1) >= 2 and a[1] ~ '^[a-z]{2,}$' and a[array_length(a, 1)] ~ '^[a-z'']{2,}$'
