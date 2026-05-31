{{ config(materialized='table') }}

/*
    Mart (MDM): organization <-> address, dated.

    bronze_locations is in BOTH the org pool (stg_locations__org) and the address
    pool (stg_locations__address) keyed on the same source_pk, so the two masters
    link directly through it — a facility org located at a master address, as of
    as_of_year. One row per distinct (master_org_id, master_address_id).

    Extendable: NCCS nonprofit addresses (990 situs) once they land in the address
    pool would add the nonprofit org<->address links here.
*/

with org as (
    select master_org_id, source_pk, as_of_year
    from {{ ref('int_organizations__clustered') }}
    where source_system = 'bronze_locations'
),

addr as (
    select master_address_id, source_pk
    from {{ ref('int_addresses__clustered') }}
    where source_system = 'bronze_locations'
)

select distinct on (o.master_org_id, a.master_address_id)
    md5(o.master_org_id || '|' || a.master_address_id)  as org_address_id,
    o.master_org_id,
    a.master_address_id,
    'located_at'                                        as relationship,
    o.as_of_year
from org o
join addr a on a.source_pk = o.source_pk
order by o.master_org_id, a.master_address_id, o.as_of_year desc nulls last
