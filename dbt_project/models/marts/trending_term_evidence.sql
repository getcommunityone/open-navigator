{{ config(
    materialized='table',
    tags=['marts', 'serving', 'trending_terms'],
    contract={'enforced': true},
    indexes=[{'columns': ['term_key', 'meeting_date']}, {'columns': ['term_key', 'state_code']}],
    pre_hook=["set local work_mem = '64MB'", "set local statement_timeout = '30min'"]
) }}

/*
    The evidence behind each served trending term (#1399, CLAUDE.md "show the match evidence"): one row per
    (term_key, video_id), a verbatim excerpt of a meeting that says the term, with the term marked by ts_headline
    (<mark>...</mark>), for the newest var trending_evidence_national (10) counted meetings nationally and the newest
    var trending_evidence_state (3) per state where the term is served in that state.

    Excerpt source, in order:
      1. a public-comment segment of that meeting that says the term (int_meeting_comment__flags: is_public_comment,
         never a possible minor): the speaker is the segment's own "First L." (meeting_comment.speaker_display_name),
         or null when unknown. start_seconds is where it starts in the recording.
      2. otherwise the transcript (event_documents.content): speaker null ("not identified").
    Privacy: for a sensitive term (health, religion, immigration ... see trending_term_sensitive) the speaker is always
    null, so the term is never tied to a person. A self-introduction ("my name is Jane Doe") inside an excerpt is
    replaced by "my name is [name]". School-board meetings are not counted, so never quoted.
*/

{%- set n_nat = var('trending_evidence_national', 10) %}
{%- set n_st = var('trending_evidence_state', 3) %}
{%- set hl = "StartSel=<mark>, StopSel=</mark>, MaxWords=30, MinWords=14, ShortWord=2, MaxFragments=1, HighlightAll=false" %}
{%- set redact = "regexp_replace({}, '(my name is|my name''s|name is)\\s+[A-Za-z''-]+(\\s+[A-Za-z''-]+)?', '\\1 [name]', 'gi')" %}

with served as (
    select distinct term_key, scope_code from {{ ref('trending_term') }} where is_served
),

term as (
    select c.term_key, c.term_tsquery::tsquery as q, c.is_sensitive
    from {{ ref('int_trending_term__candidate') }} as c
    where c.term_key in (select term_key from served)
),

doc as (
    select distinct on (d.video_id) d.video_id, d.content_tsv, d.event_document_id
    from {{ ref('event_documents') }} as d
    inner join {{ ref('int_trending_term__meeting') }} as m on m.video_id = d.video_id and m.counted
    where d.document_type = 'transcript' and d.content_tsv is not null
    order by d.video_id, d.content_length desc nulls last
),

hit as (
    select t.term_key, t.q, t.is_sensitive, m.video_id, m.meeting_date, m.state_code, m.jurisdiction_name,
           d.event_document_id,
           row_number() over (partition by t.term_key order by m.meeting_date desc, m.video_id) as rn_nat,
           row_number() over (partition by t.term_key, m.state_code order by m.meeting_date desc, m.video_id) as rn_state
    from doc as d
    inner join {{ ref('int_trending_term__meeting') }} as m on m.video_id = d.video_id
    inner join term as t on d.content_tsv @@ t.q
),

picked as (
    select h.*
    from hit as h
    where h.rn_nat <= {{ n_nat }}
       or (h.rn_state <= {{ n_st }} and exists (
              select 1 from served as s where s.term_key = h.term_key and s.scope_code = h.state_code))
),

seg as (
    select distinct on (p.term_key, p.video_id)
        p.term_key, p.video_id, f.comment_segment_id, f.comment_text, f.start_seconds
    from picked as p
    inner join {{ ref('int_meeting_comment__flags') }} as f on f.video_id = p.video_id
    where f.is_public_comment and not f.possible_minor
      and to_tsvector('english', f.comment_text) @@ p.q
    order by p.term_key, p.video_id, f.comment_index
)

select
    md5(p.term_key || '|' || p.video_id)::text                                        as trending_term_evidence_id,
    p.term_key::text                                                                  as term_key,
    p.video_id::text                                                                  as video_id,
    p.meeting_date::date                                                              as meeting_date,
    p.state_code::text                                                                as state_code,
    p.jurisdiction_name::text                                                         as jurisdiction_name,
    coalesce(ed.event_title, '')::text                                                as meeting_title,
    ed.video_url::text                                                                as video_url,
    (case when s.comment_segment_id is not null
          then ts_headline('english', {{ redact.replace('{}', 's.comment_text') }}, p.q, '{{ hl }}')
          else ts_headline('english', {{ redact.replace('{}', 'ed.content') }}, p.q, '{{ hl }}')
     end)::text                                                                       as excerpt,
    (case when s.comment_segment_id is not null then 'public_comment' else 'transcript' end)::text as excerpt_source,
    s.start_seconds::numeric(12, 3)                                                   as start_seconds,
    (case when not p.is_sensitive then mc.speaker_display_name end)::text             as speaker_display_name
from picked as p
inner join {{ ref('event_documents') }} as ed on ed.event_document_id = p.event_document_id
left join seg as s on s.term_key = p.term_key and s.video_id = p.video_id
left join {{ ref('meeting_comment') }} as mc on mc.meeting_comment_id = s.comment_segment_id
