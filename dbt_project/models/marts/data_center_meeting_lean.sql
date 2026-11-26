/*
    Jev's reading of each data center meeting (#1117, from the #1113 re-screen). Grain: one row per meeting video
    in data_center_meeting_mention that has a screen under the current Jev question version.

    Jev is a classifier (probabilities only, no text): every lean here is an AI reading of the transcript, never a
    count of speakers. Two flags are the readings the #1113 hand checks found reliable enough to show:
      public_against                  public_lean = 'mostly_opposed' with P >= 0.7 (about 7 of 8 right);
      officials_sided_against_public  the public mostly opposed AND officials mostly supportive AND the outcome is
                                      not a moratorium or denial AND it isn't approving rules rather than a project
                                      (dc_outcome = 'approved' with P(project approved) < 0.3 doesn't count).
    "Mostly supported" and "mixed" public leans stay in public_lean for audit but are not flagged or served on maps
    (about 2 of 4 right in the hand checks).
*/

with screen as (
    select *
    from {{ ref('stg_jev__transcript_screen') }}
    where is_current_question_version
),

meeting as (
    select distinct on (video_id)
        video_id, state_code, jurisdiction_id, jurisdiction_name, meeting_date
    from {{ ref('data_center_meeting_mention') }}
    order by video_id, passage_index
),

joined as (
    select
        m.video_id,
        m.state_code,
        m.jurisdiction_id,
        m.jurisdiction_name,
        m.meeting_date,
        s.dc_public_lean        as public_lean,
        s.dc_public_lean_p      as public_lean_p,
        s.dc_official_lean      as official_lean,
        s.dc_official_lean_p    as official_lean_p,
        s.dc_outcome,
        s.dc_project_approved_p as project_approved_p,
        s.question_version,
        s.screened_at
    from meeting as m
    inner join screen as s on s.video_id = m.video_id
)

select
    video_id::text                      as video_id,
    state_code::text                    as state_code,
    jurisdiction_id::text               as jurisdiction_id,
    jurisdiction_name::text             as jurisdiction_name,
    meeting_date::date                  as meeting_date,
    public_lean::text                   as public_lean,
    public_lean_p::numeric              as public_lean_p,
    official_lean::text                 as official_lean,
    official_lean_p::numeric            as official_lean_p,
    dc_outcome::text                    as dc_outcome,
    project_approved_p::numeric         as project_approved_p,
    (public_lean = 'mostly_opposed' and coalesce(public_lean_p, 0) >= 0.7)::boolean as public_against,
    (
        public_lean = 'mostly_opposed'
        and official_lean = 'mostly_supportive'
        and coalesce(dc_outcome, '') not in ('moratorium', 'denied')
        and not (dc_outcome = 'approved' and coalesce(project_approved_p, 0) < 0.3)
    )::boolean                          as officials_sided_against_public,
    question_version::text              as question_version,
    screened_at::timestamptz            as screened_at
from joined
