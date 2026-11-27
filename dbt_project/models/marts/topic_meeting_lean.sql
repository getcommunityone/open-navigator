/*
    Jev's reading of how the public and the elected officials leaned on a topic in each meeting (#1126), the
    topic-generic sibling of data_center_meeting_lean (#1117). Grain: one row per (meeting video, topic) in
    topic_transcript_link that has a screen under the topic's current Jev question version.

    Jev is a classifier (probabilities only, no text): every lean is an AI reading of the transcript, an aggregate
    for the meeting, never a count of speakers and never tied to a person (AGENTS.md, Privacy).

    Labels. Most topics use mostly_supportive / mostly_opposed / mixed / did_not_speak. Water fluoridation uses
    CareQuest's five poll positions (support_require_all, support_local_choice, no_opinion, oppose_local_choice,
    oppose_ban_all) plus did_not_speak; they are kept as public_position / official_position and rolled up here so
    the four-colour map reads the same columns for every topic:
        support_*  -> mostly_supportive    oppose_*  -> mostly_opposed    no_opinion -> no_opinion
    The rolled-up lean is the group with the most probability, and its p is that group's summed probability. For the
    shared labels this is the same as Jev's top label.

    Outcomes. outcome keeps Jev's label; outcome_group maps fluoridation's labels onto the shared ones
    (voted_to_end_fluoridation -> blocked, voted_to_keep_or_start -> advanced, discussion_only ->
    discussed_no_action, no_fluoridation_item -> no_item).

    Flags, with the data_center_meeting_lean thresholds:
      public_against                  public_lean = mostly_opposed with p >= 0.7;
      public_for                      public_lean = mostly_supportive with p >= 0.7;
      officials_sided_against_public  the public mostly opposed AND officials mostly supportive AND the body did not
                                      block it (outcome_group <> 'blocked': not denied, ended, paused or limited,
                                      the analogue of the data-center moratorium/denial/rules exclusions).
      excluded_no_item                outcome_group = no_item with p >= 0.7: a keyword false hit (#1136);
      official_action                 where the public did not speak: advanced -> for, blocked or tabled -> against,
                                      otherwise none (#1136).
*/

with screen as (
    select *
    from {{ ref('stg_jev__transcript_topic_lean') }}
    where is_current_question_version
),

link as (
    select topic_id, video_id, state_code, state, jurisdiction_name, event_date
    from {{ ref('topic_transcript_link') }}
),

video as (
    select distinct on (video_id) video_id, nullif(trim(jurisdiction_id), '') as jurisdiction_id
    from {{ ref('event_youtube_with_jurisdiction') }}
    order by video_id
),

known_jurisdictions as (
    select jurisdiction_id from {{ ref('jurisdictions') }}
),

-- Probability mass per group, from the label probabilities (fluoridation's two support / two oppose labels sum).
masses as (
    select
        s.*,
        {%- for who in ['public', 'official'] %}
        coalesce((s.{{ who }}_lean_probabilities ->> 'mostly_supportive')::numeric, 0)
            + coalesce((s.{{ who }}_lean_probabilities ->> 'support_require_all')::numeric, 0)
            + coalesce((s.{{ who }}_lean_probabilities ->> 'support_local_choice')::numeric, 0)  as {{ who }}_support_p,
        coalesce((s.{{ who }}_lean_probabilities ->> 'mostly_opposed')::numeric, 0)
            + coalesce((s.{{ who }}_lean_probabilities ->> 'oppose_local_choice')::numeric, 0)
            + coalesce((s.{{ who }}_lean_probabilities ->> 'oppose_ban_all')::numeric, 0)        as {{ who }}_oppose_p,
        coalesce((s.{{ who }}_lean_probabilities ->> 'mixed')::numeric, 0)                       as {{ who }}_mixed_p,
        coalesce((s.{{ who }}_lean_probabilities ->> 'no_opinion')::numeric, 0)                  as {{ who }}_no_opinion_p,
        coalesce((s.{{ who }}_lean_probabilities ->> 'did_not_speak')::numeric, 0)               as {{ who }}_none_p,
        {%- endfor %}
        s.public_lean_label in (
            'support_require_all', 'support_local_choice', 'no_opinion', 'oppose_local_choice', 'oppose_ban_all'
        ) or s.official_lean_label in (
            'support_require_all', 'support_local_choice', 'no_opinion', 'oppose_local_choice', 'oppose_ban_all'
        ) or s.topic_slug = 'water-fluoridation'                                                    as uses_positions
    from screen as s
),

rolled as (
    select
        m.*,
        {%- for who in ['public', 'official'] %}
        case
            when m.{{ who }}_lean_label is null then null
            when m.{{ who }}_lean_label = 'did_not_speak' then 'did_not_speak'
            when m.{{ who }}_support_p >= greatest(m.{{ who }}_oppose_p, m.{{ who }}_mixed_p, m.{{ who }}_no_opinion_p)
                then 'mostly_supportive'
            when m.{{ who }}_oppose_p >= greatest(m.{{ who }}_mixed_p, m.{{ who }}_no_opinion_p) then 'mostly_opposed'
            when m.{{ who }}_mixed_p >= m.{{ who }}_no_opinion_p then 'mixed'
            else 'no_opinion'
        end as {{ who }}_lean,
        {%- endfor %}
        case m.outcome
            when 'voted_to_end_fluoridation' then 'blocked'
            when 'voted_to_keep_or_start' then 'advanced'
            when 'discussion_only' then 'discussed_no_action'
            when 'no_fluoridation_item' then 'no_item'
            else m.outcome
        end as outcome_group
    from masses as m
),

with_p as (
    select
        r.*,
        {%- for who in ['public', 'official'] %}
        case r.{{ who }}_lean
            when 'did_not_speak' then r.{{ who }}_none_p
            when 'mostly_supportive' then r.{{ who }}_support_p
            when 'mostly_opposed' then r.{{ who }}_oppose_p
            when 'mixed' then r.{{ who }}_mixed_p
            when 'no_opinion' then r.{{ who }}_no_opinion_p
        end as {{ who }}_lean_p{{ ',' if not loop.last }}
        {%- endfor %}
    from rolled as r
)

select
    w.video_id::text                                                       as video_id,
    w.topic_id::integer                                                    as topic_id,
    w.topic_slug::text                                                     as topic_slug,
    l.state_code::text                                                     as state_code,
    l.state::text                                                          as state,
    j.jurisdiction_id::text                                                as jurisdiction_id,
    l.jurisdiction_name::text                                              as jurisdiction_name,
    (case when l.event_date > current_date then null else l.event_date end)::date as meeting_date,
    w.public_lean::text                                                    as public_lean,
    round(w.public_lean_p, 4)::numeric                                     as public_lean_p,
    w.official_lean::text                                                  as official_lean,
    round(w.official_lean_p, 4)::numeric                                   as official_lean_p,
    (case when w.uses_positions then w.public_lean_label end)::text        as public_position,
    (case when w.uses_positions then w.public_lean_probabilities end)::jsonb as public_position_probabilities,
    (case when w.uses_positions then w.official_lean_label end)::text      as official_position,
    (case when w.uses_positions then w.official_lean_probabilities end)::jsonb as official_position_probabilities,
    w.outcome::text                                                        as outcome,
    w.outcome_group::text                                                  as outcome_group,
    w.outcome_p::numeric                                                   as outcome_p,
    (w.public_lean = 'mostly_opposed' and coalesce(w.public_lean_p, 0) >= 0.7)::boolean    as public_against,
    (w.public_lean = 'mostly_supportive' and coalesce(w.public_lean_p, 0) >= 0.7)::boolean as public_for,
    (
        w.public_lean = 'mostly_opposed'
        and w.official_lean = 'mostly_supportive'
        and coalesce(w.outcome_group, '') <> 'blocked'
    )::boolean                                                             as officials_sided_against_public,
    -- #1136: a confident "no item on this topic" means the keyword link was a false hit; maps and counts drop it.
    (w.outcome_group = 'no_item' and coalesce(w.outcome_p, 0) >= 0.7)::boolean as excluded_no_item,
    -- #1136: what the body did, read from the outcome, only where the public did not speak. advanced / blocked are
    -- defined per topic in the subject's direction (fluoridation: keep or start -> for, end -> against).
    (case
        when coalesce(w.public_lean, 'did_not_speak') <> 'did_not_speak' then 'none'
        when w.outcome_group = 'advanced' then 'for'
        when w.outcome_group in ('blocked', 'tabled_or_deferred') then 'against'
        else 'none'
    end)::text                                                             as official_action,
    w.question_version::text                                               as question_version,
    w.screened_at::timestamptz                                             as screened_at
from with_p as w
inner join link as l on l.topic_id = w.topic_id and l.video_id = w.video_id
left join video as v on v.video_id = w.video_id
left join known_jurisdictions as j on j.jurisdiction_id = v.jurisdiction_id
