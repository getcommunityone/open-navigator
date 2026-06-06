{{
  config(
    materialized='table',
    on_schema_change='fail',
    contract={'enforced': true},
    tags=['marts', 'person', 'officials', 'api'],
    unique_key='person_id',
    indexes=[
      {'columns': ['person_id'], 'unique': True},
      {'columns': ['master_person_id'], 'type': 'btree'},
      {'columns': ['jurisdiction_id'], 'type': 'btree'},
      {'columns': ['state_code'], 'type': 'btree'},
      {'columns': ['is_current'], 'type': 'btree'}
    ],
    post_hook=[
      "CREATE EXTENSION IF NOT EXISTS pg_trgm",
      "CREATE INDEX IF NOT EXISTS person_government_full_name_trgm_idx ON {{ this }} USING gin (full_name gin_trgm_ops)"
    ]
  )
}}

/*
public.person_government — government officials as a PERSON SUBTYPE.

A "subclass" of person: an elected/appointed official is a kind of person, so it
is modelled here as a first-class member of the person family rather than as an
orphan officials table. Unlike mdm_person (the probabilistically-resolved master
for nonprofit officers / legislators), a government official already has an
EXACT, stable identity — its OCD membership id — so it gets a DETERMINISTIC
person identity (person_id = the OCD membership id). No Splink matching is run,
which is deliberate: it avoids both the heavy person-resolution rebuild and the
over-fragmentation that probabilistic matching produces for these single-name
roster rows.

Why a subtype and not "just use mdm_person": mdm_person carries no photo, office
title, jurisdiction, or biography — the attributes that define an official — and
these officials are not loaded into the deployed mdm_person at all. This subtype
carries those government-specific columns natively.

GRAIN: one row per official×role (= one government-person occurrence), keyed by
person_id. Sourced 1:1 from contact_official (the officials role mart), which
already unions OpenStates + scraped council members, applies the photo/bio
override seed, and resolves the jurisdiction website. We re-project that here with
the person-identity framing rather than re-deriving it, so contact_official stays
the single officials mart and nothing downstream of it changes.

KEYS:
  - PK person_id (text, = OCD membership id).
  - FK jurisdiction_id -> public.jurisdictions (nullable). Soft-resolved by
    state_code + normalized place name (same match contact_official uses for the
    website), so every non-null value is a real jurisdictions PK. NULL for
    legislators (whose "jurisdiction" is a committee, not a place) and for any
    local leader whose place does not normalize to a known jurisdiction.
  - master_person_id (text, nullable): reserved for a future DETERMINISTIC link
    to mdm_person.master_person_id (e.g. a mayor who is also a known 990 officer).
    Always NULL today; no FK is enforced because the relationship is unpopulated
    and we will not couple this lightweight subtype to the heavy person master
    until a deterministic crosswalk exists.

The pg_trgm GIN index on full_name backs ILIKE name search; the API person-detail
endpoint looks officials up by person_id (PK).
*/

select
    o.id                                                  as person_id,
    cast(null as text)                                    as master_person_id,
    o.full_name,
    o.title,
    o.jurisdiction,
    j.jurisdiction_id,
    o.office,
    o.state_code,
    o.state,
    o.party,
    o.district,
    o.email,
    o.phone,
    o.photo_url,
    o.biography,
    o.website_url,
    o.is_current
from {{ ref('contact_official') }} o
-- Soft jurisdiction resolution for LOCAL leaders only (office in government/
-- executive — these carry a place name like "Tuscaloosa Government"; a
-- legislator's jurisdiction is a committee). Same normalized name match
-- contact_official uses for the website, but returns the jurisdiction PK so the
-- value is referentially valid against public.jurisdictions. Prefer the
-- municipality/place and the shortest name when several normalize alike.
left join lateral (
    select j.jurisdiction_id
    from {{ ref('jurisdictions') }} j
    where o.office in ('government', 'executive')
      and j.state_code = o.state_code
      and {{ normalize_jurisdiction_label_for_match("regexp_replace(o.jurisdiction, '\\s+government$', '', 'gi')") }}
          = {{ normalize_jurisdiction_label_for_match('j.name') }}
    order by
        case when j.name ~* '(county|parish|school district| ccd)$' then 2 else 1 end,
        length(j.name)
    limit 1
) j on true
