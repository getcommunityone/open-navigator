{{ config(materialized='table', tags=['intermediate', 'data_centers']) }}

/*
    What each data center news item says about a company-hosted meeting (#532).
    Grain: one row per news item. Deterministic text matching only (no LLM); nothing is
    filled in that the item's own text doesn't say.

      master_org_id   the host: a data center company (mdm_organization_data_center) the
                      item names by its name or an alias, matched case-sensitively on a
                      whole word or phrase; a company's own press release is that company.
                      When several are named, a developer/operator of the matched project
                      wins, then the longest name.
      project_id      a curated project (data_center_project) the item names by its project
                      name (case-insensitive, 8+ characters), or whose stated city the item
                      names alongside one of that project's companies.
      jurisdiction_id the project's government (data_center_project.jurisdiction_id).
      event_kind      the first meeting word named in the text (town_hall, community_meeting,
                      open_house, information_session, public_meeting).
      event_date      only a date the text states after the first meeting word, in the same
                      sentence: "town hall ... October 7, 2026" (event_date_basis 'stated'), or
                      "Oct. 7" (month capitalised) with the year of publication, moved a year
                      forward when that is more than 60 days before publication, or back when
                      it is more than 300 days after ('stated_month_day'). A dateline or an
                      earlier date is never used; no date there means null.
      recording_url   a YouTube or Facebook video link the item's text carries; for a video
                      found by YouTube search (#549) that is not a news channel's
                      (source_role 'recording'), the video itself.
      source_role     article, recording or news_coverage (stg_data_center_news_item).
      status          'confirmed' when the item says "data center", names a meeting word,
                      names the host company and resolves a project; 'unconfirmed' when it
                      says "data center" and a meeting word but misses the host or project
                      (kept for review, not shown as an event); 'not_event' otherwise.
*/

{%- set month_rx = "(Jan(uary)?|Feb(ruary)?|Mar(ch)?|Apr(il)?|May|June?|July?|Aug(ust)?|Sep(t(ember)?)?|Oct(ober)?|Nov(ember)?|Dec(ember)?)\\.?" %}
{%- set date_rx = "\\m" ~ month_rx ~ "\\s+([0-9]{1,2})(st|nd|rd|th)?\\M(,?\\s+(20[0-9]{2}))?" %}
{%- set kind_rx = "\\m(town ?hall|community meeting|open house|information session|public meeting)s?\\M" %}

with items as (
    select * from {{ ref('stg_data_center_news_item') }}
),

companies as (
    select master_org_id, company_key, company_name, aliases from {{ ref('mdm_organization_data_center') }}
),

company_terms as (
    select master_org_id, company_key, company_name as term from companies
    union
    select master_org_id, company_key, a from companies cross join lateral unnest(aliases) as a
    where length(a) >= 3
),

projects as (
    select project_id, project_name, city, state_code, jurisdiction_id
    from {{ ref('data_center_project') }}
    where project_source = 'curated'
),

project_companies as (
    select project_id, master_org_id, role from {{ ref('data_center_project_company') }}
),

company_hits as (
    select i.news_item_id, t.master_org_id, max(length(t.term)) as term_len
    from items as i
    inner join company_terms as t on i.body ~ {{ phrase_regex('t.term') }}
    group by 1, 2
    union
    select i.news_item_id, c.master_org_id, 1000
    from items as i
    inner join companies as c on c.company_key = i.company_key
),

project_hits as (
    select i.news_item_id, p.project_id, 1 as hit_rank
    from items as i
    inner join projects as p
        on length(p.project_name) >= 8 and i.body ~* {{ phrase_regex('p.project_name') }}
    union all
    select i.news_item_id, p.project_id, 2
    from items as i
    inner join projects as p on p.city is not null and i.body ~ {{ phrase_regex('p.city') }}
    inner join project_companies as pc on pc.project_id = p.project_id
    inner join company_hits as ch on ch.news_item_id = i.news_item_id and ch.master_org_id = pc.master_org_id
),

best_project as (
    select distinct on (news_item_id) news_item_id, project_id
    from project_hits
    order by news_item_id, hit_rank, project_id
),

best_company as (
    select distinct on (ch.news_item_id) ch.news_item_id, ch.master_org_id
    from company_hits as ch
    left join best_project as bp on bp.news_item_id = ch.news_item_id
    left join project_companies as pc
        on pc.project_id = bp.project_id and pc.master_org_id = ch.master_org_id
       and pc.role in ('developer', 'operator')
    order by ch.news_item_id, (pc.project_id is not null) desc, ch.term_len desc, ch.master_org_id
),

-- The date must follow the meeting word in the same sentence ("... town hall Oct. 7"),
-- so a press release's dateline ("DALLAS, Oct. 2, 2026 --") or an announcement date
-- earlier in the text is never taken as the meeting date.
after_kind as (
    select
        i.news_item_id,
        left(substr(i.body, regexp_instr(i.body, '{{ kind_rx }}', 1, 1, 0, 'i')), 220) as tail
    from items as i
    where regexp_instr(i.body, '{{ kind_rx }}', 1, 1, 0, 'i') > 0
),

dated as (
    select
        a.news_item_id,
        regexp_match(a.tail, '{{ date_rx }}') as m,
        left(a.tail, regexp_instr(a.tail, '{{ date_rx }}') - 1) as before_date
    from after_kind as a
    where regexp_instr(a.tail, '{{ date_rx }}') > 0
),

event_dates as (
    select
        d.news_item_id,
        d.m[1] as month_text,
        d.m[12]::int as day_num,
        d.m[15] as year_text
    from dated as d
    where d.m is not null
      -- no sentence break between the meeting word and the date
      and d.before_date !~ '[.!?]\s+[A-Z]'
),

resolved_dates as (
    select
        e.news_item_id,
        case when e.year_text is not null then 'stated' else 'stated_month_day' end as event_date_basis,
        (make_date(y.yr, y.mo, 1) + (e.day_num - 1))::date                           as raw_date,
        y.mo,
        i.published_on
    from event_dates as e
    inner join items as i on i.news_item_id = e.news_item_id
    cross join lateral (
        select coalesce(e.year_text::int, extract(year from i.published_on)::int)  as yr,
               extract(month from to_date(left(e.month_text, 3), 'Mon'))::int      as mo
    ) as y
    where e.day_num between 1 and 31
      and y.yr is not null
),

valid_dates as (
    -- "February 30" rolls into March: drop it rather than move it
    select * from resolved_dates where extract(month from raw_date)::int = mo
)

select
    i.news_item_id::text                                              as news_item_id,
    i.source::text                                                    as source,
    i.url::text                                                       as url,
    i.title::text                                                     as title,
    i.publisher::text                                                 as publisher,
    i.published_on::date                                              as published_on,
    i.snippet::text                                                   as snippet,
    i.body::text                                                      as body,
    i.kinds::text[]                                                   as kinds,
    (case regexp_replace(lower((regexp_match(i.body, '{{ kind_rx }}', 'i'))[1]), '^townhall$', 'town hall')
        when 'town hall' then 'town_hall'
        when 'community meeting' then 'community_meeting'
        when 'open house' then 'open_house'
        when 'information session' then 'information_session'
        when 'public meeting' then 'public_meeting'
    end)::text                                                        as event_kind,
    bc.master_org_id::text                                            as master_org_id,
    bp.project_id::text                                               as project_id,
    p.jurisdiction_id::text                                           as jurisdiction_id,
    p.state_code::text                                                as state_code,
    p.city::text                                                      as city,
    (case
        when rd.event_date_basis = 'stated_month_day' and rd.raw_date < rd.published_on - 60
            then (rd.raw_date + interval '1 year')::date
        when rd.event_date_basis = 'stated_month_day' and rd.raw_date > rd.published_on + 300
            then (rd.raw_date - interval '1 year')::date
        else rd.raw_date
    end)::date                                                        as event_date,
    rd.event_date_basis::text                                         as event_date_basis,
    coalesce(
        (regexp_match(coalesce(i.snippet, ''),
            '(https?://(www\.|m\.)?(youtube\.com/(watch\?v=|live/)|youtu\.be/|facebook\.com/[^\s"<>]+/videos/)[^\s"<>]+)'))[1],
        case when i.source_role = 'recording' then i.url end
    )::text                                                           as recording_url,
    i.source_role::text                                               as source_role,
    (case
        when i.says_data_center and cardinality(i.kinds) > 0
             and bc.master_org_id is not null and bp.project_id is not null then 'confirmed'
        when i.says_data_center and cardinality(i.kinds) > 0 then 'unconfirmed'
        else 'not_event'
    end)::text                                                        as status
from items as i
left join best_company as bc on bc.news_item_id = i.news_item_id
left join best_project as bp on bp.news_item_id = i.news_item_id
left join projects as p on p.project_id = bp.project_id
left join valid_dates as rd on rd.news_item_id = i.news_item_id
