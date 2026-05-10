{{
  config(
    materialized='table',
    tags=['intermediate', 'jurisdictions', 'scraped']
  )
}}

/*
  Normalized view of all ``bronze.bronze_jurisdictions_*_scraped`` discovery rows.

  - Adds ``jurisdiction_class`` (state | municipality | county | school_district).
  - Joins ``int_jurisdictions`` for Census names/ids where GEOID overlaps that model.
  - Joins ``bronze_jurisdictions_states`` for state names when class = state.
  - Raw nested discovery remains in ``payload`` JSONB for dbt/Python consumers.
*/

WITH unioned AS (
    SELECT
        geoid,
        usps,
        discovered_at,
        homepage_url,
        homepage_final_url,
        gsa_matched_domain,
        discovery_source,
        status,
        completeness_score,
        payload,
        'state'::text AS jurisdiction_class
    FROM {{ source('bronze', 'bronze_jurisdictions_states_scraped') }}

    UNION ALL

    SELECT
        geoid,
        usps,
        discovered_at,
        homepage_url,
        homepage_final_url,
        gsa_matched_domain,
        discovery_source,
        status,
        completeness_score,
        payload,
        'municipality'::text AS jurisdiction_class
    FROM {{ source('bronze', 'bronze_jurisdictions_municipalities_scraped') }}

    UNION ALL

    SELECT
        geoid,
        usps,
        discovered_at,
        homepage_url,
        homepage_final_url,
        gsa_matched_domain,
        discovery_source,
        status,
        completeness_score,
        payload,
        'county'::text AS jurisdiction_class
    FROM {{ source('bronze', 'bronze_jurisdictions_counties_scraped') }}

    UNION ALL

    SELECT
        geoid,
        usps,
        discovered_at,
        homepage_url,
        homepage_final_url,
        gsa_matched_domain,
        discovery_source,
        status,
        completeness_score,
        payload,
        'school_district'::text AS jurisdiction_class
    FROM {{ source('bronze', 'bronze_jurisdictions_school_districts_scraped') }}
)

SELECT
    u.geoid,
    u.usps,
    u.jurisdiction_class,
    u.discovered_at,
    u.homepage_url,
    u.homepage_final_url,
    u.gsa_matched_domain,
    u.discovery_source,
    u.status,
    u.completeness_score,
    u.payload,

    j.jurisdiction_id,
    COALESCE(j.name, st.name, u.payload -> 'jurisdiction' ->> 'name') AS census_or_payload_name,

    CURRENT_TIMESTAMP AS transformed_at

FROM unioned u
LEFT JOIN {{ ref('int_jurisdictions') }} j
    ON j.geoid = u.geoid
   AND (
        (u.jurisdiction_class = 'municipality' AND j.jurisdiction_type = 'municipality')
        OR (u.jurisdiction_class = 'county' AND j.jurisdiction_type = 'county')
        OR (u.jurisdiction_class = 'school_district' AND j.jurisdiction_type = 'school_district')
    )
LEFT JOIN {{ source('bronze', 'bronze_jurisdictions_states') }} st
    ON u.jurisdiction_class = 'state'
   AND (st.geoid = u.geoid OR UPPER(TRIM(st.usps)) = UPPER(TRIM(u.usps)))
