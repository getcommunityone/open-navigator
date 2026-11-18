{{ config(materialized='table', tags=['marts', 'data_centers', 'serving']) }}

/*
    Companies on a data center project, by role (#531). Grain: one row per
    (project_id, master_org_id, role). The company is the organization master row
    (mdm_organization, via its data center satellite mdm_organization_data_center).

    role:
      developer / operator / tenant   a curated project's stated companies (the
                                      data_center_projects seed), sourced by that row's
                                      company_source_url / company_source_excerpt
                                      (else its main source);
      owner / user                    Epoch AI's "Owner" (owner of the AI hardware) and
                                      "Users" (AI labs using the site) for an Epoch site,
                                      matched to a company by its name or an alias
                                      (case-insensitive, whole name). A name Epoch gives
                                      that no company row carries stays unlinked.
    confidence: 'stated', or Epoch's own 'likely' / 'speculative' tag.
*/

with projects as (
    select project_id, project_key, data_center_site_id from {{ ref('data_center_project') }}
),

companies as (
    select master_org_id, company_key, company_name, aliases from {{ ref('mdm_organization_data_center') }}
),

company_names as (
    select master_org_id, lower(company_name) as name from companies
    union
    select master_org_id, lower(a) from companies cross join lateral unnest(aliases) as a
),

curated as (
    select p.project_id, r.role, r.company_key, c.source_kind,
           coalesce(nullif(btrim(c.company_source_url), ''), c.source_url)         as source_url,
           coalesce(nullif(btrim(c.company_source_excerpt), ''), c.source_excerpt) as source_excerpt
    from {{ ref('data_center_projects') }} as c
    inner join projects as p on p.project_key = c.project_key
    cross join lateral (values
        ('developer', nullif(btrim(c.developer_key), '')),
        ('operator',  nullif(btrim(c.operator_key), '')),
        ('tenant',    nullif(btrim(c.tenant_key), ''))
    ) as r(role, company_key)
    where r.company_key is not null
),

epoch_names as (
    select
        p.project_id,
        f.role,
        btrim(regexp_replace(n.raw, '\s*\((likely|speculative)\)\s*$', '', 'i')) as name,
        coalesce(lower((regexp_match(n.raw, '\((likely|speculative)\)\s*$', 'i'))[1]), 'stated') as confidence,
        s.source_url,
        s.site_name || ' | ' || f.label || ': ' || f.field_value as source_excerpt
    from projects as p
    inner join {{ ref('data_center_site') }} as s on s.data_center_site_id = p.data_center_site_id
    cross join lateral (values ('owner', 'Owner', s.owner), ('user', 'Users', s.users)) as f(role, label, field_value)
    cross join lateral unnest(string_to_array(coalesce(f.field_value, ''), ',')) as n(raw)
    where nullif(btrim(n.raw), '') is not null
),

linked as (
    select c.project_id, m.master_org_id, c.role, 'stated'::text as confidence,
           c.source_kind, c.source_url, c.source_excerpt, 1 as source_rank
    from curated as c
    inner join companies as m on m.company_key = c.company_key
    union all
    select e.project_id, n.master_org_id, e.role, e.confidence,
           'dataset_row', e.source_url, e.source_excerpt, 2
    from epoch_names as e
    inner join company_names as n on n.name = lower(e.name)
)

select distinct on (project_id, master_org_id, role)
    md5(project_id || '|' || master_org_id || '|' || role)::text as project_company_id,
    project_id::text      as project_id,
    master_org_id::text   as master_org_id,
    role::text            as role,
    confidence::text      as confidence,
    source_kind::text     as source_kind,
    source_url::text      as source_url,
    source_excerpt::text  as source_excerpt
from linked
order by project_id, master_org_id, role, source_rank
