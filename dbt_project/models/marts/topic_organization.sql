{{
  config(
    materialized='table',
    tags=['marts', 'topic', 'organization', 'serving'],
    indexes=[
      {'columns': ['topic_slug', 'state_code', 'evidence_rank'], 'type': 'btree'},
      {'columns': ['topic_id', 'state_code', 'city'], 'type': 'btree'},
      {'columns': ['ein'], 'type': 'btree'}
    ]
  )
}}

/*
    Mart: topic_organization (#1345) — the nonprofits tied to each curated topic. Grain: one row per
    (topic_id, master_org_id).

    PK  topic_organization_id = md5(topic_id | master_org_id).
    FK  topic_id -> civicsearch_topic; master_org_id -> mdm_organization.

    How an organization is tied (match_method, the strongest kept; match_methods lists all), never by guess:

      rank 1  named_in_meeting    named word for word near the topic's words in one of the topic's recorded meetings
                                  in its own state (int_topic_organization__named_in_meeting).
      rank 2  keyword_in_mission  its latest Form 990 mission names the topic (topic_organization_rule seed).
      rank 3  keyword_in_name     its name does.
      rank 4  ntee_code           its IRS NTEE category is the topic's field.
      (cause_tag is reserved: EveryOrg cause tags have no organization linkage in the warehouse, so no rows.)

    side is only ever a rule's stated position (a name or mission saying "Second Amendment rights" or "gun violence");
    it is null otherwise, and when an organization matches rules for both sides it is null.

    Organizations only: no officer or person data. Revenue is the latest 990 total revenue (GivingTuesday) or else the
    IRS Business Master File figure, with its tax year. Rule and spot-check: web_docs/docs/development/topic-organizations.md.
*/

with

curated_topic as (
    select topic_id, query_id as topic_slug
    from {{ ref('civicsearch_topic') }}
    where source = 'curated' and query_id is not null
),

named as (
    select topic_id, master_org_id, 'named_in_meeting'::text as match_method, 1 as evidence_rank, match_text,
           null::text as side, match_video_id, match_source_url, match_date, match_place
    from {{ ref('int_topic_organization__named_in_meeting') }}
),

rule_match as (
    select topic_id, master_org_id, match_method,
           case match_method when 'keyword_in_mission' then 2 when 'keyword_in_name' then 3 else 4 end as evidence_rank,
           match_text, side,
           null::text as match_video_id, null::text as match_source_url, null::date as match_date, null::text as match_place
    from {{ ref('int_topic_organization__rule_match') }}
),

hits as (
    select * from named
    union all
    select * from rule_match
),

per_org as (
    select
        topic_id,
        master_org_id,
        min(evidence_rank)                                                      as evidence_rank,
        array_agg(distinct match_method order by match_method)                  as match_methods,
        -- A side only when every stated side agrees.
        case when count(distinct side) = 1 then max(side) end                   as side
    from hits
    group by topic_id, master_org_id
),

best as (
    select distinct on (topic_id, master_org_id) *
    from hits
    order by topic_id, master_org_id, evidence_rank, match_date desc nulls last
),

mission as (
    select distinct on (m.ein) m.ein, m.mission
    from {{ ref('stg_givingtuesday__990_missions') }} as m
    where m.mission !~* '^\s*(see|refer to)\s+(schedule|sch\.?)\s*o'
      and length(m.mission) >= 20
    order by m.ein, m.tax_year desc
)

select
    md5(p.topic_id::text || '|' || p.master_org_id)::text                       as topic_organization_id,
    p.topic_id::integer                                                         as topic_id,
    t.topic_slug::text                                                          as topic_slug,
    p.master_org_id::text                                                       as master_org_id,
    nullif(trim(n.ein), '')::text                                               as ein,
    o.org_name::text                                                            as org_name,
    nullif(trim(o.city_norm), '')::text                                         as city,
    o.state_code::text                                                          as state_code,
    ({{ state_code_to_name('o.state_code') }})::text                            as state,
    b.match_method::text                                                        as match_method,
    p.match_methods::text[]                                                     as match_methods,
    p.evidence_rank::integer                                                    as evidence_rank,
    b.match_text::text                                                          as match_text,
    b.match_video_id::text                                                      as match_video_id,
    b.match_source_url::text                                                    as match_source_url,
    b.match_date::date                                                          as match_date,
    b.match_place::text                                                         as match_place,
    nullif(trim(n.ntee_code), '')::text                                         as ntee_code,
    left(m.mission, 400)::text                                                  as mission,
    p.side::text                                                                as side,
    coalesce(n.gt990_total_revenue, n.revenue)::bigint                          as revenue,
    (case
        when n.gt990_total_revenue is not null then n.gt990_tax_year
        when n.revenue is not null and n.tax_period ~ '^\d{4}' then left(n.tax_period, 4)::integer
     end)::integer                                                              as revenue_tax_year,
    (case
        when n.gt990_total_revenue is not null then 'irs_990'
        when n.revenue is not null then 'irs_bmf'
     end)::text                                                                 as revenue_source,
    null::text                                                                  as website_url,
    now()::timestamptz                                                          as built_at
from per_org as p
inner join best as b on b.topic_id = p.topic_id and b.master_org_id = p.master_org_id
inner join curated_topic as t on t.topic_id = p.topic_id
inner join {{ ref('mdm_organization') }} as o on o.master_org_id = p.master_org_id
left join {{ ref('mdm_organization_nonprofit') }} as n on n.master_org_id = p.master_org_id
left join mission as m on m.ein = n.ein
where o.state_code is not null
