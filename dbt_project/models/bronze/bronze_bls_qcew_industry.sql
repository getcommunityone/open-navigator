{{
    config(
        materialized='table',
        schema='bronze',
        tags=['bronze', 'bls', 'qcew']
    )
}}

-- Bronze BLS QCEW passthrough (#1019): exposes bronze.bronze_bls_qcew_industry as a dbt model so staging can ref()
-- it. Populated by ingestion.bls.qcew (FETCH -> data/cache/bls/qcew/, LAND -> bronze), not by dbt.

SELECT
    area_fips,
    own_code,
    industry_code,
    agglvl_code,
    size_code,
    year,
    qtr,
    disclosure_code,
    annual_avg_estabs,
    annual_avg_emplvl,
    total_annual_wages,
    annual_avg_wkly_wage,
    avg_annual_pay,
    oty_annual_avg_emplvl_chg,
    oty_annual_avg_emplvl_pct_chg,
    source_url,
    loaded_at
FROM {{ source('bronze', 'bronze_bls_qcew_industry') }}
