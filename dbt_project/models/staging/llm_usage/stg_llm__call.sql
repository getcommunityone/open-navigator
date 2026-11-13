/*
    Staging: model calls (#262, #268). Grain: one row per model call after its retries,
    as llm.usage records it (Gemini, DeepSeek, local Gemma; interactive, batch or local).
    Token counts stay null where the API did not report them: never estimated.
    Builds as an empty, typed relation until `python -m llm.usage.load_bronze` creates the
    bronze table (migration 111), so dbt runs keep passing: an honest "nothing loaded yet".
*/

{%- set src = source('bronze', 'bronze_llm_call') -%}
{%- set bronze_exists = execute and adapter.get_relation(
        database=src.database, schema=src.schema, identifier=src.identifier) is not none -%}

{% if bronze_exists %}

select
    cast(llm_call_id as uuid)              as llm_call_id,
    cast(called_at as timestamptz)                as called_at,
    cast(provider as text)                 as provider,
    cast(model as text)                    as model,
    cast(api_mode as text)                 as api_mode,
    cast(stage as text)                    as stage,
    cast(video_id as text)                 as video_id,
    cast(jurisdiction_id as text)          as jurisdiction_id,
    cast(run_id as text)                   as run_id,
    cast(input_token_count as integer)        as input_token_count,
    cast(cached_input_token_count as integer) as cached_input_token_count,
    cast(output_token_count as integer)       as output_token_count,
    cast(thinking_token_count as integer)     as thinking_token_count,
    cast(total_token_count as integer)        as total_token_count,
    cast(latency_seconds as double precision)          as latency_seconds,
    cast(attempt_count as integer)            as attempt_count,
    cast(is_ok as boolean)                    as is_ok,
    cast(error_type as text)               as error_type,
    cast(host_name as text)                as host_name
from {{ src }}

{% else %}

select
    cast(null as uuid)                 as llm_call_id,
    cast(null as timestamptz)          as called_at,
    cast(null as text)                 as provider,
    cast(null as text)                 as model,
    cast(null as text)                 as api_mode,
    cast(null as text)                 as stage,
    cast(null as text)                 as video_id,
    cast(null as text)                 as jurisdiction_id,
    cast(null as text)                 as run_id,
    cast(null as integer)              as input_token_count,
    cast(null as integer)              as cached_input_token_count,
    cast(null as integer)              as output_token_count,
    cast(null as integer)              as thinking_token_count,
    cast(null as integer)              as total_token_count,
    cast(null as double precision)     as latency_seconds,
    cast(null as integer)              as attempt_count,
    cast(null as boolean)              as is_ok,
    cast(null as text)                 as error_type,
    cast(null as text)                 as host_name
where false

{% endif %}
