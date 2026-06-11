{{
  config(
    materialized='table',
    tags=['marts', 'finance', 'jurisdiction', 'production'],
    unique_key='jurisdiction_finance_id',
    indexes=[
      {'columns': ['jurisdiction_id'], 'type': 'btree'},
      {'columns': ['state_code', 'gov_type'], 'type': 'btree'},
      {'columns': ['geoid'], 'type': 'btree'}
    ]
  )
}}

/*
public.jurisdiction_finance — one row per government (latest fiscal year) with
headline revenue/expenditure/tax totals and an 8-bucket expenditure-by-function
breakdown, sourced from the U.S. Census Annual Survey of State & Local Government
Finances (via TPC/Urban Institute). Powers the homepage "where your local tax
money goes" breakdown and "how much you pay in local taxes" (per-capita) figures.

GRAIN: one row per government (gov_type + id_code), most recent fiscal_year.

UNITS: all dollar columns are WHOLE DOLLARS. The Census source stores thousands;
we scale x1000 here so the API serves real dollar figures directly. Missing
source values are NULL (never 0) so "no data" stays honest.

EXPENDITURE DECOMPOSITION (so the API can reconcile):
  total_expenditure = direct_expenditure
                    + intergovernmental_expenditure
                    + insurance_trust_expenditure  (+ minor rounding)
  The 8 category columns (education ... other_debt) SUM TO direct_expenditure by
  construction — they are the "services" split. Use direct_expenditure as the
  denominator for the category pie; total_expenditure is the all-in figure.

KEYS (per CLAUDE.md, enforced as Postgres constraints via contract):
  - PK: jurisdiction_finance_id = md5(gov_type || '|' || id_code).
  - FK: jurisdiction_id -> public.jurisdictions.jurisdiction_id, NULLABLE.
    Matched by FIPS geoid (state_fips||place / state_fips||county / state_fips for
    states) — 99.9% of cities, 100% of AL counties/states matched. Unmatched
    governments (special districts, a handful of place-fips gaps) keep NULL rather
    than mis-joining; the API can still serve them by state_code + name + gov_type.
*/

with fin as (
    select * from {{ ref('stg_jurisdiction_finance') }}
),

juris as (
    select jurisdiction_id, geoid, jurisdiction_type
    from {{ ref('jurisdictions') }}
),

matched as (
    select
        fin.*,
        -- FIPS geoid the jurisdictions mart uses, by gov level.
        case
            when fin.gov_type = 'state'  then lpad(fin.state_fips, 2, '0')
            when fin.gov_type = 'county' then lpad(fin.state_fips, 2, '0') || lpad(fin.fips_county, 3, '0')
            when fin.gov_type = 'city'   and coalesce(fin.fips_place, '0') not in ('0', '00000')
                                         then lpad(fin.state_fips, 2, '0') || lpad(fin.fips_place, 5, '0')
            else null
        end as match_geoid,
        case
            when fin.gov_type = 'state'  then 'state'
            when fin.gov_type = 'county' then 'county'
            when fin.gov_type = 'city'   then 'city'
            else null
        end as match_jurisdiction_type
    from fin
)

select
    md5(m.gov_type || '|' || m.id_code)                         as jurisdiction_finance_id,
    j.jurisdiction_id                                           as jurisdiction_id,
    m.match_geoid                                               as geoid,
    m.id_code                                                   as tpc_id_code,
    m.jurisdiction_name,
    m.gov_type,
    m.state_code::text                                          as state_code,
    {{ state_code_to_name('m.state_code') }}                    as state,
    m.fiscal_year,
    m.population,

    -- Headline totals (whole dollars)
    (m.total_revenue_k        * 1000)::bigint                   as total_revenue,
    (m.total_expenditure_k    * 1000)::bigint                   as total_expenditure,
    (m.direct_expenditure_k   * 1000)::bigint                   as direct_expenditure,
    (m.ig_expenditure_k       * 1000)::bigint                   as intergovernmental_expenditure,
    (m.insur_trust_expenditure_k * 1000)::bigint                as insurance_trust_expenditure,

    -- Taxes (whole dollars). other_taxes = total - property - (gen+select sales)
    -- when derivable, clamped at >= 0 (Census subcategories can leave a residual).
    (m.total_taxes_k          * 1000)::bigint                   as total_taxes,
    (m.property_tax_k         * 1000)::bigint                   as property_tax,
    ((coalesce(m.general_sales_tax_k,0) + coalesce(m.select_sales_tax_k,0)) * 1000)::bigint as sales_tax,
    case
        when m.total_taxes_k is null then null
        else greatest(
            m.total_taxes_k
            - coalesce(m.property_tax_k, 0)
            - coalesce(m.general_sales_tax_k, 0)
            - coalesce(m.select_sales_tax_k, 0),
            0
        ) * 1000
    end::bigint                                                 as other_taxes,

    -- Per-capita local tax burden (whole dollars/person), NULL when pop missing.
    case
        when m.population is null or m.population = 0 or m.total_taxes_k is null then null
        else round((m.total_taxes_k * 1000.0) / m.population, 2)
    end                                                         as taxes_per_capita,

    -- 8 expenditure categories (whole dollars). Sum to direct_expenditure.
    (m.cat_education_k        * 1000)::bigint                   as exp_education,
    (m.cat_public_safety_k   * 1000)::bigint                   as exp_public_safety,
    (m.cat_infrastructure_k  * 1000)::bigint                   as exp_infrastructure_highways,
    (m.cat_parks_rec_k       * 1000)::bigint                   as exp_parks_recreation,
    (m.cat_health_welfare_k  * 1000)::bigint                   as exp_health_welfare,
    (m.cat_utilities_k       * 1000)::bigint                   as exp_utilities,
    (m.cat_admin_gov_k       * 1000)::bigint                   as exp_administration_government,
    ((coalesce(m.cat_other_debt_base_k,0) + coalesce(m.cat_other_debt_residual_k,0)) * 1000)::bigint as exp_other_debt

from matched m
left join juris j
    on  j.geoid = m.match_geoid
    and j.jurisdiction_type = m.match_jurisdiction_type
-- school_district included so the money modal can stack a resident's full
-- local government: city + county + their school district (which is where K-12
-- spending actually lives — the city/county "education" line is tiny).
where m.gov_type in ('state', 'county', 'city', 'school_district')
  -- A handful of defunct interstate "joint" school districts carry no
  -- state_code; drop them (state_code is NOT NULL by contract).
  and m.state_code is not null
