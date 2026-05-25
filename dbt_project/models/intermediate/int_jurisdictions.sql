{{
  config(
    materialized='table',
    tags=['intermediate', 'jurisdictions'],
    post_hook=[
      "create index if not exists {{ this.name }}_state_type_geoid_idx on {{ this }} (state_code, jurisdiction_type, geoid)"
    ]
  )
}}

/*
  ``jurisdiction_id`` is propagated from bronze: ``{place_slug}_{geoid}`` (e.g. ``andalusia_0101708``,
  ``mobile_01097``). States use 2-letter USPS from ``bronze_jurisdictions_states``.
*/

WITH

-- Nearest ZCTA centroid for non-county jurisdictions (expensive). Off by default; `zip` stays NULL.
-- Enable with project var `include_nearest_postal_zip: true` or:
--   dbt run --vars '{"include_nearest_postal_zip": true}'
-- Uses a 1-degree bounding box, then nearest centroid by Euclidean distance on lat/lon.
jurisdiction_zip AS (
{% if not var('include_nearest_postal_zip', false) %}
    SELECT NULL::VARCHAR(10) AS geoid, NULL::VARCHAR(5) AS zip WHERE false
{% else %}
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
{% endif %}
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

/*
Open States: attach OCD row when division_id has numeric place/county/school segments.
County: supports 3-digit in-state FIPS (057) or full 5-digit county GEOID (01057). Slug counties
(county:name) are still unmapped here.
*/
openstates_jurisdictions_raw AS (
    SELECT
        j.id AS open_states_jurisdiction_id,
        j.name AS openstates_name,
        j.classification AS openstates_classification,
        j.division_id,
        -- Prefer division_id when present; otherwise parse state from jurisdiction id.
        UPPER(COALESCE(
            (regexp_match(j.division_id, 'state:([a-z]{2})'))[1],
            (regexp_match(j.id, 'ocd-jurisdiction/country:us/state:([a-z]{2})'))[1]
        )) AS state_usps,
        (regexp_match(j.id, '/place:([^/]+)/'))[1]  AS place_slug,
        (regexp_match(j.id, '/county:([^/]+)/'))[1] AS county_slug
    FROM {{ source('bronze', 'bronze_jurisdictions_openstates') }} j
    WHERE regexp_match(j.id, 'ocd-jurisdiction/country:us/state:([a-z]{2})') IS NOT NULL
),

openstates_with_geoid AS (
    SELECT
        r.open_states_jurisdiction_id,
        r.openstates_name,
        r.openstates_classification,
        r.division_id,
        r.state_usps,
        sf.state_fips,
        CASE
            WHEN r.division_id ~ 'place:[0-9]+' THEN 'municipality'
            WHEN r.division_id ~ 'county:[0-9]+' THEN 'county'
            WHEN r.division_id ~ '(?:school_districts|school_district):[0-9]+' THEN 'school_district'
            ELSE NULL
        END AS map_jurisdiction_type,
        CASE
            WHEN r.division_id ~ 'place:[0-9]+'
                THEN sf.state_fips || LPAD((regexp_match(r.division_id, 'place:([0-9]+)'))[1], 5, '0')
            -- County: intra-state FIPS is 3 digits (LPAD OK). Open States sometimes encodes full 5-digit
            -- county GEOID after county: — LPAD(..., 3) would truncate (e.g. 01057 → 010) and break joins.
            WHEN r.division_id ~ 'county:[0-9]+'
                THEN CASE
                    WHEN LENGTH((regexp_match(r.division_id, 'county:([0-9]+)'))[1]) >= 5
                        THEN LEFT((regexp_match(r.division_id, 'county:([0-9]+)'))[1], 5)
                    ELSE sf.state_fips || LPAD((regexp_match(r.division_id, 'county:([0-9]+)'))[1], 3, '0')
                END
            WHEN r.division_id ~ '(?:school_districts|school_district):[0-9]+'
                THEN sf.state_fips || LPAD(
                    (regexp_match(
                        r.division_id,
                        '(?:school_districts|school_district):([0-9]+)'
                    ))[1],
                    5,
                    '0'
                )
            ELSE NULL
        END AS census_geoid
    FROM openstates_jurisdictions_raw r
    INNER JOIN state_ref sf ON r.state_usps = sf.state_code
    WHERE CASE
            WHEN r.division_id ~ 'place:[0-9]+' THEN TRUE
            WHEN r.division_id ~ 'county:[0-9]+' THEN TRUE
            WHEN r.division_id ~ '(?:school_districts|school_district):[0-9]+' THEN TRUE
            ELSE FALSE
        END
),

-- Slug-based fallback mapping: Open States uses place/county slugs (e.g. place:lexington),
-- while Census bronze tables use numeric GEOIDs. We join by normalized name within state.
openstates_with_slug_geoid AS (
    SELECT
        r.open_states_jurisdiction_id,
        r.openstates_name,
        r.openstates_classification,
        r.division_id,
        r.state_usps,
        CASE
            WHEN r.place_slug IS NOT NULL AND r.openstates_classification = 'municipality' THEN 'municipality'
            WHEN r.county_slug IS NOT NULL THEN 'county'
            ELSE NULL
        END AS map_jurisdiction_type,
        COALESCE(m.geoid, c.geoid) AS census_geoid
    FROM openstates_jurisdictions_raw r
    LEFT JOIN {{ source('bronze', 'bronze_jurisdictions_municipalities') }} m
        ON r.openstates_classification = 'municipality'
        AND r.place_slug IS NOT NULL
        AND m.usps = r.state_usps
        AND regexp_replace(
                regexp_replace(lower(m.name), ' (city|town|village|borough|cdp)$', '', 'g'),
                '[^a-z0-9]+',
                '',
                'g'
            )
            = regexp_replace(
                regexp_replace(replace(lower(r.place_slug), '_', ' '), ' (city|town|village|borough|cdp)$', '', 'g'),
                '[^a-z0-9]+',
                '',
                'g'
            )
    LEFT JOIN {{ source('bronze', 'bronze_jurisdictions_counties') }} c
        ON r.county_slug IS NOT NULL
        AND c.usps = r.state_usps
        AND regexp_replace(
                regexp_replace(lower(c.name), ' county$', '', 'g'),
                '[^a-z0-9]+',
                '',
                'g'
            )
            = regexp_replace(
                regexp_replace(replace(lower(r.county_slug), '_', ' '), ' county$', '', 'g'),
                '[^a-z0-9]+',
                '',
                'g'
            )
    WHERE (r.place_slug IS NOT NULL OR r.county_slug IS NOT NULL)
),

openstates_census_map AS (
    SELECT DISTINCT ON (map_jurisdiction_type, census_geoid, state_usps)
        open_states_jurisdiction_id,
        openstates_name,
        openstates_classification,
        map_jurisdiction_type,
        census_geoid,
        state_usps
    FROM (
        SELECT
            open_states_jurisdiction_id,
            openstates_name,
            openstates_classification,
            map_jurisdiction_type,
            census_geoid,
            state_usps
        FROM openstates_with_geoid
        UNION ALL
        SELECT
            open_states_jurisdiction_id,
            openstates_name,
            openstates_classification,
            map_jurisdiction_type,
            census_geoid,
            state_usps
        FROM openstates_with_slug_geoid
    ) x
    WHERE map_jurisdiction_type IS NOT NULL AND census_geoid IS NOT NULL
    ORDER BY map_jurisdiction_type, census_geoid, state_usps, open_states_jurisdiction_id
),

-- ── Counties ────────────────────────────────────────────────────────────────
-- GEOID = state_fips(2) + county_fips(3) = 5 chars
counties AS (
    SELECT
        jurisdiction_id,
        geoid,
        geoid                   AS fips_code,
        LEFT(geoid, 2)          AS state_fips_code,
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
municipalities AS (
    SELECT
        m.jurisdiction_id,
        m.geoid,
        m.geoid                                                         AS fips_code,
        LEFT(m.geoid, 2)                                                AS state_fips_code,
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
),

-- ── School districts ────────────────────────────────────────────────────────
-- GEOID = state_fips(2) + district_code(5) = 7 chars
school_districts AS (
    SELECT
        sd.jurisdiction_id,
        sd.geoid,
        sd.geoid                                                        AS fips_code,
        LEFT(sd.geoid, 2)                                               AS state_fips_code,
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
),

-- ── Townships ───────────────────────────────────────────────────────────────
-- GEOID = state_fips(2) + county_fips(3) + cousub_fips(5) = 10 chars
townships AS (
    SELECT
        bronze.jurisdiction_id_from_place(t.name, t.geoid) AS jurisdiction_id,
        t.geoid,
        t.geoid                         AS fips_code,
        LEFT(t.geoid, 2)                AS state_fips_code,
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

-- ── State governments (Census Gazetteer) ───────────────────────────────────
-- GEOID = 2-digit Census state FIPS (e.g. 01, 06). One row per state / DC / PR.
states AS (
    SELECT
        jurisdiction_id,
        LPAD(TRIM(geoid), 2, '0')       AS geoid,
        LPAD(TRIM(geoid), 2, '0')       AS fips_code,
        LPAD(TRIM(geoid), 2, '0')       AS state_fips_code,
        UPPER(TRIM(usps))               AS state_code,
        TRIM(name)                      AS name,
        'state'                         AS jurisdiction_type,
        ansicode,
        NULL::VARCHAR(5)                AS lsad,
        NULL::VARCHAR(1)                AS funcstat,
        NULL::VARCHAR(5)                AS lograde,
        NULL::VARCHAR(5)                AS higrade,
        aland_sqmi                      AS area_sq_miles,
        intptlat                        AS latitude,
        intptlong                       AS longitude,
        NULL::VARCHAR(5)                AS zip,
        ingestion_date
    FROM {{ source('bronze', 'bronze_jurisdictions_states') }}
    WHERE geoid IS NOT NULL
      AND TRIM(geoid) <> ''
      AND usps IS NOT NULL
      AND TRIM(usps) <> ''
),

unioned AS (
    SELECT * FROM counties
    UNION ALL
    SELECT * FROM municipalities
    UNION ALL
    SELECT * FROM school_districts
    UNION ALL
    SELECT * FROM townships
    UNION ALL
    SELECT * FROM states
)

SELECT
    -- Canonical id from bronze ({place_slug}_{geoid}); states use USPS (e.g. AL).
    u.jurisdiction_id,
    osc.open_states_jurisdiction_id,
    osc.open_states_jurisdiction_id                     AS openstates_id,
    osc.openstates_name,
    osc.openstates_classification,
    u.geoid,
    u.fips_code,
    u.state_fips_code,
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
LEFT JOIN openstates_census_map osc
    ON osc.map_jurisdiction_type = u.jurisdiction_type
    AND osc.census_geoid = u.geoid
    AND osc.state_usps = u.state_code
