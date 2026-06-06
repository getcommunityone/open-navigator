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

-- OpenStates officials (legislators, mayors, council where present) normalized
-- to the contract columns. office = the chamber/org classification; phone is not
-- carried by the OpenStates source.
with openstates as (
    select
        ocd_membership_id                                     as id,
        full_name,
        title,
        jurisdiction,
        state_code,
        state,
        party,
        district,
        chamber                                               as office,
        email,
        cast(null as text)                                    as phone,
        photo_url,
        is_current
    from {{ ref('stg_openstates__official') }}
),

-- Scraped municipal council members (ingestion.municipal.load_council_officials)
-- — fills the gap where OpenStates has a city's mayor but not its council. Same
-- contract columns; carries phone when scraped.
scraped as (
    select
        ocd_membership_id                                     as id,
        full_name,
        title,
        jurisdiction,
        state_code,
        state,
        party,
        district,
        office,
        email,
        phone,
        photo_url,
        is_current
    from {{ ref('stg_scraped__official') }}
),

unioned as (
    select id, full_name, title, jurisdiction, state_code, state,
           party, district, office, email, phone, photo_url, is_current
    from openstates
    union all
    select id, full_name, title, jurisdiction, state_code, state,
           party, district, office, email, phone, photo_url, is_current
    from scraped
)

-- Resolve the jurisdiction's official website for LOCAL leaders only
-- (office in government/executive — these carry a place name like
-- "Tuscaloosa Government"; legislators' "jurisdiction" is a committee, not a
-- place). No hard FK exists (see header), so we match on state_code + the
-- normalized place name: strip the trailing " Government" suffix, then run both
-- sides through normalize_jurisdiction_label_for_match (handles City of/county/
-- St.-> Saint, etc.). Multiple jurisdictions can normalize alike (city vs county
-- vs school district), so we prefer the municipality/place and the shortest name,
-- and require a non-null website. NULL for everyone who doesn't resolve.
select
    u.id, u.full_name, u.title, u.jurisdiction, u.state_code, u.state,
    u.party, u.district, u.office, u.email, u.phone, u.photo_url, u.is_current,
    jw.website_url
from unioned u
left join lateral (
    select j.website_url
    from {{ ref('jurisdictions') }} j
    where u.office in ('government', 'executive')
      and j.state_code = u.state_code
      and j.website_url is not null
      and {{ normalize_jurisdiction_label_for_match("regexp_replace(u.jurisdiction, '\\s+government$', '', 'gi')") }}
          = {{ normalize_jurisdiction_label_for_match('j.name') }}
    order by
        case when j.name ~* '(county|parish|school district| ccd)$' then 2 else 1 end,
        length(j.name)
    limit 1
) jw on true
