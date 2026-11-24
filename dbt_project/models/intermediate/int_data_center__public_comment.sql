{{ config(materialized='view', tags=['intermediate', 'data_centers', 'sentiment']) }}

/*
    Public comments about a data center item (#930). Grain: one row per public_comment row
    that passes the rule below. This model IS the rule: data_center_meeting_position counts
    from it and data_center_public_comment publishes it, so there is one definition.

    A public comment counts when either holds (match_basis, first that applies):
      data_center_decision  it is linked to a decision (public_comment.event_decision_id)
                            whose headline or decision_statement says a data center word
                            (data_center_regex, the same test data_center_project_mention
                            and decision_company_mention apply to decisions);
      own_words             the speaker's own stance_evidence, or the comment's summary,
                            says a data center word (data_center_regex).
    Being made in a meeting where a data center came up is NOT enough: a comment on any
    other item of that meeting is left out.

    Known misses (comments that are about a data center but are not counted):
      * general public comment, or a comment on an uncontested item, that never says the
        words (it has no event_decision_id, and uncontested items are not in event_decision);
      * a comment on a decision whose headline and statement name the project some other way
        ("the Project Sail rezoning") without a data center word;
      * meetings with no analysis: public_comment only holds analysed meetings.
    Known over-count: a comment linked to a data center decision is counted even when the
    speaker talked about a side issue of that item.

    is_counted marks the one row that stands for a speaker in a meeting: a speaker with
    several rows on data center items is counted once, taking a row with a known stance
    first, then the earliest in the recording, then public_comment_id.
    Design: web_docs/docs/development/data-center-who-spoke-up.md
*/

{%- set dc_regex = data_center_regex() %}

with dc_decisions as (
    select event_decision_id, headline
    from (
        select distinct on (event_decision_id)
            event_decision_id, headline, decision_statement
        from {{ ref('event_decision') }}
        order by event_decision_id, extracted_at desc
    ) as d
    where coalesce(d.headline, '') || ' ' || coalesce(d.decision_statement, '') ~* '{{ dc_regex }}'
),

matched as (
    select
        c.public_comment_id,
        c.event_meeting_id,
        c.event_decision_id,
        d.headline                                              as decision_headline,
        c.speaker_id,
        c.stance_bucket,
        c.stance_evidence,
        c.speaker_role,
        c.timestamp_start_seconds,
        case when d.event_decision_id is not null then 'data_center_decision' else 'own_words' end as match_basis
    from {{ ref('public_comment') }} as c
    left join dc_decisions as d on d.event_decision_id = c.event_decision_id
    where d.event_decision_id is not null
       or coalesce(c.stance_evidence, '') || ' ' || coalesce(c.summary, '') ~* '{{ dc_regex }}'
)

select
    m.*,
    (row_number() over (
        partition by m.event_meeting_id, m.speaker_id
        order by (m.stance_bucket is null), m.timestamp_start_seconds nulls last, m.public_comment_id
    ) = 1) as is_counted
from matched as m
