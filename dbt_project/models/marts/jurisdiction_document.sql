{{
  config(
    materialized='table',
    tags=['marts', 'documents', 'jurisdiction', 'production'],
    unique_key='jurisdiction_document_id',
    indexes=[
      {'columns': ['jurisdiction_id'], 'type': 'btree'},
      {'columns': ['document_type'], 'type': 'btree'}
    ]
  )
}}

/*
public.jurisdiction_document — jurisdiction-grain civic documents: comprehensive
plans / frameworks, zoning ordinances, ordinance codes, zoning maps. One row per
document, owned by a JURISDICTION (not a single meeting), so the API can surface
"plans & ordinances" on a jurisdiction view and link them to civic data.

GRAIN: one row per document.

SOURCE: staging.stg_jurisdiction_document (bronze.bronze_jurisdiction_document,
landed by ingestion.jurisdiction_documents.bronze from a curated registry of
REAL published documents — e.g. the City of Tuscaloosa "Framework" comprehensive
plan under tuscaloosa_0177256).

DISTINCT FROM event_meeting_document: that mart is meeting-grain (agenda/minutes
matched to a meeting on jurisdiction + date + body). A framework / comprehensive
plan has no meeting date and must NOT be forced through that path — it links
directly to the jurisdiction here.

KEYS (per CLAUDE.md, enforced as Postgres constraints via contract):
  - PK: jurisdiction_document_id = md5(jurisdiction_id || '|' || url_sha256).
  - FK: jurisdiction_id -> public.jurisdictions.jurisdiction_id. NOT NULL — a
    jurisdiction-grain document must belong to a real jurisdiction; an unknown id
    fails the build (a curated-registry data error worth surfacing loudly).
*/

with docs as (
    select * from {{ ref('stg_jurisdiction_document') }}
)

select
    md5(jurisdiction_id || '|' || url_sha256)   as jurisdiction_document_id,
    jurisdiction_id,
    document_type,
    title,
    document_url,
    url_sha256,
    adopted_date,
    source,
    ingestion_date::timestamp                   as ingested_at
from docs
