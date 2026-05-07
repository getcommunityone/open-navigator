{{
  config(
    materialized='table',
    tags=['intermediate', 'jurisdictions', 'websites']
  )
}}

-- Map GSA domain_type labels to the jurisdiction_type values used in int_jurisdictions
-- so the name-match join targets the right pool of records.
WITH domain_type_map AS (
    SELECT * FROM (VALUES
        ('City',             'municipality'),
        ('County',           'county'),
        ('State',            'state'),
        ('School District',  'school_district'),
        ('Township',         'township')
    ) AS t(gsa_domain_type, jur_type)
),

state_ref AS (
    SELECT * FROM (VALUES
        ('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'), ('AR', 'Arkansas'),
        ('CA', 'California'), ('CO', 'Colorado'), ('CT', 'Connecticut'), ('DE', 'Delaware'),
        ('DC', 'District of Columbia'), ('FL', 'Florida'), ('GA', 'Georgia'), ('HI', 'Hawaii'),
        ('ID', 'Idaho'), ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'),
        ('KS', 'Kansas'), ('KY', 'Kentucky'), ('LA', 'Louisiana'), ('ME', 'Maine'),
        ('MD', 'Maryland'), ('MA', 'Massachusetts'), ('MI', 'Michigan'), ('MN', 'Minnesota'),
        ('MS', 'Mississippi'), ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'),
        ('NV', 'Nevada'), ('NH', 'New Hampshire'), ('NJ', 'New Jersey'), ('NM', 'New Mexico'),
        ('NY', 'New York'), ('NC', 'North Carolina'), ('ND', 'North Dakota'), ('OH', 'Ohio'),
        ('OK', 'Oklahoma'), ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'),
        ('SC', 'South Carolina'), ('SD', 'South Dakota'), ('TN', 'Tennessee'), ('TX', 'Texas'),
        ('UT', 'Utah'), ('VT', 'Vermont'), ('VA', 'Virginia'), ('WA', 'Washington'),
        ('WV', 'West Virginia'), ('WI', 'Wisconsin'), ('WY', 'Wyoming'),
        ('AS', 'American Samoa'), ('GU', 'Guam'), ('MP', 'Northern Mariana Islands'),
        ('PR', 'Puerto Rico'), ('VI', 'U.S. Virgin Islands')
    ) AS t(state_code, state_name)
),

source AS (
    SELECT *
    FROM {{ source('bronze', 'bronze_gov_domains') }}
    -- Only local government domains; exclude federal agencies
    WHERE domain_type NOT IN ('Federal Agency', 'Federal Agency - Executive', 'Federal Agency - Legislative', 'Federal Agency - Judicial')
       OR domain_type IS NULL
),

cleaned AS (
    SELECT
        LOWER(TRIM(domain_name))                        AS domain_name,
        'https://' || LOWER(TRIM(domain_name))          AS website_url,
        TRIM(domain_type)                               AS domain_type,
        TRIM(agency)                                    AS agency,
        TRIM(organization)                              AS organization_name,
        TRIM(city)                                      AS city,
        UPPER(TRIM(state))                              AS state_code,

        -- Standardize domain_type to jurisdiction category
        CASE UPPER(TRIM(domain_type))
            WHEN 'CITY'           THEN 'municipality'
            WHEN 'COUNTY'         THEN 'county'
            WHEN 'STATE'          THEN 'state'
            WHEN 'SCHOOL DISTRICT' THEN 'school_district'
            WHEN 'TOWNSHIP'       THEN 'township'
            WHEN 'INTERSTATE'     THEN 'interstate'
            WHEN 'INDEPENDENT INTRASTATE' THEN 'special_district'
            ELSE 'other'
        END                                             AS jurisdiction_category,

        ingestion_date
    FROM source
    WHERE domain_name IS NOT NULL
      AND TRIM(domain_name) != ''
),

-- Best-effort jurisdiction match: join on normalized city name + state + type.
-- Produces NULL jurisdiction_id where no confident match exists (ambiguous names,
-- missing city, or types we don't map such as federal/interstate).
jurisdiction_match AS (
    SELECT
        c.domain_name,
        j.jurisdiction_id,
        ROW_NUMBER() OVER (
            PARTITION BY c.domain_name
            ORDER BY j.area_sq_miles DESC NULLS LAST  -- prefer larger jurisdiction on tie
        ) AS match_rank
    FROM cleaned c
    JOIN domain_type_map dtm ON UPPER(c.domain_type) = UPPER(dtm.gsa_domain_type)
    JOIN {{ ref('int_jurisdictions') }} j
        ON j.jurisdiction_type = dtm.jur_type
       AND j.state_code         = c.state_code
       AND LOWER(TRIM(j.name))  = LOWER(TRIM(c.city))
    WHERE c.city IS NOT NULL
)

SELECT
    c.domain_name,
    c.website_url,
    c.domain_type,
    c.jurisdiction_category,
    c.organization_name,
    c.agency,
    c.city,
    c.state_code,
    s.state_name                                        AS state,
    jm.jurisdiction_id,
    c.ingestion_date,
    CURRENT_TIMESTAMP                                   AS transformed_at
FROM cleaned c
LEFT JOIN state_ref s ON c.state_code = s.state_code
LEFT JOIN jurisdiction_match jm
    ON c.domain_name = jm.domain_name
   AND jm.match_rank = 1
