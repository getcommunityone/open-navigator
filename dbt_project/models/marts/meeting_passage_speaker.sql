{{ config(
    materialized='table',
    tags=['marts', 'transcripts', 'speakers', 'serving'],
    contract={'enforced': true}
) }}

/*
    meeting_passage_speaker (#1231): who said a quoted story-map passage, where the recording says so.
    Grain: one row per quoted passage (a topic_transcript_link evidence passage, or a data_center_meeting_mention
    excerpt) that falls inside a speaker's introduction window. PK meeting_passage_speaker_id.

    Rule (no model, nothing guessed):
      * The passage's place in the transcript is the character offset of its quoted words in event_documents.content
        (= bronze raw_text, the text the extractor scanned): the first 80 characters of each ts_headline fragment,
        <mark> tags removed. A fragment that can't be found, or whose words occur more than once, gets no speaker.
      * Each fragment takes the NEAREST PRECEDING introduction in the same recording, within 2,500 characters
        (about three minutes of speech, a usual public-comment limit, and the same window
        int_data_center_transcript__passage uses for untimed text). A nearer introduction always wins, so a later
        speaker ends the earlier one's window.
      * A two-fragment excerpt is attributed only when both fragments take the same introduction.
      * The introduction's display form is served as is: a suppressed introduction (student, minor, school board
        resident) yields a row with a null name, never an older speaker's name.
    Design: web_docs/docs/development/speaker-names-from-self-introductions.md
*/

{%- set window_chars = 2500 %}

with intro as (
    select meeting_speaker_intro_id, video_id, char_offset, confidence, speaker_kind, speaker_display_name,
           speaker_role
    from {{ ref('meeting_speaker_intro') }}
),

passage as (
    select
        'topic'::text                 as passage_source,
        l.topic_transcript_link_id    as passage_id,
        l.topic_transcript_link_id,
        null::text                    as data_center_meeting_mention_id,
        l.video_id,
        l.evidence_passage            as excerpt
    from {{ ref('topic_transcript_link') }} as l
    where l.evidence_passage is not null
      and l.video_id in (select video_id from intro)
    union all
    select
        'data_center'::text,
        m.data_center_meeting_mention_id,
        null::text,
        m.data_center_meeting_mention_id,
        m.video_id,
        m.evidence
    from {{ ref('data_center_meeting_mention') }} as m
    where m.evidence is not null
      and m.video_id in (select video_id from intro)
),

doc as (
    select distinct on (d.video_id) d.video_id, d.content
    from {{ ref('event_documents') }} as d
    where d.document_type = 'transcript'
      and d.content is not null
      and d.video_id in (select video_id from passage)
    order by d.video_id, d.content_length desc nulls last
),

fragment as (
    select
        p.*,
        f.ord as fragment_no,
        left(btrim(regexp_replace(f.frag, '</?mark>', '', 'g')), 80) as needle
    from passage as p
    cross join lateral unnest(string_to_array(p.excerpt, ' … ')) with ordinality as f(frag, ord)
),

located as (
    select f.*, strpos(d.content, f.needle) - 1 as fragment_offset
    from fragment as f
    join doc as d on d.video_id = f.video_id
    where length(f.needle) >= 20
      -- Words said more than once (a motion read twice) can't place the passage: no speaker rather than a guess.
      and strpos(substr(d.content, strpos(d.content, f.needle) + 1), f.needle) = 0
),

-- Nearest preceding introduction without a per-fragment scan: put introductions and fragments of each recording in
-- one ordered stream (an introduction before a fragment at the same offset; at one offset the most confident
-- introduction last), keep a running count of introductions, and give each fragment the introduction that count
-- points at.
stream as (
    select video_id, char_offset as pos, 0 as is_fragment, confidence, meeting_speaker_intro_id,
           null::text as passage_source, null::text as passage_id, null::bigint as fragment_no
    from intro
    union all
    select video_id, fragment_offset, 1, null::numeric, null::text, passage_source, passage_id, fragment_no
    from located
    where fragment_offset >= 0
),

counted as (
    select s.*,
           count(s.meeting_speaker_intro_id) over (
               partition by s.video_id
               order by s.pos, s.is_fragment, s.confidence nulls last, s.meeting_speaker_intro_id
               rows between unbounded preceding and current row
           ) as intro_seq
    from stream as s
),

intro_by_seq as (
    select video_id, intro_seq, meeting_speaker_intro_id, pos as intro_pos
    from counted
    where is_fragment = 0
),

assigned as (
    select
        l.passage_source, l.passage_id, l.topic_transcript_link_id, l.data_center_meeting_mention_id, l.video_id,
        l.fragment_no, l.fragment_offset,
        case when l.fragment_offset - i.intro_pos <= {{ window_chars }} then i.meeting_speaker_intro_id end
            as meeting_speaker_intro_id,
        case when l.fragment_offset - i.intro_pos <= {{ window_chars }} then i.intro_pos end as intro_char_offset
    from located as l
    join counted as c
        on c.is_fragment = 1 and c.passage_source = l.passage_source and c.passage_id = l.passage_id
       and c.fragment_no = l.fragment_no
    left join intro_by_seq as i
        on i.video_id = c.video_id and i.intro_seq = c.intro_seq and c.intro_seq > 0
    where l.fragment_offset >= 0
),

per_passage as (
    select
        passage_source, passage_id,
        min(topic_transcript_link_id)          as topic_transcript_link_id,
        min(data_center_meeting_mention_id)    as data_center_meeting_mention_id,
        min(video_id)                          as video_id,
        min(fragment_offset)                   as passage_char_offset,
        min(meeting_speaker_intro_id)          as meeting_speaker_intro_id,
        min(intro_char_offset)                 as intro_char_offset,
        count(*)                               as n_located,
        count(distinct meeting_speaker_intro_id) as n_intros,
        count(*) filter (where meeting_speaker_intro_id is null) as n_unassigned
    from assigned
    group by passage_source, passage_id
),

fragments_total as (
    select passage_source, passage_id, count(*) as n_fragments
    from fragment
    group by 1, 2
)

-- Provenance (#1386): how near the introduction is and whether a ">>" turn marker sits between it and the passage.
, scored as (
    select
        p.*,
        i.pattern_id,
        d.content is not null
          and strpos(substr(d.content, p.intro_char_offset + 1, greatest(p.passage_char_offset - p.intro_char_offset, 0)), '>>') > 0
            as turn_marker_between,
        p.passage_char_offset - p.intro_char_offset as gap_chars
    from per_passage as p
    join {{ ref('meeting_speaker_intro') }} as i on i.meeting_speaker_intro_id = p.meeting_speaker_intro_id
    left join doc as d on d.video_id = p.video_id
),

ruled as (
    select
        sc.*,
        case
            when sc.turn_marker_between                                  then 'passage_after_turn_marker'
            when sc.pattern_id = 'next_speaker'                          then 'passage_chair_call_window'
            when sc.gap_chars <= 600                                     then 'passage_intro_near'
            else 'passage_intro_window'
        end as rule_key
    from scored as sc
)

select
    md5(p.passage_source || '|' || p.passage_id)::text as meeting_passage_speaker_id,
    p.passage_source::text                  as passage_source,
    p.topic_transcript_link_id::text        as topic_transcript_link_id,
    p.data_center_meeting_mention_id::text  as data_center_meeting_mention_id,
    p.video_id::text                        as video_id,
    p.passage_char_offset::integer          as passage_char_offset,
    p.meeting_speaker_intro_id::text        as meeting_speaker_intro_id,
    p.intro_char_offset::integer            as intro_char_offset,
    i.speaker_kind::text                    as speaker_kind,
    i.speaker_display_name::text            as speaker_display_name,
    i.speaker_role::text                    as speaker_role,
    (case when i.speaker_kind = 'official' and p.rule_key in ('passage_intro_near', 'passage_intro_window')
          then 'official_roster_match' else r.attribution_method end)::text as attribution_method,
    (case when i.speaker_kind = 'official' and p.rule_key = 'passage_intro_near' then 0.90
          when i.speaker_kind = 'official' and p.rule_key = 'passage_intro_window' then 0.60
          else r.attribution_confidence end)::numeric(3, 2) as attribution_confidence,
    {{ attribution_tier("(case when i.speaker_kind = 'official' and p.rule_key = 'passage_intro_near' then 0.90 when i.speaker_kind = 'official' and p.rule_key = 'passage_intro_window' then 0.60 else r.attribution_confidence end)") }}::text as attribution_tier,
    ('"' || case p.pattern_id
        when 'my_name_is' then 'my name is' when 'i_am_live' then 'I''m ... I live'
        when 'this_is_from' then 'this is ... from' when 'greeting_name' then 'good evening ... here'
        else 'next speaker is' end || ' ..." at character ' || p.intro_char_offset::text
        || ', ' || p.gap_chars::text || ' characters before the passage'
        || case when p.turn_marker_between then ', with a ">>" turn marker between' else '' end)::text as attribution_evidence,
    '{{ var("speaker_attribution_version") }}'::text as attribution_version,
    now()::timestamp                        as attributed_at
from ruled as p
join fragments_total as t on t.passage_source = p.passage_source and t.passage_id = p.passage_id
join intro as i on i.meeting_speaker_intro_id = p.meeting_speaker_intro_id
join {{ ref('speaker_attribution_rules') }} as r on r.rule_key = p.rule_key
where p.n_intros = 1
  and p.n_unassigned = 0
  and p.n_located = t.n_fragments
