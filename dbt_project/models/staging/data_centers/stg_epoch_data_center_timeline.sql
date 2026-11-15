/*
    Staging: Epoch AI data center timelines (DC-4.1, #249). CC BY 4.0, credit Epoch AI.
    Grain: one row per site per as-of date, from the newest snapshot that has that site.
    Numbers are guarded casts: free text becomes null, never a guess.
*/

with rows as (
    select data_center, snapshot_on, record, loaded_at
    from {{ source('bronze', 'bronze_epoch_data_center_timelines') }}
    where nullif(btrim(data_center), '') is not null
),

-- Use each site's newest snapshot only, so an old estimate doesn't mix with a new one.
site_snapshot as (
    select data_center, max(snapshot_on) as snapshot_on
    from rows
    group by data_center
),

typed as (
    select
        r.data_center                                                                   as name,
        {{ safe_iso_date("btrim(r.record ->> 'Date')") }}                               as as_of_on,
        nullif(btrim(r.record ->> 'Construction status'), '')                           as construction_note,
        {{ safe_nonnegative_double("replace(btrim(r.record ->> 'Buildings operational'), ',', '')") }} as buildings_operational,
        {{ safe_nonnegative_double("replace(btrim(r.record ->> 'IT power (MW)'), ',', '')") }}         as it_power_mw,
        r.loaded_at
    from rows as r
    inner join site_snapshot as s
        on s.data_center = r.data_center and s.snapshot_on = r.snapshot_on
)

select distinct on (name, as_of_on)
    name,
    as_of_on,
    construction_note,
    buildings_operational,
    it_power_mw
from typed
where as_of_on is not null
order by name, as_of_on, loaded_at desc
