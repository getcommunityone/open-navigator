/*
    Every source record behind each data center site (#958). Grain: one row per (site, source
    record). A site from one source has one row; an Epoch site that the US Data Center Registry
    also lists (equal names in the state, one-to-one) has two, so both credits and both record
    URLs are kept.

      epoch                    one row per Epoch AI site; source_url is the Epoch dataset page.
      us_data_center_registry  one row per registry data center; source_url is its page on the
                               registry. match_basis says whether it joined an Epoch site
                               ('epoch_same_name') or is its own site ('own_site').
*/

with epoch as (
    select
        data_center_site_id,
        'epoch'::text           as source,
        site_name::text         as source_record_id,
        site_name::text         as source_record_name,
        source_url::text        as source_url,
        'own_site'::text        as match_basis,
        license::text           as license,
        attribution::text       as attribution
    from {{ ref('data_center_site') }}
    where source = 'epoch'
),

registry as (
    select
        m.data_center_site_id,
        'us_data_center_registry'::text as source,
        r.registry_id::text             as source_record_id,
        r.facility_name::text           as source_record_name,
        coalesce(r.profile_url, 'https://suedatacenters.org/data-centers/data')::text as source_url,
        m.match_basis::text             as match_basis,
        'CC BY 4.0'::text               as license,
        r.attribution::text             as attribution
    from {{ ref('int_data_center_facility_registry__site') }} as m
    inner join {{ ref('stg_data_center_facility_registry') }} as r on r.registry_id = m.registry_id
)

select
    md5(source || '|' || source_record_id)::text as data_center_site_source_id,
    data_center_site_id::text                    as data_center_site_id,
    source,
    source_record_id,
    source_record_name,
    source_url,
    match_basis,
    license,
    attribution
from epoch
union all
select
    md5(source || '|' || source_record_id)::text,
    data_center_site_id::text,
    source,
    source_record_id,
    source_record_name,
    source_url,
    match_basis,
    license,
    attribution
from registry
