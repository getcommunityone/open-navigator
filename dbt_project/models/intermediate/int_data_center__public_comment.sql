{{ config(materialized='view', tags=['intermediate', 'data_centers', 'sentiment']) }}

/*
    Public comments about a data center item (#930). Grain: one row per public_comment row
    that passes the rule below. This model IS the rule: data_center_meeting_position counts
    from it and data_center_public_comment publishes it, so there is one definition.

    A public comment counts when any holds (match_basis, first that applies):
      data_center_decision  it is linked to a decision (public_comment.event_decision_id)
                            whose headline or decision_statement says a data center word
                            (data_center_regex, the same test data_center_project_mention
                            and decision_company_mention apply to decisions);
      data_center_item      it is on an uncontested item (event_uncontested_item, matched on
                            the meeting and item_id) whose headline says a data center word
                            (#932);
      own_words             the speaker's own stance_evidence, or the comment's summary,
                            says a data center word (data_center_regex);
      same_item             another public speaker on the SAME item of the SAME meeting says
                            a data center word in their own words, so the item is about a
                            data center even though its headline names it another way
                            ("Phoenix Mart PAD major amendment", where a speaker says "The
                            data centers need to go away") (#932).
    Being made in a meeting where a data center came up is NOT enough: a comment on any
    other item of that meeting is left out. same_item needs an item_id, so general public
    comment (no item) never counts through another speaker.

    Known misses (comments that are about a data center but are not counted):
      * general public comment that never says the words (it has no item to share);
      * a comment on an item whose headline and statement name the project some other way
        ("the Project Sail rezoning") when no speaker on that item says a data center word;
      * meetings with no analysis: public_comment only holds analysed meetings.
    Ruled out (measured in #932): the decision narrative fields (competing_views,
    smart_brevity, human_element) add no match beyond the headline; a wider vocabulary
    ("megawatt", "servers", "substation") hits more often outside data center meetings than
    in them; comment timestamps are null, so no timing rule.
    Known over-counts: a comment on a data center item (by headline or same_item) is counted
    even when the speaker talked about a side issue of that item; and through same_item, one
    speaker's passing mention of a data center (quoted) pulls in every speaker on that item,
    even if the item itself is about something else. same_item reads only the verbatim
    quote (stance_evidence), never the summary, to keep that to the speaker's own words.

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

dc_uncontested as (
    select event_meeting_id, item_id, headline
    from {{ ref('event_uncontested_item') }}
    where coalesce(headline, '') ~* '{{ dc_regex }}'
),

comments as (
    select
        c.*,
        -- own_words: the quote or the extraction's summary of the comment
        (coalesce(c.stance_evidence, '') || ' ' || coalesce(c.summary, '') ~* '{{ dc_regex }}') as says_dc,
        -- same_item spreads only from the speaker's verbatim quote, never from the AI summary,
        -- so one paraphrase can't pull a whole item in
        (coalesce(c.stance_evidence, '') ~* '{{ dc_regex }}') as quote_says_dc
    from {{ ref('public_comment') }} as c
),

-- Items (meeting + item_id) where at least one public speaker's own quoted words say a data
-- center word.
dc_spoken_items as (
    select distinct event_meeting_id, item_id
    from comments
    where quote_says_dc and item_id is not null
),

-- Every item's headline, for display, whichever table holds it: a contested decision
-- (event_decision) or an uncontested item (event_uncontested_item), whether or not the
-- headline itself says a data center word.
decision_headline as (
    select distinct on (event_decision_id) event_decision_id, headline
    from {{ ref('event_decision') }}
    order by event_decision_id, extracted_at desc
),

uncontested_headline as (
    select event_meeting_id, item_id, headline
    from {{ ref('event_uncontested_item') }}
),

matched as (
    select
        c.public_comment_id,
        c.event_meeting_id,
        c.event_decision_id,
        coalesce(h.headline, uh.headline)                       as decision_headline,
        c.speaker_id,
        c.stance_bucket,
        c.stance_evidence,
        c.speaker_role,
        c.timestamp_start_seconds,
        case
            when d.event_decision_id is not null then 'data_center_decision'
            when u.item_id is not null then 'data_center_item'
            when c.says_dc then 'own_words'
            else 'same_item'
        end as match_basis
    from comments as c
    left join dc_decisions as d on d.event_decision_id = c.event_decision_id
    left join dc_uncontested as u
        on u.event_meeting_id = c.event_meeting_id and u.item_id = c.item_id
    left join dc_spoken_items as s
        on s.event_meeting_id = c.event_meeting_id and s.item_id = c.item_id
    left join decision_headline as h on h.event_decision_id = c.event_decision_id
    left join uncontested_headline as uh
        on uh.event_meeting_id = c.event_meeting_id and uh.item_id = c.item_id
    where d.event_decision_id is not null
       or u.item_id is not null
       or c.says_dc
       or s.item_id is not null
)

select
    m.*,
    (row_number() over (
        partition by m.event_meeting_id, m.speaker_id
        order by (m.stance_bucket is null), m.timestamp_start_seconds nulls last, m.public_comment_id
    ) = 1) as is_counted
from matched as m
