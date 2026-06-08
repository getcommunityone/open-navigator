{{
  config(
    materialized='view',
    tags=['staging', 'meetings', 'documents', 'suiteone']
  )
}}

/*
staging.stg_suiteone_meeting_documents — cleaned SuiteOne agenda/minutes PDFs.

GRAIN: one row per scraped meeting document (a single agenda or minutes PDF URL).

SOURCE: bronze.bronze_events_meetings_municipalities_scraped, restricted to the
SuiteOne municipal-calendar crawl:
    meeting_date_source = 'suiteone_listing'
    AND resource_kind   = 'pdf'
    AND doc_type IN ('agenda','minutes')
This filter is deliberately the ONLY thing scoping the model — it is NOT
Tuscaloosa-specific. Any future SuiteOne city landed with the same
meeting_date_source flows through unchanged. Other rows in the bronze table are
year-only legacy entries and are excluded by the filter above.

It produces a `body_key` — a canonical body-category token derived from the
SuiteOne `meeting_title` (after stripping the leading meeting time). The same
token is derived from event_meeting.body_name downstream so a document can be
matched to the correct body on a given date (a single date has several bodies,
each with its own agenda/minutes). See macro normalize_meeting_body_key().
*/

with src as (

    select
        jurisdiction_id,
        census_geoid,
        state_code,
        url,
        url_sha256,
        doc_type,
        meeting_date,
        meeting_title,
        raw_resource,
        loaded_at
    from {{ source('bronze', 'bronze_events_meetings_municipalities_scraped') }}
    where meeting_date_source = 'suiteone_listing'
      and resource_kind = 'pdf'
      and doc_type in ('agenda', 'minutes')
      and nullif(btrim(url), '') is not null

)

select
    -- Stable surrogate: jurisdiction_id + url (url_sha256 already hashes the url,
    -- which is unique per doc within a jurisdiction — see the bronze UNIQUE
    -- (jurisdiction_id, url_sha256) constraint).
    md5(jurisdiction_id || '|' || url_sha256)              as event_meeting_document_id,
    jurisdiction_id,
    census_geoid,
    rtrim(state_code)                                      as state_code,
    {{ state_code_to_name('rtrim(state_code)') }}          as state,
    doc_type                                               as document_type,
    -- Canonicalize the decorative document-title path segment between 'GetXFile/'
    -- and '?' down to its keyword. SuiteOne serves the file purely by the mid/aid
    -- query param, but older portal rows pollute the label with the meeting date,
    -- e.g. '.../GetAgendaFile/11/2/21%20Agenda?aid=4748' (embedded slashes/spaces
    -- 404 the link) or '.../GetMinutesFile/Synopsis%20?mid=5048'. Collapsing the
    -- label to its keyword (preserving Minutes vs Synopsis) makes the link route;
    -- this subsumes the earlier trailing-whitespace cleanup. url_sha256 (and the
    -- surrogate key derived from it) intentionally still hash the RAW url, so this
    -- display cleanup doesn't churn keys. The scraper is fixed at the source too
    -- (suiteone.portal._normalize_doc_url) so future crawls land clean urls.
    regexp_replace(
        url,
        '(/event/Get(?:Agenda|Minutes|Document)File/)[^?]*?(Agenda|Minutes|Synopsis|Packet)[^?]*(\?|$)',
        '\1\2\3',
        'i'
    )                                                      as document_url,
    meeting_date                                           as doc_date,
    meeting_title,
    -- Canonical body category for date+body matching downstream.
    {{ normalize_meeting_body_key('meeting_title') }}      as body_key,
    'suiteone'::text                                       as source,
    loaded_at                                              as created_at
from src
