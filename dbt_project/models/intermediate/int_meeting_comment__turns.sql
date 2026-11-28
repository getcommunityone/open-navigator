{{ config(materialized='table', tags=['intermediate', 'meeting_comments'],
          indexes=[{'columns': ['comment_segment_id'], 'unique': true}, {'columns': ['video_id']}]) }}

/*
    Speaker turns and speakers per meeting (#1383, epic #1232): the SPEAKER is the grain that counts, the
    caption segment is detail. Grain: one row per comment segment, carrying its turn and its speaker.

    Boundaries are the segmenter's (">>" caption markers, chair hand-offs, self-introductions); every segment
    begins at one, so a turn is a run of consecutive segments by the same NAMED speaker (a restated "my name
    is"). An unnamed segment is its own turn.

    Identity, in this order (privacy: AGENTS.md, minors and students):
      official   meeting_speaker_intro says official: full name and title from our officials data (public role);
      resident   "First L." from meeting_speaker_intro, or from the segment's own self-introduction when the
                 intro mart has no row for it;
      none       a possible minor, a student or a resident at a school board meeting (no name served), a name
                 the intro mart does not recognize, or no introduction: "Speaker N", N = order of first
                 appearance within the meeting.
    Speakers are never linked across meetings: the speaker key is (video_id, name key).
*/

with seg as (
    select
        f.comment_segment_id, f.video_id, f.comment_index, f.start_seconds, f.end_seconds, f.possible_minor,
        f.is_public_comment, f.intro_name, f.boundary_basis, f.intro_text,
        (case when f.possible_minor then null
              else {{ speaker_display_name("regexp_replace(lower(f.intro_name), '[^a-z]+', '_', 'g')", "null") }}
         end) as own_display_name,
        (coalesce(m.jurisdiction_name, '') ~* '(school|\misd\M|\musd\M|board\s+of\s+ed)'
         or coalesce(m.meeting_title, '') ~* ('(schools?\s+board|school\s+district|school\s+committee|board\s+of\s+ed'
                || '|\mboe\M|\musd\M|\misd\M|board\s+of\s+trustees.*school|student)')) as is_school_board
    from {{ ref('int_meeting_comment__flags') }} as f
    inner join {{ ref('segmented_meeting') }} as m on m.video_id = f.video_id
),

intro as (
    select distinct on (s.comment_segment_id)
        s.comment_segment_id, i.speaker_kind, i.speaker_display_name, i.speaker_role, i.person_id,
        i.pattern_id, i.start_seconds as intro_seconds
    from seg as s
    inner join {{ ref('meeting_speaker_intro') }} as i
        on i.video_id = s.video_id
       and i.start_seconds between s.start_seconds - 2 and s.end_seconds
    order by s.comment_segment_id, i.start_seconds
),

-- No introduction inside the turn: the nearest earlier one within 180 s (about 2,500 characters of speech, the
-- window meeting_passage_speaker uses) with no turn marker between. A candidate only: never shown.
earlier as (
    select s.comment_segment_id, e.speaker_display_name as candidate_name, e.start_seconds as earlier_seconds,
           e.pattern_id as earlier_pattern, s.start_seconds - e.start_seconds as gap_seconds
    from seg as s
    left join intro as i on i.comment_segment_id = s.comment_segment_id
    cross join lateral (
        select x.speaker_display_name, x.start_seconds, x.pattern_id
        from {{ ref('meeting_speaker_intro') }} as x
        where x.video_id = s.video_id and x.speaker_kind in ('resident', 'official')
          and x.start_seconds < s.start_seconds - 2 and x.start_seconds >= s.start_seconds - 180
        order by x.start_seconds desc
        limit 1
    ) as e
    where i.comment_segment_id is null and s.own_display_name is null
      and s.boundary_basis !~ '^(turn_marker|handoff)'
),

named as (
    select
        s.*,
        i.speaker_kind,
        i.person_id,
        i.speaker_role,
        i.pattern_id,
        i.intro_seconds,
        ea.candidate_name,
        ea.earlier_seconds,
        ea.gap_seconds,
        (case
            when s.possible_minor or s.is_school_board then null
            when i.speaker_kind in ('official', 'resident') then i.speaker_display_name
            when i.speaker_kind is null then s.own_display_name
        end) as name_shown,
        coalesce(s.possible_minor or s.is_school_board or i.speaker_kind = 'suppressed', false) as name_withheld
    from seg as s
    left join intro as i on i.comment_segment_id = s.comment_segment_id
    left join earlier as ea on ea.comment_segment_id = s.comment_segment_id
),

ruled as (
    select
        n.*,
        case
            when n.speaker_kind = 'official' and n.name_shown is not null                 then 'official_roster_match'
            when n.name_withheld and (n.speaker_kind is not null or n.own_display_name is not null)
                                                                                           then 'self_intro_name_withheld'
            when n.speaker_kind = 'resident' and n.pattern_id in ('my_name_is', 'i_am_live') then 'self_intro_in_turn'
            when n.speaker_kind = 'resident' and n.pattern_id in ('this_is_from', 'greeting_name') then 'self_intro_greeting'
            when n.speaker_kind = 'resident' and n.pattern_id = 'next_speaker'            then 'chair_call_name'
            when n.speaker_kind is null and n.own_display_name is not null and not n.name_withheld then 'self_intro_in_turn'
            when n.speaker_kind = 'unrecognized'                                           then 'self_intro_name_withheld'
            when n.boundary_basis ~ 'self_intro>' and n.candidate_name is null              then 'self_intro_name_withheld'
            when n.candidate_name is not null                                              then 'nearest_earlier_intro'
            when n.boundary_basis ~ '^turn_marker'                                         then 'turn_marker_only'
            else 'chair_call_turn'
        end as rule_key
    from named as n
),

keyed as (
    select
        n.*,
        coalesce(
            case when n.speaker_kind = 'official' then 'official:' || n.person_id end,
            'name:' || lower(n.name_shown),
            'seg:' || n.comment_segment_id
        ) as speaker_key
    from ruled as n
),

turned as (
    select
        k.*,
        -- a new turn when the speaker differs from the previous segment's
        case when lag(k.speaker_key) over w is not distinct from k.speaker_key and k.name_shown is not null
             then 0 else 1 end as new_turn
    from keyed as k
    window w as (partition by k.video_id order by k.comment_index)
),

numbered as (
    select
        t.*,
        sum(t.new_turn) over (partition by t.video_id order by t.comment_index) - 1 as turn_index
    from turned as t
),

speakers as (
    select
        video_id, speaker_key, min(comment_index) as first_index,
        dense_rank() over (partition by video_id order by min(comment_index)) as speaker_number
    from numbered
    group by video_id, speaker_key
)

select
    n.comment_segment_id,
    n.video_id,
    n.comment_index,
    n.turn_index::int                                           as turn_index,
    md5(n.video_id || '|turn|' || n.turn_index::text)           as meeting_speaker_turn_id,
    md5(n.video_id || '|speaker|' || n.speaker_key)             as meeting_speaker_id,
    sp.speaker_number::int                                      as speaker_number,
    n.name_shown,
    (case when n.name_shown is null and not (n.possible_minor or n.is_school_board)
          then n.candidate_name end)                            as candidate_name,
    n.speaker_kind,
    case when n.name_shown is not null then n.speaker_role end as speaker_role,
    n.name_withheld,
    n.possible_minor,
    n.is_public_comment,
    -- provenance (#1386): how we know who this is, and how sure
    n.rule_key,
    r.attribution_method::text                                  as attribution_method,
    r.attribution_confidence::numeric(3, 2)                     as attribution_confidence,
    {{ attribution_tier('r.attribution_confidence') }}::text    as attribution_tier,
    (case
        when n.rule_key in ('turn_marker_only') then '">>" caption speaker-change'
        when n.rule_key in ('chair_call_turn') then 'the chair''s call (' || split_part(n.boundary_basis, '>', 1) || ')'
        else '"' || coalesce(
                case when n.pattern_id = 'next_speaker' then 'next speaker is' end,
                substring(lower(n.intro_text) from '^(my name(?:''s| is)|name (?:and|&) address (?:is|are)|i''?m|i am|good (?:evening|morning|afternoon)|this is)'),
                'introduction') || ' ..."'
        || case when n.rule_key = 'nearest_earlier_intro' then ' ' || round(n.gap_seconds)::int::text || ' s earlier' else '' end
     end)::text                                                 as attribution_evidence,
    coalesce(n.intro_seconds, n.earlier_seconds, n.start_seconds)::numeric(12, 3) as attribution_evidence_seconds,
    '{{ var("speaker_attribution_version") }}'::text            as attribution_version,
    now()::timestamp                                            as attributed_at
from numbered as n
inner join speakers as sp on sp.video_id = n.video_id and sp.speaker_key = n.speaker_key
inner join {{ ref('speaker_attribution_rules') }} as r on r.rule_key = n.rule_key
