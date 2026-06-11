{{
  config(
    materialized='table',
    tags=['marts', 'finance', 'jurisdiction', 'production'],
    unique_key='jurisdiction_finance_category_id',
    indexes=[
      {'columns': ['jurisdiction_finance_id'], 'type': 'btree'}
    ]
  )
}}

/*
public.jurisdiction_finance_category — tidy/long companion to
public.jurisdiction_finance: one row per (government x expenditure category) with
the dollar amount and its share of DIRECT expenditure. Drives the "where your tax
money goes" pie/bar without the API having to unpivot the wide mart.

GRAIN: one row per (jurisdiction_finance_id, category). Categories with a NULL
amount in the wide mart are OMITTED (honest missing — no zero-filled rows).

share_pct = amount / direct_expenditure * 100 (0..100), NULL when
direct_expenditure is NULL/0. Shares across a government's categories sum to ~100.

KEYS (per CLAUDE.md, enforced via contract):
  - PK: jurisdiction_finance_category_id = md5(jurisdiction_finance_id || '|' || category_code).
  - FK: jurisdiction_finance_id -> public.jurisdiction_finance.jurisdiction_finance_id. NOT NULL.
*/

with f as (
    select * from {{ ref('jurisdiction_finance') }}
),

unpivoted as (
    {% set cats = [
        ('education',                'Education',                  'exp_education'),
        ('public_safety',            'Public Safety',              'exp_public_safety'),
        ('infrastructure_highways',  'Infrastructure & Highways',  'exp_infrastructure_highways'),
        ('parks_recreation',         'Parks & Recreation',         'exp_parks_recreation'),
        ('health_welfare',           'Health & Welfare',           'exp_health_welfare'),
        ('utilities',                'Utilities',                  'exp_utilities'),
        ('administration_government','Administration & Government','exp_administration_government'),
        ('other_debt',               'Other & Debt',               'exp_other_debt')
    ] %}
    {% for code, label, col in cats %}
    select
        jurisdiction_finance_id,
        '{{ code }}'::text   as category_code,
        '{{ label }}'::text  as category,
        {{ col }}            as amount,
        direct_expenditure
    from f
    where {{ col }} is not null
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select
    md5(jurisdiction_finance_id || '|' || category_code)        as jurisdiction_finance_category_id,
    jurisdiction_finance_id,
    category_code,
    category,
    amount,
    case
        when direct_expenditure is null or direct_expenditure = 0 then null
        else round(100.0 * amount / direct_expenditure, 2)
    end                                                         as share_pct
from unpivoted
