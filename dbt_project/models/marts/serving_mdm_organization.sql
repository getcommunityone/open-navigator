{{
  config(
    materialized='table',
    indexes=[
      {'columns': ["to_tsvector('english', org_name)"], 'type': 'gin'},
      {'columns': ["org_name_norm"], 'type': 'btree'},
      {'columns': ["state_code"], 'type': 'btree'}
    ],
    post_hook=[
      "{{ gold_pk_post_hook('master_org_id') }}"
    ]
  )
}}

/*
    Serving subset of mdm_organization for the Neon free-tier (0.5 GB) deployment.

    Scope rule: keep the TOP 10 organizations PER JURISDICTION, ranked by
    nonprofit revenue (fallback: income, then assets) from
    mdm_organization_nonprofit. An org is kept if it ranks in the top 10 of ANY
    jurisdiction it is bridged to (city / county / state level), so a locally
    dominant org is never dropped just because it is small at the state level.
    Fixed count per jurisdiction (NOT a percentage) — big metros no longer
    contribute thousands of orgs apiece.

    Full columns are retained here; column pruning is a separate serving rule.
*/

with org_revenue as (

    select
        b.jurisdiction_id,
        b.master_org_id,
        coalesce(np.revenue, np.income, np.assets, 0) as size_metric
    from {{ ref('mdm_bridge_org_jurisdiction') }} b
    left join {{ ref('mdm_organization_nonprofit') }} np
        on np.master_org_id = b.master_org_id

),

ranked as (

    select
        jurisdiction_id,
        master_org_id,
        row_number() over (
            partition by jurisdiction_id
            order by size_metric desc, master_org_id
        ) as juris_rank
    from org_revenue

),

kept_org_ids as (

    -- top 10 by size in at least one of its jurisdictions
    select distinct master_org_id
    from ranked
    where juris_rank <= 10

)

select o.*
from {{ ref('mdm_organization') }} o
inner join kept_org_ids k
    on k.master_org_id = o.master_org_id
