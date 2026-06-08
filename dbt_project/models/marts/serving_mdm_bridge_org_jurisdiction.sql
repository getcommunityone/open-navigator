{{
  config(
    materialized='table',
    post_hook=[
      "CREATE INDEX IF NOT EXISTS serving_mdm_bridge_org_jurisdiction_jurisdiction_id_idx ON {{ this }} (jurisdiction_id)",
      "CREATE INDEX IF NOT EXISTS serving_mdm_bridge_org_jurisdiction_master_org_id_idx ON {{ this }} (master_org_id)",
      "ALTER TABLE {{ this }} ADD CONSTRAINT serving_mdm_bridge_org_jurisdiction_master_org_id_fkey FOREIGN KEY (master_org_id) REFERENCES {{ ref('serving_mdm_organization') }} (master_org_id) NOT VALID",
      "ALTER TABLE {{ this }} ADD CONSTRAINT serving_mdm_bridge_org_jurisdiction_jurisdiction_id_fkey FOREIGN KEY (jurisdiction_id) REFERENCES {{ ref('jurisdictions') }} (jurisdiction_id) NOT VALID"
    ]
  )
}}

/*
    Serving subset of the org<->jurisdiction bridge for the Neon free-tier
    deployment. Filtered to the orgs retained in serving_mdm_organization
    (largest 10% per jurisdiction). Bridge rows for dropped orgs would dangle, so
    the inner join keeps only edges whose org is served.
*/

select b.*
from {{ ref('mdm_bridge_org_jurisdiction') }} b
inner join {{ ref('serving_mdm_organization') }} o
    on o.master_org_id = b.master_org_id
