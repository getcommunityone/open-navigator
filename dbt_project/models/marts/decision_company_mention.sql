{{ config(materialized='table', tags=['marts', 'event-extraction', 'data_centers', 'serving']) }}

/*
    Data center companies a decision's own text names (#508). Grain: one row per
    (event_decision_id, operator_name).

    Scope: decisions whose headline or decision_statement says "data center" (the shared
    data_center_regex), the latest extraction of each.

    Names come from two lists, both matched deterministically (no LLM):
      seed     data_center_operators: real operators and developers with the aliases that
               name them unambiguously. Brand names that are also ordinary words (Switch,
               Stack, Compass, Aligned, Vantage, Meta, Oracle, Tract) are listed only in a
               company form ("Switch, Inc.", "Stack Infrastructure", "Compass Datacenters",
               "Meta Platforms", "Meta's", "Oracle Cloud"), never as the bare word.
      epoch    the owner, users and project names on data_center_site (Epoch AI), with the
               "(likely)" / "(speculative)" tag removed and lists split on commas. A project
               name counts only for a decision in the site's state and is credited to the
               site's owner. An Epoch name that is a seed operator or one of its aliases is
               skipped, so the seed's company-form rule governs it (bare "Meta" never
               matches). Names shorter than 4 characters are skipped.
    Matching is case-sensitive, on a whole word or phrase (phrase_regex): "switch" or
    "stack" in ordinary lower-case text never match, nor does "AWS" inside "LAWS".
    matched_text is the exact text matched; evidence is a verbatim excerpt of the field it
    came from with the match in <mark>. The headline wins over the statement when both
    name the company.
    master_org_id (#531) is the company's organization master row: the operator_name, or
    the term that matched, equals (case-insensitively) a company name or alias in
    mdm_organization_data_center. Null when no curated company carries that name.
*/

{%- set dc_regex = data_center_regex() %}

with decisions as (
    select event_decision_id, headline, decision_statement, state_code
    from (
        select distinct on (event_decision_id)
            event_decision_id, headline, decision_statement, state_code
        from {{ ref('event_decision') }}
        order by event_decision_id, extracted_at desc
    ) as d
    where coalesce(headline, '') || ' ' || coalesce(decision_statement, '') ~* '{{ dc_regex }}'
),

texts as (
    select event_decision_id, state_code, 'headline' as text_field, 1 as field_rank, headline as body
    from decisions where nullif(btrim(headline), '') is not null
    union all
    select event_decision_id, state_code, 'decision_statement', 2, decision_statement
    from decisions where nullif(btrim(decision_statement), '') is not null
),

seed_terms as (
    select
        btrim(o.operator_name) as operator_name,
        btrim(a.alias)         as term,
        null::text             as term_state_code,
        'seed'::text           as term_source
    from {{ ref('data_center_operators') }} as o
    cross join lateral unnest(string_to_array(o.aliases, '|')) as a(alias)
    where nullif(btrim(a.alias), '') is not null
),

seed_names as (
    select lower(operator_name) as name from seed_terms
    union
    select lower(term) from seed_terms
),

epoch_raw as (
    select btrim(regexp_replace(n.name, '\s*\((likely|speculative)\)\s*$', '', 'i')) as name,
           null::text as project_state_code, null::text as project_owner
    from {{ ref('data_center_site') }} as s
    cross join lateral unnest(
        string_to_array(coalesce(s.owner, ''), ',') || string_to_array(coalesce(s.users, ''), ',')
    ) as n(name)
    union all
    select btrim(regexp_replace(s.project, '\s*\((likely|speculative)\)\s*$', '', 'i')),
           s.state_code,
           nullif(btrim(regexp_replace(s.owner, '\s*\((likely|speculative)\)\s*$', '', 'i')), '')
    from {{ ref('data_center_site') }} as s
    where nullif(btrim(s.project), '') is not null and s.state_code is not null
),

epoch_terms as (
    select distinct
        coalesce(project_owner, name) as operator_name,
        name                          as term,
        project_state_code            as term_state_code,
        'epoch'::text                 as term_source
    from epoch_raw
    where length(name) >= 4
      and lower(name) not in (select name from seed_names)
      and (project_state_code is null or project_owner is not null)
),

terms as (
    select * from seed_terms
    union all
    select * from epoch_terms
),

hits as (
    select
        t.event_decision_id,
        t.text_field,
        t.field_rank,
        t.body,
        m.operator_name,
        m.term,
        m.term_source,
        (regexp_match(t.body, {{ phrase_regex('m.term') }}))[2] as matched_text
    from texts as t
    inner join terms as m
        on t.body ~ {{ phrase_regex('m.term') }}
       and (m.term_state_code is null or m.term_state_code = t.state_code)
),

best as (
    select distinct on (event_decision_id, operator_name) *
    from hits
    order by event_decision_id, operator_name, field_rank, length(term) desc, term
),

marked as (
    select
        b.*,
        regexp_replace(b.body, {{ phrase_regex('b.term') }}, '\1<mark>\2</mark>\3') as marked_body
    from best as b
),

company_names as (
    select master_org_id, lower(company_name) as name, 1 as name_rank from {{ ref('mdm_organization_data_center') }}
    union
    select master_org_id, lower(a), 2
    from {{ ref('mdm_organization_data_center') }} cross join lateral unnest(aliases) as a
)

select
    md5(m.event_decision_id || '|' || m.operator_name)::text     as decision_company_mention_id,
    m.event_decision_id::text                                     as event_decision_id,
    m.operator_name::text                                         as operator_name,
    m.matched_text::text                                          as matched_text,
    m.term_source::text                                           as term_source,
    m.text_field::text                                            as text_field,
    (
        case when w.s > 1 then '… ' else '' end
        || substr(m.marked_body, w.s, w.e - w.s)
        || case when w.e <= length(m.marked_body) then ' …' else '' end
    )::text                                                       as evidence,
    (
        select n.master_org_id from company_names as n
        where n.name in (lower(m.operator_name), lower(m.term))
        order by (n.name = lower(m.operator_name)) desc, n.name_rank, n.master_org_id
        limit 1
    )::text                                                       as master_org_id
from marked as m
-- an ~80-character window either side of the <mark>ed match
cross join lateral (
    select
        greatest(1, strpos(m.marked_body, '<mark>') - 80) as s,
        strpos(m.marked_body, '<mark>') + length(m.matched_text) + 13 + 80 as e
) as w
