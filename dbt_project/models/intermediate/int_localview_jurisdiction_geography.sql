{{ config(
    materialized='view',
    tags=['intermediate', 'localview', 'jurisdictions']
) }}

/*
Map LocalView jurisdictions (place_name + state) onto Census Gazetteer place GEOIDs,
and then onto counties via the place→county crosswalk.

Matching tiers (each only fires if the prior tier found nothing):
  1. Municipality     — bronze_jurisdictions_municipalities
  2. School district  — bronze_jurisdictions_school_districts
  3. County direct    — bronze_jurisdictions_counties (e.g. "Montezuma County, CO")
  4. Township         — bronze_jurisdictions_townships (e.g. "Hamilton township NJ")
     County derived from the township GEOID prefix (first 5 chars = state+county FIPS).
*/

WITH localview_places AS (
    SELECT DISTINCT
        e.state_code,
        e.jurisdiction_name AS place_name_raw
    FROM {{ source('bronze', 'bronze_events_localview') }} e
    WHERE e.state_code IS NOT NULL
      AND e.jurisdiction_name IS NOT NULL
),

normalized AS (
    SELECT
        state_code,
        place_name_raw,
        TRIM(LOWER(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        -- Normalize whitespace (incl. NBSP) and trim
                        TRIM(REPLACE(place_name_raw, CHR(160), ' ')),
                        -- Remove trailing government-type phrases that often follow county/city names
                        '\s+(county\s+(commission|commissioners|board|council)|board\s+of\s+[^,]+|city\s+council|town\s+council)\s*$',
                        '',
                        1, 0, 'i'
                    ),
                    -- Remove trailing jurisdiction suffixes
                    '\s+(city|town|township|village|borough|cdp|county|census\s+area)\s*$',
                    '',
                    1, 0, 'i'
                ),
                -- Remove any remaining "Town"/"City" tokens inside the name
                '\s+(?:town|city)\s*',
                ' ',
                1, 0, 'i'
            )
        )) AS place_name_clean
    FROM localview_places
),

muni_norm AS (
    SELECT
        m.geoid AS place_geoid,
        m.usps  AS state_code,
        TRIM(LOWER(
            REGEXP_REPLACE(
                REGEXP_REPLACE(TRIM(m.name), '\s+(city|town|township|village|borough|cdp|county)$', '', 1, 0, 'i'),
                '\s+(?:town|city)\s*', ' ', 1, 0, 'i'
            )
        )) AS muni_name_clean,
        m.aland_sqmi
    FROM {{ source('bronze', 'bronze_jurisdictions_municipalities') }} m
),

sd_norm AS (
    SELECT
        sd.geoid AS school_district_geoid,
        sd.usps  AS state_code,
        LOWER(TRIM(sd.name)) AS sd_name_clean
    FROM {{ source('bronze', 'bronze_jurisdictions_school_districts') }} sd
),

county_norm AS (
    SELECT
        c.geoid AS county_geoid,
        c.usps  AS state_code,
        TRIM(LOWER(
            REGEXP_REPLACE(TRIM(REPLACE(c.name, CHR(160), ' ')), '\s+county\s*$', '', 1, 0, 'i')
        )) AS county_name_clean
    FROM {{ source('bronze', 'bronze_jurisdictions_counties') }} c
),

township_norm AS (
    SELECT
        t.geoid AS township_geoid,
        t.usps  AS state_code,
        -- New England MCDs are stored as "North Reading town" / "Amherst Town city",
        -- so mirror the place-side normalization (strip town/city/township suffixes
        -- and inner tokens) instead of only the "township" suffix.
        TRIM(LOWER(
            REGEXP_REPLACE(
                REGEXP_REPLACE(TRIM(t.name), '\s+(city|town|township|village|borough|cdp|county)$', '', 1, 0, 'i'),
                '\s+(?:town|city)\s*', ' ', 1, 0, 'i'
            )
        )) AS township_name_clean
    FROM {{ source('bronze', 'bronze_jurisdictions_townships') }} t
),

muni_matches AS (
    SELECT
        n.state_code,
        n.place_name_raw,
        n.place_name_clean,
        mn.place_geoid,
        'municipality'::TEXT AS matched_type,
        ROW_NUMBER() OVER (
            PARTITION BY n.state_code, n.place_name_clean
            ORDER BY mn.aland_sqmi DESC NULLS LAST
        ) AS rn
    FROM normalized n
    JOIN muni_norm mn
      ON mn.state_code = n.state_code
     AND mn.muni_name_clean = n.place_name_clean
),

best_muni AS (
    SELECT * FROM muni_matches WHERE rn = 1
),

sd_matches AS (
    SELECT
        n.state_code,
        n.place_name_raw,
        n.place_name_clean,
        sn.school_district_geoid,
        'school_district'::TEXT AS matched_type,
        ROW_NUMBER() OVER (
            PARTITION BY n.state_code, n.place_name_clean
            ORDER BY sn.school_district_geoid
        ) AS rn
    FROM normalized n
    JOIN sd_norm sn
      ON sn.state_code = n.state_code
     AND sn.sd_name_clean = n.place_name_clean
),

best_sd AS (
    SELECT * FROM sd_matches WHERE rn = 1
),

county_matches AS (
    SELECT
        n.state_code,
        n.place_name_raw,
        n.place_name_clean,
        cn.county_geoid,
        'county'::TEXT AS matched_type,
        ROW_NUMBER() OVER (
            PARTITION BY n.state_code, n.place_name_clean
            ORDER BY cn.county_geoid
        ) AS rn
    FROM normalized n
    JOIN county_norm cn
      ON cn.state_code = n.state_code
     AND cn.county_name_clean = n.place_name_clean
),

best_county AS (
    SELECT * FROM county_matches WHERE rn = 1
),

township_matches AS (
    SELECT
        n.state_code,
        n.place_name_raw,
        n.place_name_clean,
        tn.township_geoid,
        'township'::TEXT AS matched_type,
        ROW_NUMBER() OVER (
            PARTITION BY n.state_code, n.place_name_clean
            ORDER BY tn.township_geoid
        ) AS rn
    FROM normalized n
    JOIN township_norm tn
      ON tn.state_code = n.state_code
     AND tn.township_name_clean = n.place_name_clean
),

best_township AS (
    SELECT * FROM township_matches WHERE rn = 1
),

resolved AS (
    -- Tier 1: municipality (only matched rows)
    SELECT
        n.state_code,
        n.place_name_raw,
        n.place_name_clean,
        bm.place_geoid,
        NULL::VARCHAR(7)  AS school_district_geoid,
        NULL::VARCHAR(10) AS township_geoid,
        NULL::VARCHAR(5)  AS county_geoid_direct,
        bm.matched_type
    FROM normalized n
    JOIN best_muni bm
      ON bm.state_code = n.state_code
     AND bm.place_name_clean = n.place_name_clean

    UNION ALL

    -- Tier 2: school district (only for muni-unmatched rows with an SD match)
    SELECT
        n.state_code,
        n.place_name_raw,
        n.place_name_clean,
        NULL::VARCHAR(7)  AS place_geoid,
        bs.school_district_geoid,
        NULL::VARCHAR(10) AS township_geoid,
        NULL::VARCHAR(5)  AS county_geoid_direct,
        bs.matched_type
    FROM normalized n
    LEFT JOIN best_muni bm
      ON bm.state_code = n.state_code
     AND bm.place_name_clean = n.place_name_clean
    JOIN best_sd bs
      ON bs.state_code = n.state_code
     AND bs.place_name_clean = n.place_name_clean
    WHERE bm.place_geoid IS NULL

    UNION ALL

    -- Tier 3: county direct (only when tiers 1 and 2 both failed)
    SELECT
        n.state_code,
        n.place_name_raw,
        n.place_name_clean,
        NULL::VARCHAR(7)  AS place_geoid,
        NULL::VARCHAR(7)  AS school_district_geoid,
        NULL::VARCHAR(10) AS township_geoid,
        bc.county_geoid   AS county_geoid_direct,
        bc.matched_type
    FROM normalized n
    LEFT JOIN best_muni bm
      ON bm.state_code = n.state_code
     AND bm.place_name_clean = n.place_name_clean
    LEFT JOIN best_sd bs
      ON bs.state_code = n.state_code
     AND bs.place_name_clean = n.place_name_clean
    JOIN best_county bc
      ON bc.state_code = n.state_code
     AND bc.place_name_clean = n.place_name_clean
    WHERE bm.place_geoid IS NULL
      AND bs.school_district_geoid IS NULL

    UNION ALL

    -- Tier 4: township (only when tiers 1–3 all failed)
    -- County is derived from the GEOID prefix: SSCC? (first 5 chars = state+county FIPS)
    SELECT
        n.state_code,
        n.place_name_raw,
        n.place_name_clean,
        NULL::VARCHAR(7)  AS place_geoid,
        NULL::VARCHAR(7)  AS school_district_geoid,
        bt.township_geoid,
        NULL::VARCHAR(5)  AS county_geoid_direct,
        bt.matched_type
    FROM normalized n
    LEFT JOIN best_muni bm
      ON bm.state_code = n.state_code
     AND bm.place_name_clean = n.place_name_clean
    LEFT JOIN best_sd bs
      ON bs.state_code = n.state_code
     AND bs.place_name_clean = n.place_name_clean
    LEFT JOIN best_county bc
      ON bc.state_code = n.state_code
     AND bc.place_name_clean = n.place_name_clean
    JOIN best_township bt
      ON bt.state_code = n.state_code
     AND bt.place_name_clean = n.place_name_clean
    WHERE bm.place_geoid IS NULL
      AND bs.school_district_geoid IS NULL
      AND bc.county_geoid IS NULL

    UNION ALL

    -- Fallback: no match in any tier (emit exactly one row per place)
    SELECT
        n.state_code,
        n.place_name_raw,
        n.place_name_clean,
        NULL::VARCHAR(7)  AS place_geoid,
        NULL::VARCHAR(7)  AS school_district_geoid,
        NULL::VARCHAR(10) AS township_geoid,
        NULL::VARCHAR(5)  AS county_geoid_direct,
        NULL::TEXT        AS matched_type
    FROM normalized n
    LEFT JOIN best_muni bm
      ON bm.state_code = n.state_code
     AND bm.place_name_clean = n.place_name_clean
    LEFT JOIN best_sd bs
      ON bs.state_code = n.state_code
     AND bs.place_name_clean = n.place_name_clean
    LEFT JOIN best_county bc
      ON bc.state_code = n.state_code
     AND bc.place_name_clean = n.place_name_clean
    LEFT JOIN best_township bt
      ON bt.state_code = n.state_code
     AND bt.place_name_clean = n.place_name_clean
    WHERE bm.place_geoid IS NULL
      AND bs.school_district_geoid IS NULL
      AND bc.county_geoid IS NULL
      AND bt.township_geoid IS NULL
),

place_counties AS (
    SELECT
        r.state_code,
        r.place_name_raw,
        r.place_name_clean,
        r.place_geoid,
        r.school_district_geoid,
        r.township_geoid,
        r.matched_type,
        COALESCE(
            pc.county_geoid,
            r.county_geoid_direct,
            LEFT(r.township_geoid, 5)
        )                                                      AS county_geoid,
        COALESCE(
            pc.is_primary,
            r.matched_type IN ('county', 'township')
        )                                                      AS is_primary,
        COALESCE(pc.overlap_pct, 100.0)                       AS overlap_pct
    FROM resolved r
    LEFT JOIN {{ source('bronze', 'bronze_jurisdictions_place_county') }} pc
      ON r.place_geoid = pc.place_geoid
)

SELECT
    state_code,
    place_name_raw,
    place_name_clean,
    place_geoid,
    school_district_geoid,
    township_geoid,
    matched_type,
    MAX(CASE WHEN is_primary THEN county_geoid END)                                     AS primary_county_geoid,
    ARRAY_AGG(county_geoid ORDER BY overlap_pct DESC NULLS LAST) FILTER (WHERE county_geoid IS NOT NULL) AS county_geoids
FROM place_counties
GROUP BY 1,2,3,4,5,6,7
