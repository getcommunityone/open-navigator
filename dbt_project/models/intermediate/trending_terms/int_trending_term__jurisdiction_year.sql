{{ config(
    materialized='table',
    tags=['intermediate', 'trending_terms'],
    indexes=[{'columns': ['term_key']}, {'columns': ['state_code']}],
    pre_hook=["set local work_mem = '64MB'", "set local statement_timeout = '60min'"]
) }}

/*
    Meetings that said each kept candidate term (#1399), rolled up to one row per
    (term_key, state_code, jurisdiction_key, meeting_year). Read straight into the trending_term mart.

    Presence is read from the meeting's transcript full-text vector (event_documents.content_tsv, already built and
    GIN-indexed) for every counted meeting, with the stemmed phrase query of the term (term_tsquery, made by
    phraseto_tsquery, so no raw text becomes a query operator). Every meeting is read the same way: mixing turn text for
    some meetings with whole transcripts for others would move a term's share with turn coverage (1,297 meetings had
    turns in 2025, 2,875 in 2026), not with what people said. Only the rolled-up counts are stored, never a row per
    meeting and term.
*/

with doc as (
    select distinct on (d.video_id) d.video_id, d.content_tsv
    from {{ ref('event_documents') }} as d
    inner join {{ ref('int_trending_term__meeting') }} as m on m.video_id = d.video_id and m.counted
    where d.document_type = 'transcript' and d.content_tsv is not null
    order by d.video_id, d.content_length desc nulls last
),

cand as (
    select term_key, term_tsquery::tsquery as q
    from {{ ref('int_trending_term__candidate') }}
    where drop_reason is null
)

select
    c.term_key::text                    as term_key,
    m.state_code::text                  as state_code,
    m.jurisdiction_key::text            as jurisdiction_key,
    m.meeting_year::int                 as meeting_year,
    count(*)::int                       as meetings,
    max(m.meeting_date)::date           as latest_meeting_date
from doc as d
inner join {{ ref('int_trending_term__meeting') }} as m on m.video_id = d.video_id
inner join cand as c on d.content_tsv @@ c.q
group by c.term_key, m.state_code, m.jurisdiction_key, m.meeting_year
