{{
  config(
    materialized='table',
    post_hook=[
      "CREATE INDEX IF NOT EXISTS serving_grant_grantor_master_org_id_idx ON {{ this }} (grantor_master_org_id)",
      "CREATE INDEX IF NOT EXISTS serving_grant_grantee_master_org_id_idx ON {{ this }} (grantee_master_org_id)",
      "CREATE INDEX IF NOT EXISTS serving_grant_grantee_name_trgm_idx ON {{ this }} USING gin (grantee_name gin_trgm_ops)",
      "CREATE INDEX IF NOT EXISTS serving_grant_grantor_name_trgm_idx ON {{ this }} USING gin (grantor_name gin_trgm_ops)"
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
*/

with kept as (

    select master_org_id
    from {{ ref('serving_mdm_organization') }}

)

select g.*
from {{ ref('grant') }} g
where exists (select 1 from kept k where k.master_org_id = g.grantor_master_org_id)
   or exists (select 1 from kept k where k.master_org_id = g.grantee_master_org_id)
