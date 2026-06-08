{{
  config(
    materialized='table',
    tags=['marts', 'meetings', 'documents', 'suiteone', 'production'],
    unique_key='event_meeting_document_id',
    indexes=[
      {'columns': ['event_meeting_id'], 'type': 'btree'},
      {'columns': ['jurisdiction_id'], 'type': 'btree'},
      {'columns': ['census_geoid'], 'type': 'btree'},
      {'columns': ['document_type'], 'type': 'btree'},
      {'columns': ['doc_date'], 'type': 'btree'}
    ]
  )
}}

/*
public.event_meeting_document — scraped meeting AGENDA / MINUTES PDFs linked to
the meeting they belong to, so the API can surface document links on a
decision / meeting view.

GRAIN: one row per scraped document (a single agenda or minutes PDF).

SOURCE: staging.stg_suiteone_meeting_documents (the SuiteOne municipal-calendar
crawl in bronze; see that model for the source filter — general, not
Tuscaloosa-specific).

LINK TARGET: public.event_meeting. A document is matched to a meeting on ALL
THREE of:
  1. Jurisdiction — the 5-7 digit census geoid extracted from
     event_meeting.jurisdiction (which often embeds the id, e.g.
     'tuscaloosa_0177256' / 'municipality_0177256') equals the doc's census_geoid.
  2. Date — event_meeting.meeting_date::date = doc_date.
  3. Body — the canonical body_key (macro normalize_meeting_body_key) derived
     from both event_meeting.body_name and the SuiteOne meeting_title match.
     Body is REQUIRED: a single date has several bodies (Finance / Council /
     Projects), each with its own agenda, so date-only matching would attach the
     wrong document.

event_meeting_id is NULLABLE on purpose:
  - a document may not match any analyzed meeting (orphan) — kept with NULL FK;
  - a meeting may have an agenda but no minutes yet (or vice-versa) — that gap is
    the honest downstream signal.

event_meeting can carry several analysis rows for the same (geoid, date, body),
so the match is deduped to ONE meeting per (geoid, date, body_key) — the lowest
event_meeting_id — to keep this model at one row per document.

The ref('event_meeting') below also enforces build ordering: event_meeting must
build first so the FK target exists.
*/

with docs as (

    select
        event_meeting_document_id,
        jurisdiction_id,
        census_geoid,
        state_code,
        state,
        document_type,
        document_url,
        doc_date,
        meeting_title,
        body_key,
        source,
        created_at
    from {{ ref('stg_suiteone_meeting_documents') }}

),

-- event_meeting reduced to ONE row per (geoid, date, body_key); pick the lowest
-- event_meeting_id deterministically so a document never fans out.
meetings as (

    select distinct on (geoid, meeting_date_d, body_key)
        event_meeting_id,
        geoid,
        meeting_date_d,
        body_key
    from (
        select
            event_meeting_id,
            substring(jurisdiction from '(\d{5,7})')        as geoid,
            -- meeting_date is free TEXT and can hold 'unknown'/'' etc; only cast
            -- strings that actually look like an ISO date.
            case
                when meeting_date ~ '^\d{4}-\d{2}-\d{2}'
                then substring(meeting_date from '^\d{4}-\d{2}-\d{2}')::date
            end                                             as meeting_date_d,
            {{ normalize_meeting_body_key('body_name') }}   as body_key
        from {{ ref('event_meeting') }}
    ) em
    where geoid is not null
      and meeting_date_d is not null
      and body_key is not null
    order by geoid, meeting_date_d, body_key, event_meeting_id

),

matched as (

    select
        d.event_meeting_document_id,
        m.event_meeting_id,
        d.jurisdiction_id,
        d.census_geoid,
        d.state_code,
        d.state,
        d.document_type,
        d.document_url,
        d.doc_date,
        -- Serve the canonical body category as the cleaned body name.
        d.body_key                                          as body_name,
        d.meeting_title,
        d.source,
        d.created_at
    from docs d
    left join meetings m
        on m.geoid          = d.census_geoid
       and m.meeting_date_d = d.doc_date
       and m.body_key       = d.body_key

)

select
    event_meeting_document_id,
    event_meeting_id,
    jurisdiction_id,
    census_geoid,
    state_code,
    state,
    document_type,
    document_url,
    doc_date,
    body_name,
    meeting_title,
    source,
    created_at::timestamp                                   as created_at
from matched
