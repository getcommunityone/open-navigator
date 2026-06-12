{{
  config(
    materialized='table',
    tags=['marts', 'tax', 'sales_tax', 'production'],
    unique_key='state_sales_tax_rate_id',
    indexes=[
      {'columns': ['state_code'], 'unique': True}
    ]
  )
}}

/*
public.state_sales_tax_rate — combined state + average-local general sales-tax
rate per state (50 states + DC), from the Tax Foundation report "State and Local
Sales Tax Rates, 2026" (seed: tax_foundation_sales_tax_rates). Powers the sales-
tax line of the homepage "how much of your money is on the line" estimate.

GRAIN: one row per state_code.

WHY NOT CENSUS: the Census Bureau publishes sales-tax REVENUE (dollars collected,
already in jurisdiction_finance), never statutory RATES. The Tax Foundation table
is the standard free source for combined rates.

PRECISION: this is STATE + population-weighted AVERAGE-local — not a city-exact
rate. A resident's true local rate varies by city; the widget uses this combined
rate as the honest state-level approximation. avg_local can be slightly negative
where a state mandates reduced-rate zones (e.g. NJ UEZ) — preserved as published.

RATE FORMS: *_pct columns are percentages exactly as published (9.46 = 9.46%);
combined_sales_tax_rate is the same value as a FRACTION (0.0946) ready to multiply
by a spending amount.
*/

select
    s.state_code                                        as state_sales_tax_rate_id,
    s.state_code,
    s.state,
    s.state_sales_tax_rate                              as state_sales_tax_rate_pct,
    s.avg_local_sales_tax_rate                          as avg_local_sales_tax_rate_pct,
    s.combined_sales_tax_rate                           as combined_sales_tax_rate_pct,
    round(s.combined_sales_tax_rate / 100.0, 6)         as combined_sales_tax_rate,
    s.max_local_sales_tax_rate                          as max_local_sales_tax_rate_pct,
    s.combined_rank,
    s.as_of_date,
    s.vintage_year,
    'Tax Foundation, State and Local Sales Tax Rates, 2026'::text as source,
    current_timestamp                                   as published_at
from {{ ref('tax_foundation_sales_tax_rates') }} s
