{{ config(
    post_hook=["analyze {{ this }}"],
    materialized='table',
    tags=['marts', 'serving', 'trending_terms'],
    contract={'enforced': true},
    indexes=[{'columns': ['term_key', 'meeting_date']}, {'columns': ['term_key', 'state_code']}],
    pre_hook=["set local work_mem = '64MB'", "set local statement_timeout = '60min'"]
) }}

/*
    The evidence behind each served trending term (#1399, CLAUDE.md "show the match evidence"): one row per
    (term_key, video_id), a verbatim excerpt of a meeting that says the term, with the term marked by ts_headline
    (<mark>...</mark>), for the terms in the top var trending_evidence_rank (20) of any sort in a scope: each
    government's newest counted meeting that says the term, for the newest
    var trending_evidence_national (5) governments nationally and the newest var trending_evidence_state (1) per state
    where the term is served in that state. One meeting per government keeps one place from filling the list.

    Excerpt source, in order:
      1. a public-comment segment of that meeting that says the term (int_meeting_comment__flags: is_public_comment,
         never a possible minor): the speaker is the segment's own "First L." (meeting_comment.speaker_display_name),
         or null when unknown. start_seconds is where it starts in the recording.
      2. otherwise the transcript (event_documents.content): speaker null ("not identified").
    Privacy: for a sensitive term (health, religion, immigration ... see trending_term_sensitive) the speaker is always
    null, so the term is never tied to a person. A self-introduction ("my name is Jane Doe") inside an excerpt is
    replaced by "my name is [name]". School-board meetings are not counted, so never quoted. A meeting where a possible
    minor's own segment says the term is never quoted for that term, and a row whose excerpt has no <mark> is dropped.
*/

{%- set n_nat = var('trending_evidence_national', 5) %}
{%- set n_st = var('trending_evidence_state', 1) %}
{%- set hl = "StartSel=<mark>, StopSel=</mark>, MaxWords=22, MinWords=10, ShortWord=2, MaxFragments=1, HighlightAll=false" %}
{%- set redact = "regexp_replace({}, '(my name is|my name''s|name is)\\s+[A-Za-z''-]+(\\s+[A-Za-z''-]+)?', '\\1 [name]', 'gi')" %}

-- The terms a page can show: in the top var trending_evidence_rank (20) of any sort in the scope.
with served as materialized (
    select distinct term_key, scope_code
    from {{ ref('trending_term') }}
    where is_served
      and least(coalesce(rank_rising, 1000000), coalesce(rank_hot, 1000000), coalesce(rank_volume, 1000000))
          <= {{ var('trending_evidence_rank', 20) }}
),

term as (
    select c.term_key, c.term, c.term_tsquery::tsquery as q, c.is_sensitive
    from {{ ref('int_trending_term__candidate') }} as c
    where c.term_key in (select term_key from served)
),

-- Each government's newest meeting that says the term is already known from the counting step
-- (int_trending_term__jurisdiction_year.latest_meeting_date), so no transcript is searched blindly here.
gov as materialized (
    select jy.term_key, jy.state_code, jy.jurisdiction_key, max(jy.latest_meeting_date) as latest
    from {{ ref('int_trending_term__jurisdiction_year') }} as jy
    where jy.term_key in (select term_key from served)
    group by jy.term_key, jy.state_code, jy.jurisdiction_key
),

gov_ranked as (
    select g.*,
           row_number() over (partition by g.term_key order by g.latest desc, g.jurisdiction_key) as rn_nat,
           row_number() over (partition by g.term_key, g.state_code order by g.latest desc, g.jurisdiction_key) as rn_state
    from gov as g
),

gov_picked as materialized (
    select g.*
    from gov_ranked as g
    left join served as s on s.term_key = g.term_key and s.scope_code = g.state_code
    where g.rn_nat <= {{ n_nat }} or (g.rn_state <= {{ n_st }} and s.term_key is not null)
),

doc as materialized (
    select distinct on (d.video_id) d.video_id, d.content_tsv, d.event_document_id
    from {{ ref('event_documents') }} as d
    where d.document_type = 'transcript' and d.content_tsv is not null
      and d.video_id in (
          select m.video_id from {{ ref('int_trending_term__meeting') }} as m
          inner join gov_picked as g on g.jurisdiction_key = m.jurisdiction_key and g.latest = m.meeting_date
          where m.counted)
    order by d.video_id, d.content_length desc nulls last
),

-- That meeting (one per government; the same-day meeting that says it when there were several).
picked as materialized (
    select distinct on (g.term_key, g.jurisdiction_key)
        t.term_key, t.term, t.q, t.is_sensitive, m.video_id, m.meeting_date, m.state_code, m.jurisdiction_name,
        d.event_document_id
    from gov_picked as g
    inner join term as t on t.term_key = g.term_key
    inner join {{ ref('int_trending_term__meeting') }} as m
        on m.jurisdiction_key = g.jurisdiction_key and m.meeting_date = g.latest and m.counted
    inner join doc as d on d.video_id = m.video_id
    where d.content_tsv @@ t.q
    order by g.term_key, g.jurisdiction_key, m.video_id
),

-- Meetings where a possible minor's own segment says the term: never quoted for that term, not even from the
-- transcript (the window could be the minor's words).
minor_hit as materialized (
    select distinct p.term_key, p.video_id
    from picked as p
    inner join {{ ref('int_meeting_comment__flags') }} as f on f.video_id = p.video_id and f.possible_minor
    where to_tsvector('english', f.comment_text) @@ p.q
),

seg_tsv as materialized (
    select f.video_id, f.comment_index, f.comment_segment_id, f.comment_text, f.start_seconds,
           to_tsvector('english', f.comment_text) as tsv
    from {{ ref('int_meeting_comment__flags') }} as f
    where f.is_public_comment and not f.possible_minor
      and f.video_id in (select video_id from picked)
),

seg as (
    select distinct on (p.term_key, p.video_id)
        p.term_key, p.video_id, f.comment_segment_id, f.comment_text, f.start_seconds
    from picked as p
    inner join seg_tsv as f on f.video_id = p.video_id
    where f.tsv @@ p.q
    order by p.term_key, p.video_id, f.comment_index
)

select * from (
select
    md5(p.term_key || '|' || p.video_id)::text                                        as trending_term_evidence_id,
    p.term_key::text                                                                  as term_key,
    md5('US|' || p.term_key)::text                                                    as national_trending_term_id,
    p.video_id::text                                                                  as video_id,
    p.meeting_date::date                                                              as meeting_date,
    p.state_code::text                                                                as state_code,
    p.jurisdiction_name::text                                                         as jurisdiction_name,
    coalesce(ed.event_title, '')::text                                                as meeting_title,
    ed.video_url::text                                                                as video_url,
    (case when s.comment_segment_id is not null
          then ts_headline('english', {{ redact.replace('{}', 's.comment_text') }}, p.q, '{{ hl }}')
          else ts_headline('english', {{ redact.replace('{}', 'win.txt') }}, p.q, '{{ hl }}')
     end)::text                                                                       as excerpt,
    (case when s.comment_segment_id is not null then 'public_comment' else 'transcript' end)::text as excerpt_source,
    s.start_seconds::numeric(12, 3)                                                   as start_seconds,
    (case when not p.is_sensitive then mc.speaker_display_name end)::text             as speaker_display_name
from picked as p
inner join {{ ref('event_documents') }} as ed on ed.event_document_id = p.event_document_id
left join seg as s on s.term_key = p.term_key and s.video_id = p.video_id
-- ts_headline parses the whole text it is given, so a transcript excerpt is cut from a 2,000-character window around
-- the first place the term's display form appears as whole words (the whole transcript when that exact form isn't
-- found). Terms are lower-case letters, spaces and apostrophes only, so they are safe inside the regex.
cross join lateral (
    select case
        when s.comment_segment_id is not null then null
        when regexp_instr(ed.content, '\m' || p.term || '\M', 1, 1, 0, 'i') > 0
            then substr(ed.content, greatest(1, regexp_instr(ed.content, '\m' || p.term || '\M', 1, 1, 0, 'i') - 800), 2000)
        else ed.content
    end as txt
) as win
left join {{ ref('meeting_comment') }} as mc on mc.meeting_comment_id = s.comment_segment_id
where not exists (select 1 from minor_hit mh where mh.term_key = p.term_key and mh.video_id = p.video_id)
) as ev
-- A row is evidence only when the excerpt really marks the term.
where ev.excerpt like '%<mark>%'
