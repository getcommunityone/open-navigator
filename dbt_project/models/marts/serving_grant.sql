{{
  config(
    materialized='table',
    indexes=[
      {'columns': ["grantor_master_org_id"], 'type': 'btree'},
      {'columns': ["grantee_master_org_id"], 'type': 'btree'},
      {'columns': ["grantee_name gin_trgm_ops"], 'type': 'gin'},
      {'columns': ["grantor_name gin_trgm_ops"], 'type': 'gin'}
    ]
  )
}}

/*
    Serving subset of the `grant` mart (990 Schedule I grants) for the Neon
    free-tier deployment.

    Scope rule: keep a grant if EITHER endpoint — grantor or grantee — is one of
    the orgs retained in serving_mdm_organization (the largest-10%-per-jurisdiction
    set). A grant that touches no served org has no served detail page to link
    from, so it is dropped.

    Local warehouse (#607): excluded from the default `local_warehouse` selector.
    gold.grant is ~4 GB / ~6.7M rows; filtering against ~234k kept orgs (plus the
    GIN post_hooks below) ran >36 minutes before cancel. Build explicitly with
    `dbt run --select serving_grant` when preparing a Neon publish.
*/

with kept as (

    select master_org_id
    from {{ ref('serving_mdm_organization') }}

)

select g.*
from {{ ref('grant') }} g
where exists (select 1 from kept k where k.master_org_id = g.grantor_master_org_id)
   or exists (select 1 from kept k where k.master_org_id = g.grantee_master_org_id)
