{{ config(materialized='view') }}

/*
    Staging: jurisdiction-grain civic documents.

    Source: bronze.bronze_jurisdiction_document — landed by
    ingestion.jurisdiction_documents.bronze from a curated registry of REAL
    published documents (comprehensive plans / frameworks, zoning ordinances,
    ordinance codes, zoning maps). One row per document.

    DISTINCT ENTITY: these belong to a JURISDICTION, not a single meeting, so
    they are NOT the meeting-grain agenda/minutes in event_meeting_document
    (which match a doc to a meeting on jurisdiction + date + body). A framework /
    comprehensive plan has no meeting date; it links straight to the jurisdiction.

    Follows Stage 3 conventions (dbt_project/CONVENTIONS.md):
      - Naming: stg_<source>__<entity> is the norm; this single-table source uses
        the flat stg_jurisdiction_document name to match the mart it feeds.
      - Reads only from source(), never from another model.
      - Pinned types via the contract in _schema_stg_jurisdiction_document.yml.
      - Four-CTE template: source -> renamed -> filtered -> final.

    Notes:
      - The natural key is (jurisdiction_id, url_sha256); the mart derives the
        single-column surrogate PK from it.
      - adopted_date is a real DATE (null unless verified), so the calendar-year
        wire/string rule does not apply — it serializes as an ISO date.
      - raw keeps the full registry entry as JSONB for fidelity.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_jurisdiction_document') }}
),

renamed as (
    select
        nullif(trim(jurisdiction_id), '')         as jurisdiction_id,
        nullif(trim(url_sha256), '')              as url_sha256,
        nullif(trim(document_url), '')            as document_url,
        lower(nullif(trim(document_type), ''))    as document_type,
        nullif(trim(title), '')                   as title,
        adopted_date,
        nullif(trim(source), '')                  as source,
        raw,
        ingestion_date
    from source
),

filtered as (
    -- A document is only usable if it has an owning jurisdiction, a key, and a URL.
    select *
    from renamed
    where jurisdiction_id is not null
      and url_sha256 is not null
      and document_url is not null
),

final as (
    select
        jurisdiction_id,
        url_sha256,
        document_url,
        document_type,
        title,
        adopted_date,
        source,
        raw,
        ingestion_date
    from filtered
)

select * from final
