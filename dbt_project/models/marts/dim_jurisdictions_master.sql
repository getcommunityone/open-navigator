{{
    config(
        materialized='table',
        unique_key='master_jurisdiction_key'
    )
}}

/*
    Mart: master_jurisdictions (MDM golden records).

    Final consolidation reproducing consolidate_to_master() from the archived
    scripts/datasources/master_data/create_jurisdiction_master.py. One row per
    canonical jurisdiction: GROUP BY (canonical_name, state_code, primary_type),
    where primary_type = COALESCE(jurisdiction_type, organization_type). Source
    ids are MAX-aggregated, source_count = COUNT(*), and a completeness score is
    bucketed off source_count, exactly as the Python.

    The Python wrote a SERIAL `id`. dbt is declarative/idempotent, so we expose a
    deterministic surrogate key (md5 of the natural key) as `master_jurisdiction_key`
    instead. The canonical natural key (canonical_name, state_code, primary_type)
    is unique (tested).

    NOTE: array-typed columns from the original master_jurisdictions schema
    (alternate_names, sub_types, all_websites, domains) and metric columns
    (population, area_sq_miles) were declared in the table DDL but NEVER populated
    by consolidate_to_master() — it inserted only the scalar columns below. We
    therefore reproduce exactly the populated columns; the unused array/metric
    columns are intentionally omitted (flagged in _schema).

    Materialized as `table` (not the marts-default `incremental`) because the
    Python rebuilt master_jurisdictions from scratch each run (TRUNCATE + INSERT).
*/

with

enriched as (
    select * from {{ ref('int_master__crosswalk_enriched') }}
),

filtered as (
    -- Python: WHERE primary_name IS NOT NULL AND state_code IS NOT NULL
    select *
    from enriched
    where primary_name is not null
      and state_code is not null
),

aggregated as (
    select
        primary_name                        as canonical_name,
        state_code,
        coalesce(jurisdiction_type, organization_type) as primary_type,
        max(nces_id)                        as nces_id,
        max(fips_code)                      as fips_code,
        max(geoid)                          as geoid,
        max(full_state_name)                as state,
        max(county)                         as county,
        max(city)                           as city,
        count(*)                            as source_count
    from filtered
    group by
        primary_name,
        state_code,
        coalesce(jurisdiction_type, organization_type)
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key([
            'canonical_name', 'state_code', 'primary_type'
        ]) }}                               as master_jurisdiction_key,
        nces_id,
        fips_code,
        geoid,
        canonical_name,
        state_code,
        state,
        county,
        city,
        primary_type,
        source_count,
        case
            when source_count >= 3 then 1.0
            when source_count = 2 then 0.75
            else 0.5
        end::decimal(3, 2)                  as data_completeness_score,
        current_timestamp                   as dbt_loaded_at
    from aggregated
)

select * from final
