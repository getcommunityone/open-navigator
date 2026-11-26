{{ config(materialized='table', tags=['marts', 'event-extraction', 'data_centers', 'serving']) }}

/*
    Data center companies named for a decision (#508, #525). Grain: one row per
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

    Two places a name can be found (evidence_source):
      decision_text    the decision's own headline or statement. Matching is case-sensitive,
                       on a whole word or phrase (phrase_regex): "switch" or "stack" in
                       ordinary lower-case text never match, nor does "AWS" inside "LAWS".
                       The headline wins over the statement when both name the company.
      meeting_passage  a transcript passage of the decision's own meeting (#525): the
                       decision's analysis -> event_meeting.video_id -> the passages in
                       data_center_meeting_mention (which say "data center"). A passage
                       counts only when
                         1. it is in the same meeting (same video_id);
                         2. it falls in the decision's discussion window when the analysis
                            gave one (media_anchor start and end seconds, overlapping the
                            passage's 3-minute window); a decision with no window uses the
                            whole meeting, and an untimed passage never passes a window;
                         3. the passage says the company is the applicant or developer next
                            to the name (cue_before_regex / cue_after_regex: "on behalf of
                            X", "teamed up with X", "the applicant is X", "X is a ...
                            developer"). A company named in passing is not a match.
                       Captions are mostly lower case, so passages match case-insensitively
                       and the cue is what keeps an ordinary word from matching. The seed's
                       meeting_aliases (a bare ordinary word such as "Powerhouse") are matched
                       only here. When a company is found in both places, decision_text wins.
    matched_text is the exact text matched; evidence is a verbatim excerpt of the text it
    came from with the match in <mark> (~80 characters either side for a decision, ~120
    for a passage so the cue is in the quote).
    start_seconds (passages only) is data_center_meeting_mention.start_seconds: the first
    data center cue of the passage's 3-minute window, the moment to jump to. It is not the
    exact second of the quote. Null for decision_text and for an untimed transcript.
    data_center_meeting_mention_id names the passage the quote came from.
    master_org_id (#531) is the company's organization master row: the operator_name, or
    the term that matched, equals (case-insensitively) a company name or alias in
    mdm_organization_data_center. Null when no curated company carries that name.
*/

{%- set dc_regex = data_center_regex() %}

with decisions as (
    select event_decision_id, analysis_id, decision_id, headline, decision_statement, state_code
    from (
        select distinct on (event_decision_id)
            event_decision_id, analysis_id, decision_id, headline, decision_statement, state_code
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

-- Bare forms that name a company only in a meeting passage, under a developer cue (#525).
meeting_terms as (
    select
        btrim(o.operator_name) as operator_name,
        btrim(a.alias)         as term,
        null::text             as term_state_code,
        'seed'::text           as term_source
    from {{ ref('data_center_operators') }} as o
    cross join lateral unnest(string_to_array(o.meeting_aliases, '|')) as a(alias)
    where nullif(btrim(a.alias), '') is not null
),

seed_names as (
    select lower(operator_name) as name from seed_terms
    union
    select lower(term) from seed_terms
    union
    select lower(term) from meeting_terms
),

epoch_raw as (
    select btrim(regexp_replace(n.name, '\s*\((likely|speculative)\)\s*$', '', 'i')) as name,
           null::text as project_state_code, null::text as project_owner
    from (select * from {{ ref('data_center_site') }} where source = 'epoch') as s
    cross join lateral unnest(
        string_to_array(coalesce(s.owner, ''), ',') || string_to_array(coalesce(s.users, ''), ',')
    ) as n(name)
    union all
    select btrim(regexp_replace(s.project, '\s*\((likely|speculative)\)\s*$', '', 'i')),
           s.state_code,
           nullif(btrim(regexp_replace(s.owner, '\s*\((likely|speculative)\)\s*$', '', 'i')), '')
    from (select * from {{ ref('data_center_site') }} where source = 'epoch') as s
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

-- The decision's own text: seed and Epoch terms, never the meeting-only forms.
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

text_rows as (
    select
        b.event_decision_id,
        b.operator_name,
        b.matched_text,
        b.term_source,
        b.text_field,
        'decision_text'::text                                                    as evidence_source,
        regexp_replace(b.body, {{ phrase_regex('b.term') }}, '\1<mark>\2</mark>\3') as marked_body,
        b.term,
        80                                                                       as radius,
        null::text                                                               as data_center_meeting_mention_id,
        null::numeric                                                            as start_seconds,
        0                                                                        as source_rank,
        b.field_rank                                                             as sort_rank
    from best as b
),

-- ── #525: the decision's own meeting ───────────────────────────────────────────────
-- A decision's meeting is its analysis (event_meeting_id = event_decision.analysis_id);
-- the recording is event_meeting.video_id.
decision_meetings as (
    select d.event_decision_id, d.state_code, d.analysis_id, d.decision_id, m.video_id
    from decisions as d
    inner join {{ ref('event_meeting') }} as m on m.event_meeting_id = d.analysis_id
    where nullif(btrim(m.video_id), '') is not null
),

-- The discussion window the analysis gave each decision (media_anchor), only when both
-- bounds are clean numbers and in order. No window -> the whole meeting is used.
anchor_raw as (
    select
        a.id                                                                          as analysis_id,
        x.decision ->> 'decision_id'                                                  as decision_id,
        {{ safe_nonnegative_double("x.decision -> 'media_anchor' ->> 'timestamp_start_seconds'") }} as window_start,
        {{ safe_nonnegative_double("x.decision -> 'media_anchor' ->> 'timestamp_end_seconds'") }}   as window_end
    from {{ source('bronze', 'bronze_events_analysis_ai') }} as a
    cross join lateral jsonb_array_elements(
        case when jsonb_typeof(a.structured_analysis -> 'decisions') = 'array'
             then a.structured_analysis -> 'decisions' else '[]'::jsonb end
    ) as x(decision)
    where a.id in (select analysis_id from decision_meetings)
),

-- A decision_id can repeat inside one analysis. Each bound is then taken across all of
-- its entries (earliest start, latest end), so no entry's window loses a passage and no
-- window is built from the start of one entry and the end of another.
windows as (
    select analysis_id, decision_id, min(window_start) as window_start, max(window_end) as window_end
    from anchor_raw
    where window_start is not null and window_end is not null and window_end >= window_start
    group by 1, 2
),

-- The passages of that recording that say "data center", with the passage's own words.
passages as (
    select
        mm.data_center_meeting_mention_id,
        mm.video_id,
        mm.passage_index,
        mm.start_seconds,
        p.passage_text as body
    from {{ ref('data_center_meeting_mention') }} as mm
    inner join {{ ref('int_data_center_transcript__passage') }} as p
        on p.video_id = mm.video_id and p.passage_index = mm.passage_index
    where mm.video_id in (select video_id from decision_meetings)
      and nullif(btrim(p.passage_text), '') is not null
),

-- A timed passage is the 3-minute window [passage_index * 180, +180); it must overlap the
-- decision's window. An untimed passage cannot be placed, so it never passes a window.
decision_passages as (
    select
        dm.event_decision_id,
        dm.state_code,
        p.data_center_meeting_mention_id,
        p.start_seconds,
        p.body
    from decision_meetings as dm
    inner join passages as p on p.video_id = dm.video_id
    left join windows as w on w.analysis_id = dm.analysis_id and w.decision_id = dm.decision_id
    where w.window_start is null
       or (p.start_seconds is not null
           and p.passage_index * 180 <= w.window_end
           and p.passage_index * 180 + 180 >= w.window_start)
),

passage_terms as (
    select * from terms
    union all
    select * from meeting_terms
),

cue_before_hits as (
    select
        dp.event_decision_id,
        dp.data_center_meeting_mention_id,
        dp.start_seconds,
        t.operator_name,
        t.term,
        t.term_source,
        (regexp_match(dp.body, {{ cue_before_regex('t.term') }}, 'i'))[3]                          as matched_text,
        regexp_replace(dp.body, {{ cue_before_regex('t.term') }}, '\1\2<mark>\3</mark>\4', 'i')    as marked_body
    from decision_passages as dp
    inner join passage_terms as t
        on dp.body ~* {{ cue_before_regex('t.term') }}
       and (t.term_state_code is null or t.term_state_code = dp.state_code)
),

cue_after_hits as (
    select
        dp.event_decision_id,
        dp.data_center_meeting_mention_id,
        dp.start_seconds,
        t.operator_name,
        t.term,
        t.term_source,
        (regexp_match(dp.body, {{ cue_after_regex('t.term') }}, 'i'))[2]                           as matched_text,
        regexp_replace(dp.body, {{ cue_after_regex('t.term') }}, '\1<mark>\2</mark>\3', 'i')       as marked_body
    from decision_passages as dp
    inner join passage_terms as t
        on dp.body ~* {{ cue_after_regex('t.term') }}
       and (t.term_state_code is null or t.term_state_code = dp.state_code)
),

passage_rows as (
    select
        h.event_decision_id,
        h.operator_name,
        h.matched_text,
        h.term_source,
        'meeting_passage'::text          as text_field,
        'meeting_passage'::text          as evidence_source,
        h.marked_body,
        h.term,
        120                              as radius,
        h.data_center_meeting_mention_id,
        h.start_seconds::numeric         as start_seconds,
        1                                as source_rank,
        1                                as sort_rank
    from (
        select * from cue_before_hits
        union all
        select * from cue_after_hits
    ) as h
),

-- One row per (decision, company): the decision's own text first, else the earliest
-- passage that names it.
chosen as (
    select distinct on (event_decision_id, operator_name) *
    from (
        select * from text_rows
        union all
        select * from passage_rows
    ) as r
    order by event_decision_id, operator_name, source_rank, sort_rank,
             start_seconds nulls last, length(term) desc, term, data_center_meeting_mention_id
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
    m.evidence_source::text                                       as evidence_source,
    m.start_seconds::numeric(12, 3)                               as start_seconds,
    m.data_center_meeting_mention_id::text                        as data_center_meeting_mention_id,
    (
        select n.master_org_id from company_names as n
        where n.name in (lower(m.operator_name), lower(m.term))
        order by (n.name = lower(m.operator_name)) desc, n.name_rank, n.master_org_id
        limit 1
    )::text                                                       as master_org_id
from chosen as m
-- an ~80 (decision) or ~120 (passage) character window either side of the <mark>ed match
cross join lateral (
    select
        greatest(1, strpos(m.marked_body, '<mark>') - m.radius) as s,
        strpos(m.marked_body, '</mark>') + 7 + m.radius as e
) as w
