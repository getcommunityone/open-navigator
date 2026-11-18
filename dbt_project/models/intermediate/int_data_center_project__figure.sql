{{ config(materialized='table', tags=['intermediate', 'data_centers']) }}

/*
    Every stated figure about a data center project (#531). Grain: one row per
    (project, metric, source, value). Sources that disagree each keep their own row, so
    "1.2 million" / "1.26 million" / "1.3 million square feet" stay three rows.

    metric: investment_usd, it_mw (IT power / critical IT load), utility_mw, acres,
    square_feet, jobs. unit says how value is counted (usd, mw, acres, sq_ft, jobs).
      curated  the data_center_project_figures seed: each figure with the URL and the
               verbatim excerpt that states it.
      epoch    Epoch AI's IT power for the site, from its latest dated timeline row on or
               before today (data_center_site.it_power_mw), quoted as a dataset row.
*/

with projects as (
    select project_id, project_key, data_center_site_id from {{ ref('int_data_center_project__base') }}
),

curated as (
    select
        p.project_id,
        btrim(f.metric)                          as metric,
        f.value::numeric                         as value,
        btrim(f.unit)                            as unit,
        f.source_kind,
        f.source_url,
        f.source_excerpt,
        nullif(btrim(f.published_on), '')::date  as published_on
    from {{ ref('data_center_project_figures') }} as f
    inner join projects as p on p.project_key = f.project_key
),

epoch as (
    select
        p.project_id,
        'it_mw'                                  as metric,
        s.it_power_mw::numeric                   as value,
        'mw'                                     as unit,
        'dataset_row'                            as source_kind,
        s.source_url,
        s.site_name || ' | IT power (MW), ' || s.status_as_of::text || ': '
            || trim(trailing '.' from trim(trailing '0' from s.it_power_mw::numeric::text)) as source_excerpt,
        s.status_as_of                           as published_on
    from {{ ref('data_center_site') }} as s
    inner join projects as p on p.data_center_site_id = s.data_center_site_id
    where s.it_power_mw is not null and s.it_power_mw > 0
),

unioned as (
    select * from curated
    union all
    select * from epoch
)

select distinct on (project_id, metric, source_url, value)
    md5(project_id || '|' || metric || '|' || source_url || '|' || value::text)::text as project_figure_id,
    project_id::text      as project_id,
    metric::text          as metric,
    value::numeric        as value,
    unit::text            as unit,
    source_kind::text     as source_kind,
    source_url::text      as source_url,
    source_excerpt::text  as source_excerpt,
    published_on::date    as published_on
from unioned
order by project_id, metric, source_url, value, published_on
