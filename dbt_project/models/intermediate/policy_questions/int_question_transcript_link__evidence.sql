{{ config(materialized='table', tags=['intermediate', 'policy-questions', 'transcript', 'keyword-fts']) }}

/*
    Match evidence for each policy question <-> transcript match (#499).
    Grain: one row per (question_id, video_id) of int_question_transcript_link__match.

    evidence      verbatim transcript passage with the question's alias words marked by
                  ts_headline (<mark>…</mark>, MaxFragments=1, MaxWords=40, MinWords=15).
    start_seconds the moment to jump to; null when the transcript is untimed.

    Timed (caption segments): cues are cut into ~3-minute windows (floor(start / 180));
    the first window whose text matches the question's alias query is the passage, and
    start_seconds is the first cue in it (alone, or joined with the next cue so a phrase
    split across two cues counts) that matches, else the window's start.
    Untimed: ts_headline over the whole transcript text.

    Built in the local warehouse, where event_documents has the full text; production
    Neon's event_documents has none (#496), so the passage travels on
    question_transcript_link. NO LLM.
*/

with

scored as (
    select * from {{ ref('int_question_transcript_link__match') }}
),

valid as (
    select
        md5(primary_theme || '|' || canonical_text)                  as question_id,
        nullif(phraseto_tsquery('english', trim(a))::text, '')       as pq
    from {{ ref('curated_policy_questions') }},
         unnest(string_to_array(aliases, '|')) as a
    where trim(coalesce(a, '')) <> ''
),

-- One OR-tsquery per question over all its alias phrases: what ts_headline marks
-- and what picks the passage.
question_query as (
    select question_id, string_agg('(' || pq || ')', ' | ')::tsquery as q
    from valid
    where pq is not null
    group by question_id
),

-- The transcript text and caption cues of each linked video (same "longest
-- transcript wins" rule as `doc`).
linked_doc as (
    select distinct on (d.video_id)
        d.video_id,
        d.content,
        d.segments
    from {{ ref('event_documents') }} d
    where d.document_type = 'transcript'
      and d.video_id in (select video_id from scored)
      and d.content_tsv is not null
    order by d.video_id, d.content_length desc nulls last
),

cues as materialized (
    select
        ld.video_id,
        s.ord,
        (s.cue ->> 'start')::numeric                                   as start_s,
        floor((s.cue ->> 'start')::numeric / 180)::int                 as window_index,
        btrim(regexp_replace(coalesce(s.cue ->> 'text', ''), '\s+', ' ', 'g')) as cue_text
    from linked_doc ld
    cross join lateral jsonb_array_elements(ld.segments) with ordinality as s(cue, ord)
    where jsonb_typeof(ld.segments) = 'array'
      and (s.cue ->> 'start') ~ '^[0-9]+(\.[0-9]+)?$'
),

-- ~3-minute windows, each lexed ONCE (to_tsvector is the expensive step).
windows as materialized (
    select
        video_id,
        window_index,
        min(start_s)                                                    as window_start,
        string_agg(nullif(cue_text, ''), ' ' order by ord)              as passage_text
    from cues
    group by video_id, window_index
),

windows_tsv as materialized (
    select w.*, to_tsvector('english', coalesce(w.passage_text, '')) as tsv
    from windows w
),

-- First window per (question, video) whose own words match the alias query.
timed_pick as materialized (
    select distinct on (s.question_id, s.video_id)
        s.question_id,
        s.video_id,
        w.window_index,
        w.window_start,
        w.passage_text,
        qq.q
    from scored s
    join question_query qq on qq.question_id = s.question_id
    join windows_tsv w on w.video_id = s.video_id
    where w.tsv @@ qq.q
    order by s.question_id, s.video_id, w.window_index
),

-- The cues of the chosen windows only, each joined with the next cue so a phrase
-- split across two cues still counts.
picked_cues as (
    select
        t.question_id,
        t.video_id,
        t.q,
        c.start_s,
        c.cue_text || ' ' || coalesce(lead(c.cue_text) over (
            partition by t.question_id, t.video_id order by c.ord
        ), '')                                                          as cue_pair_text
    from timed_pick t
    join cues c
      on c.video_id = t.video_id
     and c.window_index = t.window_index
),

-- The first such cue that says an alias: the moment to jump to.
timed_start as (
    select question_id, video_id, min(start_s) as start_s
    from picked_cues
    where to_tsvector('english', cue_pair_text) @@ q
    group by question_id, video_id
),

timed as (
    select
        t.question_id,
        t.video_id,
        coalesce(ts.start_s, t.window_start)                            as start_seconds,
        ts_headline('english', t.passage_text, t.q,
            'StartSel=<mark>, StopSel=</mark>, MaxFragments=1, MaxWords=40, MinWords=15')
                                                                        as evidence
    from timed_pick t
    left join timed_start ts
      on ts.question_id = t.question_id
     and ts.video_id = t.video_id
),

-- No timed window matched (no segments, or the match is only in the text): the
-- whole transcript text, with no jump time.
untimed as (
    select
        s.question_id,
        s.video_id,
        null::numeric                                                   as start_seconds,
        ts_headline('english', ld.content, qq.q,
            'StartSel=<mark>, StopSel=</mark>, MaxFragments=1, MaxWords=40, MinWords=15')
                                                                        as evidence
    from scored s
    join question_query qq on qq.question_id = s.question_id
    join linked_doc ld on ld.video_id = s.video_id
    where ld.content is not null
      and not exists (
          select 1 from timed t
          where t.question_id = s.question_id and t.video_id = s.video_id
      )
),

evidence as (
    select * from timed
    union all
    select * from untimed
)

select
    question_id::text                   as question_id,
    video_id::text                      as video_id,
    evidence::text                      as evidence,
    start_seconds::numeric(12, 3)       as start_seconds
from evidence
