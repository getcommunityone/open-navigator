{{ config(materialized='table') }}

/*
    Mart (MDM): person <-> address relationships.

    The person and address pools resolve separately, but they connect where a
    single source row carries BOTH a person and an address. Today that is parcel
    records (bronze_addresses): the owner_name (a person occurrence) and the situs
    (an address occurrence) share the same source_pk, so the owner is linked to
    the master address they own/occupy.

    Grain: one row per parcel owner<->address link. Extend with other dual-entity
    sources (e.g. contributor mailing addresses) as they are added to both pools.
*/

with persons as (
    select person_uid, source_system, source_pk, raw_name
    from {{ ref('int_persons__unioned') }}
    where source_system = 'bronze_addresses'
),

addresses as (
    select source_system, source_pk, address_uid, master_address_id
    from {{ ref('int_addresses__clustered') }}
    where source_system = 'bronze_addresses'
)

select
    p.person_uid,
    p.raw_name                  as person_name,
    'parcel_owner'              as relationship,
    a.address_uid,
    a.master_address_id
from persons p
join addresses a
    on a.source_system = p.source_system
   and a.source_pk = p.source_pk
