/*
    Staging: jobs claims from the Part 1 meeting analysis (DC-1.1, #246).
    Grain: one row per element of structured_analysis->'job_claims' per analysis.

    Each claim is something a speaker said about jobs a project will bring, split by
    phase (construction vs operations), with the verbatim quote and its timestamp.

    Every cast is guarded (macros/safe_json_casts.sql): a free-text headcount or date
    becomes NULL, never a guess. Rows the job_claim mart can't keep (no quote, a phase
    outside construction/operations) stay here so the warn-level tests in
    _schema_stg_data_centers.yml count them in every run.

    Attribution (DC-1.2, #247): speaker_role is the role said in the meeting. When the
    claim binds its speaker to the analysis's people[] (speaker_person_id), a missing
    speaker_name or speaker_role is filled from that entry. Nothing else is inferred.
*/

with source_analyses as (
    select
        id,
        ai_model,
        created_at,
        structured_analysis
    from {{ source('bronze', 'bronze_events_analysis_ai') }}
    where structured_analysis is not null
      and {{ is_publishable_governance_analysis('structured_analysis') }}
      and structured_analysis ? 'job_claims'
      -- jsonb_array_elements raises on a non-array; a malformed key yields no rows
      and jsonb_typeof(structured_analysis -> 'job_claims') = 'array'
),

claims as (
    select
        a.id,
        a.ai_model,
        a.created_at,
        a.structured_analysis -> 'people'                            as people,
        c.claim
    from source_analyses as a
    cross join lateral jsonb_array_elements(a.structured_analysis -> 'job_claims') as c(claim)
),

typed as (
    select
        cast(id as integer)                                          as event_meeting_id,
        nullif(lower(btrim(claim ->> 'phase')), '')                  as phase,
        {{ safe_nonnegative_integer("claim ->> 'headcount_low'") }}  as headcount_low,
        {{ safe_nonnegative_integer("claim ->> 'headcount_high'") }} as headcount_high,
        {{ safe_iso_date("btrim(claim ->> 'starts_on')") }}          as starts_on,
        {{ safe_iso_date("btrim(claim ->> 'ends_on')") }}            as ends_on,
        nullif(btrim(claim ->> 'project_name'), '')                  as project_name,
        nullif(lower(btrim(claim ->> 'project_type')), '')           as project_type,
        nullif(btrim(claim ->> 'speaker_name'), '')                  as claim_speaker_name,
        nullif(btrim(claim ->> 'speaker_role'), '')                  as claim_speaker_role,
        nullif(btrim(claim ->> 'speaker_person_id'), '')             as speaker_person_ref,
        people,
        {{ safe_nonnegative_double("claim ->> 'start_seconds'") }}   as start_seconds,
        -- verbatim: not trimmed or rewritten
        claim ->> 'quote'                                            as quote,
        cast(ai_model as text)                                       as source_ai_model,
        cast(created_at as timestamptz)                              as extracted_at
    from claims
),

-- The people[] entry the claim names as its speaker (the first with that person_id).
attributed as (
    select
        t.*,
        p.full_name as person_full_name,
        p.role      as person_role
    from typed as t
    left join lateral (
        select
            nullif(btrim(e ->> 'full_name'), '') as full_name,
            nullif(btrim(e ->> 'role'), '')      as role
        from jsonb_array_elements(
            case when jsonb_typeof(t.people) = 'array' then t.people else '[]'::jsonb end
        ) as e
        where t.speaker_person_ref is not null
          and e ->> 'person_id' = t.speaker_person_ref
        limit 1
    ) as p on true
)

select
    md5(
        event_meeting_id::text
        || '|' || coalesce(start_seconds::text, '')
        || '|' || coalesce(phase, '')
        || '|' || coalesce(quote, '')
    )                   as job_claim_id,
    event_meeting_id,
    phase,
    headcount_low,
    headcount_high,
    starts_on,
    ends_on,
    project_name,
    project_type,
    coalesce(claim_speaker_name, person_full_name) as speaker_name,
    coalesce(claim_speaker_role, person_role)      as speaker_role,
    speaker_person_ref,
    start_seconds,
    quote,
    source_ai_model,
    extracted_at
from attributed
