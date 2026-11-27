{{ config(materialized='view') }}

/*
    Staging: nonprofits' websites from their latest Form 990 e-file (#1347). One row per EIN with a website.
*/

select
    nullif(trim(ein), '')                 as ein,
    nullif(trim(website_url), '')         as website_url,
    tax_year::integer                     as tax_year,
    fetched_at,
    crawl_status,
    crawled_at,
    events_found
from {{ source('bronze', 'bronze_organization_website') }}
where nullif(trim(website_url), '') is not null
