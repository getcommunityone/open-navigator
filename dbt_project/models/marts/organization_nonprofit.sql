{{
  config(
    materialized='table',
    tags=['gold', 'nonprofits', 'api'],
    database='open_navigator'
  )
}}

/*
Gold Nonprofits - API-Ready Search Table

Final nonprofit organization search table for API consumption.
Enriched with NTEE descriptions and state names.

Purpose:
- Fast full-text search on nonprofit organizations
- Supports filtering by state, NTEE code, city
- Includes financial data for sorting/filtering

Target: API routes (api/routes/search_postgres.py)
*/

WITH silver_nonprofits AS (
    SELECT *
    FROM {{ ref('int_nonprofits_combined') }}
),

-- Map NTEE codes to descriptions
ntee_enriched AS (
    SELECT
        s.*,
        CASE 
            -- Major NTEE categories
            WHEN s.ntee_code LIKE 'A%' THEN 'Arts, Culture & Humanities'
            WHEN s.ntee_code LIKE 'B%' THEN 'Education'
            WHEN s.ntee_code LIKE 'C%' THEN 'Environmental Quality, Protection'
            WHEN s.ntee_code LIKE 'D%' THEN 'Animal-Related'
            WHEN s.ntee_code LIKE 'E%' THEN 'Health'
            WHEN s.ntee_code LIKE 'F%' THEN 'Mental Health, Crisis Intervention'
            WHEN s.ntee_code LIKE 'G%' THEN 'Diseases, Disorders, Medical Disciplines'
            WHEN s.ntee_code LIKE 'H%' THEN 'Medical Research'
            WHEN s.ntee_code LIKE 'I%' THEN 'Crime, Legal Related'
            WHEN s.ntee_code LIKE 'J%' THEN 'Employment, Job Related'
            WHEN s.ntee_code LIKE 'K%' THEN 'Food, Agriculture, Nutrition'
            WHEN s.ntee_code LIKE 'L%' THEN 'Housing, Shelter'
            WHEN s.ntee_code LIKE 'M%' THEN 'Public Safety, Disaster Preparedness'
            WHEN s.ntee_code LIKE 'N%' THEN 'Recreation, Sports, Leisure'
            WHEN s.ntee_code LIKE 'O%' THEN 'Youth Development'
            WHEN s.ntee_code LIKE 'P%' THEN 'Human Services - Multipurpose'
            WHEN s.ntee_code LIKE 'Q%' THEN 'International, Foreign Affairs'
            WHEN s.ntee_code LIKE 'R%' THEN 'Civil Rights, Social Action, Advocacy'
            WHEN s.ntee_code LIKE 'S%' THEN 'Community Improvement, Capacity Building'
            WHEN s.ntee_code LIKE 'T%' THEN 'Philanthropy, Voluntarism'
            WHEN s.ntee_code LIKE 'U%' THEN 'Science and Technology Research'
            WHEN s.ntee_code LIKE 'V%' THEN 'Social Science Research'
            WHEN s.ntee_code LIKE 'W%' THEN 'Public, Society Benefit'
            WHEN s.ntee_code LIKE 'X%' THEN 'Religion Related'
            WHEN s.ntee_code LIKE 'Y%' THEN 'Mutual/Membership Benefit'
            WHEN s.ntee_code LIKE 'Z%' THEN 'Unknown'
            ELSE 'Other'
        END AS ntee_description
    FROM silver_nonprofits s
),

-- Add state names
state_enriched AS (
    SELECT
        n.*,
        CASE n.state_code_clean
            WHEN 'AL' THEN 'Alabama'
            WHEN 'AK' THEN 'Alaska'
            WHEN 'AZ' THEN 'Arizona'
            WHEN 'AR' THEN 'Arkansas'
            WHEN 'CA' THEN 'California'
            WHEN 'CO' THEN 'Colorado'
            WHEN 'CT' THEN 'Connecticut'
            WHEN 'DE' THEN 'Delaware'
            WHEN 'FL' THEN 'Florida'
            WHEN 'GA' THEN 'Georgia'
            WHEN 'HI' THEN 'Hawaii'
            WHEN 'ID' THEN 'Idaho'
            WHEN 'IL' THEN 'Illinois'
            WHEN 'IN' THEN 'Indiana'
            WHEN 'IA' THEN 'Iowa'
            WHEN 'KS' THEN 'Kansas'
            WHEN 'KY' THEN 'Kentucky'
            WHEN 'LA' THEN 'Louisiana'
            WHEN 'ME' THEN 'Maine'
            WHEN 'MD' THEN 'Maryland'
            WHEN 'MA' THEN 'Massachusetts'
            WHEN 'MI' THEN 'Michigan'
            WHEN 'MN' THEN 'Minnesota'
            WHEN 'MS' THEN 'Mississippi'
            WHEN 'MO' THEN 'Missouri'
            WHEN 'MT' THEN 'Montana'
            WHEN 'NE' THEN 'Nebraska'
            WHEN 'NV' THEN 'Nevada'
            WHEN 'NH' THEN 'New Hampshire'
            WHEN 'NJ' THEN 'New Jersey'
            WHEN 'NM' THEN 'New Mexico'
            WHEN 'NY' THEN 'New York'
            WHEN 'NC' THEN 'North Carolina'
            WHEN 'ND' THEN 'North Dakota'
            WHEN 'OH' THEN 'Ohio'
            WHEN 'OK' THEN 'Oklahoma'
            WHEN 'OR' THEN 'Oregon'
            WHEN 'PA' THEN 'Pennsylvania'
            WHEN 'RI' THEN 'Rhode Island'
            WHEN 'SC' THEN 'South Carolina'
            WHEN 'SD' THEN 'South Dakota'
            WHEN 'TN' THEN 'Tennessee'
            WHEN 'TX' THEN 'Texas'
            WHEN 'UT' THEN 'Utah'
            WHEN 'VT' THEN 'Vermont'
            WHEN 'VA' THEN 'Virginia'
            WHEN 'WA' THEN 'Washington'
            WHEN 'WV' THEN 'West Virginia'
            WHEN 'WI' THEN 'Wisconsin'
            WHEN 'WY' THEN 'Wyoming'
            WHEN 'DC' THEN 'District of Columbia'
            WHEN 'PR' THEN 'Puerto Rico'
            ELSE NULL
        END AS state
    FROM ntee_enriched n
)

SELECT
    ein,
    name,
    street_address,
    city,
    zip_code,
    county,
    ntee_code,
    ntee_description,
    subsection AS subsection_code,
    affiliation AS affiliation_code,
    classification AS classification_code,
    revenue,
    assets,
    income,
    ruling AS ruling_date,
    foundation AS foundation_code,
    pf_filing_requirement_code,
    accounting_period,
    asset_code,
    income_code,
    filing_requirement_code,
    status AS exempt_organization_status_code,
    tax_period,
    assets AS asset_amount,
    income AS income_amount,
    revenue AS form_990_revenue_amount,
    datasource AS source,
    last_updated,
    state_code_clean AS state_code,
    state,
    datasource,
    datasource_id,
    1.0 AS confidence_score,
    true AS verified,
    NULL::timestamp AS verification_date,
    false AS needs_review,
    NULL::text AS review_notes,
    CURRENT_TIMESTAMP AS published_at
FROM state_enriched
WHERE state_code_clean IS NOT NULL  -- Must have state
  AND city IS NOT NULL               -- Must have city
  AND name IS NOT NULL               -- Must have name
