{{ config(materialized='view') }}

/*
    Staging (#1032): the Jev transcript screen, typed, for rows screened with the policy-question / outcome questions
    (#1029: question_probabilities is set). Jev is a classifier: probabilities only, no text.

    #1117: the public / official lean on data centers and P(the approved item was a specific project), and
    is_current_question_version (the version with the latest screened_at). Consumers of the leans keep only current
    rows: older versions asked differently worded questions, so their answers aren't comparable.
*/

select
    video_id::text                                                    as video_id,
    question_version::text                                            as question_version,
    model::text                                                       as model,
    meeting_kind::text                                                as meeting_kind,
    nullif(dc_outcome, '')::text                                      as dc_outcome,
    (dc_outcome_probabilities ->> nullif(dc_outcome, ''))::numeric    as dc_outcome_p,
    nullif(dc_public_lean, '')::text                                  as dc_public_lean,
    dc_public_lean_probabilities                                      as dc_public_lean_probabilities,
    (dc_public_lean_probabilities ->> nullif(dc_public_lean, ''))::numeric as dc_public_lean_p,
    nullif(dc_official_lean, '')::text                                as dc_official_lean,
    dc_official_lean_probabilities                                    as dc_official_lean_probabilities,
    (dc_official_lean_probabilities ->> nullif(dc_official_lean, ''))::numeric as dc_official_lean_p,
    dc_project_approved_p::numeric                                    as dc_project_approved_p,
    (question_version = (
        -- The current question version: the one screened most recently (#1117). Not hardcoded, so a new wording
        -- takes over as soon as its first rows land.
        select b2.question_version
        from {{ source('bronze', 'bronze_transcript_screen_jev') }} as b2
        where b2.question_probabilities is not null
        group by b2.question_version
        order by max(b2.screened_at) desc
        limit 1
    ))                                                                as is_current_question_version,
    nullif(str_outcome, '')::text                                     as str_outcome,
    (str_outcome_probabilities ->> nullif(str_outcome, ''))::numeric  as str_outcome_p,
    question_probabilities                                            as question_probabilities,
    screened_at                                                       as screened_at
from {{ source('bronze', 'bronze_transcript_screen_jev') }}
where question_probabilities is not null
