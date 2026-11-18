{{ config(materialized='table', tags=['intermediate', 'data_centers']) }}

/*
    Data center projects before figures and governments are attached (#531). Grain: one
    row per project. data_center_project is this plus the agreed figures and the primary
    government; the figure and government models build from here, so the marts that
    carry a foreign key to data_center_project don't form a cycle with it.
    See data_center_project for the two inputs (curated seed, Epoch AI sites).
*/

with curated as (
    select * from {{ ref('data_center_projects') }}
),

sites as (
    select * from {{ ref('data_center_site') }}
),

projects as (
    select
        md5('curated|' || c.project_key)                      as project_id,
        c.project_key::text                                   as project_key,
        'curated'::text                                       as project_source,
        c.project_name::text                                  as project_name,
        s.data_center_site_id,
        nullif(btrim(c.area), '')::text                       as area,
        nullif(btrim(c.city), '')::text                       as city,
        nullif(btrim(c.county), '')::text                     as county,
        nullif(upper(btrim(c.state_code)), '')::text          as state_code,
        nullif(btrim(c.status), '')::text                     as status,
        case when nullif(btrim(c.announced_source_url), '') is not null
             then nullif(btrim(c.announced_on), '')::date end   as announced_on,
        nullif(btrim(c.announced_source_url), '')::text       as announced_source_url,
        nullif(btrim(c.announced_source_excerpt), '')::text   as announced_source_excerpt,
        c.source_kind::text                                   as source_kind,
        c.source_url::text                                    as source_url,
        c.source_excerpt::text                                as source_excerpt
    from curated as c
    left join sites as s on s.site_name = nullif(btrim(c.data_center_site_name), '')
    union all
    select
        md5('epoch|' || s.data_center_site_id),
        ('epoch:' || s.data_center_site_id)::text,
        'epoch',
        s.site_name,
        s.data_center_site_id,
        s.address,
        null::text,
        null::text,
        s.state_code,
        s.status,
        null::date,
        null::text,
        null::text,
        'dataset_row',
        s.source_url,
        concat_ws(' | ', s.site_name,
                  'Owner: ' || nullif(s.owner, ''),
                  'Project: ' || nullif(s.project, ''),
                  'Address: ' || nullif(s.address, ''))
    from sites as s
    where s.data_center_site_id not in (
        select x.data_center_site_id
        from curated as c
        inner join sites as x on x.site_name = nullif(btrim(c.data_center_site_name), '')
    )
)

select * from projects
