{{ config(materialized='view') }}

/*
    Staging: NTEE classification codes (1 row per code).

    Reads the raw code table landed by ingestion.ntee.codes
    (bronze.bronze_ntee_codes). Light cleaning + type stabilization only. The
    hierarchical cause_breadcrumb is derived downstream in int_ntee__breadcrumb
    (recursive CTE over parent_code), not here — that logic used to live in
    Python (build_breadcrumb) and was moved to dbt per dbt_project/CONVENTIONS.md.
    Four-CTE template: source → renamed → filtered → final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_ntee_codes') }}
),

renamed as (
    select
        nullif(trim(code), '')              as code,
        nullif(trim(name), '')              as name,
        nullif(trim(description), '')       as description,
        nullif(trim(cause_type), '')        as cause_type,
        nullif(trim(parent_code), '')       as parent_code,
        nullif(trim(category), '')          as category,
        nullif(trim(subcategory), '')       as subcategory,
        nullif(trim(code_source), '')       as code_source,
        ingestion_date                      as source_ingested_at
    from source
),

filtered as (
    -- Business rule: drop rows with no code (the natural key).
    select *
    from renamed
    where code is not null
),

final as (
    select
        code,
        name,
        description,
        cause_type,
        parent_code,
        category,
        subcategory,
        code_source,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from filtered
)

select * from final
