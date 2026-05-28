{{
    config(
        materialized='table',
        schema='bronze',
        tags=['bronze', 'census', 'government_finance']
    )
}}

-- Bronze Census Finance Variables passthrough — exposes
-- bronze.bronze_census_finance_variables as a dbt model so staging /
-- intermediate models can ref() it. Data is populated by the
-- ingestion.census.govsstatefin_variables pipeline
-- (FETCH→data/cache/census/govsstatefin_variables/, LAND→bronze; thin shim
-- at scripts/datasources/census/download_census_finance_variables.py), not
-- by dbt.
--
-- Pairs with bronze_jurisdiction_tpc: the variable_code values in
-- this codebook map to the keys inside that table's raw_record JSONB.

SELECT
    dataset,
    variable_code,
    label,
    concept,
    predicate_type,
    var_group,
    var_limit,
    attributes,
    required,
    source_url,
    snapshot_at,
    raw_record,
    loaded_at,
    last_updated
FROM {{ source('bronze', 'bronze_census_finance_variables') }}

{% if target.name == 'neon_init' %}
WHERE 1 = 0
{% endif %}
