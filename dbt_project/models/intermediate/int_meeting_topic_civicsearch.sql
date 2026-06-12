{{
    config(
        materialized='table',
        tags=['intermediate', 'civic', 'meeting-browse', 'topic']
    )
}}

/*
int_meeting_topic_civicsearch — full-text match of CivicSearch topics against
meeting transcripts.

GRAIN: one row per (event_meeting_id, topic_id) where the meeting's transcript
full-text-matches the topic's keyword set.

WHY: the stored CivicSearch *tag* join (civicsearch snippet -> meeting) is sparse
(~54 meetings). This model instead does a TRUE full-text match: it ORs each
topic's keyword_stats[] keyword set into one tsquery and tests it against the
meeting transcript's content_tsv (the existing gold.event_documents GIN index is
reused — to_tsquery @@ tsvector hits event_documents_content_tsv_idx).

INJECTION SAFETY: the tsquery is built with plainto_tsquery('english', <keyword>)
per keyword (which fully sanitizes free text and turns multi-word phrases into
'&'-joined lexemes), then those sanitized fragments are ORed together with ' | '.
No raw keyword text ever becomes a tsquery operator, so this is injection-safe.

SOURCE : event_documents (transcript, content_tsv), event_meeting, civicsearch_topic
TARGET : gold.int_meeting_topic_civicsearch (intermediate; consumed by
         meeting_topic_link).
*/

with topic_query as (
    -- One OR-tsquery per CivicSearch topic, built injection-safe from its
    -- keyword_stats[] vocabulary. Drop keywords that sanitize to empty
    -- (stop-words only) so they don't break to_tsquery.
    select
        t.topic_id,
        t.name as topic_name,
        to_tsquery(
            'english',
            string_agg(distinct nullif(plainto_tsquery('english', kw.elem)::text, ''), ' | ')
        ) as ts_query
    from {{ ref('civicsearch_topic') }} t
    cross join lateral jsonb_array_elements_text(t.keyword_stats) as kw(elem)
    group by t.topic_id, t.name
    -- only keep topics that produced a non-empty query
    having string_agg(distinct nullif(plainto_tsquery('english', kw.elem)::text, ''), ' | ') is not null
),

-- One transcript tsvector per meeting (a meeting maps to its video_id; collapse
-- any duplicate transcript docs for the same video_id to a single row so the
-- topic match is DISTINCT per meeting).
meeting_transcript as (
    select distinct on (m.event_meeting_id)
        m.event_meeting_id,
        d.content_tsv
    from {{ ref('event_meeting') }} m
    join {{ ref('event_documents') }} d
        on d.video_id = m.video_id
       and d.document_type = 'transcript'
    where m.video_id is not null
      and d.content_tsv is not null
    order by m.event_meeting_id, d.content_length desc nulls last
)

select
    mt.event_meeting_id,
    tq.topic_id,
    tq.topic_name
from meeting_transcript mt
join topic_query tq
    on mt.content_tsv @@ tq.ts_query
