{{ config(materialized='table', tags=['marts', 'topics', 'serving']) }}

/*
    The companies each curated topic names (#1052). Grain: one row per (topic, company).

      data-centers          mdm_organization_data_center (in the organization master), plus the
                            data_center_operators seed's operators that aren't in it (no master_org_id).
      short-term-rentals    mdm_organization_short_term_rental (#1015).
      everything else       the topic_companies seed (license-plate readers, guns).

    match_terms are what topic_company_mention looks for: lowercase words or phrases. Data center names are
    matched only inside a passage that already talks about a data center, so "Google" or "Amazon" said in passing
    elsewhere doesn't count. Bare words that are also ordinary words are kept out of the seed (Flock is matched as
    "flock safety" / "flock camera", never "flock").
*/

with topics as (
    select topic_id, query_id from {{ ref('civicsearch_topic') }} where query_id is not null
),

dc_master as (
    select
        'data-centers'::text                                        as topic_query_id,
        d.company_key::text                                         as company_key,
        d.company_name::text                                        as company_name,
        d.aliases::text[]                                           as aliases,
        array(
            select distinct lower(regexp_replace(btrim(a), '''s$', ''))
            from unnest(d.aliases || array[d.company_name]) as a
            where length(btrim(a)) >= 3
            order by 1
        )::text[]                                                   as match_terms,
        d.website_url::text                                         as website_url,
        d.master_org_id::text                                       as master_org_id
    from {{ ref('mdm_organization_data_center') }} as d
),

dc_operators as (
    select
        'data-centers'::text                                        as topic_query_id,
        trim(both '-' from regexp_replace(lower(o.operator_name), '[^a-z0-9]+', '-', 'g'))::text as company_key,
        o.operator_name::text                                       as company_name,
        string_to_array(o.aliases, '|')::text[]                     as aliases,
        array(
            select distinct lower(regexp_replace(btrim(a), '''s$', ''))
            from unnest(string_to_array(coalesce(o.aliases, ''), '|') || string_to_array(coalesce(o.meeting_aliases, ''), '|')) as a
            where length(btrim(a)) >= 3
            order by 1
        )::text[]                                                   as match_terms,
        null::text                                                  as website_url,
        null::text                                                  as master_org_id
    from {{ ref('data_center_operators') }} as o
    where not exists (
        select 1 from dc_master as m where lower(m.company_name) = lower(o.operator_name)
    )
),

str as (
    select
        'short-term-rentals'::text                                  as topic_query_id,
        s.company_key::text                                         as company_key,
        s.company_name::text                                        as company_name,
        s.aliases::text[]                                           as aliases,
        s.match_terms::text[]                                       as match_terms,
        s.website_url::text                                         as website_url,
        s.master_org_id::text                                       as master_org_id
    from {{ ref('mdm_organization_short_term_rental') }} as s
),

seeded as (
    select
        t.topic_query_id::text                                      as topic_query_id,
        t.company_key::text                                         as company_key,
        t.company_name::text                                        as company_name,
        string_to_array(t.aliases, '|')::text[]                     as aliases,
        array(
            select distinct lower(btrim(m)) from unnest(string_to_array(t.match_terms, '|')) as m
            where nullif(btrim(m), '') is not null order by 1
        )::text[]                                                   as match_terms,
        nullif(btrim(t.website_url), '')::text                      as website_url,
        null::text                                                  as master_org_id
    from {{ ref('topic_companies') }} as t
),

unioned as (
    select * from dc_master
    union all select * from dc_operators
    union all select * from str
    union all select * from seeded
)

select
    md5(u.topic_query_id || '|' || u.company_key)::text             as topic_company_id,
    u.topic_query_id,
    tp.topic_id::integer                                            as topic_id,
    u.company_key,
    u.company_name,
    u.aliases,
    u.match_terms,
    u.website_url,
    u.master_org_id
from unioned as u
inner join topics as tp on tp.query_id = u.topic_query_id
where cardinality(u.match_terms) > 0
