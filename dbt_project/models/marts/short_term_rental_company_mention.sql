{{ config(materialized='table', tags=['marts', 'short_term_rentals', 'serving']) }}

/*
    Where a short-term rental platform is named (#1015). Grain: one row per (company, meeting video) whose
    transcript names it, and one row per (company, decision) whose record names it. A company is matched on its
    match_terms (mdm_organization_short_term_rental): Airbnb on "airbnb", Expedia Group on "vrbo" / "homeaway",
    Booking Holdings on "booking.com"; English full-text, the same tsvector the transcript and decision search use.

    evidence is a verbatim ts_headline of the matched record with the terms in <mark> (the match-evidence rule):
    the transcript for a meeting, the headline + statement for a decision. Nothing is inferred beyond the words.
*/

with companies as (
    select
        master_org_id,
        company_key,
        company_name,
        to_tsquery('english', array_to_string(match_terms, ' | '))  as q
    from {{ ref('mdm_organization_short_term_rental') }}
),

meeting_hits as (
    select distinct on (c.company_key, d.video_id)
        c.master_org_id,
        c.company_key,
        c.company_name,
        'meeting'::text                                         as mention_kind,
        d.video_id::text                                        as video_id,
        null::text                                              as event_decision_id,
        d.event_title::text                                     as title,
        d.event_date::date                                      as event_date,
        d.jurisdiction_name::text                               as jurisdiction_name,
        d.state_code::text                                      as state_code,
        d.state::text                                           as state,
        coalesce(d.video_url, 'https://www.youtube.com/watch?v=' || d.video_id)::text as url,
        ts_headline(
            'english', d.content, c.q,
            'MaxFragments=2, MinWords=8, MaxWords=30, StartSel=<mark>, StopSel=</mark>'
        )::text                                                 as evidence
    from companies as c
    inner join {{ ref('event_documents') }} as d
        on to_tsvector('english', d.content) @@ c.q
    where d.video_id is not null
    order by c.company_key, d.video_id, d.event_document_id
),

decision_hits as (
    select
        c.master_org_id,
        c.company_key,
        c.company_name,
        'decision'::text                                        as mention_kind,
        m.video_id::text                                        as video_id,
        e.event_decision_id::text                               as event_decision_id,
        e.headline::text                                        as title,
        case when m.meeting_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' then left(m.meeting_date, 10)::date end as event_date,
        e.jurisdiction_name::text                               as jurisdiction_name,
        e.state_code::text                                      as state_code,
        e.state::text                                           as state,
        ('/decisions/' || e.event_decision_id)::text            as url,
        ts_headline(
            'english', coalesce(e.headline, '') || '. ' || coalesce(e.decision_statement, ''), c.q,
            'MaxFragments=2, MinWords=8, MaxWords=30, StartSel=<mark>, StopSel=</mark>'
        )::text                                                 as evidence
    from companies as c
    inner join {{ ref('event_decision') }} as e
        on e.search_tsv @@ c.q
    left join lateral (
        select em.video_id, em.meeting_date
        from {{ ref('event_meeting') }} as em
        where em.c1_event_id = e.c1_event_id
        order by em.event_meeting_id
        limit 1
    ) as m on true
),

unioned as (
    select * from meeting_hits
    union all
    select * from decision_hits
)

select
    md5(company_key || '|' || mention_kind || '|' || coalesce(event_decision_id, video_id))::text as mention_id,
    master_org_id,
    company_key,
    company_name,
    mention_kind,
    video_id,
    event_decision_id,
    title,
    event_date,
    jurisdiction_name,
    state_code,
    state,
    url,
    evidence
from unioned
