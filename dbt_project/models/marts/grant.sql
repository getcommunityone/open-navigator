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

    grant_id is a deterministic surrogate hash over the FULL grant-line grain.
    The source (990 Schedule I Part II) has no stable per-line id, and a filing
    legitimately reports the same grantor/grantee/amount/purpose more than once
    while differing only in recipient location or IRC section. So the grain MUST
    include the recipient location/section columns, not just
    grantor/grantee/amount/purpose/url, otherwise distinct grant lines collide.
    Investigation (2026-06): of ~31k key collisions on the old narrow grain,
    ~1.7k differed by grantee_zip / grantee_city / grantee_state_code /
    irc_section / valuation_method / noncash_description (genuinely distinct
    lines, kept) while the rest were fully-identical rows (true duplicates: same
    filing ingested twice / re-reported). The `deduped` CTE drops only
    fully-identical rows (row_number over EVERY source column), so true dupes
    collapse to one row and location/section-differing lines survive. The hash
    is stable within a build given stable bronze content.
*/

with

grants_raw as (
    select * from {{ ref('stg_grants_gt990__schedule_i') }}
),

-- Drop ONLY fully-identical duplicate grant lines (same values in every source
-- column). Rows that differ in ANY column survive, since their distinguishing
-- columns are all part of the surrogate-key grain below. Implemented as
-- SELECT DISTINCT over every column (equivalent to row_number over all columns
-- = 1, but lets Postgres use a HashAggregate instead of a full 15-key sort of
-- ~5.6M wide rows -- the sort was the dominant cost of the old ~32-min build).
deduped as (
    select distinct
        grantor_ein, grantor_name, tax_year,
        grantee_name, grantee_ein, grantee_city,
        grantee_state_code, grantee_zip, irc_section,
        cash_grant_amount, noncash_assistance_amount,
        valuation_method, noncash_description, purpose, source_url
    from grants_raw
),

grants as (
    select * from deduped
),

resolved as (
    -- PERF: join the base MDM tables DIRECTLY rather than through a shared
    -- `org_master_by_ein` CTE. The EIN->master satellite is referenced twice
    -- (grantor + grantee). When wrapped in a CTE, Postgres materializes it and
    -- loses the unique-EIN cardinality, which made the planner pick a merge
    -- join with a ~34-billion-row intermediate + sort/materialize (the old
    -- ~31-min build). Joining the base tables directly lets it use the existing
    -- indexes (mdm_organization_nonprofit_ein_idx, mdm_organization PK on
    -- master_org_id) and pick parallel hash joins instead. EIN is verified
    -- unique in mdm_organization_nonprofit, so no fan-out. No new index needed.
    select
        g.*,
        gm.master_org_id   as grantor_master_org_id,
        gl.state_code      as grantor_state_code,
        gl.city_norm       as grantor_city_norm,
        am.master_org_id   as grantee_master_org_id
    from grants g
    join {{ ref('mdm_organization_nonprofit') }} gm
        on gm.ein = g.grantor_ein
        and gm.ein is not null
    left join {{ ref('mdm_organization') }} gl
        on gl.master_org_id = gm.master_org_id
    left join {{ ref('mdm_organization_nonprofit') }} am
        on g.grantee_ein is not null
        and am.ein = g.grantee_ein
)

select
    {{ dbt_utils.generate_surrogate_key([
        'grantor_ein', 'grantor_name', 'tax_year',
        'grantee_name', 'grantee_ein', 'grantee_city',
        'grantee_state_code', 'grantee_zip', 'irc_section',
        'cash_grant_amount', 'noncash_assistance_amount',
        'valuation_method', 'noncash_description', 'purpose', 'source_url'
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
