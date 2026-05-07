{{
  config(
    materialized='table',
    tags=['intermediate', 'jurisdictions']
  )
}}

-- State abbreviation → FIPS + full name lookup
WITH

-- ZCTAs that map unambiguously to a single county
single_county_zctas AS (
    SELECT zcta, MIN(county_geoid) AS county_geoid
    FROM {{ source('bronze', 'bronze_jurisdictions_zip_county') }}
    GROUP BY zcta
    HAVING COUNT(DISTINCT county_geoid) = 1
),

-- Municipality place GEOID → county via the ZCTA-to-place relationship.
-- When a municipality spans multiple ZCTAs, pick the county that covers the
-- most land area across all its ZCTAs (ties broken by county_geoid).
muni_county_via_zip AS (
    SELECT DISTINCT ON (zp.place_geoid)
        zp.place_geoid                  AS geoid,
        sc.county_geoid                 AS county_fips_code
    FROM {{ source('bronze', 'bronze_jurisdictions_zip_place') }} zp
    INNER JOIN single_county_zctas sc ON zp.zcta = sc.zcta
    ORDER BY zp.place_geoid, zp.arealand_part DESC, sc.county_geoid
),

-- Spatial enrichment fallback (municipalities unresolved above + school districts).
-- Populated by scripts/datasources/census/enrich_jurisdictions_county_fips.py.
geo_enriched AS (
    SELECT geoid, county_fips_code
    FROM {{ source('bronze', 'bronze_jurisdictions_county_fips_enriched') }}
),

state_ref AS (
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
-- County resolved via: (1) single-county ZCTA mapping, (2) spatial enrichment script.
municipalities AS (
    SELECT
        m.geoid,
        m.geoid                                                         AS fips_code,
        LEFT(m.geoid, 2)                                                AS state_fips_code,
        COALESCE(mz.county_fips_code, ge.county_fips_code)             AS county_fips_code,
        CASE
            WHEN COALESCE(mz.county_fips_code, ge.county_fips_code) IS NOT NULL
            THEN ARRAY[COALESCE(mz.county_fips_code, ge.county_fips_code)]::TEXT[]
            ELSE NULL::TEXT[]
        END                                                             AS county_fips_codes,
        m.usps                                                          AS state_code,
        m.name,
        'municipality'                                                  AS jurisdiction_type,
        m.ansicode,
        m.lsad,
        m.funcstat,
        NULL::VARCHAR(5)                                                AS lograde,
        NULL::VARCHAR(5)                                                AS higrade,
        m.aland_sqmi                                                    AS area_sq_miles,
        m.intptlat                                                      AS latitude,
        m.intptlong                                                     AS longitude,
        m.ingestion_date
    FROM {{ source('bronze', 'bronze_jurisdictions_municipalities') }} m
    LEFT JOIN muni_county_via_zip mz ON m.geoid = mz.geoid
    LEFT JOIN geo_enriched ge ON m.geoid = ge.geoid
),

-- ── School districts ────────────────────────────────────────────────────────
-- GEOID = state_fips(2) + district_code(5) = 7 chars
-- County not encoded in GEOID; resolved via spatial enrichment script.
-- No ZCTA-to-school-district relationship exists in Census data.
school_districts AS (
    SELECT
        sd.geoid,
        sd.geoid                                AS fips_code,
        LEFT(sd.geoid, 2)                       AS state_fips_code,
        ge.county_fips_code                     AS county_fips_code,
        CASE
            WHEN ge.county_fips_code IS NOT NULL
            THEN ARRAY[ge.county_fips_code]::TEXT[]
            ELSE NULL::TEXT[]
        END                                     AS county_fips_codes,
        sd.usps                                 AS state_code,
        sd.name,
        'school_district'                       AS jurisdiction_type,
        NULL::VARCHAR(8)                        AS ansicode,
        NULL::VARCHAR(5)                        AS lsad,
        NULL::VARCHAR(1)                        AS funcstat,
        sd.lograde,
        sd.higrade,
        sd.aland_sqmi                           AS area_sq_miles,
        sd.intptlat                             AS latitude,
        sd.intptlong                            AS longitude,
        sd.ingestion_date
    FROM {{ source('bronze', 'bronze_jurisdictions_school_districts') }} sd
    LEFT JOIN geo_enriched ge ON sd.geoid = ge.geoid
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
