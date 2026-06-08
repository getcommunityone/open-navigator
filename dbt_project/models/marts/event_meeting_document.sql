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
  1. Jurisdiction — matched two ways, geoid PREFERRED with a name FALLBACK:
       (a) the 5-7 digit census geoid extracted from event_meeting.jurisdiction
           (which sometimes embeds the id, e.g. 'tuscaloosa_0177256') equals the
           doc's census_geoid; OR
       (b) when no geoid can be extracted (~53% of rows are free-text like
           'City of Tuscaloosa, Alabama'), fall back to state_code +
           normalized jurisdiction name: event_meeting.state_code = doc.state_code
           AND a normalized event_meeting.jurisdiction_name ('Tuscaloosa' ->
           'tuscaloosa') equals the doc's normalized jurisdiction slug (the token
           before the last '_' in jurisdiction_id, e.g.
           'tuscaloosa_0177256' -> 'tuscaloosa').
     The name fallback is the jurisdiction dimension ONLY; state_code + date +
     body_key are still required so two different cities never cross-link.
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

event_meeting can carry several analysis rows for the same jurisdiction, date and
body, so after joining the match is deduped (DISTINCT ON the document) to ONE
meeting per document — preferring a geoid match over a name-fallback match, then
the lowest event_meeting_id — to keep this model at one row per document and
guarantee a document never fans out to multiple meetings.

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
        -- jurisdiction_id is '<name-slug>_<geoid>' (e.g. 'tuscaloosa_0177256');
        -- the name slug is everything before the LAST '_'. Normalize it the same
        -- way as the event_meeting side so the name fallback compares apples to
        -- apples ('tuscaloosa').
        regexp_replace(
            lower(regexp_replace(jurisdiction_id, '_[^_]*$', '')),
            '[^a-z0-9]+', ' ', 'g'
        )                                                   as juris_name_norm,
        source,
        created_at
    from {{ ref('stg_suiteone_meeting_documents') }}

),

-- event_meeting reduced to the columns used for matching. geoid may be NULL
-- (free-text jurisdiction); in that case the state_code + normalized-name
-- fallback carries the join. Multiple analysis rows can share a
-- (jurisdiction, date, body) — the final DISTINCT ON over the document collapses
-- them so a document never fans out.
meetings as (

    select
        event_meeting_id,
        geoid,
        state_code,
        juris_name_norm,
        meeting_date_d,
        body_key
    from (
        select
            event_meeting_id,
            state_code,
            substring(jurisdiction from '(\d{5,7})')        as geoid,
            -- Normalize jurisdiction_name to the bare city token:
            -- lowercase, drop 'city of '/'town of ' prefix, drop a trailing
            -- state name, reduce punctuation to single spaces, trim.
            trim(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            lower(coalesce(jurisdiction_name, '')),
                            '^\s*(city|town|village|borough|township)\s+of\s+', '', 'i'
                        ),
                        ',?\s*(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\s*$', '', 'i'
                    ),
                    '[^a-z0-9]+', ' ', 'g'
                )
            )                                               as juris_name_norm,
            -- meeting_date is free TEXT and can hold 'unknown'/'' etc; only cast
            -- strings that actually look like an ISO date.
            case
                when meeting_date ~ '^\d{4}-\d{2}-\d{2}'
                then substring(meeting_date from '^\d{4}-\d{2}-\d{2}')::date
            end                                             as meeting_date_d,
            {{ normalize_meeting_body_key('body_name') }}   as body_key
        from {{ ref('event_meeting') }}
    ) em
    where meeting_date_d is not null
      and body_key is not null

),

-- Join docs to candidate meetings on date + body, with the jurisdiction matched
-- by geoid (preferred) OR by state_code + normalized name (fallback for the
-- geoid-less free-text rows). geoid_match flags the preferred path so the
-- dedupe can favor it.
joined as (

    select
        d.event_meeting_document_id,
        m.event_meeting_id,
        (m.geoid is not null and m.geoid = d.census_geoid) as geoid_match,
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
        on m.meeting_date_d = d.doc_date
       and m.body_key       = d.body_key
       and (
                -- (a) geoid match, preferred when event_meeting embeds the id
                (m.geoid is not null and m.geoid = d.census_geoid)
                -- (b) name fallback: same state + same normalized city name
             or (
                    m.state_code = d.state_code
                and m.juris_name_norm <> ''
                and m.juris_name_norm = d.juris_name_norm
                )
           )

),

-- One row per document: prefer a geoid match, then lowest event_meeting_id.
-- Orphans (no candidate meeting) keep event_meeting_id NULL and still pass
-- through exactly once.
matched as (

    select distinct on (event_meeting_document_id)
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
        created_at
    from joined
    order by
        event_meeting_document_id,
        geoid_match desc nulls last,
        event_meeting_id asc nulls last

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
