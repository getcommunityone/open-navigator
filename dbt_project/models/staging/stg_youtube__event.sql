{{ config(materialized='view') }}

/*
    Staging: YouTube meeting-video events (1 row per video_id).

    Reads the RAW landing table bronze.bronze_events_youtube, populated by the
    LAND loader ingestion.youtube.events (which lands pre-collected video records
    verbatim — title, published_at, channel metadata — with NO derivation). This
    model reproduces the derivation that used to live in the Python scraper/loader
    (scripts/datasources/youtube/load_youtube_events_to_postgres.py):

      - event_date: parsed from the meeting TITLE (e.g. "Council Meeting
        9/23/2024" -> 2024-09-23), mirroring extract_meeting_date_from_title /
        resolve_meeting_event_date. Falls back to published_at::date when the
        title carries no parseable date. The Python code preferred the title
        date over the upload day; this CTE does the same.
      - channel_type: keyword classification of jurisdiction_name / title
        (city/county/state/school) mirroring video_to_event_record's logic, with
        the landed channel_type as a fallback.
      - dedup: collapse to ONE row per video_id (keep most recently loaded),
        replacing the Python dedupe_meeting_videos step.

    All done in SQL against the raw bronze columns. Four-CTE template:
    source -> renamed -> derived -> final. See dbt_project/CONVENTIONS.md.

    Regex notes (Postgres substring/regexp; meeting titles carry dates in many
    shapes — M/D/YYYY, M-D-YYYY, YYYY-MM-DD, and "Month D, YYYY"). The Python
    parser preferred the LAST date token in the title; SQL keeps it simple and
    takes the first well-formed match, which is equivalent for the common
    "<body> <date>" title shape.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_events_youtube') }}
),

renamed as (
    select
        video_id,
        event_id,
        nullif(trim(title), '')                              as title,
        nullif(trim(description), '')                        as description,
        published_at                                         as published_at,
        nullif(trim(jurisdiction_id), '')                    as jurisdiction_id,
        nullif(trim(jurisdiction_name), '')                  as jurisdiction_name,
        nullif(trim(jurisdiction_type), '')                  as jurisdiction_type,
        upper(nullif(trim(state_code), ''))                  as state_code,
        nullif(trim(state), '')                              as state,
        nullif(trim(city), '')                               as city,
        nullif(trim(channel_id), '')                         as channel_id,
        nullif(trim(channel_url), '')                        as channel_url,
        nullif(trim(channel_type), '')                       as channel_type_raw,
        nullif(trim(meeting_type), '')                       as meeting_type,
        nullif(trim(video_url), '')                          as video_url,
        nullif(trim(location_description), '')               as location_description,
        view_count                                           as view_count,
        duration_minutes                                     as duration_minutes,
        like_count                                           as like_count,
        nullif(trim(language), '')                           as language,
        nullif(trim(datasource), '')                         as datasource,
        nullif(trim(datasource_id), '')                      as datasource_id,
        coalesce(last_updated, loaded_at)                    as source_ingested_at
    from source
    where video_id is not null
      and length(trim(video_id)) > 0
),

derived as (
    select
        video_id,
        event_id,
        title,
        description,
        published_at,
        jurisdiction_id,
        jurisdiction_name,
        jurisdiction_type,
        state_code,
        state,
        city,
        channel_id,
        channel_url,
        meeting_type,
        video_url,
        location_description,
        view_count,
        duration_minutes,
        like_count,
        coalesce(language, 'en')                             as language,
        datasource,
        datasource_id,
        source_ingested_at,

        -- event_date: prefer a date parsed from the title, else the upload day.
        coalesce(
            -- YYYY-MM-DD
            (substring(title from '(\d{4}-\d{1,2}-\d{1,2})'))::date,
            -- M/D/YYYY or M-D-YYYY -> to_date handles both separators via FMMM
            case
                when title ~ '\d{1,2}[/-]\d{1,2}[/-]\d{4}'
                then to_date(
                    replace(substring(title from '(\d{1,2}[/-]\d{1,2}[/-]\d{4})'), '-', '/'),
                    'FMMM/FMDD/YYYY'
                )
            end,
            -- "Month D, YYYY" / "Month D YYYY"
            case
                when title ~* '(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(st|nd|rd|th)?,?\s+\d{4}'
                then to_date(
                    regexp_replace(
                        substring(title from '(?i)((jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(st|nd|rd|th)?,?\s+\d{4})'),
                        '(\d{1,2})(st|nd|rd|th)', '\1'
                    ),
                    'FMMonth FMDD, YYYY'
                )
            end,
            published_at::date
        )                                                    as event_date,

        -- channel_type: keyword classification (city/county/state/school) from
        -- jurisdiction_name then title, else the landed channel_type, else unknown.
        coalesce(
            case
                when lower(coalesce(jurisdiction_name, '') || ' ' || coalesce(title, '')) ~ '\m(county|parish)\M'  then 'county'
                when lower(coalesce(jurisdiction_name, '') || ' ' || coalesce(title, '')) ~ '\m(state|commonwealth)\M' then 'state'
                when lower(coalesce(jurisdiction_name, '') || ' ' || coalesce(title, '')) ~ '\m(school|district|education)\M' then 'school'
                when lower(coalesce(jurisdiction_name, '') || ' ' || coalesce(title, '')) ~ '\m(city|town|village|municipal)\M' then 'municipal'
            end,
            nullif(channel_type_raw, 'unknown'),
            channel_type_raw,
            'unknown'
        )                                                    as channel_type
    from renamed
),

final as (
    -- Dedup: one row per video_id, keep the most recently loaded (replaces the
    -- Python dedupe_meeting_videos step). Columns here MUST match the contract.
    select distinct on (video_id)
        video_id,
        event_id,
        title,
        description,
        event_date,
        published_at,
        jurisdiction_id,
        jurisdiction_name,
        jurisdiction_type,
        state_code,
        state,
        city,
        channel_id,
        channel_url,
        channel_type,
        meeting_type,
        video_url,
        location_description,
        view_count,
        duration_minutes,
        like_count,
        language,
        datasource,
        datasource_id,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from derived
    order by video_id, source_ingested_at desc nulls last
)

select * from final
