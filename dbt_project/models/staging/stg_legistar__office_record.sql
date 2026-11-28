{{ config(materialized='view', tags=['staging', 'bodies', 'platform_meetings']) }}

/*
staging.stg_legistar__office_record (#1443): current Legistar office records, one row per (portal,
office_record_id), with the body and its jurisdiction. Light typing only.
SOURCE: bronze.bronze_legistar_office_record (scrapers.platforms.legistar_people).
*/

select
    r.portal::text                                          as portal,
    r.office_record_id::integer                             as office_record_id,
    nullif(btrim(r.jurisdiction_id), '')::text              as jurisdiction_id,
    r.person_id::integer                                    as legistar_person_id,
    btrim(r.full_name)::text                                as full_name,
    r.body_id::integer                                      as body_id,
    nullif(btrim(coalesce(r.body_name, b.body_name)), '')::text as body_name,
    nullif(btrim(r.title), '')::text                        as title,
    nullif(btrim(r.member_type), '')::text                  as member_type,
    r.start_date::date                                      as start_date,
    r.end_date::date                                        as end_date,
    'https://webapi.legistar.com/v1/' || r.portal || '/officerecords/' || r.office_record_id::text as source_url,
    r.fetched_at::timestamptz                               as fetched_at
from {{ source('bronze', 'bronze_legistar_office_record') }} as r
left join {{ source('bronze', 'bronze_legistar_body') }} as b
    on b.portal = r.portal and b.body_id = r.body_id
where nullif(btrim(r.full_name), '') is not null
