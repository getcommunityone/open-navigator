{{
  config(
    materialized='table',
    contract={'enforced': True}
  )
}}

/*
    Mart: public.nonprofit_sector_revenue — a SINGLE-ROW pre-aggregation of the
    U.S. 990 nonprofit-sector revenue decomposition (contributions / program-
    service / total + org count), sourced from mdm_organization_nonprofit.

    WHY THIS EXISTS: the /api/money-flow "economy" lens needs this national
    total on every page load. Computing it inline (SUM over the 3.6M-row MDM
    satellite) seq-scanned the whole table on every request (~590ms). This mart
    collapses it to one tuple so the serving query reads a single row.

    The figure is genuinely NATIONAL — the satellite has no usable state column,
    so this lens is always the U.S. sector and there is nothing to scope by
    jurisdiction. Rebuilt whenever mdm_organization_nonprofit rebuilds; the
    numbers trace 1:1 to real 990 e-file aggregates (no fabrication).
*/

select
    'us'::text                                                       as scope,
    coalesce(sum(gt990_total_contributions), 0)::bigint              as contributions,
    coalesce(sum(gt990_program_service_revenue), 0)::bigint          as program_service_revenue,
    coalesce(sum(coalesce(gt990_total_revenue, revenue)), 0)::bigint as total_revenue,
    count(*)::bigint                                                 as org_count,
    current_timestamp                                               as dbt_loaded_at
from {{ ref('mdm_organization_nonprofit') }}
