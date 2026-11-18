{{ config(materialized='table', tags=['marts', 'data_centers', 'serving']) }}

/*
    Decisions and meeting passages that discuss a data center project (#531). Grain: one
    row per (project_id, record_type, record_id).

    record_type:
      decision          an event_decision (latest extraction) whose headline or
                        decision_statement says "data center" (data_center_regex);
                        record_id = event_decision_id.
      meeting_passage   a transcript passage in data_center_meeting_mention (#445);
                        record_id = data_center_meeting_mention_id.

    match_basis (deterministic, no LLM; the first that applies wins):
      project_name       the text names the project (name of 8+ characters) and the record
                         is in the project's state;
      company_and_place  the text names one of the project's companies (its name or an
                         alias, from mdm_organization_data_center; only 'stated' links, not
                         Epoch's likely/speculative ones) AND the record's government is one
                         of the project's governments (data_center_project_jurisdiction),
                         and the company has no other project in that government; a
                         company named as a web address ("google.com") doesn't count.
    A company named somewhere else, or a place alone, is not a match. company_and_place
    says the record names the company where the project is, not that it names the project:
    the page labels it that way.
    Decisions match case-sensitively on a whole word or phrase (as decision_company_mention
    does); caption text is mostly lower case, so passages match case-insensitively.
    evidence is a verbatim excerpt of the record's own text, ~120 characters either side,
    with the matched words in <mark>.
*/

{%- set dc_regex = data_center_regex() %}

with projects as (
    select project_id, project_name, state_code from {{ ref('data_center_project') }}
),

project_terms as (
    select project_id, state_code, null::text as master_org_id, project_name as term,
           'project_name' as basis, 1 as basis_rank
    from projects
    where length(project_name) >= 8
    union
    select pc.project_id, null, pc.master_org_id, t.term, 'company_and_place', 2
    from {{ ref('data_center_project_company') }} as pc
    inner join {{ ref('mdm_organization_data_center') }} as c on c.master_org_id = pc.master_org_id
    cross join lateral unnest(array_append(c.aliases, c.company_name)) as t(term)
    where pc.confidence = 'stated' and length(t.term) >= 3
),

project_places as (
    select project_id, jurisdiction_id from {{ ref('data_center_project_jurisdiction') }}
),

-- How many projects a company has in one government. A company named in a record from a
-- government where it has two or more projects (Colossus 1 and 2 in Memphis) can't say
-- which one, so that match is skipped.
company_place_projects as (
    select pc.master_org_id, pp.jurisdiction_id, count(distinct pc.project_id) as n_projects
    from {{ ref('data_center_project_company') }} as pc
    inner join project_places as pp on pp.project_id = pc.project_id
    where pc.confidence = 'stated'
    group by 1, 2
),

decisions as (
    select d.event_decision_id, d.state_code, j.jurisdiction_id,
           coalesce(d.headline, '') || ' — ' || coalesce(d.decision_statement, '') as body
    from (
        select distinct on (event_decision_id) event_decision_id, state_code, headline, decision_statement
        from {{ ref('event_decision') }}
        order by event_decision_id, extracted_at desc
    ) as d
    left join {{ ref('int_event_decision__jurisdiction') }} as j on j.event_decision_id = d.event_decision_id
    where coalesce(d.headline, '') || ' ' || coalesce(d.decision_statement, '') ~* '{{ dc_regex }}'
),

passages as (
    select m.data_center_meeting_mention_id, m.state_code, m.jurisdiction_id, p.passage_text as body
    from {{ ref('data_center_meeting_mention') }} as m
    inner join {{ ref('int_data_center_transcript__passage') }} as p
        on p.video_id = m.video_id and p.passage_index = m.passage_index
),

hits as (
    select t.project_id, 'decision' as record_type, d.event_decision_id as record_id,
           d.event_decision_id, null::text as data_center_meeting_mention_id,
           t.basis, t.basis_rank, t.term, d.body, false as ci
    from decisions as d
    inner join project_terms as t
        on d.body ~ {{ phrase_regex('t.term') }}
       and (
            (t.basis = 'project_name' and t.state_code = d.state_code)
         or (t.basis = 'company_and_place' and exists (
                select 1 from project_places as pp
                where pp.project_id = t.project_id and pp.jurisdiction_id = d.jurisdiction_id)
             and (select cp.n_projects from company_place_projects as cp
                  where cp.master_org_id = t.master_org_id and cp.jurisdiction_id = d.jurisdiction_id) = 1
             -- a web address ("google.com", "google dot com") is not the company acting
             and d.body !~* ({{ regex_escape('t.term') }} || '(\s*\.\s*|\s+dot\s+|\s+)com\M'))
       )
    union all
    select t.project_id, 'meeting_passage', p.data_center_meeting_mention_id,
           null, p.data_center_meeting_mention_id,
           t.basis, t.basis_rank, t.term, p.body, true
    from passages as p
    inner join project_terms as t
        on p.body ~* {{ phrase_regex('t.term') }}
       and (
            (t.basis = 'project_name' and t.state_code = p.state_code)
         or (t.basis = 'company_and_place' and exists (
                select 1 from project_places as pp
                where pp.project_id = t.project_id and pp.jurisdiction_id = p.jurisdiction_id)
             and (select cp.n_projects from company_place_projects as cp
                  where cp.master_org_id = t.master_org_id and cp.jurisdiction_id = p.jurisdiction_id) = 1
             -- a web address ("google.com", "google dot com") is not the company acting
             and p.body !~* ({{ regex_escape('t.term') }} || '(\s*\.\s*|\s+dot\s+|\s+)com\M'))
       )
),

best as (
    select distinct on (project_id, record_type, record_id) *
    from hits
    order by project_id, record_type, record_id, basis_rank, length(term) desc, term
),

marked as (
    select
        b.*,
        case when b.ci
             then regexp_replace(b.body, {{ phrase_regex('b.term') }}, '\1<mark>\2</mark>\3', 'i')
             else regexp_replace(b.body, {{ phrase_regex('b.term') }}, '\1<mark>\2</mark>\3')
        end as marked_body
    from best as b
)

select
    md5(m.project_id || '|' || m.record_type || '|' || m.record_id)::text as project_mention_id,
    m.project_id::text                                                    as project_id,
    m.record_type::text                                                   as record_type,
    m.record_id::text                                                     as record_id,
    m.event_decision_id::text                                             as event_decision_id,
    m.data_center_meeting_mention_id::text                                as data_center_meeting_mention_id,
    m.basis::text                                                         as match_basis,
    m.term::text                                                          as matched_term,
    (
        case when w.s > 1 then '… ' else '' end
        || substr(m.marked_body, w.s, w.e - w.s)
        || case when w.e <= length(m.marked_body) then ' …' else '' end
    )::text                                                               as evidence
from marked as m
cross join lateral (
    select
        greatest(1, strpos(m.marked_body, '<mark>') - 120) as s,
        strpos(m.marked_body, '</mark>') + 7 + 120 as e
) as w
