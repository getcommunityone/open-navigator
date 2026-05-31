{{ config(materialized='table') }}

/*
    Mart (MDM Layer 5): one golden record per resolved address.

    Survivorship picks the most-complete occurrence per master_address_id:
    prefer rows that have a street number, ZIP, and geocode, then by source trust
    (parcels > facilities > AI-extracted), then a deterministic id tiebreak.
    n_occurrences / n_sources expose how much evidence backs each master address.

    Serve address-map search from here; join back to sources via bridge_address_xref.
*/

with clustered as (
    select * from {{ ref('int_addresses__clustered') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by master_address_id
            order by
                (street_number is not null) desc,
                (zip5 is not null) desc,
                (lat is not null) desc,
                case source_system
                    when 'bronze_addresses' then 1       -- parcels: structured situs
                    when 'bronze_locations' then 2       -- curated facilities (geocoded)
                    when 'bronze_places_from_ai' then 3  -- AI-extracted: lowest trust
                    else 4
                end,
                address_uid
        ) as rn
    from clustered
),

golden as (
    select * from ranked where rn = 1
),

evidence as (
    select
        master_address_id,
        count(*)                          as n_occurrences,
        count(distinct source_system)     as n_sources
    from clustered
    group by 1
)

select
    g.master_address_id,
    g.address_norm,
    g.street_number,
    g.street_name,
    g.city_norm,
    g.state_code,
    g.zip5,
    g.lat,
    g.lon,
    e.n_occurrences,
    e.n_sources
from golden g
join evidence e using (master_address_id)
