{{
  config(
    materialized='table',
    tags=['marts', 'finance', 'jurisdiction'],
    indexes=[
      {'columns': ['jurisdiction_id', 'fiscal_year'], 'type': 'btree'},
      {'columns': ['grantee_id'], 'type': 'btree'}
    ]
  )
}}

/*
    cdbg_activity (#1394): one row per HUD CDBG activity (IDIS). Grain: grantee x
    activity (cdbg_activity_id = grantee_id-idis_activity_id, the PK). fiscal_year is the
    federal fiscal year of the completion date and is NULL while the activity is open.
    jurisdiction_id is NULL when the grantee could not be matched with confidence.
    Gold only (about 400k rows); the served slice is cdbg_activity_summary.
*/

select
    a.cdbg_activity_id::text           as cdbg_activity_id,
    m.jurisdiction_id::text            as jurisdiction_id,
    m.match_confidence::numeric        as match_confidence,
    a.grantee_id::text                 as grantee_id,
    a.grantee_name::text               as grantee_name,
    a.state_code::text                 as state_code,
    s.state_name::text                 as state,
    a.activity_group::text             as activity_group,
    a.activity_name::text              as activity_name,
    a.funding_amount::numeric          as funding_amount,
    a.completed_on::date               as completed_on,
    a.fiscal_year::integer             as fiscal_year,
    a.source_updated_at::timestamp     as source_updated_at
from {{ ref('stg_hud_cdbg__activity') }} a
left join {{ ref('int_hud_cdbg_grantee__jurisdiction_match') }} m
  on m.grantee_id = a.grantee_id and m.state_code = a.state_code
left join (select state_code, max(state_name) as state_name from {{ ref('jurisdictions') }} group by 1) s
  on s.state_code = a.state_code
