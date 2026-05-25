{{ config(
    materialized='table',
    tags=['mart', 'jurisdictions', 'data_quality']
) }}

/*
Municipality-only rollups split by Census Gazetteer **LSAD** (place kind):

- ``incorporated_city`` — LSAD ``25`` (legal incorporated city)
- ``census_designated_place`` — LSAD ``37`` (CDP)
- ``incorporated_other`` — other incorporated / statistical place codes (town, village, borough, …)
- ``unknown`` — municipality row with missing / blank LSAD

Same URL / mapping metrics as ``jurisdiction_mapping_quality_summary`` but grouped by
``municipality_place_kind`` instead of lumping all municipalities together.
*/

SELECT
    municipality_place_kind,
    COUNT(*)::BIGINT AS total_jurisdictions,
    COUNT(*) FILTER (WHERE has_primary_website)::BIGINT AS with_primary_website,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE has_primary_website)::NUMERIC
        / NULLIF(COUNT(*)::NUMERIC, 0),
        2
    ) AS pct_with_primary_website,
    COUNT(*) FILTER (WHERE COALESCE(primary_url_syntax_ok, FALSE))::BIGINT AS with_primary_url_syntax_ok,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE COALESCE(primary_url_syntax_ok, FALSE))::NUMERIC
        / NULLIF(COUNT(*)::NUMERIC, 0),
        2
    ) AS pct_with_primary_url_syntax_ok,
    COUNT(*) FILTER (WHERE COALESCE(primary_url_passes_basic_checks, FALSE))::BIGINT AS with_primary_url_passes_basic_checks,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE COALESCE(primary_url_passes_basic_checks, FALSE))::NUMERIC
        / NULLIF(COUNT(*)::NUMERIC, 0),
        2
    ) AS pct_with_primary_url_passes_basic_checks,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE has_primary_website AND COALESCE(primary_url_syntax_ok, FALSE)
        )::NUMERIC
        / NULLIF(COUNT(*) FILTER (WHERE has_primary_website)::NUMERIC, 0),
        2
    ) AS pct_syntax_ok_among_with_primary,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE has_primary_website AND COALESCE(primary_url_passes_basic_checks, FALSE)
        )::NUMERIC
        / NULLIF(COUNT(*) FILTER (WHERE has_primary_website)::NUMERIC, 0),
        2
    ) AS pct_basic_checks_ok_among_with_primary,
    COUNT(*) FILTER (WHERE COALESCE(primary_url_likely_wrong_host, FALSE))::BIGINT AS with_primary_url_likely_wrong_host,
    COUNT(*) FILTER (WHERE has_naco_source)::BIGINT AS jurisdictions_touching_naco,
    COUNT(*) FILTER (WHERE has_uscm_source)::BIGINT AS jurisdictions_touching_uscm,
    COUNT(*) FILTER (WHERE has_nces_directory_source)::BIGINT AS jurisdictions_touching_nces,
    COUNT(*) FILTER (WHERE has_gsa_source)::BIGINT AS jurisdictions_touching_gsa,
    COUNT(*) FILTER (WHERE has_league_source)::BIGINT AS jurisdictions_touching_league,
    COUNT(*) FILTER (WHERE has_wikidata_source)::BIGINT AS jurisdictions_touching_wikidata,
    COUNT(*) FILTER (WHERE has_override_source)::BIGINT AS jurisdictions_touching_override,
    {{ jurisdiction_mapping_primary_from_source_columns() }},
    {{ jurisdiction_mapping_youtube_summary_columns() }},
    CURRENT_TIMESTAMP AS summary_generated_at
FROM {{ ref('jurisdiction_mapping_analysis') }}
WHERE jurisdiction_type = 'municipality'
  AND municipality_place_kind IS NOT NULL
GROUP BY municipality_place_kind
