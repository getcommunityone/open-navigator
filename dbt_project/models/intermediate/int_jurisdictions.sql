{{
  config(
    materialized='table',
    tags=['intermediate', 'jurisdictions']
  )
}}

WITH

-- Nearest ZCTA centroid for all non-county jurisdictions.
-- Uses a 1-degree bounding box to avoid a full cross join, then picks the
-- closest centroid by Euclidean distance on lat/lon.
jurisdiction_zip AS (
    SELECT DISTINCT ON (j.geoid)
        j.geoid,
        z.geoid AS zip
    FROM (
        SELECT geoid, intptlat, intptlong FROM {{ source('bronze', 'bronze_jurisdictions_municipalities') }}
        UNION ALL
        SELECT geoid, intptlat, intptlong FROM {{ source('bronze', 'bronze_jurisdictions_school_districts') }}
        UNION ALL
        SELECT geoid, intptlat, intptlong FROM {{ source('bronze', 'bronze_jurisdictions_townships') }}
    ) j
    JOIN {{ source('bronze', 'bronze_jurisdictions_zcta') }} z
        ON ABS(z.intptlat  - j.intptlat)  < 1.0
        AND ABS(z.intptlong - j.intptlong) < 1.0
    WHERE j.intptlat  IS NOT NULL
      AND j.intptlong IS NOT NULL
    ORDER BY j.geoid,
        (z.intptlat  - j.intptlat)^2 + (z.intptlong - j.intptlong)^2
),

-- ZIPs that map unambiguously to a single county
single_county_zips AS (
    SELECT zip, MIN(county) AS county
    FROM {{ source('bronze', 'bronze_jurisdictions_zip_county') }}
    GROUP BY zip
    HAVING COUNT(DISTINCT county) = 1
),

-- Nearest-ZIP → county for non-county jurisdictions.
-- Only resolves when the nearest ZCTA maps to exactly one county.
zip_county_lookup AS (
    SELECT jz.geoid, sc.county AS county_fips_code
    FROM jurisdiction_zip jz
    JOIN single_county_zips sc ON jz.zip = sc.zip
),

-- Spatial enrichment fallback for jurisdictions unresolved by ZIP lookup.
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
        NULL::VARCHAR(5)        AS zip,
        ingestion_date
    FROM {{ source('bronze', 'bronze_jurisdictions_counties') }}
),

-- ── Municipalities ──────────────────────────────────────────────────────────
-- GEOID = state_fips(2) + place_fips(5) = 7 chars
-- County resolved via: (1) nearest-ZCTA ZIP → single-county lookup,
--                      (2) spatial enrichment script fallback.
municipalities AS (
    SELECT
        m.geoid,
        m.geoid                                                         AS fips_code,
        LEFT(m.geoid, 2)                                                AS state_fips_code,
        COALESCE(zc.county_fips_code, ge.county_fips_code)             AS county_fips_code,
        CASE
            WHEN COALESCE(zc.county_fips_code, ge.county_fips_code) IS NOT NULL
            THEN ARRAY[COALESCE(zc.county_fips_code, ge.county_fips_code)]::TEXT[]
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
        jz.zip,
        m.ingestion_date
    FROM {{ source('bronze', 'bronze_jurisdictions_municipalities') }} m
    LEFT JOIN jurisdiction_zip   jz ON m.geoid = jz.geoid
    LEFT JOIN zip_county_lookup  zc ON m.geoid = zc.geoid
    LEFT JOIN geo_enriched       ge ON m.geoid = ge.geoid
),

-- ── School districts ────────────────────────────────────────────────────────
-- GEOID = state_fips(2) + district_code(5) = 7 chars
-- County resolved via: (1) nearest-ZCTA ZIP → single-county lookup,
--                      (2) spatial enrichment script fallback.
school_districts AS (
    SELECT
        sd.geoid,
        sd.geoid                                                        AS fips_code,
        LEFT(sd.geoid, 2)                                               AS state_fips_code,
        COALESCE(zc.county_fips_code, ge.county_fips_code)             AS county_fips_code,
        CASE
            WHEN COALESCE(zc.county_fips_code, ge.county_fips_code) IS NOT NULL
            THEN ARRAY[COALESCE(zc.county_fips_code, ge.county_fips_code)]::TEXT[]
            ELSE NULL::TEXT[]
        END                                                             AS county_fips_codes,
        sd.usps                                                         AS state_code,
        sd.name,
        'school_district'                                               AS jurisdiction_type,
        NULL::VARCHAR(8)                                                AS ansicode,
        NULL::VARCHAR(5)                                                AS lsad,
        NULL::VARCHAR(1)                                                AS funcstat,
        sd.lograde,
        sd.higrade,
        sd.aland_sqmi                                                   AS area_sq_miles,
        sd.intptlat                                                     AS latitude,
        sd.intptlong                                                    AS longitude,
        jz.zip,
        sd.ingestion_date
    FROM {{ source('bronze', 'bronze_jurisdictions_school_districts') }} sd
    LEFT JOIN jurisdiction_zip   jz ON sd.geoid = jz.geoid
    LEFT JOIN zip_county_lookup  zc ON sd.geoid = zc.geoid
    LEFT JOIN geo_enriched       ge ON sd.geoid = ge.geoid
),

-- ── Townships ───────────────────────────────────────────────────────────────
-- GEOID = state_fips(2) + county_fips(3) + cousub_fips(5) = 10 chars
-- county_fips_code is always LEFT(geoid, 5) — directly embedded
townships AS (
    SELECT
        t.geoid,
        t.geoid                         AS fips_code,
        LEFT(t.geoid, 2)                AS state_fips_code,
        LEFT(t.geoid, 5)                AS county_fips_code,
        ARRAY[LEFT(t.geoid, 5)]::TEXT[] AS county_fips_codes,
        t.usps                          AS state_code,
        t.name,
        'township'                      AS jurisdiction_type,
        t.ansicode,
        NULL::VARCHAR(5)                AS lsad,
        t.funcstat,
        NULL::VARCHAR(5)                AS lograde,
        NULL::VARCHAR(5)                AS higrade,
        t.aland_sqmi                    AS area_sq_miles,
        t.intptlat                      AS latitude,
        t.intptlong                     AS longitude,
        jz.zip,
        t.ingestion_date
    FROM {{ source('bronze', 'bronze_jurisdictions_townships') }} t
    LEFT JOIN jurisdiction_zip jz ON t.geoid = jz.geoid
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
    u.zip,
    u.ingestion_date,
    CURRENT_TIMESTAMP                                   AS transformed_at
FROM unioned u
LEFT JOIN state_ref s ON u.state_code = s.state_code
