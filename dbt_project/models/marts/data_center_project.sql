{{ config(materialized='table', tags=['marts', 'data_centers', 'serving']) }}

/*
    Data center projects (#531). Grain: one row per announced or tracked project.

    Two inputs:
      curated  the data_center_projects seed: projects found in company announcements and
               news, each with the source that names it (source_url + verbatim
               source_excerpt). A curated row that names an Epoch site
               (data_center_site_name) carries that site's data_center_site_id, and the
               site is not repeated as its own project.
      epoch    every other Epoch AI site (data_center_site), one project each, credited to
               Epoch with the site's own fields quoted as the excerpt.

    Figures (investment, MW, acres, square feet, jobs) live one row per (project, metric,
    source) in data_center_project_figure. Here a figure is shown only when every source
    that states it agrees; when sources disagree the column is null,
    has_conflicting_figures is true, and each figure keeps its own source there. Each
    shown figure carries the URL and verbatim excerpt of its first source.

    jurisdiction_id is the most specific government the project resolves to
    (data_center_project_jurisdiction: a stated city or town, else the stated county);
    null when none resolves. Nothing is inferred: a seed column left blank stays null.
*/

with projects as (
    select * from {{ ref('int_data_center_project__base') }}
),

figures as (
    select * from {{ ref('int_data_center_project__figure') }}
),

figure_summary as (
    select
        project_id,
        metric,
        count(distinct value)                                                    as n_values,
        (array_agg(value order by published_on nulls last, source_url))[1]        as value,
        (array_agg(source_url order by published_on nulls last, source_url))[1]   as source_url,
        (array_agg(source_excerpt order by published_on nulls last, source_url))[1] as source_excerpt
    from figures
    group by project_id, metric
),

primary_jurisdiction as (
    select distinct on (project_id) project_id, jurisdiction_id
    from {{ ref('int_data_center_project__jurisdiction') }}
    order by project_id,
             case basis when 'stated_city' then 1 when 'meeting_source_survey' then 2
                        when 'address_city' then 3 when 'stated_county' then 4 else 5 end,
             jurisdiction_id
)

select
    p.project_id::text                                                       as project_id,
    p.project_key,
    p.project_source,
    p.project_name,
    p.data_center_site_id::text                                              as data_center_site_id,
    p.area,
    p.city,
    p.county,
    p.state_code,
    case when p.state_code is not null then {{ state_code_to_name('p.state_code') }} end::text as state,
    j.jurisdiction_id::text                                                  as jurisdiction_id,
    p.status,
    p.announced_on,
    (case when inv.n_values = 1 then inv.value end)::numeric                 as investment_usd,
    (case when inv.n_values = 1 then inv.source_url end)::text               as investment_source_url,
    (case when inv.n_values = 1 then inv.source_excerpt end)::text           as investment_source_excerpt,
    (case when mw.n_values = 1 then mw.value end)::numeric                   as it_mw,
    (case when mw.n_values = 1 then mw.source_url end)::text                 as it_mw_source_url,
    (case when mw.n_values = 1 then mw.source_excerpt end)::text             as it_mw_source_excerpt,
    (case when ac.n_values = 1 then ac.value end)::numeric                   as acres,
    (case when ac.n_values = 1 then ac.source_url end)::text                 as acres_source_url,
    (case when ac.n_values = 1 then ac.source_excerpt end)::text             as acres_source_excerpt,
    coalesce((select bool_or(fs.n_values > 1) from figure_summary as fs
              where fs.project_id = p.project_id), false)                    as has_conflicting_figures,
    p.source_kind,
    p.source_url,
    p.source_excerpt
from projects as p
left join primary_jurisdiction as j on j.project_id = p.project_id
left join figure_summary as inv on inv.project_id = p.project_id and inv.metric = 'investment_usd'
left join figure_summary as mw on mw.project_id = p.project_id and mw.metric = 'it_mw'
left join figure_summary as ac on ac.project_id = p.project_id and ac.metric = 'acres'
