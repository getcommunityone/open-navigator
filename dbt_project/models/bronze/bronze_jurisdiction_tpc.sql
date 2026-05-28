{{
    config(
        materialized='table',
        schema='bronze',
        tags=['bronze', 'tpc', 'government_finance']
    )
}}

-- Bronze TPC Government Finance passthrough — exposes
-- bronze.bronze_jurisdiction_tpc as a dbt model so staging /
-- intermediate models can ref() it. Data is populated by the
-- ingestion.tpc.finance pipeline (FETCH→data/cache/tpc/, LAND→bronze; a
-- thin shim at scripts/datasources/tpc/load_tpc_finance.py is preserved for
-- back-compat), not by dbt.
--
-- raw_record carries the wide finance-variable space (~300 columns) verbatim
-- so downstream staging models can normalize the schema drift TPC reconciled
-- without us re-loading bronze every time the variable set evolves.

SELECT
    id_code,
    name,
    state_fips,
    state_code,
    gov_type,
    fiscal_year,
    population,
    raw_record,
    source_file,
    loaded_at,
    last_updated
FROM {{ source('bronze', 'bronze_jurisdiction_tpc') }}

{% if target.name == 'neon_init' %}
WHERE 1 = 0
{% endif %}
