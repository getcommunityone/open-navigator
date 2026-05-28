{{
    config(
        materialized='table',
        schema='bronze',
        tags=['bronze', 'bls', 'cpi']
    )
}}

-- Bronze BLS CPI passthrough — exposes bronze.bronze_bls_cpi as a dbt model so
-- staging / intermediate models can ref() it. Data is populated by the
-- ingestion.bls.cpi pipeline (FETCH→data/cache/bls/, LAND→bronze; thin shim at
-- scripts/datasources/bls/load_bls_cpi.py is preserved for back-compat), not
-- by dbt.
--
-- One national series (default CUUR0000SA0, CPI-U NSA all items, U.S. city avg)
-- drives the frontend real-dollar toggle, applied uniformly across geographies.
-- period codes: M01..M12 = months, M13 = annual average. See
-- stg_bls__cpi_annual for the annual-average lens consumed downstream.

SELECT
    series_id,
    year,
    period,
    period_name,
    value,
    footnotes,
    loaded_at,
    last_updated
FROM {{ source('bronze', 'bronze_bls_cpi') }}

{% if target.name == 'neon_init' %}
WHERE 1 = 0
{% endif %}
