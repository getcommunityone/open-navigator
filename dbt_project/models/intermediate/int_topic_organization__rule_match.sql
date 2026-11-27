{{ config(materialized='table', tags=['intermediate', 'topic', 'organization']) }}

/*
    Nonprofits tied to a curated topic by a curated rule (#1345): one row per (topic_id, master_org_id, match_method).
    The rules are the topic_organization_rule seed:

      ntee_code         the organization's IRS NTEE code starts with the rule's three characters.
      keyword_in_name   its name matches the rule's regex.
      keyword_in_mission  its latest Form 990 mission (GivingTuesday datamart) matches the rule's regex.

    match_text is the evidence as the record states it: the NTEE category's label, the name, or the mission with the
    matched words in <mark>. side comes only from a rule whose words state a position. topic_organization picks the
    strongest method per organization; int_topic_organization__named_in_meeting adds meeting mentions.
*/

with

curated_topic as (
    select topic_id, query_id as topic_slug
    from {{ ref('civicsearch_topic') }}
    where source = 'curated' and query_id is not null
),

rules as (
    select t.topic_id, t.topic_slug, r.rule_type, r.pattern, nullif(trim(r.side), '') as side, nullif(trim(r.label), '') as label
    from {{ ref('topic_organization_rule') }} as r
    inner join curated_topic as t on t.topic_slug = r.topic_query_id
),

nonprofit as (
    select
        n.master_org_id,
        nullif(trim(n.ein), '')                      as ein,
        upper(left(nullif(trim(n.ntee_code), ''), 3)) as ntee3,
        o.org_name
    from {{ ref('mdm_organization_nonprofit') }} as n
    inner join {{ ref('mdm_organization') }} as o on o.master_org_id = n.master_org_id
    where o.state_code is not null and o.org_name is not null
),

-- The latest substantive mission per EIN ("See Schedule O" points elsewhere and is not a mission).
mission as (
    select distinct on (m.ein) m.ein, m.tax_year, m.mission
    from {{ ref('stg_givingtuesday__990_missions') }} as m
    where m.mission !~* '^\s*(see|refer to)\s+(schedule|sch\.?)\s*o'
      and length(m.mission) >= 20
    order by m.ein, m.tax_year desc
),

ntee_hits as (
    select r.topic_id, n.master_org_id, 'ntee_code'::text as match_method,
           coalesce(r.label, 'IRS category ' || r.pattern) as match_text, r.side
    from rules as r
    inner join nonprofit as n on n.ntee3 = r.pattern
    where r.rule_type = 'ntee_code'
),

name_hits as (
    select r.topic_id, n.master_org_id, 'keyword_in_name'::text as match_method,
           regexp_replace(n.org_name, '(' || r.pattern || ')', '<mark>\1</mark>', 'gi') as match_text, r.side
    from rules as r
    inner join nonprofit as n on n.org_name ~* r.pattern
    where r.rule_type = 'name_keyword'
),

mission_hits as (
    select r.topic_id, n.master_org_id, 'keyword_in_mission'::text as match_method,
           regexp_replace(
               case when length(m.mission) <= 1000 then m.mission
                    else substr(m.mission, greatest(1, regexp_instr(m.mission, r.pattern, 1, 1, 0, 'i') - 300), 1000) end,
               '(' || r.pattern || ')', '<mark>\1</mark>', 'gi') as match_text, r.side
    from rules as r
    inner join mission as m on m.mission ~* r.pattern
    inner join nonprofit as n on n.ein = m.ein
    where r.rule_type = 'mission_keyword'
),

unioned as (
    select * from ntee_hits
    union all
    select * from name_hits
    union all
    select * from mission_hits
)

-- One row per (topic, organization, method): a stated side wins over none.
select distinct on (topic_id, master_org_id, match_method)
    topic_id::integer      as topic_id,
    master_org_id::text    as master_org_id,
    match_method::text     as match_method,
    match_text::text       as match_text,
    side::text             as side
from unioned
order by topic_id, master_org_id, match_method, (side is null), match_text
