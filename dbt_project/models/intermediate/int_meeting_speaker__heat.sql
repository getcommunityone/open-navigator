{{ config(materialized='table', tags=['intermediate', 'meeting_comments'],
          indexes=[{'columns': ['meeting_speaker_id'], 'unique': true}]) }}

/*
    Heat (1-5) per meeting x speaker (#1386), with its method, like attribution:
      ai_meeting_analysis  the AI meeting analysis's own rating (public_comment.heat) of a comment in the same
                           meeting whose verbatim quote (stance_evidence, 40+ characters, first 60 normalized
                           characters) sits inside one of the speaker's segments; several -> the rounded mean.
      classifier           (#1391) TypeSafe Jev's heat ladder (P(heat >= k), k = 2..5) on the speaker's own passages,
                           current question version, heat_confidence >= var('speaker_heat_min_confidence'); a speaker
                           read for several topics -> the rounded mean, confidence the mean margin. Only where the AI
                           meeting analysis has no rating for the speaker (that one is kept).
      rules                free baseline from the comment_heat_terms lexicon + "!" + ALL-CAPS words on the
                           speaker's own text. NULL unless var heat_rules_enabled (it is off: the calibration
                           against the AI-rated comments did not beat a constant guess; see the decision page).
    Private (reads comment text); the marts carry only the number, method, confidence and version.
*/

{%- set thresholds = [0.5, 1.5, 3.0, 5.0] %}

with spk as (
    select
        t.meeting_speaker_id, t.video_id,
        string_agg(f.comment_text, ' ' order by t.comment_index) as txt
    from {{ ref('int_meeting_comment__turns') }} as t
    inner join {{ ref('int_meeting_comment__flags') }} as f on f.comment_segment_id = t.comment_segment_id
    group by t.meeting_speaker_id, t.video_id
),

seg as (
    select t.meeting_speaker_id, t.video_id,
           btrim(regexp_replace(regexp_replace(lower(f.comment_text), '[^a-z0-9 ]', ' ', 'g'), '\s+', ' ', 'g')) as norm
    from {{ ref('int_meeting_comment__turns') }} as t
    inner join {{ ref('int_meeting_comment__flags') }} as f on f.comment_segment_id = t.comment_segment_id
),

ai as (
    select
        s.meeting_speaker_id,
        round(avg(pc.heat))::int as heat,
        count(distinct pc.public_comment_id) as n_matched
    from {{ ref('public_comment') }} as pc
    inner join seg as s on s.video_id = pc.video_id
    where pc.heat between 1 and 5
      and length(pc.stance_evidence) >= 40
      and strpos(s.norm, left(btrim(regexp_replace(regexp_replace(lower(pc.stance_evidence), '[^a-z0-9 ]', ' ', 'g'), '\s+', ' ', 'g')), 60)) > 0
    group by s.meeting_speaker_id
),

clf as (
    select
        meeting_speaker_id,
        round(avg(heat))::int              as heat,
        round(avg(heat_confidence), 2)     as heat_confidence,
        'jev:' || string_agg(distinct question_version, '+' order by question_version) as heat_version
    from {{ ref('stg_jev__speaker_topic_stance') }}
    where is_current_question_version and heat between 1 and 5
      and side is distinct from 'off_topic'
      and heat_confidence >= {{ var('speaker_heat_min_confidence') }}
    group by meeting_speaker_id
),

rules as (
    select
        spk.meeting_speaker_id,
        (
            coalesce((select sum(least(
                        (select count(*) from regexp_matches(spk.txt, h.pattern, 'gi')) * h.weight::numeric,
                        coalesce(h.cap::numeric, 1000000)))
                      from {{ ref('comment_heat_terms') }} as h), 0)
            + 0.5 * least((select count(*) from regexp_matches(spk.txt, '!', 'g')), 4)
            + 0.5 * least((select count(*) from regexp_matches(spk.txt, '\y[A-Z]{4,}\y', 'g')), 2)
        ) as raw_score
    from spk
)

select
    spk.meeting_speaker_id::text as meeting_speaker_id,
    (case
        when ai.heat is not null then ai.heat
        when clf.heat is not null then clf.heat
        when {{ 'true' if var('heat_rules_enabled') else 'false' }} then
            1 + {% for t in thresholds %}(r.raw_score >= {{ t }})::int{{ ' + ' if not loop.last }}{% endfor %}
    end)::int as heat,
    (case
        when ai.heat is not null then 'ai_meeting_analysis'
        when clf.heat is not null then 'classifier'
        when {{ 'true' if var('heat_rules_enabled') else 'false' }} then 'rules'
    end)::text as heat_method,
    (case
        when ai.heat is not null then 0.80
        when clf.heat is not null then clf.heat_confidence
        when {{ 'true' if var('heat_rules_enabled') else 'false' }} then {{ var('heat_rules_within1') }}
    end)::numeric(3, 2) as heat_confidence,
    (case
        when ai.heat is not null then '{{ var("heat_version") }}'
        when clf.heat is not null then clf.heat_version
        when {{ 'true' if var('heat_rules_enabled') else 'false' }} then '{{ var("heat_version") }}'
    end)::text as heat_version,
    r.raw_score::numeric(8, 2) as rules_raw_score
from spk
inner join rules as r on r.meeting_speaker_id = spk.meeting_speaker_id
left join ai on ai.meeting_speaker_id = spk.meeting_speaker_id
left join clf on clf.meeting_speaker_id = spk.meeting_speaker_id
