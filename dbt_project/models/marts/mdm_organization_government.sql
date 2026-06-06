{#
  government_level index rationale: government_level is the primary browse/filter
  facet for gov orgs (Federal / State / County / City Government); a btree keeps
  level-scoped lookups off a seq scan as the satellite grows. (Jinja comment, NOT
  a `--` SQL comment inside config(), which would break `dbt parse`.)
#}
{{
  config(
    materialized='table',
    post_hook=[
      "CREATE INDEX IF NOT EXISTS mdm_organization_government_level_idx ON {{ this }} (government_level)"
    ]
  )
}}

/*
    Mart (MDM satellite): Data.gov (CKAN) publishing-government detail for the
    subset of mdm_organization that resolved to a Data.gov government org. One row
    per master_org_id (1:1 with the gov population in the master). PK
    master_org_id, FK -> mdm_organization.

    Mirrors mdm_organization_nonprofit: identity (name/type) lives on the master
    (mdm_organization); the gov-specific CKAN detail (government_level, dataset &
    follower counts, CKAN slug/title, logo, created_at) lives here.

    Keying: gov orgs have NO EIN, so the master_org_id is the deterministic
    `gov:<ckan_id>` namespaced scheme minted in int_organizations__clustered for
    source_system = 'bronze_organizations_gov' (parallel to the `jur:`/`sch:`
    schemes). This satellite mints the SAME value from the CKAN id, guaranteeing
    the FK relationship back to the master resolves 1:1.

    Sourced from the cleaned staging model (stg_data_gov__organizations) — the
    same row population that flows through stg_data_gov__org into the master — not
    bronze directly.
*/

with

gov as (
    select * from {{ ref('stg_data_gov__organizations') }}
),

-- Mint the same master_org_id the master uses for this population, and confirm
-- it actually landed in mdm_organization (anti-orphan guard: only emit rows
-- whose key resolved into the master, keeping the FK 1:1).
master as (
    select master_org_id
    from {{ ref('mdm_organization') }}
),

keyed as (
    select
        'gov:' || g.id          as master_org_id,
        g.*
    from gov as g
),

joined as (
    select k.*
    from keyed as k
    join master as m on m.master_org_id = k.master_org_id
)

select
    cast(master_org_id as text)             as master_org_id,
    cast(id as text)                        as ckan_id,
    cast(slug as text)                      as slug,
    cast(title as text)                     as title,
    cast(display_name as text)              as display_name,
    cast(description as text)               as description,
    cast(website_url as text)               as website_url,
    cast(image_url as text)                 as image_url,
    cast(image_display_url as text)         as image_display_url,
    cast(government_level as text)          as government_level,
    cast(dataset_count as integer)          as dataset_count,
    cast(follower_count as integer)         as follower_count,
    cast(source_created_at as timestamp)    as source_created_at,
    current_timestamp                       as dbt_loaded_at
from joined
