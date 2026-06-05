{{
  config(
    materialized='table',
    on_schema_change='fail',
    contract={'enforced': true},
    tags=['marts', 'officials', 'api'],
    unique_key='id',
    indexes=[
      {'columns': ['id'], 'unique': True},
      {'columns': ['state_code'], 'type': 'btree'},
      {'columns': ['is_current'], 'type': 'btree'}
    ],
    post_hook=[
      "CREATE EXTENSION IF NOT EXISTS pg_trgm",
      "CREATE INDEX IF NOT EXISTS contact_official_full_name_trgm_idx ON {{ this }} USING gin (full_name gin_trgm_ops)",
      "CREATE INDEX IF NOT EXISTS contact_official_title_trgm_idx ON {{ this }} USING gin (title gin_trgm_ops)"
    ]
  )
}}

/*
public.contact_official — API-ready current government officials.

Single source of truth for officials search, consumed by the API (repointing
off the legacy gold parquet at data/gold/states/<ST>/contact_official.parquet,
produced by ingestion.openstates.export_legislators_to_gold). The previous
public.contact_official table was dropped by migration 052 and is rebuilt here
as a proper warehouse mart.

GRAIN: one row per official×role (PK id = the OCD membership id). Includes
mayors, council members, and legislators — ALL current memberships, not just
legislative chambers (the legacy parquet export wrongly filtered to upper/lower/
legislature, excluding mayors).

Lineage:
  bronze.bronze_officials_openstates (ingestion.openstates.officials)
    -> stg_openstates__official  (clean/cast, derive state_code + state + title,
                                  drop jurisdiction-less committee memberships)
    -> contact_official          (this mart)

KEYS: PK id (text, = ocd_membership_id). No FK is declared: the official's
organization is identified by an OCD jurisdiction slug
(ocd-jurisdiction/.../place:tuscaloosa/government), which has no clean key into
public.jurisdictions (PK = census slug+geoid) — there is no OCD-slug -> census
crosswalk in the warehouse. The jurisdiction NAME is denormalized onto the row
(jurisdiction column) for display; resolving a hard FK is a follow-up.

The trigram (pg_trgm) GIN indexes on full_name and title back the API's ILIKE
name/title search.
*/

with officials as (
    select * from {{ ref('stg_openstates__official') }}
)

select
    ocd_membership_id                                          as id,
    full_name,
    title,
    jurisdiction,
    state_code,
    state,
    party,
    district,
    -- office: the chamber/organization classification, surfaced as a nullable
    -- API field (e.g. 'government', 'upper', 'lower'). NULL where unknown.
    chamber                                                    as office,
    email,
    -- phone: not carried by the OpenStates person/membership source; reserved
    -- nullable column so the API contract matches the legacy parquet shape.
    cast(null as text)                                         as phone,
    photo_url,
    is_current
from officials
