{% macro escalate_invalid() %}
-- Post-hook on bronze_transcript_analysis: re-run ONLY the rows whose primary-model
-- output is invalid (errorMessage set, or JSON missing a meeting object) against
-- the escalate_model, and merge the better result back in place. No-op when
-- escalate_model == primary_model (escalation disabled).
{% if var('escalate_model') != var('primary_model') %}
merge into {{ this }} as tgt
using (
    select
        t.video_id,
        ai_query(
            '{{ var("escalate_model") }}',
            concat(p.prompt, '\n\n--- TRANSCRIPT ---\n', t.transcript_text),
            responseFormat => '{"type": "json_object"}',
            modelParameters => named_struct('max_tokens', {{ var("max_output_tokens") }}, 'temperature', 0.0),
            failOnError => false
        ) as resp
    from {{ source('bronze', 'transcript_to_analyze') }} t
    cross join {{ source('bronze', 'analysis_prompt') }} p
    where t.video_id in (
        select video_id
        from {{ this }}
        where error_message is not null
           or get_json_object(analysis_json, '$.meeting') is null
    )
) esc
on tgt.video_id = esc.video_id
when matched then update set
    tgt.analysis_json   = esc.resp.result,
    tgt.error_message   = esc.resp.errorMessage,
    tgt.source_ai_model = '{{ var("escalate_model") }}',
    tgt.analyzed_at     = current_timestamp()
{% endif %}
{% endmacro %}
