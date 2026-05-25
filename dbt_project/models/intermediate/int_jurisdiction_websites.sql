{{
  config(
    materialized='table',
    tags=['intermediate', 'jurisdictions', 'websites']
  )
}}

-- Relation in Postgres: intermediate.int_jurisdiction_websites (see dbt intermediate +schema).
-- Performance (ops): ``ANALYZE`` bronze sources after bulk loads; run ``EXPLAIN (ANALYZE, BUFFERS)``
-- on compiled SQL under ``target/run/``. Index ``idx_int_jurisdictions_state_type`` is created by
-- ``dbt_project/scripts/ensure_int_jurisdictions_indexes.sh`` (called from ``dbt_project/setup.sh``)
-- because ``CREATE INDEX CONCURRENTLY`` cannot run inside dbt's transaction. For heavy GSA name
-- joins, optionally ``SET work_mem = '256MB'`` in the session before ``dbt run`` (avoid embedding in
-- ``config(pre_hook=...)`` here: dbt's config parser rejects nested string quotes in some versions).
-- Query that schema/name after ``dbt run --select int_jurisdiction_websites`` — public.* may be stale/wrong.
--
-- After adding denylist rows: ``dbt seed --select jurisdiction_website_domain_denylist`` then rebuild this model.
-- Curated URLs: ``jurisdiction_website_url_overrides`` seed (``dbt seed --select jurisdiction_website_url_overrides``).
-- Python scrapers rank **override** (this seed) first, then **NACO over GSA** for county slug ids so
-- curated and NACo county URLs beat questionable GSA .gov registry matches. **League** municipal
-- directories union in after USCM with the same name-normalization join pattern.

-- Map GSA domain_type labels to the jurisdiction_type values used in int_jurisdictions
-- so the name-match join targets the right pool of records.
WITH domain_type_map AS (
    SELECT * FROM (VALUES
        ('City',                          'municipality'),
        ('Town',                          'municipality'),
        ('Village',                       'municipality'),
        ('Borough',                       'municipality'),
        ('County',                        'county'),
        ('State',                         'state'),
        ('State or territory',            'state'),
        ('State or territory - Election', 'state'),
        ('School District',               'school_district'),
        ('Township',                      'township')
    ) AS t(gsa_domain_type, jur_type)
),

-- Normalized place name for GSA ↔ Census ``int_jurisdictions`` matching (see macro).
jurisdictions_name_normalized AS (
    SELECT
        jurisdiction_id,
        state_code,
        jurisdiction_type,
        area_sq_miles,
        {{ normalize_jurisdiction_label_for_match('name') }} AS name_norm
    FROM {{ ref('int_jurisdictions') }}
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

gsa_domains_raw AS (
    SELECT *
    FROM {{ source('bronze', 'bronze_gov_domains') }}
    -- Only local government domains; exclude federal agencies
    WHERE domain_type NOT IN ('Federal Agency', 'Federal Agency - Executive', 'Federal Agency - Legislative', 'Federal Agency - Judicial')
       OR domain_type IS NULL
),

gsa_cleaned AS (
    SELECT
        LOWER(TRIM(domain_name))                        AS domain_name,
        'https://' || LOWER(TRIM(domain_name))          AS website_url,
        'gsa'                                           AS website_source,
        LOWER(TRIM(domain_name))                        AS website_record_key,
        TRIM(domain_type)                               AS domain_type,
        TRIM(agency)                                    AS agency,
        TRIM(organization)                              AS organization_name,
        TRIM(city)                                      AS city,
        UPPER(TRIM(state))                              AS state_code,

        {{ normalize_jurisdiction_label_for_match('city') }} AS city_normalized,

        {{ normalize_jurisdiction_label_for_match(
            "REGEXP_REPLACE(TRIM(organization), ',\\s*[A-Za-z]{2}\\s*$', '', 'gi')"
        ) }} AS organization_normalized,

        {{ normalize_jurisdiction_label_for_match(
            "REGEXP_REPLACE(TRIM(agency), ',\\s*[A-Za-z]{2}\\s*$', '', 'gi')"
        ) }} AS agency_normalized,

        CASE
            WHEN UPPER(TRIM(domain_type)) IN ('STATE', 'STATE OR TERRITORY', 'STATE OR TERRITORY - ELECTION')
                THEN 'state'
            WHEN UPPER(TRIM(domain_type)) = 'CITY' THEN 'municipality'
            WHEN UPPER(TRIM(domain_type)) = 'COUNTY' THEN 'county'
            WHEN UPPER(TRIM(domain_type)) = 'SCHOOL DISTRICT' THEN 'school_district'
            WHEN UPPER(TRIM(domain_type)) = 'TOWNSHIP' THEN 'township'
            WHEN UPPER(TRIM(domain_type)) = 'INTERSTATE' THEN 'interstate'
            WHEN UPPER(TRIM(domain_type)) = 'INDEPENDENT INTRASTATE' THEN 'special_district'
            ELSE 'other'
        END                                             AS jurisdiction_category,

        ingestion_date
    FROM gsa_domains_raw
    WHERE domain_name IS NOT NULL
      AND TRIM(domain_name) != ''
),

-- GSA ``jurisdiction_id``: same state + mapped domain_type as ``int_jurisdictions`` type, then tie-break
-- name match on organization (registrant) > agency > city, then prefix matches, then land area.
jurisdiction_match AS (
    SELECT
        c.domain_name,
        j.jurisdiction_id,
        ROW_NUMBER() OVER (
            PARTITION BY c.domain_name
            ORDER BY
                CASE
                    WHEN j.name_norm = c.organization_normalized
                         AND c.organization_normalized IS NOT NULL THEN 0
                    WHEN j.name_norm = c.agency_normalized
                         AND c.agency_normalized IS NOT NULL THEN 1
                    WHEN j.name_norm = c.city_normalized
                         AND c.city_normalized IS NOT NULL THEN 2
                    WHEN j.name_norm LIKE c.organization_normalized || ' %'
                         AND c.organization_normalized IS NOT NULL THEN 3
                    WHEN c.organization_normalized LIKE j.name_norm || ' %'
                         AND c.organization_normalized IS NOT NULL THEN 4
                    WHEN j.name_norm LIKE c.agency_normalized || ' %'
                         AND c.agency_normalized IS NOT NULL THEN 5
                    WHEN c.agency_normalized LIKE j.name_norm || ' %'
                         AND c.agency_normalized IS NOT NULL THEN 6
                    WHEN j.name_norm LIKE c.city_normalized || ' %'
                         AND c.city_normalized IS NOT NULL THEN 7
                    WHEN c.city_normalized LIKE j.name_norm || ' %'
                         AND c.city_normalized IS NOT NULL THEN 8
                    ELSE 9
                END,
                j.area_sq_miles DESC NULLS LAST
        ) AS match_rank
    FROM gsa_cleaned c
    JOIN domain_type_map dtm
        ON UPPER(TRIM(c.domain_type)) = UPPER(dtm.gsa_domain_type)
    JOIN jurisdictions_name_normalized j
        ON j.jurisdiction_type = dtm.jur_type
       AND j.state_code = c.state_code
    WHERE j.name_norm IS NOT NULL
      AND (
            c.organization_normalized IS NOT NULL
         OR c.agency_normalized IS NOT NULL
         OR c.city_normalized IS NOT NULL
          )
      AND (
            j.name_norm = c.organization_normalized
         OR j.name_norm = c.agency_normalized
         OR j.name_norm = c.city_normalized
         OR (
                c.organization_normalized IS NOT NULL
            AND (
                    j.name_norm LIKE c.organization_normalized || ' %'
                 OR c.organization_normalized LIKE j.name_norm || ' %'
                )
            )
         OR (
                c.agency_normalized IS NOT NULL
            AND (
                    j.name_norm LIKE c.agency_normalized || ' %'
                 OR c.agency_normalized LIKE j.name_norm || ' %'
                )
            )
         OR (
                c.city_normalized IS NOT NULL
            AND (
                    j.name_norm LIKE c.city_normalized || ' %'
                 OR c.city_normalized LIKE j.name_norm || ' %'
                )
            )
          )
),

uscm_base AS (
    SELECT
        UPPER(TRIM(state_code))                           AS state_code,
        TRIM(municipality_name)                           AS municipality_name,
        TRIM(city_website)                                AS raw_website,
        ingestion_date,
        {{ normalize_jurisdiction_label_for_match('municipality_name') }} AS name_normalized
    FROM {{ source('bronze', 'bronze_jurisdictions_municipalities_uscm') }}
    WHERE city_website IS NOT NULL
      AND TRIM(city_website) != ''
),

uscm_ranked AS (
    SELECT
        u.state_code,
        u.municipality_name,
        u.raw_website,
        u.ingestion_date,
        u.name_normalized,
        j.jurisdiction_id,
        ROW_NUMBER() OVER (
            PARTITION BY u.state_code, u.municipality_name
            ORDER BY (j.jurisdiction_id IS NOT NULL) DESC,
                     j.area_sq_miles DESC NULLS LAST
        ) AS match_rank
    FROM uscm_base u
    LEFT JOIN {{ ref('int_jurisdictions') }} j
        ON j.jurisdiction_type = 'municipality'
       AND j.state_code = u.state_code
       AND u.name_normalized IS NOT NULL
       AND (
           ({{ normalize_jurisdiction_label_for_match('j.name') }}) = u.name_normalized
           OR ({{ normalize_jurisdiction_label_for_match('j.name') }}) LIKE u.name_normalized || ' %'
           OR u.name_normalized LIKE ({{ normalize_jurisdiction_label_for_match('j.name') }}) || ' %'
       )
),

uscm_rows_raw AS (
    SELECT
        'uscm|' || u.state_code || '|' || LOWER(REGEXP_REPLACE(TRIM(u.municipality_name), '\\s+', ' ', 'g'))
                                                          AS website_record_key,
        'uscm'                                              AS website_source,
        NULLIF(
          LOWER(TRIM((regexp_match(
            regexp_replace(
              CASE
                WHEN u.raw_website ~* '^https?://' THEN TRIM(u.raw_website)
                ELSE 'https://' || TRIM(REGEXP_REPLACE(u.raw_website, '^/+', ''))
              END,
              '^https?://', '', 'i'
            ),
            '^([^/?#]+)'
          ))[1])),
          ''
        )                                                   AS domain_name,
        CASE
            WHEN u.raw_website ~* '^https?://' THEN TRIM(u.raw_website)
            ELSE 'https://' || TRIM(REGEXP_REPLACE(u.raw_website, '^/+', ''))
        END                                                 AS website_url,
        CAST(NULL AS VARCHAR)                               AS domain_type,
        'municipality'                                      AS jurisdiction_category,
        u.municipality_name                                 AS organization_name,
        CAST(NULL AS VARCHAR)                               AS agency,
        u.municipality_name                                 AS city,
        u.state_code,
        s.state_name                                        AS state,
        u.jurisdiction_id,
        u.ingestion_date,
        CURRENT_TIMESTAMP                                   AS transformed_at
    FROM uscm_ranked u
    LEFT JOIN state_ref s ON u.state_code = s.state_code
    WHERE u.match_rank = 1
),

uscm_rows AS (
    SELECT *
    FROM uscm_rows_raw u
    WHERE NOT {{ uscm_league_county_portal_blocked('u.organization_name', 'u.domain_name') }}
),

league_base AS (
    SELECT
        TRIM(l.row_key)                                   AS row_key,
        UPPER(TRIM(l.state_code))                         AS state_code,
        TRIM(l.municipality_name)                         AS municipality_name,
        TRIM(l.website)                                   AS raw_website,
        NULLIF(TRIM(l.jurisdiction_id), '')               AS bronze_jurisdiction_id,
        NULLIF(TRIM(l.census_geoid), '')                  AS bronze_census_geoid,
        l.ingestion_date,
        {{ normalize_jurisdiction_label_for_match('l.municipality_name') }} AS name_normalized
    FROM {{ source('bronze', 'bronze_jurisdictions_municipalities_league') }} l
    WHERE l.website IS NOT NULL
      AND TRIM(l.website) != ''
      AND TRIM(l.website) !~* '^https?://\s*/?\s*$'
      AND LOWER(TRIM(l.website)) NOT IN ('https://', 'http://', 'https://)', 'http://)')
),

league_ranked AS (
    SELECT
        l.row_key,
        l.state_code,
        l.municipality_name,
        l.raw_website,
        l.ingestion_date,
        l.name_normalized,
        -- Bronze league loader copies ``m-{ST}-{geoid}`` ids from bronze municipalities; warehouse
        -- jurisdictions use ``municipality_{geoid}``. Only trust bronze_jurisdiction_id when it
        -- exists in int_jurisdictions, otherwise fall back to GEOID / normalized name match.
        COALESCE(j_bronze.jurisdiction_id, jg.jurisdiction_id, j.jurisdiction_id) AS jurisdiction_id,
        ROW_NUMBER() OVER (
            PARTITION BY l.row_key
            ORDER BY (COALESCE(j_bronze.jurisdiction_id, jg.jurisdiction_id, j.jurisdiction_id) IS NOT NULL) DESC,
                     j_bronze.jurisdiction_id IS NOT NULL DESC,
                     jg.jurisdiction_id IS NOT NULL DESC,
                     j.area_sq_miles DESC NULLS LAST
        ) AS match_rank
    FROM league_base l
    LEFT JOIN {{ ref('int_jurisdictions') }} j_bronze
        ON NULLIF(TRIM(l.bronze_jurisdiction_id), '') = j_bronze.jurisdiction_id
       AND j_bronze.jurisdiction_type = 'municipality'
    LEFT JOIN {{ ref('int_jurisdictions') }} jg
        ON j_bronze.jurisdiction_id IS NULL
       AND l.bronze_census_geoid IS NOT NULL
       AND jg.jurisdiction_type = 'municipality'
       AND jg.state_code = l.state_code
       AND jg.geoid = l.bronze_census_geoid
    LEFT JOIN {{ ref('int_jurisdictions') }} j
        ON j_bronze.jurisdiction_id IS NULL
       AND jg.jurisdiction_id IS NULL
       AND j.jurisdiction_type = 'municipality'
       AND j.state_code = l.state_code
       AND l.name_normalized IS NOT NULL
       AND (
           ({{ normalize_jurisdiction_label_for_match('j.name') }}) = l.name_normalized
           OR ({{ normalize_jurisdiction_label_for_match('j.name') }}) LIKE l.name_normalized || ' %'
           OR l.name_normalized LIKE ({{ normalize_jurisdiction_label_for_match('j.name') }}) || ' %'
       )
),

league_rows_raw AS (
    SELECT
        'league|' || l.row_key                                  AS website_record_key,
        'league'                                                AS website_source,
        NULLIF(
          LOWER(TRIM((regexp_match(
            regexp_replace(
              CASE
                WHEN l.raw_website ~* '^https?://' THEN TRIM(l.raw_website)
                ELSE 'https://' || TRIM(REGEXP_REPLACE(l.raw_website, '^/+', ''))
              END,
              '^https?://', '', 'i'
            ),
            '^([^/?#]+)'
          ))[1])),
          ''
        )                                                       AS domain_name,
        CASE
            WHEN l.raw_website ~* '^https?://' THEN TRIM(l.raw_website)
            ELSE 'https://' || TRIM(REGEXP_REPLACE(l.raw_website, '^/+', ''))
        END                                                     AS website_url,
        CAST(NULL AS VARCHAR)                                   AS domain_type,
        'municipality'                                          AS jurisdiction_category,
        l.municipality_name                                     AS organization_name,
        CAST(NULL AS VARCHAR)                                   AS agency,
        l.municipality_name                                     AS city,
        l.state_code,
        s.state_name                                            AS state,
        l.jurisdiction_id,
        l.ingestion_date,
        CURRENT_TIMESTAMP                                       AS transformed_at
    FROM league_ranked l
    LEFT JOIN state_ref s ON l.state_code = s.state_code
    WHERE l.match_rank = 1
),

league_rows AS (
    SELECT *
    FROM league_rows_raw l
    WHERE NOT {{ uscm_league_county_portal_blocked('l.organization_name', 'l.domain_name') }}
),

nces_base AS (
    SELECT
        TRIM(n.nces_id)                                   AS nces_id,
        TRIM(n.district_name)                             AS district_name,
        UPPER(TRIM(n.state_code))                         AS state_code,
        TRIM(n.website)                                   AS raw_website,
        n.ingestion_date,
        j.jurisdiction_id
    FROM {{ source('bronze', 'bronze_jurisdictions_school_districts_nces_directory') }} n
    LEFT JOIN {{ ref('int_jurisdictions') }} j
        ON j.jurisdiction_type = 'school_district'
       AND j.geoid = LPAD(TRIM(n.nces_id), 7, '0')
    WHERE n.website IS NOT NULL
      AND TRIM(n.website) != ''
),

nces_rows AS (
    SELECT
        'nces_directory|' || n.nces_id                      AS website_record_key,
        'nces_directory'                                  AS website_source,
        NULLIF(
          LOWER(TRIM((regexp_match(
            regexp_replace(
              CASE
                WHEN n.raw_website ~* '^https?://' THEN TRIM(n.raw_website)
                ELSE 'https://' || TRIM(REGEXP_REPLACE(n.raw_website, '^/+', ''))
              END,
              '^https?://', '', 'i'
            ),
            '^([^/?#]+)'
          ))[1])),
          ''
        )                                                   AS domain_name,
        CASE
            WHEN n.raw_website ~* '^https?://' THEN TRIM(n.raw_website)
            ELSE 'https://' || TRIM(REGEXP_REPLACE(n.raw_website, '^/+', ''))
        END                                                 AS website_url,
        CAST(NULL AS VARCHAR)                               AS domain_type,
        'school_district'                                  AS jurisdiction_category,
        n.district_name                                     AS organization_name,
        CAST(NULL AS VARCHAR)                               AS agency,
        CAST(NULL AS VARCHAR)                               AS city,
        n.state_code,
        s.state_name                                        AS state,
        n.jurisdiction_id,
        n.ingestion_date,
        CURRENT_TIMESTAMP                                   AS transformed_at
    FROM nces_base n
    LEFT JOIN state_ref s ON n.state_code = s.state_code
),

naco_base AS (
    SELECT
        TRIM(n.county_name)                               AS county_name,
        UPPER(TRIM(n.state_code))                         AS state_code,
        LPAD(TRIM(n.fips_code), 5, '0')                   AS county_geoid,
        TRIM(n.website)                                   AS raw_website,
        n.ingestion_date,
        j.jurisdiction_id
    FROM {{ source('bronze', 'bronze_jurisdictions_counties_naco') }} n
    LEFT JOIN {{ ref('int_jurisdictions') }} j
        ON j.jurisdiction_type = 'county'
       AND j.state_code = UPPER(TRIM(n.state_code))
       AND j.geoid = LPAD(TRIM(n.fips_code), 5, '0')
    WHERE n.website IS NOT NULL
      AND TRIM(n.website) != ''
      AND n.fips_code IS NOT NULL
      AND TRIM(n.fips_code) != ''
),

-- Normalize to https://host (lowercase, strip trailing /, drop www.) for URL ↔ jurisdiction matching on GSA rows
uscm_url_referral AS (
    SELECT
        (regexp_match(
            NULLIF(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            LOWER(
                                CASE
                                    WHEN u.raw_website ~* '^https?://' THEN TRIM(u.raw_website)
                                    ELSE 'https://' || TRIM(REGEXP_REPLACE(u.raw_website, '^/+', ''))
                                END
                            ),
                            '^http:', 'https:',
                            'i'
                        ),
                        '^https://www\.', 'https://',
                        'i'
                    ),
                    '/+$', '',
                    'g'
                ),
                ''
            ),
            '^(https://[^/?#]+)'
        ))[1]                                                    AS origin_norm,
        u.jurisdiction_id,
        'municipality'                                           AS matched_jurisdiction_category,
        'uscm'                                                   AS referral_source
    FROM uscm_ranked u
    WHERE u.match_rank = 1
      AND u.jurisdiction_id IS NOT NULL
),

league_url_referral AS (
    SELECT
        (regexp_match(
            NULLIF(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            LOWER(
                                CASE
                                    WHEN l.raw_website ~* '^https?://' THEN TRIM(l.raw_website)
                                    ELSE 'https://' || TRIM(REGEXP_REPLACE(l.raw_website, '^/+', ''))
                                END
                            ),
                            '^http:', 'https:',
                            'i'
                        ),
                        '^https://www\.', 'https://',
                        'i'
                    ),
                    '/+$', '',
                    'g'
                ),
                ''
            ),
            '^(https://[^/?#]+)'
        ))[1]                                                    AS origin_norm,
        l.jurisdiction_id,
        'municipality'                                           AS matched_jurisdiction_category,
        'league'                                                 AS referral_source
    FROM league_ranked l
    WHERE l.match_rank = 1
      AND l.jurisdiction_id IS NOT NULL
),

nces_url_referral AS (
    SELECT
        (regexp_match(
            NULLIF(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            LOWER(
                                CASE
                                    WHEN n.raw_website ~* '^https?://' THEN TRIM(n.raw_website)
                                    ELSE 'https://' || TRIM(REGEXP_REPLACE(n.raw_website, '^/+', ''))
                                END
                            ),
                            '^http:', 'https:',
                            'i'
                        ),
                        '^https://www\.', 'https://',
                        'i'
                    ),
                    '/+$', '',
                    'g'
                ),
                ''
            ),
            '^(https://[^/?#]+)'
        ))[1]                                                    AS origin_norm,
        n.jurisdiction_id,
        'school_district'                                      AS matched_jurisdiction_category,
        'nces_directory'                                       AS referral_source
    FROM nces_base n
    WHERE n.jurisdiction_id IS NOT NULL
),

naco_url_referral AS (
    SELECT
        (regexp_match(
            NULLIF(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            LOWER(
                                CASE
                                    WHEN n.raw_website ~* '^https?://' THEN TRIM(n.raw_website)
                                    ELSE 'https://' || TRIM(REGEXP_REPLACE(n.raw_website, '^/+', ''))
                                END
                            ),
                            '^http:', 'https:',
                            'i'
                        ),
                        '^https://www\.', 'https://',
                        'i'
                    ),
                    '/+$', '',
                    'g'
                ),
                ''
            ),
            '^(https://[^/?#]+)'
        ))[1]                                                    AS origin_norm,
        n.jurisdiction_id,
        'county'                                               AS matched_jurisdiction_category,
        'naco'                                                 AS referral_source
    FROM naco_base n
    WHERE n.jurisdiction_id IS NOT NULL
),

referral_url_jurisdictions AS (
    SELECT * FROM uscm_url_referral WHERE origin_norm IS NOT NULL
    UNION ALL
    SELECT * FROM league_url_referral WHERE origin_norm IS NOT NULL
    UNION ALL
    SELECT * FROM nces_url_referral WHERE origin_norm IS NOT NULL
    UNION ALL
    SELECT * FROM naco_url_referral WHERE origin_norm IS NOT NULL
),

gsa_url_match AS (
    SELECT
        c.domain_name,
        r.jurisdiction_id,
        ROW_NUMBER() OVER (
            PARTITION BY c.domain_name
            ORDER BY
                CASE WHEN r.matched_jurisdiction_category = c.jurisdiction_category THEN 0 ELSE 1 END,
                CASE r.referral_source
                    WHEN 'uscm' THEN 1
                    WHEN 'league' THEN 2
                    WHEN 'nces_directory' THEN 3
                    WHEN 'naco' THEN 4
                END
        ) AS match_rank
    FROM gsa_cleaned c
    INNER JOIN referral_url_jurisdictions r
        ON r.origin_norm = (regexp_match(
            NULLIF(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            LOWER(TRIM(c.website_url)),
                            '^http:', 'https:',
                            'i'
                        ),
                        '^https://www\.', 'https://',
                        'i'
                    ),
                    '/+$', '',
                    'g'
                ),
                ''
            ),
            '^(https://[^/?#]+)'
        ))[1]
),

-- When registrant text does not match Census ``name`` but the ``.gov`` host stem equals the
-- jurisdiction name (letters only, optional trailing state code in the domain), attach the row.
-- Runs only after URL and full name-match passes; tie-break by land area.
gsa_domain_compact_hint AS (
    SELECT
        c.domain_name,
        j.jurisdiction_id,
        ROW_NUMBER() OVER (
            PARTITION BY c.domain_name
            ORDER BY j.area_sq_miles DESC NULLS LAST
        ) AS match_rank
    FROM gsa_cleaned c
    INNER JOIN domain_type_map dtm
        ON UPPER(TRIM(c.domain_type)) = UPPER(dtm.gsa_domain_type)
    INNER JOIN jurisdictions_name_normalized j
        ON j.state_code = c.state_code
       AND j.jurisdiction_type = dtm.jur_type
       AND j.name_norm IS NOT NULL
    CROSS JOIN LATERAL (
        SELECT
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    LOWER(TRIM(c.domain_name)),
                    '\.(gov|us)$',
                    '',
                    'i'
                ),
                '[^a-z0-9]+',
                '',
                'g'
            ) AS stem_all
    ) sa
    CROSS JOIN LATERAL (
        SELECT
            CASE
                WHEN LENGTH(sa.stem_all) > 2
                     AND RIGHT(sa.stem_all, 2) = LOWER(TRIM(c.state_code))
                THEN SUBSTRING(sa.stem_all, 1, LENGTH(sa.stem_all) - 2)
                ELSE sa.stem_all
            END AS stem_no_state
    ) sn
    WHERE LENGTH(sn.stem_no_state) >= 6
      AND REGEXP_REPLACE(j.name_norm, '[^a-z0-9]+', '', 'g') = sn.stem_no_state
),

-- GSA ``State or territory`` (and election variant): attach to the single state-government row
-- for that USPS code. Registrant ``organization`` is often blank and agency text rarely equals
-- Census ``name`` (e.g. "State of Connecticut …" vs "Connecticut"); short hosts like ``ct.gov``
-- fail the >=6-letter stem rule in ``gsa_domain_compact_hint``.
gsa_state_direct_match AS (
    SELECT
        c.domain_name,
        j.jurisdiction_id
    FROM gsa_cleaned c
    INNER JOIN domain_type_map dtm
        ON UPPER(TRIM(c.domain_type)) = UPPER(dtm.gsa_domain_type)
       AND dtm.jur_type = 'state'
    INNER JOIN jurisdictions_name_normalized j
        ON j.jurisdiction_type = 'state'
       AND j.state_code = c.state_code
),

gsa_rows AS (
    SELECT
        c.website_record_key,
        c.website_source,
        c.domain_name,
        c.website_url,
        c.domain_type,
        c.jurisdiction_category,
        c.organization_name,
        c.agency,
        c.city,
        c.state_code,
        s.state_name                                        AS state,
        COALESCE(
            gsm.jurisdiction_id,
            gum.jurisdiction_id,
            jm.jurisdiction_id,
            gdh.jurisdiction_id
        ) AS jurisdiction_id,
        c.ingestion_date,
        CURRENT_TIMESTAMP                                   AS transformed_at
    FROM gsa_cleaned c
    LEFT JOIN state_ref s ON c.state_code = s.state_code
    LEFT JOIN gsa_state_direct_match gsm
        ON c.domain_name = gsm.domain_name
    LEFT JOIN jurisdiction_match jm
        ON c.domain_name = jm.domain_name
       AND jm.match_rank = 1
    LEFT JOIN gsa_url_match gum
        ON c.domain_name = gum.domain_name
       AND gum.match_rank = 1
    LEFT JOIN gsa_domain_compact_hint gdh
        ON c.domain_name = gdh.domain_name
       AND gdh.match_rank = 1
),

wikidata_municipality_base AS (
    SELECT
        TRIM(w.geoid)                                     AS geoid,
        UPPER(TRIM(w.usps))                               AS state_code,
        TRIM(w.official_website)                          AS raw_website,
        NULLIF(TRIM(w.wikidata_id), '')                   AS wikidata_id,
        TRIM(w.name)                                      AS place_name,
        COALESCE(
            w.official_website_updated_at,
            w.wikidata_last_updated,
            w.wikidata_fetched_at
        )                                                 AS ingestion_ts,
        j.jurisdiction_id
    FROM {{ source('bronze', 'bronze_jurisdictions_municipalities_wikidata') }} w
    LEFT JOIN {{ ref('int_jurisdictions') }} j
        ON j.jurisdiction_type = 'municipality'
       AND j.state_code = UPPER(TRIM(w.usps))
       AND j.geoid = TRIM(w.geoid)
    WHERE w.official_website IS NOT NULL
      AND BTRIM(w.official_website) <> ''
),

wikidata_county_base AS (
    SELECT
        TRIM(w.geoid)                                     AS geoid,
        UPPER(TRIM(w.usps))                               AS state_code,
        TRIM(w.official_website)                          AS raw_website,
        NULLIF(TRIM(w.wikidata_id), '')                   AS wikidata_id,
        TRIM(w.name)                                      AS county_name,
        COALESCE(
            w.official_website_updated_at,
            w.wikidata_last_updated,
            w.wikidata_fetched_at
        )                                                 AS ingestion_ts,
        j.jurisdiction_id
    FROM {{ source('bronze', 'bronze_jurisdictions_counties_wikidata') }} w
    LEFT JOIN {{ ref('int_jurisdictions') }} j
        ON j.jurisdiction_type = 'county'
       AND j.state_code = UPPER(TRIM(w.usps))
       AND j.geoid = TRIM(w.geoid)
    WHERE w.official_website IS NOT NULL
      AND BTRIM(w.official_website) <> ''
),

wikidata_rows AS (
    SELECT
        'wikidata|' || COALESCE(w.wikidata_id, w.geoid)   AS website_record_key,
        'wikidata'                                        AS website_source,
        NULLIF(
          LOWER(TRIM((regexp_match(
            regexp_replace(
              CASE
                WHEN w.raw_website ~* '^https?://' THEN TRIM(w.raw_website)
                ELSE 'https://' || TRIM(REGEXP_REPLACE(w.raw_website, '^/+', ''))
              END,
              '^https?://', '', 'i'
            ),
            '^([^/?#]+)'
          ))[1])),
          ''
        )                                                 AS domain_name,
        CASE
            WHEN w.raw_website ~* '^https?://' THEN TRIM(w.raw_website)
            ELSE 'https://' || TRIM(REGEXP_REPLACE(w.raw_website, '^/+', ''))
        END                                               AS website_url,
        CAST(NULL AS VARCHAR)                             AS domain_type,
        'municipality'                                    AS jurisdiction_category,
        w.place_name                                      AS organization_name,
        CAST(NULL AS VARCHAR)                             AS agency,
        CAST(NULL AS VARCHAR)                             AS city,
        w.state_code,
        s.state_name                                      AS state,
        w.jurisdiction_id,
        w.ingestion_ts                                    AS ingestion_date,
        CURRENT_TIMESTAMP                                 AS transformed_at
    FROM wikidata_municipality_base w
    LEFT JOIN state_ref s ON w.state_code = s.state_code

    UNION ALL

    SELECT
        'wikidata|' || COALESCE(w.wikidata_id, w.geoid)   AS website_record_key,
        'wikidata'                                        AS website_source,
        NULLIF(
          LOWER(TRIM((regexp_match(
            regexp_replace(
              CASE
                WHEN w.raw_website ~* '^https?://' THEN TRIM(w.raw_website)
                ELSE 'https://' || TRIM(REGEXP_REPLACE(w.raw_website, '^/+', ''))
              END,
              '^https?://', '', 'i'
            ),
            '^([^/?#]+)'
          ))[1])),
          ''
        )                                                 AS domain_name,
        CASE
            WHEN w.raw_website ~* '^https?://' THEN TRIM(w.raw_website)
            ELSE 'https://' || TRIM(REGEXP_REPLACE(w.raw_website, '^/+', ''))
        END                                               AS website_url,
        CAST(NULL AS VARCHAR)                             AS domain_type,
        'county'                                          AS jurisdiction_category,
        w.county_name                                     AS organization_name,
        CAST(NULL AS VARCHAR)                             AS agency,
        CAST(NULL AS VARCHAR)                             AS city,
        w.state_code,
        s.state_name                                      AS state,
        w.jurisdiction_id,
        w.ingestion_ts                                    AS ingestion_date,
        CURRENT_TIMESTAMP                                 AS transformed_at
    FROM wikidata_county_base w
    LEFT JOIN state_ref s ON w.state_code = s.state_code
),

naco_rows AS (
    SELECT
        'naco|' || n.county_geoid                           AS website_record_key,
        'naco'                                            AS website_source,
        NULLIF(
          LOWER(TRIM((regexp_match(
            regexp_replace(
              CASE
                WHEN n.raw_website ~* '^https?://' THEN TRIM(n.raw_website)
                ELSE 'https://' || TRIM(REGEXP_REPLACE(n.raw_website, '^/+', ''))
              END,
              '^https?://', '', 'i'
            ),
            '^([^/?#]+)'
          ))[1])),
          ''
        )                                                   AS domain_name,
        CASE
            WHEN n.raw_website ~* '^https?://' THEN TRIM(n.raw_website)
            ELSE 'https://' || TRIM(REGEXP_REPLACE(n.raw_website, '^/+', ''))
        END                                                 AS website_url,
        CAST(NULL AS VARCHAR)                               AS domain_type,
        'county'                                           AS jurisdiction_category,
        n.county_name                                       AS organization_name,
        CAST(NULL AS VARCHAR)                               AS agency,
        CAST(NULL AS VARCHAR)                               AS city,
        n.state_code,
        s.state_name                                        AS state,
        n.jurisdiction_id,
        n.ingestion_date,
        CURRENT_TIMESTAMP                                   AS transformed_at
    FROM naco_base n
    LEFT JOIN state_ref s ON n.state_code = s.state_code
),

-- Hand-picked canonical URL when upstream sources omit it or list a failing / alternate host.
jurisdiction_url_override_seed AS (
    SELECT
        TRIM(ob.jurisdiction_id) AS jurisdiction_id,
        TRIM(ob.website_url) AS raw_website
    FROM {{ ref('jurisdiction_website_url_overrides') }} ob
    WHERE ob.jurisdiction_id IS NOT NULL
      AND TRIM(ob.jurisdiction_id) <> ''
      AND ob.website_url IS NOT NULL
      AND TRIM(ob.website_url) <> ''
),

-- Census GEOIDs embed 2-digit state FIPS at the left; map to USPS for orphan overrides (no int_jurisdictions row).
state_fips_to_usps AS (
    SELECT * FROM (VALUES
        ('01', 'AL'), ('02', 'AK'), ('04', 'AZ'), ('05', 'AR'), ('06', 'CA'), ('08', 'CO'), ('09', 'CT'),
        ('10', 'DE'), ('11', 'DC'), ('12', 'FL'), ('13', 'GA'), ('15', 'HI'), ('16', 'ID'), ('17', 'IL'),
        ('18', 'IN'), ('19', 'IA'), ('20', 'KS'), ('21', 'KY'), ('22', 'LA'), ('23', 'ME'), ('24', 'MD'),
        ('25', 'MA'), ('26', 'MI'), ('27', 'MN'), ('28', 'MS'), ('29', 'MO'), ('30', 'MT'), ('31', 'NE'),
        ('32', 'NV'), ('33', 'NH'), ('34', 'NJ'), ('35', 'NM'), ('36', 'NY'), ('37', 'NC'), ('38', 'ND'),
        ('39', 'OH'), ('40', 'OK'), ('41', 'OR'), ('42', 'PA'), ('44', 'RI'), ('45', 'SC'), ('46', 'SD'),
        ('47', 'TN'), ('48', 'TX'), ('49', 'UT'), ('50', 'VT'), ('51', 'VA'), ('53', 'WA'), ('54', 'WV'),
        ('55', 'WI'), ('56', 'WY'), ('60', 'AS'), ('66', 'GU'), ('69', 'MP'), ('72', 'PR'), ('78', 'VI')
    ) AS m(state_fips, state_code)
),

override_rows AS (
    SELECT
        -- One seed row per URL; multiple overrides per jurisdiction must not share the same key
        -- (schema uniqueness test and any dedupe-on-key tooling).
        'override|' || TRIM(o.jurisdiction_id) || '|' || md5(
            CASE
                WHEN o.raw_website ~* '^https?://' THEN TRIM(o.raw_website)
                ELSE 'https://' || TRIM(REGEXP_REPLACE(o.raw_website, '^/+', ''))
            END
        ) AS website_record_key,
        'override' AS website_source,
        NULLIF(
          LOWER(TRIM((regexp_match(
            regexp_replace(
              CASE
                WHEN o.raw_website ~* '^https?://' THEN TRIM(o.raw_website)
                ELSE 'https://' || TRIM(REGEXP_REPLACE(o.raw_website, '^/+', ''))
              END,
              '^https?://', '', 'i'
            ),
            '^([^/?#]+)'
          ))[1])),
          ''
        ) AS domain_name,
        CASE
            WHEN o.raw_website ~* '^https?://' THEN TRIM(o.raw_website)
            ELSE 'https://' || TRIM(REGEXP_REPLACE(o.raw_website, '^/+', ''))
        END AS website_url,
        CAST(NULL AS VARCHAR) AS domain_type,
        COALESCE(
            j.jurisdiction_type,
            CASE
                WHEN o.jurisdiction_id ~* '^county_' THEN 'county'
                WHEN o.jurisdiction_id ~* '^municipality_' THEN 'municipality'
                WHEN o.jurisdiction_id ~* '^school_district_' THEN 'school_district'
                WHEN o.jurisdiction_id ~* '^township_' THEN 'township'
                WHEN o.jurisdiction_id ~* '^state_' THEN 'state'
                ELSE 'municipality'
            END
        ) AS jurisdiction_category,
        COALESCE(j.name, TRIM(o.jurisdiction_id)) AS organization_name,
        CAST(NULL AS VARCHAR) AS agency,
        CAST(NULL AS VARCHAR) AS city,
        COALESCE(j.state_code, s2.state_code) AS state_code,
        COALESCE(s.state_name, s2.state_name) AS state,
        TRIM(o.jurisdiction_id) AS jurisdiction_id,
        CURRENT_TIMESTAMP AS ingestion_date,
        CURRENT_TIMESTAMP AS transformed_at
    FROM jurisdiction_url_override_seed o
    LEFT JOIN {{ ref('int_jurisdictions') }} j
        ON j.jurisdiction_id = TRIM(o.jurisdiction_id)
    LEFT JOIN state_ref s ON j.state_code = s.state_code
    LEFT JOIN state_fips_to_usps fmap
        ON fmap.state_fips = LEFT(
            regexp_replace(TRIM(o.jurisdiction_id), '^(county|municipality|state|township|school_district)_', '', 'i'),
            2
        )
    LEFT JOIN state_ref s2 ON s2.state_code = fmap.state_code
),

combined AS (
    SELECT * FROM gsa_rows
    UNION ALL
    SELECT * FROM uscm_rows
    UNION ALL
    SELECT * FROM league_rows
    UNION ALL
    SELECT * FROM nces_rows
    UNION ALL
    SELECT * FROM naco_rows
    UNION ALL
    SELECT * FROM wikidata_rows
    UNION ALL
    SELECT * FROM override_rows
),

-- Human-curated hostnames to exclude (wrong GSA rows, parked domains, etc.). See seed CSV.
domain_denylist AS (
    SELECT lower(btrim(domain)) AS domain
    FROM {{ ref('jurisdiction_website_domain_denylist') }}
    WHERE domain IS NOT NULL
      AND btrim(domain) <> ''
)

SELECT
    c.website_record_key,
    c.website_source,
    c.domain_name,
    c.website_url,
    c.domain_type,
    c.jurisdiction_category,
    c.organization_name,
    c.agency,
    c.city,
    c.state_code,
    c.state,
    c.jurisdiction_id,
    c.ingestion_date,
    c.transformed_at
FROM combined c
WHERE NOT EXISTS (
    SELECT 1
    FROM domain_denylist d
    WHERE d.domain = lower(btrim(c.domain_name))
)
