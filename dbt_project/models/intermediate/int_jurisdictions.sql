{{
  config(
    materialized='table',
    tags=['intermediate', 'jurisdictions']
  )
}}

-- State abbreviation → FIPS + full name lookup
WITH state_ref AS (
    SELECT * FROM (VALUES
        ('AL', '01', 'Alabama'),
        ('AK', '02', 'Alaska'),
        ('AZ', '04', 'Arizona'),
        ('AR', '05', 'Arkansas'),
        ('CA', '06', 'California'),
        ('CO', '08', 'Colorado'),
        ('CT', '09', 'Connecticut'),
        ('DE', '10', 'Delaware'),
        ('DC', '11', 'District of Columbia'),
        ('FL', '12', 'Florida'),
        ('GA', '13', 'Georgia'),
        ('HI', '15', 'Hawaii'),
        ('ID', '16', 'Idaho'),
        ('IL', '17', 'Illinois'),
        ('IN', '18', 'Indiana'),
        ('IA', '19', 'Iowa'),
        ('KS', '20', 'Kansas'),
        ('KY', '21', 'Kentucky'),
        ('LA', '22', 'Louisiana'),
        ('ME', '23', 'Maine'),
        ('MD', '24', 'Maryland'),
        ('MA', '25', 'Massachusetts'),
        ('MI', '26', 'Michigan'),
        ('MN', '27', 'Minnesota'),
        ('MS', '28', 'Mississippi'),
        ('MO', '29', 'Missouri'),
        ('MT', '30', 'Montana'),
        ('NE', '31', 'Nebraska'),
        ('NV', '32', 'Nevada'),
        ('NH', '33', 'New Hampshire'),
        ('NJ', '34', 'New Jersey'),
        ('NM', '35', 'New Mexico'),
        ('NY', '36', 'New York'),
        ('NC', '37', 'North Carolina'),
        ('ND', '38', 'North Dakota'),
        ('OH', '39', 'Ohio'),
        ('OK', '40', 'Oklahoma'),
        ('OR', '41', 'Oregon'),
        ('PA', '42', 'Pennsylvania'),
        ('RI', '44', 'Rhode Island'),
        ('SC', '45', 'South Carolina'),
        ('SD', '46', 'South Dakota'),
        ('TN', '47', 'Tennessee'),
        ('TX', '48', 'Texas'),
        ('UT', '49', 'Utah'),
        ('VT', '50', 'Vermont'),
        ('VA', '51', 'Virginia'),
        ('WA', '53', 'Washington'),
        ('WV', '54', 'West Virginia'),
        ('WI', '55', 'Wisconsin'),
        ('WY', '56', 'Wyoming'),
        ('AS', '60', 'American Samoa'),
        ('GU', '66', 'Guam'),
        ('MP', '69', 'Northern Mariana Islands'),
        ('PR', '72', 'Puerto Rico'),
        ('VI', '78', 'U.S. Virgin Islands')
    ) AS t(state_code, state_fips, state_name)
),

-- ── Counties ────────────────────────────────────────────────────────────────
-- GEOID = state_fips(2) + county_fips(3) = 5 chars
-- county_fips_code IS the geoid for counties
counties AS (
    SELECT
        geoid,
        geoid                   AS fips_code,
        LEFT(geoid, 2)          AS state_fips_code,
        geoid                   AS county_fips_code,
        ARRAY[geoid]::TEXT[]    AS county_fips_codes,
        usps                    AS state_code,
        name,
        'county'                AS jurisdiction_type,
        ansicode,
        NULL::VARCHAR(5)        AS lsad,
        NULL::VARCHAR(1)        AS funcstat,
        NULL::VARCHAR(5)        AS lograde,
        NULL::VARCHAR(5)        AS higrade,
        aland_sqmi              AS area_sq_miles,
        intptlat                AS latitude,
        intptlong               AS longitude,
        ingestion_date
    FROM {{ source('bronze', 'bronze_jurisdictions_counties') }}
),

-- ── Municipalities ──────────────────────────────────────────────────────────
-- GEOID = state_fips(2) + place_fips(5) = 7 chars
-- county_fips_code is NULL here — county is not encoded in the place GEOID.
-- Enrichment requires the Census place-county relationship files
-- (bronze_jurisdictions_zip_place + bronze_jurisdictions_zip_county),
-- which are loaded separately via download_census_relationships.py.
municipalities AS (
    SELECT
        m.geoid,
        m.geoid                     AS fips_code,
        LEFT(m.geoid, 2)            AS state_fips_code,
        NULL::TEXT                  AS county_fips_code,
        NULL::TEXT[]                AS county_fips_codes,
        m.usps                      AS state_code,
        m.name,
        'municipality'              AS jurisdiction_type,
        m.ansicode,
        m.lsad,
        m.funcstat,
        NULL::VARCHAR(5)            AS lograde,
        NULL::VARCHAR(5)            AS higrade,
        m.aland_sqmi                AS area_sq_miles,
        m.intptlat                  AS latitude,
        m.intptlong                 AS longitude,
        m.ingestion_date
    FROM {{ source('bronze', 'bronze_jurisdictions_municipalities') }} m
),

-- ── School districts ────────────────────────────────────────────────────────
-- GEOID = state_fips(2) + district_code(5) = 7 chars
-- County is not encoded in the GEOID; left NULL at silver — can be enriched later
school_districts AS (
    SELECT
        geoid,
        geoid                   AS fips_code,
        LEFT(geoid, 2)          AS state_fips_code,
        NULL::TEXT              AS county_fips_code,
        NULL::TEXT[]            AS county_fips_codes,
        usps                    AS state_code,
        name,
        'school_district'       AS jurisdiction_type,
        NULL::VARCHAR(8)        AS ansicode,
        NULL::VARCHAR(5)        AS lsad,
        NULL::VARCHAR(1)        AS funcstat,
        lograde,
        higrade,
        aland_sqmi              AS area_sq_miles,
        intptlat                AS latitude,
        intptlong               AS longitude,
        ingestion_date
    FROM {{ source('bronze', 'bronze_jurisdictions_school_districts') }}
),

-- ── Townships ───────────────────────────────────────────────────────────────
-- GEOID = state_fips(2) + county_fips(3) + cousub_fips(5) = 10 chars
-- county_fips_code is always LEFT(geoid, 5) — directly embedded
townships AS (
    SELECT
        geoid,
        geoid                           AS fips_code,
        LEFT(geoid, 2)                  AS state_fips_code,
        LEFT(geoid, 5)                  AS county_fips_code,
        ARRAY[LEFT(geoid, 5)]::TEXT[]   AS county_fips_codes,
        usps                            AS state_code,
        name,
        'township'                      AS jurisdiction_type,
        ansicode,
        NULL::VARCHAR(5)                AS lsad,
        funcstat,
        NULL::VARCHAR(5)                AS lograde,
        NULL::VARCHAR(5)                AS higrade,
        aland_sqmi                      AS area_sq_miles,
        intptlat                        AS latitude,
        intptlong                       AS longitude,
        ingestion_date
    FROM {{ source('bronze', 'bronze_jurisdictions_townships') }}
),

unioned AS (
    SELECT * FROM counties
    UNION ALL
    SELECT * FROM municipalities
    UNION ALL
    SELECT * FROM school_districts
    UNION ALL
    SELECT * FROM townships
)

SELECT
    -- Singleton primary key: type-prefixed GEOID guarantees uniqueness across
    -- all four jurisdiction types (municipality and school_district share 7-digit
    -- GEOID namespace and DO have collisions in practice)
    u.jurisdiction_type || '_' || u.geoid               AS jurisdiction_id,
    u.geoid,
    u.fips_code,
    u.state_fips_code,
    u.county_fips_code,
    u.county_fips_codes,
    u.state_code,
    s.state_name                                        AS state,
    u.name,
    u.jurisdiction_type,
    u.ansicode,
    u.lsad,
    u.funcstat,
    u.lograde,
    u.higrade,
    u.area_sq_miles,
    u.latitude,
    u.longitude,
    u.ingestion_date,
    CURRENT_TIMESTAMP                                   AS transformed_at
FROM unioned u
LEFT JOIN state_ref s ON u.state_code = s.state_code
