{{ config(materialized='table') }}

/*
    Mart (MDM): the source-system page link for a person occurrence, where the
    source provides one. Lets the frontend show a labelled "view source" link and
    a biography when the source page carries one.

      - bronze_persons_scraped  -> profile_url, else the source_page_url it was
                                   scraped from (100% have a page url); label is
                                   the scraped organization, bio from the page
      - bronze_persons_osf_ledb -> ballotpedia_url (label "Ballotpedia")

    source_url is the page where the person's name/details were published; when a
    person has both a directory page and a richer profile page, the profile_url
    (the one that carries the biography) wins. biography is backfilled from the
    curated official_photo_override seed (a mayor's "meet the <office>" page,
    shared with contact_official) when the source page itself has none.

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
        bronze_person_id::text       as source_pk,
        nullif(profile_url, '')      as profile_url,
        nullif(source_page_url, '')  as source_page_url,
        nullif(organization, '')     as organization
    from {{ ref('stg_bronze_persons_scraped') }}
),

-- Biography lives on the bronze row (staging drops it); keyed by the same id.
scraped_bio as (
    select
        id::text                     as source_pk,
        nullif(trim(biography), '')  as biography
    from {{ source('bronze', 'bronze_persons_scraped') }}
),

ledb as (
    select
        (ledb_candid::bigint)::text  as source_pk,
        nullif(ballotpedia_url, '')  as ballotpedia_url
    from {{ source('bronze', 'bronze_persons_osf_ledb') }}
),

-- Curated/scraped official bios (mayors etc.), keyed by name. Same seed that
-- patches contact_official, reused here to fill a missing biography.
bio_override as (
    select lower(trim(full_name)) as full_name_key,
           nullif(trim(biography), '') as biography
    from {{ ref('official_photo_override') }}
    where nullif(trim(biography), '') is not null
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
    -- Human label for the source link.
    case p.source_system
        when 'bronze_persons_scraped'  then coalesce(s.organization, 'Official directory')
        when 'bronze_persons_osf_ledb' then 'Ballotpedia'
    end                          as source_label,
    s.profile_url,
    s.source_page_url,
    -- Bio from the source page, else the curated official override seed.
    coalesce(sb.biography, bo.biography) as biography
from persons p
left join scraped s
    on p.source_system = 'bronze_persons_scraped' and s.source_pk = p.source_pk
left join scraped_bio sb
    on p.source_system = 'bronze_persons_scraped' and sb.source_pk = p.source_pk
left join ledb l
    on p.source_system = 'bronze_persons_osf_ledb' and l.source_pk = p.source_pk
left join bio_override bo
    on bo.full_name_key = lower(trim(p.full_name))
where coalesce(
        case p.source_system
            when 'bronze_persons_scraped'  then coalesce(s.profile_url, s.source_page_url)
            when 'bronze_persons_osf_ledb' then l.ballotpedia_url
        end, '') <> ''
order by p.person_uid, s.profile_url nulls last
