{{ config(materialized='view') }}

/*
    Staging: HUD CDBG activities (#1394). One row per IDIS activity (site duplicates collapsed).
    Source: bronze.bronze_hud_cdbg_activity (python -m ingestion.hud.load_cdbg).
    Types pinned here: dollars numeric, completion date real DATE, fiscal_year integer
    (federal FY, Oct-Sep, of the completion date; NULL while the activity is open).
    No street addresses or point locations are loaded.
*/

with src as (
    -- an activity with several sites is listed once per site with the SAME activity
    -- total, so keep one row per grantee x activity (the funding is not summed twice)
    select *, to_date(nullif(completed_date, ''), 'MM/DD/YYYY') as completed_on,
        row_number() over (partition by grantee_id, idis_activity_id order by objectid) as rn
    from {{ source('bronze', 'bronze_hud_cdbg_activity') }}
)

select
    (grantee_id || '-' || idis_activity_id)::text              as cdbg_activity_id,
    grantee_id::text                                           as grantee_id,
    grantee::text                                              as grantee_name,
    grantee_type::text                                         as grantee_type_code,
    idis_activity_id::text                                     as idis_activity_id,
    state_code::text                                           as state_code,
    activity_group::text                                       as activity_group,
    activity_name::text                                        as activity_name,
    funding_amount::numeric(16,2)                              as funding_amount,
    completed_on::date                                         as completed_on,
    (extract(year from completed_on)::int
        + case when extract(month from completed_on) >= 10 then 1 else 0 end)::integer as fiscal_year,
    ingestion_date::timestamp                                  as source_updated_at
from src
where rn = 1 and grantee_id is not null and idis_activity_id is not null
