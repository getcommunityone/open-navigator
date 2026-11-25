/*
    Data center sites (DC-4.1, #249; #958). Grain: one row per site.
    Sources (source), each CC BY 4.0 and credited on every row (source_name, source_url,
    license, attribution):
      epoch                    Epoch AI, "AI data centers" (https://epoch.ai/data/data-centers):
                               the largest AI data centers, with street addresses and dated
                               status rows.
      us_data_center_registry  US Data Center Registry (SueDataCenters.org; base data from
                               Compute Atlas): about 2,300 US data centers with city, county,
                               coordinates and the registry's own status. A registry record that
                               is the same site as an Epoch site (int_data_center_facility_registry__site:
                               equal names in the state, one-to-one) is not repeated: the Epoch
                               row stands, and data_center_site_source lists both records.
                               source_url is the record's page on the registry.

    Registry status (source_status keeps the registry's word): operational -> operating,
    under_construction -> under_construction, proposed and permitted -> planned, cancelled ->
    cancelled (only because the registry publishes it). A record the registry drops reads
    no_longer_listed, keeping last_known_status, as for Epoch.

    The Epoch status rules:

    status comes from Epoch's dated timeline rows; Epoch publishes no status field:
      operating           latest row on or before today has a building operational (or, when
                          that count is blank, reports IT power above zero)
      under_construction  a dated row on or before today, nothing operational yet
      planned             only future-dated rows
      null                no timeline rows at all (shown as "Status not published")
    A site missing from the newest download has status = 'no_longer_listed' and keeps
    last_known_status and last_seen_on, so it stays visible. Epoch has no cancelled flag,
    so an Epoch row never says "cancelled".

    No FK: Epoch gives a street address, not a jurisdiction. state_code comes from the
    address when it ends in a US state code (the registry gives state, city and county).
    Models that match sites by name (projects, agenda items, meeting mentions, the governments
    near a site) read source = 'epoch' only, until they are widened deliberately.
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
            when p.name is not null
             and (coalesce(p.buildings_operational, 0) > 0
                  or (p.buildings_operational is null and coalesce(p.it_power_mw, 0) > 0)) then 'operating'
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
,

registry as (
    select
        r.*,
        case r.registry_status
            when 'operational' then 'operating'
            when 'under_construction' then 'under_construction'
            when 'proposed' then 'planned'
            when 'permitted' then 'planned'
            when 'cancelled' then 'cancelled'
        end as known_status
    from {{ ref('stg_data_center_facility_registry') }} as r
    inner join {{ ref('int_data_center_facility_registry__site') }} as m
        on m.registry_id = r.registry_id and m.match_basis = 'own_site'
),

epoch_rows as (
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
    'Epoch AI, "AI data centers". Published online at epoch.ai. Licensed CC BY 4.0.'::text as attribution,
    'epoch'::text                                       as source,
    null::text                                          as source_status,
    null::text                                          as operator,
    null::text                                          as city,
    null::text                                          as county,
    null::double precision                              as latitude,
    null::double precision                              as longitude,
    null::double precision                              as capacity_mw_planned,
    null::double precision                              as capacity_mw_operational
from classified
),

registry_rows as (
select
    md5('us_data_center_registry|' || registry_id)::text as data_center_site_id,
    facility_name::text                                 as site_name,
    null::text                                          as owner,
    null::text                                          as users,
    null::text                                          as project,
    null::text                                          as address,
    'United States'::text                               as country,
    state_code::text                                    as state_code,
    {{ state_code_to_name('state_code') }}::text        as state,
    (case when is_listed then known_status else 'no_longer_listed' end)::text as status,
    known_status::text                                  as last_known_status,
    record_updated_on::date                             as status_as_of,
    null::text                                          as construction_note,
    null::double precision                              as it_power_mw,
    first_seen_on::date                                 as first_seen_on,
    last_seen_on::date                                  as last_seen_on,
    is_listed::boolean                                  as is_listed,
    'US Data Center Registry (SueDataCenters.org)'::text as source_name,
    profile_url::text                                   as source_url,
    'CC BY 4.0'::text                                   as license,
    attribution::text                                   as attribution,
    'us_data_center_registry'::text                     as source,
    registry_status::text                               as source_status,
    operator::text                                      as operator,
    city::text                                          as city,
    county::text                                        as county,
    latitude::double precision                          as latitude,
    longitude::double precision                         as longitude,
    capacity_mw_planned::double precision               as capacity_mw_planned,
    capacity_mw_operational::double precision           as capacity_mw_operational
from registry
)

select * from epoch_rows
union all
select * from registry_rows
