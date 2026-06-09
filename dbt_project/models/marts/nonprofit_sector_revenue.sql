{{
  config(
    materialized='table',
    contract={'enforced': True}
  )
}}

/*
    Mart: public.nonprofit_sector_revenue — a pre-aggregation of the 990
    nonprofit-sector revenue decomposition (contributions / program-service /
    total + org count), sourced from mdm_organization_nonprofit, at THREE grains:
      - scope = 'us'                     : the national total (one row)
      - scope = 'state'                  : one row per state_code
      - scope = 'city'                   : one row per (state_code, city_norm)

    WHY THIS EXISTS: the /api/money-flow "economy" lens needs this decomposition
    on every page load, scoped to the visitor's jurisdiction. Computing it inline
    (SUM over the 3.6M-row MDM satellite) seq-scanned the whole table per request
    (~590ms). This mart collapses each grain to one tuple so the serving query
    reads a single row by `scope_key`.

    GEOGRAPHY: the satellite itself has no state column, but it is 1:1 with
    mdm_organization on master_org_id, which carries state_code / city_norm
    (~99.9% populated). Joining there is what lets this lens be jurisdiction-aware
    instead of national-only. Numbers trace 1:1 to real 990 e-file aggregates
    (no fabrication). Rebuilt whenever mdm_organization_nonprofit rebuilds.

    scope_key (PK) encodes grain + place so the API can look up the most specific
    available row and fall back ('city:AL|tuscaloosa' -> 'state:AL' -> 'us').

    The three grains are built as explicit UNIONs (not GROUPING SETS) so that
    orgs with a state but no city can't alias a 'state' row into two PKs.
*/

with joined as (
    select
        o.state_code,
        o.city_norm,
        n.gt990_total_contributions                       as contributions,
        n.gt990_program_service_revenue                   as program_service_revenue,
        coalesce(n.gt990_total_revenue, n.revenue)        as total_revenue
    from {{ ref('mdm_organization_nonprofit') }} n
    join {{ ref('mdm_organization') }} o using (master_org_id)
),

us as (
    select
        'us'::text                                          as scope_key,
        'us'::text                                          as scope,
        null::text                                          as state_code,
        null::text                                          as city_norm,
        coalesce(sum(contributions), 0)::bigint             as contributions,
        coalesce(sum(program_service_revenue), 0)::bigint   as program_service_revenue,
        coalesce(sum(total_revenue), 0)::bigint             as total_revenue,
        count(*)::bigint                                    as org_count
    from joined
),

per_state as (
    select
        'state:' || state_code                              as scope_key,
        'state'::text                                       as scope,
        state_code,
        null::text                                          as city_norm,
        coalesce(sum(contributions), 0)::bigint             as contributions,
        coalesce(sum(program_service_revenue), 0)::bigint   as program_service_revenue,
        coalesce(sum(total_revenue), 0)::bigint             as total_revenue,
        count(*)::bigint                                    as org_count
    from joined
    where state_code is not null
    group by state_code
),

per_city as (
    select
        'city:' || state_code || '|' || city_norm           as scope_key,
        'city'::text                                        as scope,
        state_code,
        city_norm,
        coalesce(sum(contributions), 0)::bigint             as contributions,
        coalesce(sum(program_service_revenue), 0)::bigint   as program_service_revenue,
        coalesce(sum(total_revenue), 0)::bigint             as total_revenue,
        count(*)::bigint                                    as org_count
    from joined
    where state_code is not null and city_norm is not null
    group by state_code, city_norm
)

select scope_key, scope, state_code, city_norm,
       contributions, program_service_revenue, total_revenue, org_count,
       current_timestamp as dbt_loaded_at
from us
union all
select scope_key, scope, state_code, city_norm,
       contributions, program_service_revenue, total_revenue, org_count,
       current_timestamp as dbt_loaded_at
from per_state
union all
select scope_key, scope, state_code, city_norm,
       contributions, program_service_revenue, total_revenue, org_count,
       current_timestamp as dbt_loaded_at
from per_city
