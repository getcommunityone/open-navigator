{{ config(materialized='view') }}

/*
    Staging: Google Data Commons jurisdiction enrichment.

    Source: bronze.bronze_jurisdiction_datacommons — landed by
    ingestion.google_data_commons.bronze from the Data Commons v2 observation
    API (/v2/observation). One row per jurisdiction FIPS code, carrying the
    latest demographic / economic / education / health / housing statistics.

    Follows Stage 3 conventions (dbt_project/CONVENTIONS.md):
      - Naming: stg_<source>__<entity>
      - Reads only from source(), never from another model
      - Pinned types via the contract in _schema_stg_data_commons.yml
      - Four-CTE template: source -> renamed -> filtered -> final

    Notes:
      - `fips_code` is the natural/primary key (5-digit county or 7-digit place).
        `state_fips_code` is derived as its first two digits; the full `state` /
        `state_code` mapping is resolved downstream by joining int_jurisdictions
        (a staging model must not read another model).
      - The bronze metric columns are DOUBLE PRECISION for raw fidelity; counts
        are conceptually integers but kept as-is here (no lossy casting in
        staging). Rates (e.g. unemployment_rate) are genuinely fractional.
      - `stats` is the full {statvar: value} JSONB kept for fidelity / any
        variable not promoted to a typed column.
*/

with

source as (
    select *
    from {{ source('bronze', 'bronze_jurisdiction_datacommons') }}
),

renamed as (
    select
        -- Identity
        nullif(trim(fips_code), '')              as fips_code,
        left(nullif(trim(fips_code), ''), 2)     as state_fips_code,
        nullif(trim(dcid), '')                   as dcid,

        -- Demographics
        population                               as population,
        population_male                          as population_male,
        population_female                        as population_female,
        median_age                               as median_age,
        population_white                         as population_white,
        population_black                         as population_black,
        population_hispanic                      as population_hispanic,
        population_asian                         as population_asian,

        -- Economic
        median_household_income                  as median_household_income,
        unemployment_rate                        as unemployment_rate,
        poverty_count                            as poverty_count,
        median_earnings                          as median_earnings,

        -- Education
        bachelors_or_higher                      as bachelors_or_higher,
        hs_grad_or_higher                        as hs_grad_or_higher,

        -- Health
        insured_count                            as insured_count,
        uninsured_count                          as uninsured_count,

        -- Housing
        median_home_price                        as median_home_price,
        housing_units                            as housing_units,
        households                               as households,

        -- Provenance
        stats                                    as stats,
        retrieval_date                           as source_retrieved_at,
        ingestion_date                           as source_ingested_at
    from source
),

filtered as (
    select *
    from renamed
    where fips_code is not null
),

final as (
    select
        fips_code,
        state_fips_code,
        dcid,
        population,
        population_male,
        population_female,
        median_age,
        population_white,
        population_black,
        population_hispanic,
        population_asian,
        median_household_income,
        unemployment_rate,
        poverty_count,
        median_earnings,
        bachelors_or_higher,
        hs_grad_or_higher,
        insured_count,
        uninsured_count,
        median_home_price,
        housing_units,
        households,
        stats,
        source_retrieved_at,
        source_ingested_at,
        current_timestamp as dbt_loaded_at
    from filtered
)

select * from final
