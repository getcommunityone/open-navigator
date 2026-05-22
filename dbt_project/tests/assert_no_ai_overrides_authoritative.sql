/*
    Test: Assert AI extractions don't override authoritative sources
    
    This test checks that no contact with an authoritative datasource
    (openstates_api, irs_990, irs_bmf) was updated AFTER an AI extraction
    with the same normalized name.
    
    If this test returns rows, it means AI data incorrectly overwrote
    authoritative data.
*/

WITH ai_contacts AS (
    SELECT 
        id,
        name,
        LOWER(TRIM(name)) as name_normalized,
        datasource,
        last_updated
    FROM {{ ref('contact_ai') }}
    WHERE datasource = 'gemini_ai_extraction'
),

authoritative_contacts AS (
    SELECT 
        id,
        name,
        LOWER(TRIM(name)) as name_normalized,
        datasource,
        last_updated
    FROM contact
    WHERE datasource IN ('openstates_api', 'irs_990', 'irs_bmf')
),

conflicts AS (
    SELECT 
        ai.id as ai_contact_id,
        ai.name as ai_name,
        ai.datasource as ai_source,
        ai.last_updated as ai_updated,
        auth.id as auth_contact_id,
        auth.name as auth_name,
        auth.datasource as auth_source,
        auth.last_updated as auth_updated
    FROM ai_contacts ai
    INNER JOIN authoritative_contacts auth
        ON ai.name_normalized = auth.name_normalized
    WHERE ai.last_updated > auth.last_updated
)

SELECT * FROM conflicts
