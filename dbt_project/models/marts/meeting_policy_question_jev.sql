{{ config(materialized='table', tags=['marts', 'policy_questions', 'serving']) }}

/*
    Meetings Jev read as debating a policy question, and what happened (#1032). Grain: one row per (meeting video,
    policy question), for the questions with a verbatim passage on record: "Should we allow new data centers?"
    (passage from data_center_meeting_mention) and "Should we allow short-term rentals?" (passage from
    topic_transcript_link, topic 100003), for meetings Jev read as a government meeting or town hall. A row is kept when Jev put P(debated) >= 0.5 or read an action
    (approved, denied, tabled_or_deferred, moratorium).

    outcome is Jev's reading (a classifier), never an extracted decision; evidence is the verbatim transcript passage
    that put the meeting in the cohort, with the matched words in <mark>. Nothing is paraphrased.
*/

with screen as (
    select * from {{ ref('stg_jev__transcript_screen') }}
),

questions as (
    -- The slug Jev was asked under (#1029) -> the registry's question, by its canonical text.
    select v.slug, v.outcome_topic, q.question_id
    from (values
        ('allow_data_centers', 'data-centers', 'Should we allow new data centers?'),
        ('allow_short_term_rentals', 'short-term-rentals', 'Should we allow short-term rentals?')
    ) as v(slug, outcome_topic, canonical_text)
    join {{ ref('policy_question') }} as q on q.canonical_text = v.canonical_text
),

dc_passage as (
    select distinct on (video_id) video_id, evidence, start_seconds
    from {{ ref('data_center_meeting_mention') }}
    order by video_id, passage_index
),

str_passage as (
    select distinct on (video_id) video_id, evidence_passage as evidence, null::numeric as start_seconds
    from {{ ref('topic_transcript_link') }}
    where topic_id = 100003
    order by video_id, n_keyword_hits desc
),

meeting as (
    select distinct on (video_id)
        video_id, event_title, event_date, jurisdiction_name, state_code, state, city, video_url
    from {{ ref('event_documents') }}
    where video_id is not null
    order by video_id, event_document_id
),

rows as (
    select
        s.video_id,
        q.question_id,
        q.outcome_topic,
        (s.question_probabilities ->> q.slug)::numeric                                         as debated_p,
        case q.outcome_topic when 'data-centers' then s.dc_outcome else s.str_outcome end      as outcome,
        case q.outcome_topic when 'data-centers' then s.dc_outcome_p else s.str_outcome_p end  as outcome_p,
        s.question_version,
        s.screened_at
    from screen as s
    cross join questions as q
    -- Government meetings and town halls only: Jev's own meeting_kind drops news shows, podcasts and ceremonies
    -- that mention the topic.
    where s.meeting_kind in ('government_meeting', 'town_hall')
)

select
    md5(r.video_id || '|' || r.question_id)::text          as meeting_policy_question_jev_id,
    r.question_id::text                                    as question_id,
    r.video_id::text                                       as video_id,
    r.outcome_topic::text                                  as outcome_topic,
    r.debated_p                                            as debated_p,
    (r.debated_p >= 0.5)                                   as debated,
    case when r.outcome in ('approved', 'denied', 'tabled_or_deferred', 'moratorium', 'discussed_no_action')
         then r.outcome end::text                          as outcome,
    r.outcome_p                                            as outcome_p,
    coalesce(dp.evidence, sp.evidence)::text               as evidence,
    coalesce(dp.start_seconds, sp.start_seconds)           as start_seconds,
    m.event_title::text                                    as meeting_title,
    m.event_date::date                                     as meeting_date,
    m.jurisdiction_name::text                              as jurisdiction_name,
    m.city::text                                           as city,
    m.state_code::text                                     as state_code,
    m.state::text                                          as state,
    coalesce(m.video_url, 'https://www.youtube.com/watch?v=' || r.video_id)::text as video_url,
    r.question_version::text                               as question_version,
    r.screened_at                                          as screened_at
from rows as r
left join dc_passage as dp on r.outcome_topic = 'data-centers' and dp.video_id = r.video_id
left join str_passage as sp on r.outcome_topic = 'short-term-rentals' and sp.video_id = r.video_id
left join meeting as m on m.video_id = r.video_id
where (r.debated_p >= 0.5 or r.outcome in ('approved', 'denied', 'tabled_or_deferred', 'moratorium'))
  and coalesce(dp.evidence, sp.evidence) is not null
