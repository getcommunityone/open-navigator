{{ config(materialized='table', tags=['marts', 'mdm', 'data_centers', 'serving']) }}

/*
    MDM satellite (#531): data center detail for organizations in the master that are
    data center companies (operators, developers, owners, tenants/users, utility
    partners). Grain: one row per master_org_id, 1:1 with the subset of mdm_organization
    that the data_center_companies seed names. Sibling of mdm_organization_nonprofit.

    The company enters mdm_organization through the MDM pipeline (stg_data_center_
    companies__org -> int_organizations__unioned -> __clustered), so master_org_id is the
    cluster id the company landed in: an existing master row when one matched (e.g. the
    AI-extracted national "Google"), else a new one. This satellite only adds what the
    master has no column for.

    Every row carries its source: source_url plus a verbatim source_excerpt. source_kind
    says what the excerpt is: 'company_announcement' (the company's own press release),
    'news_article' (a headline or passage from coverage), or 'dataset_row' (a field of a
    published dataset, quoted as "<row> | <field>: <value>", e.g. Epoch AI's site list).
*/

with seed as (
    select * from {{ ref('data_center_companies') }}
),

clustered as (
    select source_pk as company_key, master_org_id
    from {{ ref('int_organizations__clustered') }}
    where source_system = 'seed_data_center_companies'
)

select distinct on (c.master_org_id)
    c.master_org_id::text                                                   as master_org_id,
    s.company_key::text                                                     as company_key,
    s.company_name::text                                                    as company_name,
    array(
        select distinct btrim(a) from unnest(string_to_array(s.aliases, '|')) as a
        where nullif(btrim(a), '') is not null order by 1
    )::text[]                                                               as aliases,
    array(
        select distinct btrim(r) from unnest(string_to_array(s.roles, '|')) as r
        where nullif(btrim(r), '') is not null order by 1
    )::text[]                                                               as roles,
    nullif(btrim(s.website_url), '')::text                                  as website_url,
    nullif(btrim(s.press_feed_url), '')::text                               as press_feed_url,
    s.source_kind::text                                                     as source_kind,
    s.source_url::text                                                      as source_url,
    s.source_excerpt::text                                                  as source_excerpt
from seed as s
inner join clustered as c on c.company_key = s.company_key
inner join {{ ref('mdm_organization') }} as m on m.master_org_id = c.master_org_id
order by c.master_org_id, s.company_key
