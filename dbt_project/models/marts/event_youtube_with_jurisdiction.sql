{{
    config(
        materialized='view',
        tags=['mart', 'youtube', 'events', 'jurisdictions', 'serving'],
    )
}}

/*
Serving view: bronze.bronze_event_youtube with jurisdiction/geo columns resolved.

Thin, column-superset VIEW over bronze.bronze_event_youtube. Every bronze column
passes through unchanged EXCEPT the five geo columns, which are COALESCE-overridden
with the canonical values from int_event_youtube__jurisdiction_resolved (grain: one
row per video_id) when that model resolved the row:

    jurisdiction_id, jurisdiction_name, jurisdiction_type, state_code, state

This replaces the old in-place Python UPDATE of bronze
(packages/scrapers/src/scrapers/youtube/backfill_youtube_jurisdiction_from_channels.py):
a downstream consumer reads resolved jurisdiction_ids from this view while bronze
stays raw.

Cardinality: bronze.video_id is unique and the resolved model is one row per
video_id, so the LEFT JOIN never fans out — row count == bronze row count MINUS
rows on channels positively classified as junk / non-government (see junk_channels).
*/

with

bronze as (
    select * from {{ source('bronze', 'bronze_event_youtube') }}
),

-- ── Junk gate ────────────────────────────────────────────────────────────────
-- Channels POSITIVELY classified as junk (is_junk = TRUE) or non-government
-- (is_government = FALSE) by the ingestion-track classifier
-- (bronze_youtube_channel_classification) are excluded from the served feed.
-- This is the true chokepoint: it removes junk rows even when their bronze
-- jurisdiction_id was already populated (so they never reached the resolved
-- intermediate), and every downstream policy/trending mart that builds on this
-- view inherits the filter. Conservative: unclassified channels (no row / NULL
-- flags) are left in — we never drop a channel merely for being unscored.
junk_channels as (
    select distinct nullif(trim(channel_id), '') as channel_id
    from {{ source('bronze', 'bronze_youtube_channel_classification') }}
    where nullif(trim(channel_id), '') is not null
      and (is_junk is true or is_government is false)
),

resolved as (
    select
        video_id,
        jurisdiction_id,
        jurisdiction_name,
        jurisdiction_type,
        state_code,
        state
    from {{ ref('int_event_youtube__jurisdiction_resolved') }}
),

-- Authoritative jurisdiction names, used to repair the raw `c-XX-NNNNN` county
-- code that some bronze rows carry in jurisdiction_name (display bug). The row's
-- effective jurisdiction_id is still valid and joinable, so we resolve the real
-- name from here when the bronze/resolved name is the bogus code.
juris as (
    select jurisdiction_id, name as jurisdiction_name, state_code, state
    from {{ ref('int_jurisdictions') }}
    where jurisdiction_id is not null
)

select
    -- Primary key
    b.id,

    -- Event identification
    b.event_id,
    b.video_id,

    -- Event details
    b.event_date,
    b.event_time,
    b.title,
    b.description,

    -- Jurisdiction linkage — resolved value wins, bronze is the fallback.
    coalesce(nullif(r.jurisdiction_id, ''),   nullif(b.jurisdiction_id, ''))   as jurisdiction_id,
    -- Display-bug repair: when the effective name is the raw `c-XX-NNNNN` county
    -- code, substitute the authoritative int_jurisdictions name (joined on the
    -- effective jurisdiction_id). If the id isn't joinable, null the bogus name
    -- rather than surfacing the code. Non-bogus names pass through unchanged.
    case
        when coalesce(nullif(r.jurisdiction_name, ''), nullif(b.jurisdiction_name, '')) ~ '^c-[A-Z]{2}-[0-9]+$'
            then j.jurisdiction_name
        else coalesce(nullif(r.jurisdiction_name, ''), nullif(b.jurisdiction_name, ''))
    end as jurisdiction_name,
    coalesce(nullif(r.jurisdiction_type, ''), nullif(b.jurisdiction_type, '')) as jurisdiction_type,
    b.city,
    coalesce(nullif(r.state_code, ''), nullif(b.state_code, ''), j.state_code)  as state_code,
    coalesce(nullif(r.state, ''),      nullif(b.state, ''),      j.state)       as state,

    -- Meeting details
    b.meeting_type,
    b.location,
    b.location_description,

    -- YouTube channel info
    b.channel_id,
    b.channel_url,
    b.channel_type,

    -- Video metadata
    b.video_url,
    b.view_count,
    b.duration_minutes,
    b.like_count,
    b.language,

    -- Data source tracking
    b.datasource,
    b.datasource_id,

    -- Publishing metadata
    b.published_at,

    -- Audit fields
    b.loaded_at,
    b.last_updated,

    -- Audio pipeline
    b.audio_downloaded_at,
    b.audio_file_path,
    b.audio_file_size_mb,

    -- Transcript pipeline
    b.transcript_download_at,
    b.transcript_file_path,
    b.transcript_file_size,
    b.transcript_file_error,
    b.transcript_download_attempts,

    -- Policy analysis pipeline
    b.policy_analysis_at,
    b.policy_analysis_error,
    b.policy_analysis_path,
    b.policy_report_at,
    b.policy_report_error,
    b.policy_report_path

from bronze b
left join resolved r on r.video_id = b.video_id
left join junk_channels jc on jc.channel_id = nullif(trim(b.channel_id), '')
left join juris j
    on j.jurisdiction_id = coalesce(nullif(r.jurisdiction_id, ''), nullif(b.jurisdiction_id, ''))
where jc.channel_id is null
