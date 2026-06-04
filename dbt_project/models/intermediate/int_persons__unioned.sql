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
      - stg_openstates__person     (bronze_persons_scraped, is_usable_person only)
      - stg_osf_ledb__person       (bronze_persons_osf_ledb; candidates, given/family)
      - stg_persons_ai__person     (bronze_persons_from_ai; AI, lowest trust)
      - stg_contributions__person  (bronze_campaigns_contributions; LAST, FIRST)
      - stg_parcels__person        (bronze_addresses owner_name; SURNAME FIRST)
      - stg_990_officers__person   (bronze_990_officers; Form 990 Part VII people,
                                    identity-collapsed to name + EIN, no geography)

    TODO: add stg_nccs__org / stg_orgs_ai__org to a parallel org pool.
*/

with unioned as (
    select * from {{ ref('stg_openstates__person') }}
    union all
    select * from {{ ref('stg_osf_ledb__person') }}
    union all
    select * from {{ ref('stg_persons_ai__person') }}
    union all
    select * from {{ ref('stg_contributions__person') }}
    union all
    select * from {{ ref('stg_parcels__person') }}
    union all
    select * from {{ ref('stg_990_officers__person') }}
)

select
    md5(source_system || '|' || source_pk)  as person_uid,
    source_system,
    source_pk,
    entity_type,
    raw_name,
    name_norm,
    -- display name: title-cased normalized name ("john smith" -> "John Smith")
    initcap(name_norm)                          as full_name,
    -- cheap quality flag: false for orgs, names with digits, and 1-token / 6+-token
    -- strings (titles, date headings, "hours of operation ...", UI chrome). Tune
    -- alongside the is_usable_person filter on the scraped source.
    case
        when entity_type <> 'person' then false
        when name_norm ~ '[0-9]' then false
        when coalesce(array_length(string_to_array(btrim(name_norm), ' '), 1), 0)
             not between 2 and 5 then false
        else true
    end                                         as is_probable_person,
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
