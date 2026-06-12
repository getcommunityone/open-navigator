{{
  config(
    materialized='table',
    tags=['marts', 'census', 'property_tax', 'production'],
    unique_key='jurisdiction_property_tax_rate_id',
    indexes=[
      {'columns': ['geoid'], 'type': 'btree'},
      {'columns': ['jurisdiction_id'], 'type': 'btree'},
      {'columns': ['state_code', 'geography_type'], 'type': 'btree'}
    ]
  )
}}

/*
public.jurisdiction_property_tax_rate — effective property-tax rate per place and
county, from ACS B25103 (median real estate taxes paid) ÷ B25077 (median home
value), 5-year estimates. Powers the homepage "how much of your money is on the
line" property-tax estimate.

GRAIN: one row per (geography_type, geoid, acs_vintage_year).

EFFECTIVE RATE — IMPORTANT MODELING NOTE
  B25103 is the household's TOTAL annual real-estate tax bill, which already
  combines every overlapping levy (county + municipal + school district + special
  districts). So:
    - place grain  -> the ALL-IN effective rate for a resident INSIDE that city.
    - county grain -> the ALL-IN effective rate for a resident in the
      UNINCORPORATED part of that county.
  These are NOT additive layers — do not sum a city rate on top of its county
  rate (that double-counts). For a city resident use the place row; for an
  unincorporated resident use the county row.

effective_property_tax_rate = median_real_estate_taxes_paid / median_home_value
  (a fraction, e.g. 0.0048 = 0.48%). NULL when home value is missing/zero or
  taxes are suppressed — honest "no data", never 0.

jurisdiction_id is the FK into public.jurisdictions (matched by geoid + type;
place -> 'city'). NULL where the ACS geography has no jurisdiction row yet; the
rate is still served by geoid.
*/

with acs as (
    select * from {{ ref('stg_acs_property_tax') }}
),

acs_keyed as (
    select
        a.*,
        {{ state_fips_to_code('a.state_fips') }}            as state_code,
        -- jurisdictions stores places as type 'city'
        case when a.geography_type = 'place' then 'city' else a.geography_type end
                                                            as match_jurisdiction_type
    from acs a
),

juris as (
    select jurisdiction_id, geoid, jurisdiction_type
    from {{ ref('jurisdictions') }}
)

select
    k.geography_type || ':' || k.geoid || ':' || k.acs_vintage_year::text
                                                        as jurisdiction_property_tax_rate_id,
    j.jurisdiction_id,
    k.geography_type,
    k.geoid,
    k.state_fips,
    k.state_code,
    {{ state_code_to_name('k.state_code') }}            as state,
    k.name,
    k.acs_vintage_year,
    k.median_real_estate_taxes_paid,
    k.median_home_value,
    round(
        k.median_real_estate_taxes_paid::numeric / nullif(k.median_home_value, 0),
        6
    )                                                   as effective_property_tax_rate,
    current_timestamp                                   as published_at
from acs_keyed k
left join juris j
    on  j.geoid = k.geoid
    and j.jurisdiction_type = k.match_jurisdiction_type
