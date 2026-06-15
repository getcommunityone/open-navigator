{{
  config(
    materialized='incremental',
    unique_key='video_id',
    incremental_strategy='merge',
    post_hook="{{ escalate_invalid() }}"
  )
}}

-- Bronze: one raw LLM analysis JSON per transcript, via ai_query batch inference.
-- Incremental + merge on video_id → each run only analyzes transcripts not yet
-- in this table (the expensive step never reprocesses what's done). The
-- escalation re-run on invalid rows happens in the post_hook (escalate_invalid).
-- failOnError => false isolates a bad row (its errorMessage is recorded) instead
-- of failing the whole batch — skip-and-continue, like the Gemini pipeline.

-- Batch the expensive ai_query: each run analyzes at most `analysis_batch_size`
-- transcripts not yet analyzed. Incremental on video_id, so re-running the job
-- catches up the backlog a batch at a time (set batch size to 0 for "all at once").
with to_do as (
    select t.video_id, t.transcript_text
    from {{ source('bronze', 'transcript_to_analyze') }} t
    {% if is_incremental() %}
    where t.video_id not in (select video_id from {{ this }})
    {% endif %}
    {% if (var('analysis_batch_size') | int) > 0 %}
    order by t.video_id
    limit {{ var('analysis_batch_size') | int }}
    {% endif %}
),

src as (
    select d.video_id, d.transcript_text, p.prompt
    from to_do d
    cross join {{ source('bronze', 'analysis_prompt') }} p
),

scored as (
    select
        video_id,
        ai_query(
            '{{ var("primary_model") }}',
            concat(prompt, '\n\n--- TRANSCRIPT ---\n', transcript_text),
            responseFormat => '{"type": "json_object"}',
            modelParameters => named_struct('max_tokens', {{ var("max_output_tokens") }}, 'temperature', 0.0),
            failOnError => false
        ) as resp
    from src
)

select
    video_id,
    resp.result                          as analysis_json,
    resp.errorMessage                    as error_message,
    '{{ var("primary_model") }}'         as source_ai_model,
    current_timestamp()                  as analyzed_at
from scored
