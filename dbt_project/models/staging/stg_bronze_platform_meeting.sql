{{ config(materialized='view', tags=['staging', 'meetings', 'platform_meetings']) }}

/*
staging.stg_bronze_platform_meeting — meetings read from Granicus portals and the
Legistar Web API (#536). Grain: one row per (platform, meeting_uid), the bronze PK.

Light typing only: trimmed text, the 2-letter state code plus the full state name,
the census geoid taken from the canonical jurisdiction_id ('dakota_27037' -> '27037'),
and a stable text surrogate platform_meeting_id = md5(platform | meeting_uid).

SOURCE: bronze.bronze_platform_meeting (scrapers.platforms.store).
*/

select
    md5(platform || '|' || meeting_uid)                     as platform_meeting_id,
    platform::text                                          as platform,
    meeting_uid::text                                       as meeting_uid,
    portal::text                                            as portal,
    nullif(btrim(jurisdiction_id), '')::text                as jurisdiction_id,
    substring(jurisdiction_id from '_(\d+)$')::text         as census_geoid,
    nullif(btrim(state_code), '')::text                     as state_code,
    {{ state_code_to_name("nullif(btrim(state_code), '')") }} as state,
    nullif(btrim(body_name), '')::text                      as body_name,
    nullif(btrim(title), '')::text                          as title,
    meeting_date::date                                      as meeting_date,
    nullif(btrim(meeting_time), '')::text                   as meeting_time,
    nullif(btrim(location), '')::text                       as location,
    nullif(btrim(agenda_url), '')::text                     as agenda_url,
    nullif(btrim(minutes_url), '')::text                    as minutes_url,
    nullif(btrim(video_url), '')::text                      as video_url,
    video_url_source::text                                  as video_url_source,
    video_clip_id::text                                     as video_clip_id,
    nullif(btrim(detail_url), '')::text                     as detail_url,
    nullif(btrim(agenda_text), '')::text                    as agenda_text,
    nullif(btrim(minutes_text), '')::text                   as minutes_text,
    has_captions::boolean                                   as has_captions,
    transcription_status::text                              as transcription_status,
    source_modified_at::timestamptz                         as source_modified_at,
    first_seen_at::timestamptz                              as first_seen_at,
    fetched_at::timestamptz                                 as fetched_at
from {{ source('bronze', 'bronze_platform_meeting') }}
