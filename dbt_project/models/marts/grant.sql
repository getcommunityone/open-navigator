{{
  config(
    materialized='table',
    post_hook=[
      "CREATE INDEX IF NOT EXISTS grant_grantor_master_org_id_idx ON {{ this }} (grantor_master_org_id)",
      "CREATE INDEX IF NOT EXISTS grant_grantee_master_org_id_idx ON {{ this }} (grantee_master_org_id)",
      "CREATE INDEX IF NOT EXISTS grant_grantor_state_code_idx ON {{ this }} (grantor_state_code)"
    ]
  )
}}

/*
    Mart: public.grant — one row per Schedule I Part II grant line (nonprofit
    grantmaking: grantor org -> grantee, cash amount, purpose). Sourced from
    stg_grants_gt990__schedule_i.

    Grantor resolution: the filer EIN is joined to mdm_organization_nonprofit
    (the EIN-keyed MDM satellite) to pick up master_org_id, then to
    mdm_organization for the grantor's golden location (state_code, city_norm)
    so grants search can filter by grantor location WITHOUT a separate bridge.
    Every Schedule I filer is itself a 990-filing nonprofit, so the grantor
    almost always resolves; rows whose grantor EIN has no master record are
    dropped (grantor_master_org_id is a NOT-NULL FK).

    Grantee resolution: optional. When the grantee EIN is present AND matches an
    org master, grantee_master_org_id is filled; otherwise it is NULL (grantee
    is carried by name only). FK enforced for non-null values.

    grant_id is a deterministic surrogate hash over the natural grain
    (grantor EIN, grantee name/EIN, tax year, amount, source URL) — the source
    has no stable per-line id, so this is stable within a build given stable
    bronze content.
*/

with

grants as (
    select * from {{ ref('stg_grants_gt990__schedule_i') }}
),

-- EIN -> master_org_id (1:1; the satellite is keyed by master_org_id with a
-- unique non-null EIN).
org_master_by_ein as (
    select master_org_id, ein
    from {{ ref('mdm_organization_nonprofit') }}
    where ein is not null
),

-- Golden grantor location for location filtering (state_code, city_norm).
org_location as (
    select master_org_id, state_code, city_norm
    from {{ ref('mdm_organization') }}
),

resolved as (
    select
        g.*,
        gm.master_org_id   as grantor_master_org_id,
        gl.state_code      as grantor_state_code,
        gl.city_norm       as grantor_city_norm,
        am.master_org_id   as grantee_master_org_id
    from grants g
    join org_master_by_ein gm
        on gm.ein = g.grantor_ein
    left join org_location gl
        on gl.master_org_id = gm.master_org_id
    left join org_master_by_ein am
        on g.grantee_ein is not null
        and am.ein = g.grantee_ein
)

select
    {{ dbt_utils.generate_surrogate_key([
        'grantor_ein', 'grantee_ein', 'grantee_name', 'tax_year',
        'cash_grant_amount', 'noncash_assistance_amount', 'purpose', 'source_url'
    ]) }}                                           as grant_id,
    cast(grantor_master_org_id as text)             as grantor_master_org_id,
    cast(grantor_ein as text)                       as grantor_ein,
    cast(grantor_name as text)                      as grantor_name,
    cast(grantor_state_code as text)                as grantor_state_code,
    cast(grantor_city_norm as text)                 as grantor_city_norm,
    cast(grantee_master_org_id as text)             as grantee_master_org_id,
    cast(grantee_name as text)                      as grantee_name,
    cast(grantee_ein as text)                       as grantee_ein,
    cast(grantee_city as text)                      as grantee_city,
    cast(grantee_state_code as text)                as grantee_state_code,
    cast(grantee_zip as text)                       as grantee_zip,
    cast(irc_section as text)                       as irc_section,
    cast(cash_grant_amount as bigint)               as amount,
    cast(noncash_assistance_amount as bigint)       as noncash_assistance_amount,
    cast(valuation_method as text)                  as valuation_method,
    cast(noncash_description as text)               as noncash_description,
    cast(purpose as text)                           as purpose,
    cast(tax_year as integer)                       as tax_year,
    cast(source_url as text)                        as source_url,
    current_timestamp                               as dbt_loaded_at
from resolved
