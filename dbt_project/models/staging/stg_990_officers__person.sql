{{
  config(
    materialized='table',
    indexes=[
      {'columns': ['source_pk'], 'unique': True},
      {'columns': ['name_norm'], 'type': 'btree'}
    ]
  )
}}
-- Materialized as a TABLE on purpose: the DISTINCT ON + double-metaphone over the
-- ~40M-row officer source is expensive and must run ONCE here, not re-execute
-- inside the int_persons__unioned build (which as a view turned a multi-hour
-- rebuild into a non-finisher). Precomputing to ~11.7M rows keeps the union cheap.

/*
    Staging (MDM person conformance): IRS Form 990 Part VII people (officers,
    directors, trustees, key employees) from stg_990_officers, mapped onto the
    shared person contract so they join the conformed person pool that Splink
    resolves.

    stg_990_officers is one row per (ein, tax_year, person) reporting line
    (~39M rows). A trustee who appears across 12 filing years for the same org is
    ONE entity for resolution, so this collapses to one row per distinct
    officer-org identity (name_norm + ein) — the same identity-grain collapse
    stg_contributions__person applies to 24.5M transaction rows. The per-year
    officer-org line lives in mdm_bridge_person_organization, not the person pool.

    Geography: the 990 Part VII source carries NO person geography of its own
    (city/state/zip are inherited from the org downstream), so city_norm /
    state_code / zip5 are left null here — same as stg_openstates__person, which
    leaves city null because the source address is unparsed. The org EIN is carried
    in `ein` so a future Splink pass can attach geography from the org master.

    entity_type classifies institutional trustees (org-shaped names) out of the
    person pool, mirroring stg_contributions__person. source_pk is a deterministic
    hash of the (name_norm, ein) identity.

    See web_docs/docs/dbt/entity-resolution-mdm.md (Layer 2, person pipeline).
    Four-CTE template: source -> parsed -> deduped -> final.
*/

with

source as (
    select * from {{ ref('stg_990_officers') }}
    -- stg_990_officers already drops rows where normalize_person_name is null
    -- and classifies entity_type; institutional trustees stay (org-shaped names
    -- are routed out of the person match pool by entity_type downstream).
),

parsed as (
    select
        ein_norm                                               as ein,
        entity_type,
        person_name                                            as raw_name,
        name_norm,
        {{ name_phonetic_first('person_name') }}               as name_phonetic_first,
        {{ name_phonetic_key('person_name') }}                 as name_phonetic_last
    from source
),

deduped as (
    -- one row per distinct officer-org identity (name_norm + ein), collapsing the
    -- per-tax-year reporting lines.
    select distinct on (
        name_norm,
        coalesce(ein, '')
    ) *
    from parsed
    order by
        name_norm,
        coalesce(ein, ''),
        raw_name
),

final as (
    select
        'bronze_990_officers'                                  as source_system,
        md5(name_norm || '|' || coalesce(ein, ''))             as source_pk,
        entity_type,
        raw_name,
        name_norm,
        null::text                                             as given_name_norm,
        null::text                                             as family_name_norm,
        name_phonetic_first,
        name_phonetic_last,
        null::text                                             as email,
        null::text                                             as phone,
        ein,
        ein                                                    as external_id,
        null::text                                             as city_norm,
        null::text                                             as state_code,
        null::text                                             as zip5
    from deduped
)

select * from final
