{{ config(materialized='table') }}

/*
    Mart (MDM): master address <-> COUNTY, as a many-to-many bridge.

    A ZIP can fall in several counties (28.8% of ZIPs do), so this keeps ONE ROW
    PER (master_address_id, county) candidate rather than forcing a single county.
    allocation_ratio (HUD tot_ratio) is the share of the ZIP in that county;
    is_dominant marks the largest share so simple queries can `where is_dominant`
    for a best-guess single county while the full set stays available.

    Precise disambiguation needs point-in-polygon on lat/lon (no PostGIS yet);
    until then ZIP allocation ratios are the signal.

    Grain: one row per (master_address_id, county_name).
*/

with addr as (
    select master_address_id, zip5, state_code
    from {{ ref('mdm_address') }}
    where zip5 is not null
),

zip_county as (
    select
        zip,
        county::text                                            as county_name,
        usps_zip_pref_city::text                                as usps_city,
        usps_zip_pref_state::text                               as usps_state,
        tot_ratio                                              as allocation_ratio,
        tot_ratio = max(tot_ratio) over (partition by zip)      as is_dominant
    from {{ source('bronze', 'bronze_jurisdictions_zip_county') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['a.master_address_id', 'zc.county_name']) }}
                                            as address_county_id,
    a.master_address_id,
    a.zip5,
    a.state_code,
    zc.county_name,
    zc.usps_city,
    zc.allocation_ratio,
    zc.is_dominant
from addr a
join zip_county zc on zc.zip = a.zip5
