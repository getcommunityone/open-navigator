{{ config(materialized='view') }}

/*
    Staging (#1032): the Jev transcript screen, typed, for rows screened with the policy-question / outcome questions
    (#1029: question_probabilities is set). Jev is a classifier: probabilities only, no text.
*/

select
    video_id::text                                                    as video_id,
    question_version::text                                            as question_version,
    model::text                                                       as model,
    meeting_kind::text                                                as meeting_kind,
    nullif(dc_outcome, '')::text                                      as dc_outcome,
    (dc_outcome_probabilities ->> nullif(dc_outcome, ''))::numeric    as dc_outcome_p,
    nullif(str_outcome, '')::text                                     as str_outcome,
    (str_outcome_probabilities ->> nullif(str_outcome, ''))::numeric  as str_outcome_p,
    question_probabilities                                            as question_probabilities,
    screened_at                                                       as screened_at
from {{ source('bronze', 'bronze_transcript_screen_jev') }}
where question_probabilities is not null
