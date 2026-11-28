{{ config(materialized='view', tags=['staging', 'bodies', 'openstates']) }}

/*
staging.stg_openstates__chamber_member (#1443): state legislators' seats in their chamber (OpenStates memberships of
an 'upper' or 'lower' organization), one row per OCD membership. stg_openstates__official drops these (they carry
no role), so they are read here. Current = no end date, or an end date today or later.
SOURCE: bronze.bronze_officials_openstates.
*/

select
    s.ocd_membership_id::text                                                    as ocd_membership_id,
    s.ocd_person_id::text                                                        as ocd_person_id,
    btrim(s.full_name)::text                                                     as full_name,
    nullif(btrim(s.party), '')::text                                             as party,
    nullif(btrim(s.district), '')::text                                          as district,
    btrim(s.organization_classification)::text                                   as chamber,
    nullif(btrim(s.organization_name), '')::text                                 as chamber_name,
    upper((regexp_match(s.ocd_jurisdiction_id, '/(?:state|territory|district):([a-z]{2})(?:/|$)'))[1])::text
                                                                                 as state_code,
    case when s.start_date ~ '^\d{4}-\d{2}-\d{2}' then substring(s.start_date from 1 for 10)::date end as start_date,
    case when s.end_date ~ '^\d{4}-\d{2}-\d{2}' then substring(s.end_date from 1 for 10)::date end     as end_date
from {{ source('bronze', 'bronze_officials_openstates') }} as s
where btrim(s.organization_classification) in ('upper', 'lower')
  and nullif(btrim(s.full_name), '') is not null
  and (nullif(btrim(s.end_date), '') is null or s.end_date >= to_char(current_date, 'YYYY-MM-DD'))
