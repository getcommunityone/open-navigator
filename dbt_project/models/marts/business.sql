{{ config(materialized='table', tags=['marts', 'business', 'serving']) }}

/*
    The businesses that meetings and decisions name (#1089, #1088; design: businesses-search.md).
    Grain: one row per business named in at least one meeting or decision (business_mention has the mentions).

    Built from int_business_mention__source, which holds the sources and the exclusions (government bodies and
    political committees are left out there). business_id is master_org_id when the name matched the organization
    master, else md5(normalized name | state_code).

    business_type_code, by fixed rules in this order, no model guessing:
      1. nonprofit     an EIN found in mdm_organization_nonprofit, or the extraction typed it nonprofit or church;
      2. corporation   a company in the data-center, short-term-rental or topic company tables
                       (mdm_organization_data_center, mdm_organization_short_term_rental, topic_company), or named in
                       records from 2 or more states;
      3. local_business  any other business.
    is_all_locations is true for every company in mdm_organization_data_center (and a data-centers topic company, the
    operators the seed adds), and for a corporation named in 2 or more states. Those rows keep no single city.
    A business with no master match is keyed per state, so the same unmatched name in two states is two rows;
    the 2-state count is over the name, not the row.
*/

with m as (
    select *, coalesce(master_org_id, name_key) as group_key
    from {{ ref('int_business_mention__source') }}
),

state_spread as (
    select group_key, count(distinct state_code) as state_count
    from m
    where state_code is not null
    group by group_key
),

agg as (
    select
        m.business_id,
        (array_agg(m.business_name order by m.mention_date desc nulls last, m.business_name))[1] as business_name,
        max(m.master_org_id)                                            as master_org_id,
        max(m.ein)                                                      as mention_ein,
        bool_or(m.org_type_code in ('nonprofit', 'church'))             as is_typed_nonprofit,
        bool_or(m.is_topic_company)                                     as is_topic_company,
        bool_or(m.is_data_center_company)                               as is_data_center_company,
        mode() within group (order by coalesce(m.business_state_code, m.state_code)) as mention_state_code,
        coalesce(max(s.state_count), 0)                                 as state_count,
        count(*)                                                        as mention_count,
        min(m.mention_date)                                             as first_mentioned_date,
        max(m.mention_date)                                             as last_mentioned_date
    from m
    left join state_spread as s on s.group_key = m.group_key
    group by m.business_id
),

resolved as (
    select
        a.*,
        o.state_code                                                    as master_state_code,
        o.city_norm                                                     as master_city,
        o.website                                                       as master_website,
        coalesce(o.ein, a.mention_ein)                                  as ein,
        exists (
            select 1 from {{ ref('mdm_organization_data_center') }} as dc where dc.master_org_id = a.master_org_id
        ) or a.is_data_center_company                                   as is_data_center
    from agg as a
    left join {{ ref('mdm_organization') }} as o on o.master_org_id = a.master_org_id
),

typed as (
    select
        r.*,
        (
            r.is_typed_nonprofit
            or (r.ein is not null and exists (
                select 1 from {{ ref('mdm_organization_nonprofit') }} as n where n.ein = r.ein
            ))
        )                                                               as is_nonprofit,
        (
            r.is_topic_company or r.is_data_center
            or (r.master_org_id is not null and (
                exists (select 1 from {{ ref('mdm_organization_short_term_rental') }} as s where s.master_org_id = r.master_org_id)
            ))
            or r.state_count >= 2
        )                                                               as is_corporation
    from resolved as r
)

select
    t.business_id::text                                                 as business_id,
    t.business_name::text                                               as business_name,
    (case
        when t.is_nonprofit then 'nonprofit'
        when t.is_corporation then 'corporation'
        else 'local_business'
    end)::text                                                          as business_type_code,
    t.master_org_id::text                                               as master_org_id,
    coalesce(t.master_state_code, t.mention_state_code)::text           as state_code,
    {{ state_code_to_name('coalesce(t.master_state_code, t.mention_state_code)') }}::text as state,
    (case when t.is_data_center
               or (not t.is_nonprofit and t.state_count >= 2) then null else t.master_city end)::text as city,
    (t.is_data_center or (not t.is_nonprofit and t.state_count >= 2))   as is_all_locations,
    t.ein::text                                                         as ein,
    t.master_website::text                                              as website_url,
    t.mention_count::bigint                                             as mention_count,
    t.first_mentioned_date::date                                        as first_mentioned_date,
    t.last_mentioned_date::date                                         as last_mentioned_date
from typed as t
