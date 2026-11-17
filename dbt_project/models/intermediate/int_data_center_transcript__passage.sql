{{ config(materialized='table', tags=['intermediate', 'data_centers', 'transcripts']) }}

/*
    Transcript passages that say "data center" (#445).
    Grain: one row per (video_id, passage_index).

    A passage is a ~3-minute window of timed caption cues (passage_index = floor(start / 180)),
    taken from segments (JSON cues with start seconds) or, when a transcript has no segments,
    from caption_text_timed ("{HH:MM:SS} words ..." markers; at least 20 markers, else it is
    treated as untimed). A transcript with neither is cut into 2,500-character windows of
    raw_text (passage_index = window number, start_seconds null).

    passage_text is the transcript's own words, cue texts joined with a space in cue order;
    the caption tool's "[N SECOND PAUSE]" / "<N MINUTE PASSED>" notes are dropped.
    start_seconds is the start of the first cue in the passage that says a data center word
    (the moment to jump to), else the passage's first cue. Only passages whose own text
    matches data_center_regex are kept.
*/

with candidates as (
    select * from {{ ref('stg_event_youtube_transcript__data_center') }}
),

segment_cues as (
    select
        c.video_id,
        'segments'::text                    as timing_source,
        (s.cue ->> 'start')::numeric        as start_s,
        s.cue ->> 'text'                    as cue_text,
        s.ord
    from candidates as c
    cross join lateral jsonb_array_elements(c.segments) with ordinality as s(cue, ord)
    where c.segments is not null
      and (s.cue ->> 'start') ~ '^[0-9]+(\.[0-9]+)?$'
),

timed_candidates as (
    select c.video_id, c.caption_text_timed
    from candidates as c
    where c.segments is null
      and c.caption_text_timed is not null
      and (select count(*) from regexp_matches(c.caption_text_timed, '\{\d+:\d\d:\d\d\}', 'g')) >= 20
),

timed_cues as (
    select
        c.video_id,
        'caption_text_timed'::text          as timing_source,
        (m.parts[1]::int * 3600 + m.parts[2]::int * 60 + m.parts[3]::int)::numeric as start_s,
        regexp_replace(m.parts[4], '\[\d+ SECONDS? PAUSE\]|<\d+ MINUTES? PASSED>', ' ', 'g') as cue_text,
        m.ord
    from timed_candidates as c
    cross join lateral regexp_matches(
        c.caption_text_timed, '\{(\d+):(\d\d):(\d\d)\}([^{]*)', 'g'
    ) with ordinality as m(parts, ord)
),

cues as (
    select * from segment_cues
    union all
    select * from timed_cues
),

timed_passages as (
    select
        video_id,
        floor(start_s / 180)::int           as passage_index,
        min(timing_source)                  as timing_source,
        coalesce(
            min(start_s) filter (where cue_text ~* '{{ data_center_regex() }}'),
            min(start_s)
        )                                   as start_seconds,
        string_agg(nullif(btrim(regexp_replace(cue_text, '\s+', ' ', 'g')), ''), ' ' order by ord) as passage_text
    from cues
    group by 1, 2
),

untimed_passages as (
    select
        c.video_id,
        w.i                                 as passage_index,
        null::text                          as timing_source,
        null::numeric                       as start_seconds,
        substr(c.raw_text, w.i * 2500 + 1, 2500) as passage_text
    from candidates as c
    cross join lateral generate_series(0, (length(c.raw_text) - 1) / 2500) as w(i)
    where c.raw_text is not null
      and not exists (select 1 from cues as u where u.video_id = c.video_id)
),

passages as (
    select * from timed_passages
    union all
    select * from untimed_passages
)

select
    video_id::text                          as video_id,
    passage_index::int                      as passage_index,
    timing_source::text                     as timing_source,
    start_seconds::numeric                  as start_seconds,
    passage_text::text                      as passage_text
from passages
where passage_text ~* '{{ data_center_regex() }}'
