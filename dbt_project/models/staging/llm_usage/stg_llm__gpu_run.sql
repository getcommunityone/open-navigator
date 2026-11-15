/*
    Staging: GPU steps (#262, #268). Grain: one row per GPU step wrapped in llm.usage.gpu.gpu_run
    (WhisperX diarization, a local Gemma generation).
    Builds as an empty, typed relation until `python -m llm.usage.load_bronze` creates the
    bronze table (migration 111), so dbt runs keep passing: an honest "nothing loaded yet".
*/

{%- set src = source('bronze', 'bronze_gpu_run') -%}
{%- set bronze_exists = execute and adapter.get_relation(
        database=src.database, schema=src.schema, identifier=src.identifier) is not none -%}

{% if bronze_exists %}

select
    cast(gpu_run_id as uuid)              as gpu_run_id,
    cast(step_name as text)               as step_name,
    cast(started_at as timestamptz)              as started_at,
    cast(ended_at as timestamptz)                as ended_at,
    cast(wall_seconds as double precision)            as wall_seconds,
    cast(gpu_count as integer)               as gpu_count,
    cast(gpu_name as text)                as gpu_name,
    cast(gpu_hours as double precision)               as gpu_hours,
    cast(gpu_sample_count as integer)        as gpu_sample_count,
    cast(avg_gpu_utilization_pct as double precision) as avg_gpu_utilization_pct,
    cast(max_gpu_memory_used_mb as double precision)  as max_gpu_memory_used_mb,
    cast(energy_wh as double precision)               as energy_wh,
    cast(video_id as text)                as video_id,
    cast(jurisdiction_id as text)         as jurisdiction_id,
    cast(run_id as text)                  as run_id,
    cast(host_name as text)               as host_name
from {{ src }}

{% else %}

select
    cast(null as uuid)                 as gpu_run_id,
    cast(null as text)                 as step_name,
    cast(null as timestamptz)          as started_at,
    cast(null as timestamptz)          as ended_at,
    cast(null as double precision)     as wall_seconds,
    cast(null as integer)              as gpu_count,
    cast(null as text)                 as gpu_name,
    cast(null as double precision)     as gpu_hours,
    cast(null as integer)              as gpu_sample_count,
    cast(null as double precision)     as avg_gpu_utilization_pct,
    cast(null as double precision)     as max_gpu_memory_used_mb,
    cast(null as double precision)     as energy_wh,
    cast(null as text)                 as video_id,
    cast(null as text)                 as jurisdiction_id,
    cast(null as text)                 as run_id,
    cast(null as text)                 as host_name
where false

{% endif %}
