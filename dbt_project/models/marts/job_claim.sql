/*
    Jobs claims (DC-1.1, #246). Grain: one row per jobs claim per meeting.
    Contract enforced in _schema_job_claim.yml: PK job_claim_id, FK jurisdiction_id to
    jurisdictions, phase CHECK (construction | operations).

    Kept: claims with a non-empty verbatim quote and a phase of construction or
    operations, for meetings present in event_meeting (inner join, so every row's
    event_meeting_id resolves). Everything else stays in stg_job_claim_ai, where
    warn-level tests count it.

    jurisdiction_id comes from the meeting's video (event_youtube_with_jurisdiction) and
    is kept only when it exists in jurisdictions; otherwise null, so the FK holds.
    person_id is null until speaker resolution lands (see the schema description).
*/

with claims as (
    select *
    from {{ ref('stg_job_claim_ai') }}
    where nullif(btrim(quote), '') is not null
      and phase in ('construction', 'operations')
),

-- A re-analysis can bring the same claim twice: keep its latest row.
latest_claims as (
    select distinct on (job_claim_id) *
    from claims
    order by job_claim_id, extracted_at desc nulls last
),

meetings as (
    select
        event_meeting_id,
        meeting_date,
        video_id,
        state_code,
        state,
        jurisdiction_name
    from {{ ref('event_meeting') }}
),

-- video_id is unique in the view today; distinct on keeps the join from fanning out
-- even if that changes.
video_jurisdiction as (
    select distinct on (video_id)
        video_id,
        nullif(jurisdiction_id, '') as jurisdiction_id
    from {{ ref('event_youtube_with_jurisdiction') }}
    where video_id is not null
    order by video_id, jurisdiction_id nulls last
),

known_jurisdictions as (
    select jurisdiction_id
    from {{ ref('jurisdictions') }}
)

select
    c.job_claim_id::text                                   as job_claim_id,
    c.event_meeting_id::integer                            as event_meeting_id,
    {{ safe_iso_date('m.meeting_date') }}::date            as meeting_date,
    m.video_id::text                                       as video_id,
    m.state_code::text                                     as state_code,
    m.state::text                                          as state,
    j.jurisdiction_id::text                                as jurisdiction_id,
    m.jurisdiction_name::text                              as jurisdiction_name,
    null::text                                             as person_id,
    c.phase::text                                          as phase,
    c.headcount_low::integer                               as headcount_low,
    c.headcount_high::integer                              as headcount_high,
    c.starts_on::date                                      as starts_on,
    c.ends_on::date                                        as ends_on,
    c.project_name::text                                   as project_name,
    c.project_type::text                                   as project_type,
    c.speaker_name::text                                   as speaker_name,
    c.start_seconds::double precision                      as start_seconds,
    c.quote::text                                          as quote,
    c.source_ai_model::text                                as source_ai_model,
    c.extracted_at::timestamptz                            as extracted_at
from latest_claims as c
inner join meetings as m
    on m.event_meeting_id = c.event_meeting_id
left join video_jurisdiction as v
    on v.video_id = m.video_id
left join known_jurisdictions as j
    on j.jurisdiction_id = v.jurisdiction_id::text
