{{ config(materialized='table') }}

/*
    Intermediate (MDM): the conformed person pool — every source name mapped onto
    one schema and stacked. This is the table Splink reads to build the person
    clusters (see web_docs/docs/dbt/entity-resolution-mdm.md, Layer 2→3).

    Grain: one row per source name occurrence (NOT deduplicated). entity_type
    ('person' | 'organization') is carried through so Splink can block within type
    — org-shaped contributor/owner names stay out of the person match pool and
    feed a future organization master instead.

    Person sources wired so far:
      - stg_openstates__person     (bronze_persons_scraped; has given/family + ids)
      - stg_persons_ai__person     (bronze_persons_from_ai; AI, lowest trust)
      - stg_contributions__person  (bronze_campaigns_contributions; LAST, FIRST)
      - stg_parcels__person        (bronze_addresses owner_name; SURNAME FIRST)

    TODO: add stg_nccs__org / stg_orgs_ai__org to a parallel org pool.
*/

with unioned as (
    select * from {{ ref('stg_openstates__person') }}
    union all
    select * from {{ ref('stg_persons_ai__person') }}
    union all
    select * from {{ ref('stg_contributions__person') }}
    union all
    select * from {{ ref('stg_parcels__person') }}
)

select
    md5(source_system || '|' || source_pk)  as person_uid,
    source_system,
    source_pk,
    entity_type,
    raw_name,
    name_norm,
    given_name_norm,
    family_name_norm,
    name_phonetic_first,
    name_phonetic_last,
    email,
    phone,
    ein,
    external_id,
    city_norm,
    state_code,
    zip5
from unioned
