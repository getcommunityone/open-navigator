{{
  config(
    materialized='table',
    post_hook=[
      "CREATE INDEX IF NOT EXISTS serving_mdm_organization_nonprofit_ein_idx ON {{ this }} (ein)",
      "ALTER TABLE {{ this }} ADD CONSTRAINT serving_mdm_organization_nonprofit_master_org_id_fkey FOREIGN KEY (master_org_id) REFERENCES {{ ref('serving_mdm_organization') }} (master_org_id) NOT VALID"
    ]
  )
}}

/*
    Serving subset of the mdm_organization_nonprofit satellite (990 financials)
    for the Neon free-tier deployment. Filtered to the orgs retained in
    serving_mdm_organization (largest 10% per jurisdiction) so the 1:1 satellite
    stays referentially consistent with its served master.
*/

select np.*
from {{ ref('mdm_organization_nonprofit') }} np
inner join {{ ref('serving_mdm_organization') }} o
    on o.master_org_id = np.master_org_id
