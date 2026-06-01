{{ config(materialized='table') }}

/*
    Mart (MDM): the source-system page link for a person occurrence, where the
    source provides one. Lets the frontend show a "view source" link.

      - bronze_persons_scraped  -> profile_url, else the source_page_url it was
                                   scraped from (100% have a page url)
      - bronze_persons_osf_ledb -> ballotpedia_url

    Grain: one row per person_uid that has a source link. Restricted to real
    people (entity_type = 'person', is_probable_person) so every person_uid
    resolves to mdm_person (enforced FK).
*/

with persons as (
    select person_uid, master_person_id, match_confidence, source_system, source_pk, full_name
    from {{ ref('int_persons__clustered') }}
    where source_system in ('bronze_persons_scraped', 'bronze_persons_osf_ledb')
      and entity_type = 'person'
      and is_probable_person
),

scraped as (
    select
        bronze_person_id::text  as source_pk,
        nullif(profile_url, '')      as profile_url,
        nullif(source_page_url, '')  as source_page_url
    from {{ ref('stg_bronze_persons_scraped') }}
),

ledb as (
    select
        (ledb_candid::bigint)::text  as source_pk,
        nullif(ballotpedia_url, '')  as ballotpedia_url
    from {{ source('bronze', 'bronze_persons_osf_ledb') }}
)

-- distinct on person_uid: a source row could repeat its key; keep one link per person
select distinct on (p.person_uid)
    p.person_uid,
    p.master_person_id,
    p.match_confidence,
    p.full_name,
    p.source_system,
    p.source_pk,
    case p.source_system
        when 'bronze_persons_scraped'  then coalesce(s.profile_url, s.source_page_url)
        when 'bronze_persons_osf_ledb' then l.ballotpedia_url
    end                          as source_url,
    s.profile_url,
    s.source_page_url
from persons p
left join scraped s
    on p.source_system = 'bronze_persons_scraped' and s.source_pk = p.source_pk
left join ledb l
    on p.source_system = 'bronze_persons_osf_ledb' and l.source_pk = p.source_pk
where coalesce(
        case p.source_system
            when 'bronze_persons_scraped'  then coalesce(s.profile_url, s.source_page_url)
            when 'bronze_persons_osf_ledb' then l.ballotpedia_url
        end, '') <> ''
order by p.person_uid, s.profile_url nulls last
