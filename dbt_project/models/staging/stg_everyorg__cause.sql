{{ config(materialized='view') }}

/*
    Staging: EveryOrg curated cause taxonomy (1 row per cause_id).

    Reads the raw cause table landed by ingestion.everyorg.causes
    (bronze.bronze_everyorg_causes). Light cleaning + type stabilization only.
    Four-CTE template: source → renamed → filtered → final.
*/

with

source as (
    select * from {{ source('bronze', 'bronze_everyorg_causes') }}
),

renamed as (
    select
        nullif(trim(cause_id), '')      as cause_id,
        nullif(trim(cause_name), '')    as cause_name,
        nullif(trim(description), '')   as description,
        nullif(trim(icon), '')          as icon,
        nullif(trim(category), '')      as category,
        nullif(trim(parent_id), '')     as parent_id,
        popularity_rank                 as popularity_rank,
        ingestion_date                  as source_ingested_at
    from source
),

filtered as (
    -- Business rule: drop rows with no cause_id (the natural key).
    select *
    from renamed
    where cause_id is not null
),

final as (
    select
        cause_id,
        cause_name,
        description,
        icon,
        category,
        parent_id,
        popularity_rank,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from filtered
)

select * from final
