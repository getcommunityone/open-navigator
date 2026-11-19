{{ config(
    materialized='table',
    tags=['mart', 'jurisdictions', 'data_quality', 'llm_export'],
    post_hook=[gold_pk_post_hook('jurisdiction_id, website_record_key')]
) }}

/*
Detail: every website candidate row from ``int_jurisdiction_websites`` for counties,
municipalities, and school districts — for auditing overlaps and LLM tool context.
*/

SELECT
    s.jurisdiction_id,
    j.name AS jurisdiction_name,
    j.state_code,
    j.jurisdiction_type,
    s.website_record_key,
    s.website_source,
    s.website_url,
    s.domain_name,
    s.organization_name,
    s.ingestion_date,
    s.transformed_at
FROM {{ ref('int_jurisdiction_websites') }} s
INNER JOIN {{ ref('int_jurisdictions') }} j
    ON j.jurisdiction_id = s.jurisdiction_id
WHERE j.jurisdiction_type IN ('county', 'municipality', 'school_district', 'state')
