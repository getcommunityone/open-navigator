{{ config(materialized='table') }}

/*
    Mart (MDM): organization <-> address, dated.

    A source that lands in BOTH the org pool and the address pool keyed on the
    same source_pk links the two masters directly. Today:

      - bronze_locations (stg_locations__org + stg_locations__address): a facility
        org `located_at` a master address, as of as_of_year.
      - bronze_addresses (stg_parcels__org + stg_parcels__address): an
        organization `parcel_owner` of a master address (the business/government
        owners; person owners go to mdm_bridge_person_address). Parcels carry no
        date, so as_of_year is null.

    One row per distinct (master_org_id, master_address_id); when a pair appears
    from both sources the dated (located_at) row wins the relationship label.

    Extendable: NCCS nonprofit addresses (990 situs) once they land in the address
    pool would add the nonprofit org<->address links here.
*/

with located as (
    select
        o.master_org_id,
        a.master_address_id,
        'located_at'        as relationship,
        o.as_of_year
    from (
        select master_org_id, source_pk, as_of_year
        from {{ ref('int_organizations__clustered') }}
        where source_system = 'bronze_locations'
    ) o
    join (
        select master_address_id, source_pk
        from {{ ref('int_addresses__clustered') }}
        where source_system = 'bronze_locations'
    ) a on a.source_pk = o.source_pk
),

parcel_owned as (
    select
        o.master_org_id,
        a.master_address_id,
        'parcel_owner'      as relationship,
        null::int           as as_of_year
    from (
        select master_org_id, source_pk
        from {{ ref('int_organizations__clustered') }}
        where source_system = 'bronze_addresses'
    ) o
    join (
        select master_address_id, source_pk
        from {{ ref('int_addresses__clustered') }}
        where source_system = 'bronze_addresses'
    ) a on a.source_pk = o.source_pk
),

combined as (
    select * from located
    union all
    select * from parcel_owned
)

select distinct on (master_org_id, master_address_id)
    md5(master_org_id || '|' || master_address_id)  as org_address_id,
    master_org_id,
    master_address_id,
    relationship,
    as_of_year
from combined
-- dated located_at (real as_of_year) wins the label over null-dated parcel_owner
order by master_org_id, master_address_id, as_of_year desc nulls last
