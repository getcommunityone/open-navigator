/*
    LLM usage by day (#268). Grain: one row per usage_date (UTC), model and api_mode.
    Contract enforced in _schema_llm_usage_daily.yml: PK (usage_date, model, api_mode).

    Sums what the APIs reported. A token sum is null when no call that day reported that
    count, not zero: "not reported" and "none used" stay different. No cost column: cost is
    derived from these sums and packages/llm/src/llm/usage/prices.yaml (python -m
    llm.usage.report), so a corrected price reprices history.
*/

select
    cast(called_at at time zone 'UTC' as date)          as usage_date,
    model,
    api_mode,
    cast(count(*) as integer)                            as call_count,
    cast(count(*) filter (where not is_ok) as integer)  as failed_call_count,
    cast(count(*) filter (where attempt_count > 1) as integer) as retried_call_count,
    cast(sum(input_token_count) as bigint)               as input_token_count,
    cast(sum(cached_input_token_count) as bigint)        as cached_input_token_count,
    cast(sum(output_token_count) as bigint)              as output_token_count,
    cast(sum(thinking_token_count) as bigint)            as thinking_token_count,
    cast(avg(latency_seconds) as double precision)       as avg_latency_seconds
from {{ ref('stg_llm__call') }}
group by 1, 2, 3
