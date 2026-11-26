{{ config(materialized='table', tags=['marts', 'mdm', 'short_term_rentals', 'serving']) }}

/*
    MDM satellite (#1015): short-term rental platform detail for organizations in the master that are platform
    companies (Airbnb, Expedia Group / Vrbo, Booking Holdings). Grain: one row per master_org_id, 1:1 with the
    short_term_rental_companies seed. Sibling of mdm_organization_data_center; same entry path
    (stg_short_term_rental_companies__org -> int_organizations__unioned -> __clustered), so master_org_id is the
    cluster the company landed in. Every row carries source_url and a verbatim source_excerpt from the company's
    own page. match_terms are the words that name the company in a transcript or decision.
*/

with seed as (
    select * from {{ ref('short_term_rental_companies') }}
),

clustered as (
    select source_pk as company_key, master_org_id
    from {{ ref('int_organizations__clustered') }}
    where source_system = 'seed_short_term_rental_companies'
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
        select distinct lower(btrim(t)) from unnest(string_to_array(s.match_terms, '|')) as t
        where nullif(btrim(t), '') is not null order by 1
    )::text[]                                                               as match_terms,
    array(
        select distinct btrim(r) from unnest(string_to_array(s.roles, '|')) as r
        where nullif(btrim(r), '') is not null order by 1
    )::text[]                                                               as roles,
    nullif(btrim(s.website_url), '')::text                                  as website_url,
    s.source_kind::text                                                     as source_kind,
    s.source_url::text                                                      as source_url,
    s.source_excerpt::text                                                  as source_excerpt
from seed as s
inner join clustered as c on c.company_key = s.company_key
inner join {{ ref('mdm_organization') }} as m on m.master_org_id = c.master_org_id
order by c.master_org_id, s.company_key
