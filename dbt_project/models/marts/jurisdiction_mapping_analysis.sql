{{ config(
    materialized='table',
    tags=['mart', 'jurisdictions', 'data_quality', 'llm_export']
) }}

/*
Mart: one row per jurisdiction (county, municipality, school district) with the
**primary** website chosen using the same source priority as
``scripts/discovery/jurisdiction_discovery_pipeline.py`` (NACO before GSA for counties;
GSA before NACO for other types). USCM = municipal / Conference of Mayors–style directory;
NCES = school district directory; NACO = county association directory; Wikidata = P856 from
``bronze_jurisdictions_{municipalities,counties}_wikidata`` (fallback after curated directories).

``primary_url_syntax_ok`` / ``primary_url_likely_wrong_host`` / ``primary_url_passes_basic_checks`` are
**static** SQL checks (scheme + hostname shape + simple deny patterns), not HTTP reachability. For live
HEAD/GET validation see ``scripts/enrichment/enrich_jurisdiction_websites_search.py``.

Downstream: LLM context, QA dashboards, ``export_jurisdiction_mapping_quality_json.py``.
``municipality_place_kind`` / ``lsad`` split municipalities for CDP vs incorporated city (LSAD 25) vs other LSADs.
Latest matching ``public.jurisdiction_acs`` row (by ``acs_vintage_year``) adds ``acs_population_tier`` (B01003 size class)
and ``acs_income_level`` (B19013 bucket) for county / municipality / school_district GEOIDs.
*/

WITH base AS (
    SELECT
        j.jurisdiction_id,
        j.name,
        j.state_code,
        j.jurisdiction_type,
        s.website_source,
        s.website_url,
        s.website_record_key,
        s.domain_name,
        CASE
            WHEN j.jurisdiction_type = 'municipality'
                 AND s.website_source IN ('uscm', 'league')
                 AND {{ uscm_league_county_portal_blocked('j.name', 's.domain_name') }}
                THEN 99
            WHEN j.jurisdiction_id LIKE 'county_%' THEN
                CASE s.website_source
                    WHEN 'override' THEN 0
                    WHEN 'naco' THEN 1
                    WHEN 'gsa' THEN 2
                    WHEN 'wikidata' THEN 3
                    WHEN 'league' THEN 4
                    WHEN 'uscm' THEN 5
                    WHEN 'nces_directory' THEN 6
                    ELSE 9
                END
            ELSE
                CASE s.website_source
                    WHEN 'override' THEN 0
                    WHEN 'gsa' THEN 1
                    WHEN 'league' THEN 2
                    WHEN 'wikidata' THEN 3
                    WHEN 'uscm' THEN 4
                    WHEN 'nces_directory' THEN 5
                    WHEN 'naco' THEN 6
                    ELSE 9
                END
        END AS source_priority
    FROM {{ ref('int_jurisdictions') }} j
    LEFT JOIN {{ ref('int_jurisdiction_websites') }} s
        ON s.jurisdiction_id = j.jurisdiction_id
    WHERE j.jurisdiction_type IN ('county', 'municipality', 'school_district', 'state')
),

flags AS (
    SELECT
        jurisdiction_id,
        BOOL_OR(website_source = 'naco') AS has_naco_row,
        BOOL_OR(website_source = 'uscm') AS has_uscm_row,
        BOOL_OR(website_source = 'nces_directory') AS has_nces_row,
        BOOL_OR(website_source = 'gsa') AS has_gsa_row,
        BOOL_OR(website_source = 'league') AS has_league_row,
        BOOL_OR(website_source = 'wikidata') AS has_wikidata_row,
        BOOL_OR(website_source = 'override') AS has_override_row,
        COUNT(*) FILTER (WHERE website_url IS NOT NULL AND BTRIM(website_url) <> '') AS n_url_rows
    FROM {{ ref('int_jurisdiction_websites') }}
    GROUP BY 1
),

primary_pick AS (
    SELECT DISTINCT ON (b.jurisdiction_id)
        b.jurisdiction_id,
        b.website_source AS primary_website_source,
        b.website_url AS primary_website_url,
        b.website_record_key AS primary_website_record_key,
        b.domain_name AS primary_domain_name
    FROM base b
    WHERE b.website_url IS NOT NULL
      AND BTRIM(b.website_url) <> ''
    ORDER BY
        b.jurisdiction_id,
        b.source_priority,
        -- Among GSA state-portal candidates, prefer ``{st}.gov`` / ``portal.{st}.gov`` over specialty .gov sites.
        CASE
            WHEN b.jurisdiction_type = 'state' AND b.website_source = 'gsa' THEN
                CASE
                    WHEN LOWER(TRIM(b.domain_name)) = LOWER(TRIM(b.state_code)) || '.gov' THEN 0
                    WHEN LOWER(TRIM(b.domain_name)) = 'portal.' || LOWER(TRIM(b.state_code)) || '.gov' THEN 1
                    WHEN LOWER(TRIM(b.domain_name)) LIKE 'www.' || LOWER(TRIM(b.state_code)) || '.gov' THEN 2
                    ELSE 3
                END
            ELSE 0
        END,
        LENGTH(COALESCE(b.domain_name, '')),
        b.website_record_key
),

/* URL shape only — not HTTP reachability (no network signal in the warehouse). */
picked AS (
    SELECT
        j.jurisdiction_id,
        j.name,
        j.state_code,
        j.jurisdiction_type,
        j.geoid,
        j.lsad,
        p.primary_website_url,
        p.primary_website_source,
        p.primary_website_record_key,
        p.primary_domain_name,
        COALESCE(f.has_naco_row, FALSE) AS has_naco_source,
        COALESCE(f.has_uscm_row, FALSE) AS has_uscm_source,
        COALESCE(f.has_nces_row, FALSE) AS has_nces_directory_source,
        COALESCE(f.has_gsa_row, FALSE) AS has_gsa_source,
        COALESCE(f.has_league_row, FALSE) AS has_league_source,
        COALESCE(f.has_wikidata_row, FALSE) AS has_wikidata_source,
        COALESCE(f.has_override_row, FALSE) AS has_override_source,
        COALESCE(f.n_url_rows, 0)::BIGINT AS n_website_candidate_rows,
        (p.primary_website_url IS NOT NULL AND BTRIM(p.primary_website_url) <> '') AS has_primary_website,
        LOWER(BTRIM(COALESCE(p.primary_website_url, ''))) AS primary_url_lc
    FROM {{ ref('int_jurisdictions') }} j
    LEFT JOIN flags f ON f.jurisdiction_id = j.jurisdiction_id
    LEFT JOIN primary_pick p ON p.jurisdiction_id = j.jurisdiction_id
    WHERE j.jurisdiction_type IN ('county', 'municipality', 'school_district', 'state')
),

{% if jurisdiction_acs_exists() %}
acs_latest AS (
    SELECT
        picked.*,
        acs_row.acs_vintage_year,
        acs_row.total_population AS acs_total_population,
        acs_row.jurisdiction AS acs_population_tier,
        acs_row.income_level AS acs_income_level
    FROM picked
    LEFT JOIN LATERAL (
        SELECT
            a.acs_vintage_year,
            a.total_population,
            a.jurisdiction,
            a.income_level
        FROM {{ source('gold_runtime', 'jurisdiction_acs') }} a
        WHERE (
            picked.jurisdiction_type = 'municipality'
            AND a.geography_type = 'place'
            AND a.geoid = picked.geoid
        )
        OR (
            picked.jurisdiction_type = 'county'
            AND a.geography_type = 'county'
            AND a.geoid = picked.geoid
        )
        OR (
            picked.jurisdiction_type = 'school_district'
            AND a.geography_type = 'sduni'
            AND a.geoid = picked.geoid
        )
        ORDER BY a.acs_vintage_year DESC NULLS LAST
        LIMIT 1
    ) acs_row ON TRUE
)
{% else %}
acs_latest AS (
    SELECT
        picked.*,
        CAST(NULL AS VARCHAR(4)) AS acs_vintage_year,
        CAST(NULL AS BIGINT) AS acs_total_population,
        CAST(NULL AS VARCHAR(120)) AS acs_population_tier,
        CAST(NULL AS VARCHAR(80)) AS acs_income_level
    FROM picked
)
{% endif %}

SELECT
    picked.jurisdiction_id,
    picked.name,
    picked.state_code,
    picked.jurisdiction_type,
    picked.geoid,
    picked.primary_website_url,
    picked.primary_website_source,
    picked.primary_website_record_key,
    picked.primary_domain_name,
    'source_priority_ranked_union' AS website_mapping_method,
    picked.has_naco_source,
    picked.has_uscm_source,
    picked.has_nces_directory_source,
    picked.has_gsa_source,
    picked.has_league_source,
    picked.has_wikidata_source,
    picked.has_override_source,
    picked.n_website_candidate_rows,
    picked.has_primary_website,
    CASE
        WHEN NOT picked.has_primary_website THEN NULL::BOOLEAN
        ELSE
            picked.primary_url_lc ~ '^https?://'
            AND COALESCE(SUBSTRING(picked.primary_url_lc FROM '^https?://([^/?#]+)'), '') <> ''
            AND LENGTH(SUBSTRING(picked.primary_url_lc FROM '^https?://([^/?#]+)')) >= 3
            AND SUBSTRING(picked.primary_url_lc FROM '^https?://([^/?#]+)') ~ '\.'
    END AS primary_url_syntax_ok,
    CASE
        WHEN NOT picked.has_primary_website THEN NULL::BOOLEAN
        ELSE
            SUBSTRING(picked.primary_url_lc FROM '^https?://([^/?#]+)') ~* '(wikipedia|wikidata|facebook|fb\\.com|instagram|twitter|t\\.co|youtube|youtu\\.be|linkedin)\\.|[./](facebook|instagram|twitter|youtube|linkedin|wikipedia|wikidata)\\.'
            OR (
                picked.jurisdiction_type = 'municipality'
                AND picked.primary_website_source IN ('uscm', 'league')
                AND {{ uscm_league_county_portal_blocked('picked.name', 'picked.primary_domain_name') }}
            )
    END AS primary_url_likely_wrong_host,
    CASE
        WHEN NOT picked.has_primary_website THEN NULL::BOOLEAN
        WHEN
            picked.primary_url_lc ~ '^https?://'
            AND COALESCE(SUBSTRING(picked.primary_url_lc FROM '^https?://([^/?#]+)'), '') <> ''
            AND LENGTH(SUBSTRING(picked.primary_url_lc FROM '^https?://([^/?#]+)')) >= 3
            AND SUBSTRING(picked.primary_url_lc FROM '^https?://([^/?#]+)') ~ '\.'
            AND NOT (
                SUBSTRING(picked.primary_url_lc FROM '^https?://([^/?#]+)')
                ~* '(wikipedia|wikidata|facebook|fb\\.com|instagram|twitter|t\\.co|youtube|youtu\\.be|linkedin)\\.|[./](facebook|instagram|twitter|youtube|linkedin|wikipedia|wikidata)\\.'
            )
            AND NOT (
                picked.jurisdiction_type = 'municipality'
                AND picked.primary_website_source IN ('uscm', 'league')
                AND {{ uscm_league_county_portal_blocked('picked.name', 'picked.primary_domain_name') }}
            )
            THEN TRUE
        ELSE FALSE
    END AS primary_url_passes_basic_checks,
    picked.lsad,
    CASE
        WHEN picked.jurisdiction_type <> 'municipality' THEN NULL::VARCHAR(32)
        WHEN NULLIF(BTRIM(picked.lsad::TEXT), '') IS NULL THEN 'unknown'
        WHEN BTRIM(picked.lsad::TEXT) = '37' THEN 'census_designated_place'
        WHEN BTRIM(picked.lsad::TEXT) = '25' THEN 'incorporated_city'
        ELSE 'incorporated_other'
    END AS municipality_place_kind,
    picked.acs_vintage_year,
    picked.acs_total_population,
    picked.acs_population_tier,
    picked.acs_income_level,
    CAST(NULL AS TEXT) AS leadership_directory_url,
    CAST(NULL AS TEXT) AS leadership_mapping_method,
    CURRENT_TIMESTAMP AS analysis_generated_at
FROM acs_latest picked
