/*
    What residents object to, by area (DC-4.3, #251).
    Grain: one row per area per concern. Area = a jurisdiction (state_code +
    jurisdiction_name, as event_decision carries it) or the whole nation
    (area_level = 'national').

    Source: the objections recorded in an area's own meetings, the counter_views on
    event_decision.competing_views (label, problem diagnosis, causal story, remedy).
    Each objection counts once per concern it mentions (local_concern_patterns()).
    share = mentions / all objections in the area, so shares can sum past 1 (one
    objection can raise water and noise). Real counts only: an area with no
    objections has no rows, and nothing is filled in.

    is_dominant marks the top concern (rank 1) once it has at least 3 mentions, so one
    stray comment can't set an area's ranking.
*/

{%- set patterns = local_concern_patterns() %}

with decisions as (
    select
        d.event_decision_id,
        d.state_code,
        nullif(btrim(d.jurisdiction_name), '') as jurisdiction_name,
        m.meeting_date,
        d.competing_views
    from {{ ref('event_decision') }} as d
    left join {{ ref('event_meeting') }} as m on m.event_meeting_id = d.analysis_id
    where jsonb_typeof(d.competing_views -> 'counter_views') = 'array'
),

objections as (
    select
        d.event_decision_id,
        d.state_code,
        d.jurisdiction_name,
        {{ safe_iso_date('d.meeting_date::text') }} as meeting_on,
        concat_ws(' ',
            v ->> 'view_label', v ->> 'problem_diagnosis', v ->> 'causal_story', v ->> 'proposed_remedy'
        ) as objection_text
    from decisions as d
    cross join lateral jsonb_array_elements(d.competing_views -> 'counter_views') as v
    where jsonb_typeof(v) = 'object'
),

tagged as (
    select
        o.*,
        array_remove(array[
        {%- for concern, regex in patterns %}
            case when o.objection_text ~* '{{ regex }}' then '{{ concern }}' end{{ "," if not loop.last }}
        {%- endfor %}
        ], null) as concerns
    from objections as o
    where nullif(btrim(o.objection_text), '') is not null
),

areas as (
    select 'jurisdiction'::text as area_level, state_code as s, jurisdiction_name as j, concerns, meeting_on
    from tagged
    where state_code is not null and jurisdiction_name is not null
    union all
    select 'national'::text, null::text, null::text, concerns, meeting_on
    from tagged
),

area_totals as (
    select area_level, s, j, count(*)::int as objection_count
    from areas
    group by 1, 2, 3
),

area_mentions as (
    select
        a.area_level, a.s, a.j, c.concern,
        count(*)::int        as mention_count,
        min(a.meeting_on)    as first_meeting_on,
        max(a.meeting_on)    as last_meeting_on
    from areas as a
    cross join lateral unnest(a.concerns) as c(concern)
    group by 1, 2, 3, 4
),

ranked as (
    select
        m.*,
        t.objection_count,
        rank() over (partition by m.area_level, m.s, m.j order by m.mention_count desc) as concern_rank
    from area_mentions as m
    inner join area_totals as t
        on t.area_level = m.area_level
       and t.s is not distinct from m.s
       and t.j is not distinct from m.j
)

select
    md5(concat_ws('|', area_level, coalesce(s, ''), coalesce(j, ''), concern))::text as area_concern_id,
    area_level::text                                         as area_level,
    s::text                                                  as state_code,
    case when s is not null then {{ state_code_to_name('s') }} end::text as state,
    j::text                                                  as jurisdiction_name,
    concern::text                                            as concern,
    mention_count::integer                                   as mention_count,
    objection_count::integer                                 as objection_count,
    (mention_count::double precision / nullif(objection_count, 0))::double precision as share,
    concern_rank::integer                                    as concern_rank,
    (concern_rank = 1 and mention_count >= 3)::boolean       as is_dominant,
    first_meeting_on::date                                   as first_meeting_on,
    last_meeting_on::date                                    as last_meeting_on
from ranked
