{{ config(
    materialized='table',
    tags=['intermediate', 'jurisdictions', 'youtube', 'meetings_scrape']
) }}

/*
  YouTube **channel** URLs from meetings crawl manifests loaded into
  ``bronze.bronze_events_meetings_{counties,municipalities,school_districts}_scraped``.

  Grain: one row per (canonical ``jurisdiction_id``, normalized channel URL).
  Video / embed / live URLs are excluded — only durable channel handles.

  Downstream: ``sync_bronze_jurisdiction_youtube_from_meetings_scrape.py`` enriches
  and upserts into ``bronze.bronze_jurisdiction_youtube*`` (same pattern as LocalView).
*/

WITH meetings_youtube AS (
    SELECT
        jurisdiction_id,
        state_code,
        census_geoid,
        homepage_url,
        manifest_scraped_at,
        manifest_relative_path,
        url,
        raw_resource,
        is_likely_meeting,
        'county'::text AS source_jurisdiction_type
    FROM {{ source('bronze', 'bronze_events_meetings_counties_scraped') }}
    WHERE resource_kind = 'youtube'
      AND NULLIF(BTRIM(url), '') IS NOT NULL

    UNION ALL

    SELECT
        jurisdiction_id,
        state_code,
        census_geoid,
        homepage_url,
        manifest_scraped_at,
        manifest_relative_path,
        url,
        raw_resource,
        is_likely_meeting,
        'municipality'::text AS source_jurisdiction_type
    FROM {{ source('bronze', 'bronze_events_meetings_municipalities_scraped') }}
    WHERE resource_kind = 'youtube'
      AND NULLIF(BTRIM(url), '') IS NOT NULL

    UNION ALL

    SELECT
        jurisdiction_id,
        state_code,
        census_geoid,
        homepage_url,
        manifest_scraped_at,
        manifest_relative_path,
        url,
        raw_resource,
        is_likely_meeting,
        'school_district'::text AS source_jurisdiction_type
    FROM {{ source('bronze', 'bronze_events_meetings_school_districts_scraped') }}
    WHERE resource_kind = 'youtube'
      AND NULLIF(BTRIM(url), '') IS NOT NULL
),

normalized AS (
    SELECT
        my.*,
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    LOWER(BTRIM(my.url)),
                    '^http:',
                    'https:',
                    'i'
                ),
                '^https://www\.',
                'https://',
                'i'
            ),
            '/+$',
            '',
            'g'
        ) AS channel_url_norm,
        LOWER(BTRIM(my.url)) AS url_l,
        COALESCE(NULLIF(BTRIM(my.raw_resource->>'link_type'), ''), '') AS link_type,
        NULLIF(BTRIM(my.raw_resource->>'discovered_on'), '') AS discovered_on,
        NULLIF(BTRIM(my.raw_resource->>'found_via'), '') AS found_via,
        (my.raw_resource->>'meeting_relevance') AS meeting_relevance
    FROM meetings_youtube my
),

channel_only AS (
    SELECT *
    FROM normalized n
    WHERE n.channel_url_norm IS NOT NULL
      AND n.channel_url_norm <> ''
      AND n.url_l NOT LIKE '%watch?v=%'
      AND n.url_l NOT LIKE '%/embed/%'
      AND n.url_l NOT LIKE '%/live/%'
      AND n.url_l NOT LIKE '%/shorts/%'
      AND (
          n.link_type = 'channel'
          OR n.url_l LIKE '%youtube.com/@%'
          OR n.url_l LIKE '%youtube.com/channel/%'
          OR n.url_l LIKE '%youtube.com/user/%'
          OR (
              n.url_l LIKE '%youtube.com/c/%'
              AND n.url_l NOT LIKE '%watch?v=%'
          )
      )
),

with_channel_id AS (
    SELECT
        c.*,
        COALESCE(
            NULLIF(
                UPPER(SUBSTRING(c.url_l FROM '(?i)/channel/(uc[a-z0-9_-]{22})')),
                ''
            ),
            NULLIF(
                UPPER(SUBSTRING(c.url_l FROM '(?i)channel/(uc[a-z0-9_-]{22})')),
                ''
            )
        ) AS channel_id_from_url
    FROM channel_only c
),

joined AS (
    SELECT
        j.jurisdiction_id,
        j.name AS jurisdiction_name,
        j.state_code,
        j.state,
        j.jurisdiction_type,
        j.geoid,
        w.homepage_url,
        w.manifest_scraped_at,
        w.manifest_relative_path,
        w.url AS channel_url,
        w.channel_url_norm,
        w.channel_id_from_url AS channel_id,
        w.link_type,
        w.discovered_on,
        w.found_via,
        w.meeting_relevance,
        w.is_likely_meeting,
        w.raw_resource,
        CASE
            WHEN w.link_type = 'channel' AND w.discovered_on ILIKE '%meeting%' THEN 0.85::DOUBLE PRECISION
            WHEN w.link_type = 'channel' THEN 0.80::DOUBLE PRECISION
            WHEN w.url_l LIKE '%youtube.com/@%' THEN 0.78::DOUBLE PRECISION
            ELSE 0.75::DOUBLE PRECISION
        END AS confidence_score,
        'website_scrape'::TEXT AS discovery_method
    FROM with_channel_id w
    INNER JOIN {{ ref('int_jurisdictions') }} j
        ON j.geoid = w.census_geoid
       AND j.state_code = w.state_code
       AND j.jurisdiction_type::text = w.source_jurisdiction_type
),

ranked AS (
    SELECT
        j.*,
        ROW_NUMBER() OVER (
            PARTITION BY j.jurisdiction_id, j.channel_url_norm
            ORDER BY
                j.confidence_score DESC,
                j.manifest_scraped_at DESC NULLS LAST,
                j.discovered_on NULLS LAST
        ) AS rn
    FROM joined j
)

SELECT
    jurisdiction_id,
    jurisdiction_name,
    state_code,
    state,
    jurisdiction_type,
    geoid,
    homepage_url,
    manifest_scraped_at,
    manifest_relative_path,
    channel_url,
    channel_url_norm,
    channel_id,
    link_type,
    discovered_on,
    found_via,
    meeting_relevance,
    is_likely_meeting,
    confidence_score,
    discovery_method,
    raw_resource,
    CURRENT_TIMESTAMP AS transformed_at
FROM ranked
WHERE rn = 1
