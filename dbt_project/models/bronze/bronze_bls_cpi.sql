{{
    config(
        materialized='table',
        schema='bronze',
        tags=['bronze', 'bls', 'cpi']
    )
}}

-- Bronze BLS CPI passthrough — exposes bronze.bronze_bls_cpi as a dbt model
-- so staging / intermediate models can ref() it. Data is populated by the
-- loader script (scripts/datasources/bls/load_bls_cpi.py), not by dbt.

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
