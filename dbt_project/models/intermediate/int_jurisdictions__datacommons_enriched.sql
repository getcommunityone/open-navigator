{{ config(materialized='table') }}

/*
    Intermediate: APPLY the Google Data Commons demographic enrichment to the
    canonical jurisdiction list.

    Every int_jurisdictions row (the grain — one per jurisdiction_id) is kept and
    LEFT JOINed to stg_data_commons__jurisdiction on fips_code, gaining the latest
    demographic / economic / education / health / housing statistics (or NULLs
    when Data Commons has no observation for that FIPS). This is the join that
    resolves the bronze loader's FIPS-only rows to full jurisdiction identity
    (state / state_code / name / type) — a staging model can't do it because it
    may only read source(), not another model.

    Grain: one row per jurisdiction_id (LEFT JOIN does not fan out — the Data
    Commons staging model is unique on fips_code). `has_datacommons` flags whether
    enrichment was attached.
*/

with

jurisdictions as (
    select * from {{ ref('int_jurisdictions') }}
),

datacommons as (
    select * from {{ ref('stg_data_commons__jurisdiction') }}
),

joined as (
    select
        -- Jurisdiction identity (cast to text for a deterministic contract)
        j.jurisdiction_id::text          as jurisdiction_id,
        j.fips_code::text                as fips_code,
        j.state_code::text               as state_code,
        j.state::text                    as state,
        j.name::text                     as name,
        j.jurisdiction_type::text        as jurisdiction_type,

        -- Data Commons place id + enrichment-present flag
        dc.dcid                          as dcid,
        (dc.fips_code is not null)       as has_datacommons,

        -- Demographics
        dc.population,
        dc.population_male,
        dc.population_female,
        dc.median_age,
        dc.population_white,
        dc.population_black,
        dc.population_hispanic,
        dc.population_asian,

        -- Economic
        dc.median_household_income,
        dc.unemployment_rate,
        dc.poverty_count,
        dc.median_earnings,

        -- Education
        dc.bachelors_or_higher,
        dc.hs_grad_or_higher,

        -- Health
        dc.insured_count,
        dc.uninsured_count,

        -- Housing
        dc.median_home_price,
        dc.housing_units,
        dc.households,

        -- Provenance
        dc.source_retrieved_at,
        current_timestamp                as dbt_loaded_at
    from jurisdictions j
    left join datacommons dc
        on j.fips_code = dc.fips_code
)

select * from joined
