{{ config(materialized='table') }}

/*
    Intermediate (#1393): match each distinct USAspending recipient (name + state) to
    gold.jurisdictions by normalized name + state + kind (place vs county).

    Matching is deterministic and conservative:
      * kind is read from the recipient name ("CITY OF X", "X, MA, CITY OF", "X COUNTY",
        "COUNTY OF X", "X PARISH"); other recipients (housing authorities, districts,
        regional bodies) stay unmatched, never forced.
      * the normalized base name must equal the jurisdiction's normalized name in the
        same state and kind (cities/towns -> jurisdiction_type 'city'; counties -> 'county').
      * match_confidence 0.95 when exactly one jurisdiction fits, 0.60 when several share
        the name in the state (the most populous is picked and flagged by the lower score).
    Matching runs per distinct recipient (not per award) to keep the join small.
*/

with recipients as (
    select
        upper(recipient_name) as recipient_name_u,
        coalesce(recipient_state_code, pop_state_code) as state_code,
        min(recipient_name) as recipient_name
    from {{ ref('stg_usaspending__award') }}
    where recipient_name is not null
    group by 1, 2
),

kinded as (
    select
        *,
        case
            when recipient_name_u ~ '^COUNTY OF ' or recipient_name_u ~ ' (COUNTY|PARISH)( GOVERNMENT)?$' then 'county'
            when recipient_name_u ~ '^(CITY|TOWN|VILLAGE|BOROUGH) OF '
              or recipient_name_u ~ ', (CITY|TOWN|VILLAGE|BOROUGH) OF$'
              or recipient_name_u ~ ' (CITY|TOWN|VILLAGE)$' then 'place'
        end as kind
    from recipients
),

based as (
    select
        *,
        trim(regexp_replace(
            regexp_replace(
                case kind
                    when 'county' then regexp_replace(regexp_replace(recipient_name_u, '^COUNTY OF ', ''), ' (COUNTY|PARISH)( GOVERNMENT)?$', '')
                    else regexp_replace(regexp_replace(regexp_replace(recipient_name_u,
                            '^(CITY|TOWN|VILLAGE|BOROUGH) OF ', ''),
                            ', [A-Z]{2}, (CITY|TOWN|VILLAGE|BOROUGH) OF$', ''),
                            '(, (CITY|TOWN|VILLAGE|BOROUGH) OF| (CITY|TOWN|VILLAGE))$', '')
                end,
                '[^A-Z0-9 ]', '', 'g'),
            '\mSAINT\M', 'ST', 'g')) as base_name
    from kinded
    where kind is not null
),

jur as (
    select
        jurisdiction_id,
        state_code,
        jurisdiction_type as kind_type,
        population,
        trim(regexp_replace(
            regexp_replace(
                case when jurisdiction_type = 'county'
                     then regexp_replace(upper(name), ' (COUNTY|PARISH|BOROUGH|CENSUS AREA|MUNICIPALITY)$', '')
                     else upper(name) end,
                '[^A-Z0-9 ]', '', 'g'),
            '\mSAINT\M', 'ST', 'g')) as base_name
    from {{ ref('jurisdictions') }}
    where jurisdiction_type in ('city', 'county')
),

cands as (
    select
        b.recipient_name_u, b.state_code, b.recipient_name,
        j.jurisdiction_id, j.population,
        count(*) over (partition by b.recipient_name_u, b.state_code) as n_cands,
        row_number() over (
            partition by b.recipient_name_u, b.state_code
            order by j.population desc nulls last, j.jurisdiction_id
        ) as rn
    from based b
    join jur j
      on j.state_code = b.state_code
     and j.base_name = b.base_name
     and j.kind_type = case b.kind when 'county' then 'county' else 'city' end
)

select
    recipient_name_u,
    state_code,
    jurisdiction_id,
    case when n_cands = 1 then 0.95 else 0.60 end::numeric(3,2) as match_confidence
from cands
where rn = 1
