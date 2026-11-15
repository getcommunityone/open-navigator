/*
    Data center sites (DC-4.1, #249). Grain: one row per site.
    Source: Epoch AI, "AI data centers" (https://epoch.ai/data/data-centers), CC BY 4.0.
    Every row carries the credit (source_name, source_url, license, attribution).

    Status comes from Epoch's dated timeline rows; Epoch publishes no status field:
      operating           latest row on or before today has a building operational
      under_construction  a dated row on or before today, nothing operational yet
      planned             only future-dated rows
      null                no timeline rows at all (shown as "Status not published")
    A site missing from the newest download has status = 'no_longer_listed' and keeps
    last_known_status and last_seen_on, so it stays visible. Epoch has no cancelled flag,
    so this model never says "cancelled".

    No FK: Epoch gives a street address, not a jurisdiction. state_code comes from the
    address when it ends in a US state code.
*/

with sites as (
    select * from {{ ref('stg_epoch_data_center') }}
),

timeline as (
    select * from {{ ref('stg_epoch_data_center_timeline') }}
),

latest_past as (
    select distinct on (name) name, as_of_on, construction_note, buildings_operational, it_power_mw
    from timeline
    where as_of_on <= current_date
    order by name, as_of_on desc
),

first_future as (
    select distinct on (name) name, as_of_on, construction_note
    from timeline
    where as_of_on > current_date
    order by name, as_of_on asc
),

classified as (
    select
        s.*,
        case
            when p.name is not null and coalesce(p.buildings_operational, 0) > 0 then 'operating'
            when p.name is not null then 'under_construction'
            when f.name is not null then 'planned'
        end                                            as known_status,
        coalesce(p.as_of_on, f.as_of_on)               as status_as_of,
        coalesce(p.construction_note, f.construction_note) as construction_note,
        p.it_power_mw
    from sites as s
    left join latest_past as p on p.name = s.name
    left join first_future as f on f.name = s.name
)

select
    md5('epoch|' || name)::text                         as data_center_site_id,
    name::text                                          as site_name,
    owner::text                                         as owner,
    users::text                                         as users,
    project::text                                       as project,
    address::text                                       as address,
    country::text                                       as country,
    state_code::text                                    as state_code,
    case when state_code is not null then {{ state_code_to_name('state_code') }} end::text as state,
    (case when is_listed then known_status else 'no_longer_listed' end)::text as status,
    known_status::text                                  as last_known_status,
    status_as_of::date                                  as status_as_of,
    construction_note::text                             as construction_note,
    it_power_mw::double precision                       as it_power_mw,
    first_seen_on::date                                 as first_seen_on,
    last_seen_on::date                                  as last_seen_on,
    is_listed::boolean                                  as is_listed,
    'Epoch AI'::text                                    as source_name,
    'https://epoch.ai/data/data-centers'::text          as source_url,
    'CC BY 4.0'::text                                   as license,
    'Epoch AI, "AI data centers". Published online at epoch.ai. Licensed CC BY 4.0.'::text as attribution
from classified
