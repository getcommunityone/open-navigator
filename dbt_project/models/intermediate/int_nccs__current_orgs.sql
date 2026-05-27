{{ config(materialized='table') }}

/*
    Intermediate: current (most-recent) NCCS record per EIN.

    Replaces the Python "current table" dual-write that ingestion.nccs.bulk used
    to compute (most-recent-per-EIN by org_year_last). That dedup is business
    logic and belongs here, not in the loader — the loader now lands only the
    raw history table. Uses the latest_per_natural_key macro.
*/

with

ranked as (
    {{ latest_per_natural_key(ref('stg_nccs__organizations'), 'ein', 'org_year_last') }}
),

final as (
    select
        ein,
        ntee_irs,
        ntee_nccs,
        nccs_level_1,
        org_name_current,
        city,
        state_code,
        org_year_first,
        org_year_last,
        latitude,
        longitude,
        total_revenue_recent,
        total_assets_recent,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from ranked
)

select * from final
