{{
  config(
    materialized='view',
    tags=['staging', 'meetings', 'documents', 'scraped_meetings']
  )
}}

/*
staging.stg_scraped_meeting_documents — agenda/minutes PDFs from the nationwide
jurisdiction homepage crawl (scripts/discovery/comprehensive_discovery_pipeline_jurisdiction
-> load_scraped_meetings_manifests_to_bronze), for counties and municipalities in
every state. Issue #392.

GRAIN: one row per scraped meeting document (jurisdiction_id, url_sha256).

SOURCE: bronze.bronze_events_meetings_{counties,municipalities}_scraped, admitting
only rows that are:
  - resource_kind = 'pdf' with a non-empty url;
  - doc_type IN ('agenda','minutes') (the crawl's URL/anchor classifier);
  - dated to a real DAY: meeting_date present and its source is not
    'manifest_year_only' (that path stamps January 1 of the folder year, which
    would show a made-up date — see CLAUDE.md "No Fabricated Data");
  - NOT a SuiteOne row (manifest_relative_path 'suiteone:%' or
    meeting_date_source 'suiteone_listing'). SuiteOne rows, and the SuiteOne
    model's 'unknown' attachments, are owned by stg_suiteone_meeting_documents;
    the exclusion below mirrors its filter so a document is in exactly one model;
  - NOT a link into a SuiteOne portal (*.suiteonemedia.com). The crawl can reach
    a portal PDF under a variant (dated-label) URL that 404s; the SuiteOne
    scraper owns those portals and publishes the clean link, so publishing the
    crawl's copy would show the same agenda twice, once broken.

SCHOOL DISTRICTS are left out on purpose: their 7-digit NCES ids can equal a
city's 7-digit place geoid, and both the mart's geoid match and the
/jurisdictions/{geoid}/meeting-documents lookup key on census_geoid, so a
district's agenda would attach to (and list under) a city. Adding them needs a
type-aware key first.

event_meeting_document_id uses the same md5(jurisdiction_id || '|' || url_sha256)
surrogate as the SuiteOne model, so the union in the mart stays one row per doc.
meeting_title is the PDF's link text / filename title; body_key is derived from it
with the same macro, so a dated agenda for a recognizable body can attach to its
analyzed meeting, and anything else stays an orphan (event_meeting_id NULL).
*/

with source as (

    select 'county'::text as jurisdiction_type, jurisdiction_id, census_geoid, state_code, url, url_sha256,
           doc_type, resource_category, resource_kind, meeting_date, meeting_date_source,
           meeting_title, manifest_relative_path, loaded_at
    from {{ source('bronze', 'bronze_events_meetings_counties_scraped') }}

    union all

    select 'municipality'::text, jurisdiction_id, census_geoid, state_code, url, url_sha256,
           doc_type, resource_category, resource_kind, meeting_date, meeting_date_source,
           meeting_title, manifest_relative_path, loaded_at
    from {{ source('bronze', 'bronze_events_meetings_municipalities_scraped') }}

),

filtered as (

    select *
    from source
    where resource_kind = 'pdf'
      and nullif(btrim(url), '') is not null
      and doc_type in ('agenda', 'minutes')
      and meeting_date is not null
      and nullif(btrim(meeting_date_source), '') is not null
      and meeting_date_source <> 'manifest_year_only'
      -- Owned by stg_suiteone_meeting_documents (keep the two models disjoint).
      and coalesce(manifest_relative_path, '') not like 'suiteone:%'
      and coalesce(meeting_date_source, '') <> 'suiteone_listing'
      and url !~* '^https?://[^/]*suiteonemedia\.com'

),

renamed as (

    select
        md5(jurisdiction_id || '|' || url_sha256)          as event_meeting_document_id,
        jurisdiction_id,
        jurisdiction_type,
        census_geoid,
        url_sha256,
        rtrim(state_code)                                  as state_code,
        {{ state_code_to_name('rtrim(state_code)') }}      as state,
        doc_type                                           as document_type,
        url                                                as document_url,
        meeting_date                                       as doc_date,
        meeting_date_source,
        meeting_title,
        {{ normalize_meeting_body_key('meeting_title') }}  as body_key,
        'scraped_meetings'::text                           as source,
        loaded_at                                          as created_at
    from filtered

),

final as (

    -- A jurisdiction_id belongs to one type table, but guard the grain anyway:
    -- keep the most recently loaded copy of a document.
    select distinct on (event_meeting_document_id) *
    from renamed
    order by event_meeting_document_id, created_at desc

)

select * from final
