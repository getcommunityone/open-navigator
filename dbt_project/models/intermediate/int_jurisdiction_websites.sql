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
-- Python scrapers rank **override** (this seed) first, then **NACO over GSA** for ``county_*`` ids so
-- curated and NACo county URLs beat questionable GSA .gov registry matches.

-- Map GSA domain_type labels to the jurisdiction_type values used in int_jurisdictions
-- so the name-match join targets the right pool of records.
WITH domain_type_map AS (
    SELECT * FROM (VALUES
        ('City',             'municipality'),
        ('Town',             'municipality'),
        ('Village',          'municipality'),
        ('Borough',          'municipality'),
        ('County',           'county'),
        ('State',            'state'),
        ('School District',  'school_district'),
        ('Township',         'township')
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

uscm_rows AS (
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
                    WHEN 'nces_directory' THEN 2
                    WHEN 'naco' THEN 3
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
        COALESCE(gum.jurisdiction_id, jm.jurisdiction_id, gdh.jurisdiction_id) AS jurisdiction_id,
        c.ingestion_date,
        CURRENT_TIMESTAMP                                   AS transformed_at
    FROM gsa_cleaned c
    LEFT JOIN state_ref s ON c.state_code = s.state_code
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

override_rows AS (
    SELECT
        'override|' || j.jurisdiction_id AS website_record_key,
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
        j.jurisdiction_type AS jurisdiction_category,
        j.name AS organization_name,
        CAST(NULL AS VARCHAR) AS agency,
        CAST(NULL AS VARCHAR) AS city,
        j.state_code,
        s.state_name AS state,
        j.jurisdiction_id,
        CURRENT_TIMESTAMP AS ingestion_date,
        CURRENT_TIMESTAMP AS transformed_at
    FROM jurisdiction_url_override_seed o
    INNER JOIN {{ ref('int_jurisdictions') }} j
        ON j.jurisdiction_id = o.jurisdiction_id
    LEFT JOIN state_ref s ON j.state_code = s.state_code
),

combined AS (
    SELECT * FROM gsa_rows
    UNION ALL
    SELECT * FROM uscm_rows
    UNION ALL
    SELECT * FROM nces_rows
    UNION ALL
    SELECT * FROM naco_rows
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
