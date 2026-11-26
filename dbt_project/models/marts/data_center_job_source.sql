{{ config(materialized='table', tags=['marts', 'data_centers', 'serving']) }}

/*
    Where data center jobs are tracked (#1019): the job boards and official sources cited on the jobs screen, from the
    data_center_job_sources seed. Grain: one row per source. Only bls-qcew is loaded (data_center_employment); the
    boards are cited, not scraped (see automated_access and web_docs development/data-center-payroll-jobs.md).
*/

select
    job_source_id::text           as job_source_id,
    name::text                    as name,
    url::text                     as url,
    kind::text                    as kind,
    nullif(description, '')::text as description,
    nullif(description_source_url, '')::text as description_source_url,
    automated_access::text        as automated_access,
    checked_on::date              as checked_on
from {{ ref('data_center_job_sources') }}
