{{ config(
    materialized='table',
    tags=['marts', 'money', 'serving'],
    post_hook=[
      "CREATE INDEX IF NOT EXISTS company_grant_master_org_id_idx ON {{ this }} (master_org_id)",
      "CREATE INDEX IF NOT EXISTS company_grant_foundation_master_org_id_idx ON {{ this }} (foundation_master_org_id)",
      "CREATE INDEX IF NOT EXISTS company_grant_grantee_master_org_id_idx ON {{ this }} (grantee_master_org_id)"
    ]
) }}

/*
    Grants from the foundations tied to the companies we track (#1073). Grain: one row per grant line
    (grant.grant_id) whose grantor EIN is a foundation in the company_foundation seed.

    The amounts are the grant mart's, i.e. exactly what the foundation's IRS 990 Schedule I reports; nothing is
    summed, estimated or filled here. The grant mart holds 990 public-charity filers only (no 990-PF), so only
    foundations that file a 990 can appear.

    The company's master_org_id comes from topic_company (data centers, short-term rentals and topic companies).
    A company with no master_org_id there is left out: company_grant's FK to mdm_organization needs one.

    grant is ~6.7M rows with no grantor_ein index, so the foundation EIN is first resolved to its master row through
    mdm_organization_nonprofit (indexed on ein), the same way grant.sql resolves grantor_master_org_id, and grant is
    read through its grantor_master_org_id index. grantor_ein is still checked so only that filer's lines count.
*/

with foundations as (
    select
        f.company_key::text                                         as company_key,
        f.company_name::text                                        as company_name,
        lpad(regexp_replace(f.foundation_ein::text, '[^0-9]', '', 'g'), 9, '0') as foundation_ein,
        f.foundation_name::text                                     as foundation_name,
        f.relationship::text                                        as relationship,
        f.source_url::text                                          as foundation_source_url
    from {{ ref('company_foundation') }} as f
),

companies as (
    select distinct on (company_key)
        company_key,
        master_org_id
    from {{ ref('topic_company') }}
    where master_org_id is not null
    order by company_key, master_org_id
),

linked as (
    select
        f.*,
        c.master_org_id,
        np.master_org_id                                            as foundation_master_org_id
    from foundations as f
    inner join companies as c on c.company_key = f.company_key
    inner join {{ ref('mdm_organization') }} as m on m.master_org_id = c.master_org_id
    inner join {{ ref('mdm_organization_nonprofit') }} as np on np.ein = f.foundation_ein
)

select
    g.grant_id::text                                                as grant_id,
    l.company_key,
    l.company_name,
    l.master_org_id::text                                           as master_org_id,
    l.foundation_ein,
    l.foundation_name,
    l.foundation_master_org_id::text                                as foundation_master_org_id,
    l.relationship,
    l.foundation_source_url,
    g.grantor_name::text                                            as grantor_name_on_filing,
    g.grantee_name::text                                            as grantee_name,
    g.grantee_ein::text                                             as grantee_ein,
    g.grantee_master_org_id::text                                   as grantee_master_org_id,
    g.grantee_city::text                                            as grantee_city,
    g.grantee_state_code::text                                      as grantee_state_code,
    g.amount::bigint                                                as amount,
    g.purpose::text                                                 as purpose,
    g.tax_year::integer                                             as tax_year,
    g.source_url::text                                              as source_url
from linked as l
inner join {{ ref('grant') }} as g
    on g.grantor_master_org_id = l.foundation_master_org_id
   and g.grantor_ein = l.foundation_ein
