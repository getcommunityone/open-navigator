/*
public.recent_transcribed_meeting — recent meetings that have a transcript but no AI
analysis yet (#509). Feeds the homepage "What's New" rail through
GET /api/meetings?sort=recent, next to the analyzed meetings in meeting_browse.

WHY: event_meeting / meeting_browse hold only AI-analyzed meetings, and analysis
stopped in early June 2026, so "What's New" froze there while hundreds of newer
meetings were transcribed. These rows are shown honestly as "Not yet analyzed":
title, date, place and video only. No decisions, outcomes or counts exist for them,
so none are carried here.

INCLUSION:
  * a transcript in event_documents (document_type = 'transcript');
  * the video passes the junk-channel gate: it must be in
    event_youtube_with_jurisdiction, which drops channels classified as junk or
    non-government;
  * its title names a public meeting (meeting_title_regex: council, board,
    commission, committee, hearing...), so a government channel's promos and
    ceremonies aren't shown as meetings;
  * NOT analyzed: its video_id is not in event_meeting. Once a meeting is analyzed
    it leaves this table on the next build, and the API also hides any video that
    meeting_browse already serves, so it switches to its analyzed card at once;
  * recent: meeting_date in the last 180 days and not later than today (#472, at
    build time; the API re-checks against today at request time).

EVIDENCE: when the transcript matches a curated topic or question, the row carries
that link's stored passage verbatim (topic_transcript_link.evidence_passage, else
question_transcript_link.evidence, the most specific match first). Both are cut in
dbt from the full local transcript with <mark> around the matched words, so this
model never reads event_documents.content and nothing needs transcript text at
request time (production Neon has none, #496). No match => evidence is null.

GRAIN: one row per video_id.
PK   : video_id.
FK   : jurisdiction_id -> jurisdictions (null when the id doesn't resolve there).

SOURCE : event_documents, event_youtube_with_jurisdiction, event_meeting,
         topic_transcript_link, civicsearch_topic, question_transcript_link,
         policy_question, jurisdictions.
TARGET : public.recent_transcribed_meeting (served via publish_public_serving).
*/

with

-- One transcript per video: the longest, the same canonical pick the link marts use.
transcript as (
    select distinct on (d.video_id)
        d.video_id,
        nullif(trim(d.event_title), '') as event_title,
        d.event_date,
        nullif(trim(d.video_url), '')   as video_url,
        nullif(trim(d.city), '')        as city
    from {{ ref('event_documents') }} d
    where d.document_type = 'transcript'
      and d.video_id is not null
      and d.event_date >  current_date - 180
      and d.event_date <= current_date
    order by d.video_id, d.content_length desc nulls last
),

analyzed as (
    select distinct video_id
    from {{ ref('event_meeting') }}
    where video_id is not null
),

-- Junk-channel gate + resolved place.
video as (
    select
        y.video_id::text                             as video_id,
        nullif(trim(y.title), '')                    as title,
        nullif(trim(y.video_url), '')                as video_url,
        nullif(trim(y.jurisdiction_id), '')          as jurisdiction_id,
        nullif(trim(y.jurisdiction_name), '')        as jurisdiction_name,
        nullif(trim(y.city), '')                     as city,
        nullif(trim(y.state_code), '')               as state_code,
        nullif(trim(y.state), '')                    as state
    from {{ ref('event_youtube_with_jurisdiction') }} y
    where y.video_id in (select video_id from transcript)
),

-- Candidate evidence passages, best first: a curated topic (the most keyword hits),
-- then a curated question (the most alias hits). Only <mark>ed passages count.
evidence_candidate as (
    select
        l.video_id,
        l.evidence_passage           as evidence,
        'topic'::text                as evidence_source,
        t.name                       as evidence_label,
        null::numeric                as evidence_start_seconds,
        1                            as source_rank,
        l.n_keyword_hits             as hits
    from {{ ref('topic_transcript_link') }} l
    join {{ ref('civicsearch_topic') }} t on t.topic_id = l.topic_id
    where l.evidence_passage like '%<mark>%'
      and l.video_id in (select video_id from transcript)

    union all

    select
        q.video_id,
        q.evidence,
        'question'::text,
        p.canonical_text,
        q.start_seconds,
        2,
        q.n_alias_hits
    from {{ ref('question_transcript_link') }} q
    join {{ ref('policy_question') }} p on p.question_id = q.question_id
    where q.evidence like '%<mark>%'
      and q.video_id in (select video_id from transcript)
),

evidence as (
    select distinct on (video_id) *
    from evidence_candidate
    order by video_id, source_rank, hits desc nulls last, evidence_label
),

known_jurisdictions as (
    select jurisdiction_id, name as jurisdiction_name
    from {{ ref('jurisdictions') }}
)

select
    t.video_id::text                                                        as video_id,
    coalesce(t.event_title, v.title)::text                                  as meeting_title,
    t.event_date::date                                                      as meeting_date,
    j.jurisdiction_id::text                                                 as jurisdiction_id,
    coalesce(v.jurisdiction_name, j.jurisdiction_name)::text                as jurisdiction_name,
    coalesce(v.city, t.city)::text                                          as city,
    v.state_code::text                                                      as state_code,
    coalesce(
        v.state,
        case when v.state_code is not null then {{ state_code_to_name('v.state_code') }} end
    )::text                                                                 as state,
    coalesce(t.video_url, v.video_url, 'https://www.youtube.com/watch?v=' || t.video_id)::text as video_url,
    e.evidence::text                                                        as evidence,
    e.evidence_source::text                                                 as evidence_source,
    e.evidence_label::text                                                  as evidence_label,
    e.evidence_start_seconds::numeric(12, 3)                                as evidence_start_seconds
from transcript t
join video v
    on v.video_id = t.video_id
left join known_jurisdictions j
    on j.jurisdiction_id = v.jurisdiction_id
left join evidence e
    on e.video_id = t.video_id
where t.video_id not in (select video_id from analyzed)
  and coalesce(t.event_title, v.title) ~* '{{ meeting_title_regex() }}'
