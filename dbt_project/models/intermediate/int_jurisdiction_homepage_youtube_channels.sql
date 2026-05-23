{{ config(
    materialized='table',
    tags=['intermediate', 'jurisdictions', 'youtube']
) }}

/*
  Homepage-discovered YouTube channels mapped back to jurisdiction_id.

  This model explodes ``payload->youtube_channels`` from the jurisdiction scraping
  tables, keeps one best jurisdiction candidate per normalized YouTube URL, and
  exposes a deterministic join key for downstream channel enrichment.
*/

WITH scraped AS (
    SELECT
        'state'::text AS jurisdiction_class,
        geoid,
        usps,
        homepage_url,
        homepage_final_url,
        discovery_source,
        status,
        completeness_score,
        payload
    FROM {{ source('bronze', 'bronze_jurisdictions_states_scraped') }}

    UNION ALL

    SELECT
        'municipality'::text AS jurisdiction_class,
        geoid,
        usps,
        homepage_url,
        homepage_final_url,
        discovery_source,
        status,
        completeness_score,
        payload
    FROM {{ source('bronze', 'bronze_jurisdictions_municipalities_scraped') }}

    UNION ALL

    SELECT
        'county'::text AS jurisdiction_class,
        geoid,
        usps,
        homepage_url,
        homepage_final_url,
        discovery_source,
        status,
        completeness_score,
        payload
    FROM {{ source('bronze', 'bronze_jurisdictions_counties_scraped') }}

    UNION ALL

    SELECT
        'school_district'::text AS jurisdiction_class,
        geoid,
        usps,
        homepage_url,
        homepage_final_url,
        discovery_source,
        status,
        completeness_score,
        payload
    FROM {{ source('bronze', 'bronze_jurisdictions_school_districts_scraped') }}
),

youtube_catalog AS (
    SELECT DISTINCT
        NULLIF(BTRIM(channel_id), '') AS channel_id,
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    LOWER(NULLIF(BTRIM(channel_url), '')),
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
        CASE
            WHEN LOWER(NULLIF(BTRIM(channel_url), '')) LIKE 'http%://%@%'
              OR LOWER(NULLIF(BTRIM(channel_url), '')) LIKE '%youtube.com/@%'
                THEN NULLIF(
                    REGEXP_REPLACE(
                        SPLIT_PART(
                            REGEXP_REPLACE(
                                REGEXP_REPLACE(
                                    REGEXP_REPLACE(
                                        LOWER(NULLIF(BTRIM(channel_url), '')),
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
                            ),
                            '/@',
                            2
                        ),
                        '[\\?/].*$',
                        ''
                    ),
                    ''
                )
            ELSE NULL
        END AS channel_handle_norm
    FROM {{ source('bronze', 'bronze_events_youtube') }}
    WHERE NULLIF(BTRIM(channel_id), '') IS NOT NULL
),

youtube_lookup_by_url AS (
    SELECT
        channel_url_norm,
        CASE
            WHEN COUNT(DISTINCT channel_id) = 1 THEN MAX(channel_id)
            ELSE NULL
        END AS resolved_channel_id
    FROM youtube_catalog
    WHERE channel_url_norm IS NOT NULL
      AND channel_url_norm != ''
    GROUP BY channel_url_norm
),

youtube_lookup_by_handle AS (
    SELECT
        channel_handle_norm,
        CASE
            WHEN COUNT(DISTINCT channel_id) = 1 THEN MAX(channel_id)
            ELSE NULL
        END AS resolved_channel_id
    FROM youtube_catalog
    WHERE channel_handle_norm IS NOT NULL
      AND channel_handle_norm != ''
    GROUP BY channel_handle_norm
),

exploded_base AS (
    SELECT
        j.jurisdiction_id,
        j.name AS jurisdiction_name,
        j.state_code,
        j.state,
        j.jurisdiction_type,
        j.geoid,
        s.jurisdiction_class,
        s.homepage_url,
        s.homepage_final_url,
        s.discovery_source,
        s.status,
        s.completeness_score,
        NULLIF(BTRIM(yc->>'channel_url'), '') AS channel_url,
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    LOWER(NULLIF(BTRIM(yc->>'channel_url'), '')),
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
        NULLIF(BTRIM(yc->>'channel_id'), '') AS payload_channel_id,
        NULLIF(BTRIM(yc->>'channel_title'), '') AS channel_title,
        COALESCE((yc->>'confidence')::numeric, 0.0) AS confidence_score,
        COALESCE((yc->>'video_count')::bigint, 0) AS video_count,
        COALESCE((yc->>'subscriber_count')::bigint, 0) AS subscriber_count,
        COALESCE((yc->>'view_count')::bigint, 0) AS view_count,
        NULLIF(BTRIM(yc->>'discovery_method'), '') AS discovery_method
    FROM scraped s
    INNER JOIN {{ ref('int_jurisdictions') }} j
        ON j.geoid = s.geoid
       AND j.jurisdiction_type::text = s.jurisdiction_class
    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(s.payload->'youtube_channels', '[]'::jsonb)) AS yc
    WHERE NULLIF(BTRIM(yc->>'channel_url'), '') IS NOT NULL
),

exploded AS (
    SELECT
        eb.jurisdiction_id,
        eb.jurisdiction_name,
        eb.state_code,
        eb.state,
        eb.jurisdiction_type,
        eb.geoid,
        eb.jurisdiction_class,
        eb.homepage_url,
        eb.homepage_final_url,
        eb.discovery_source,
        eb.status,
        eb.completeness_score,
        eb.channel_url,
        eb.channel_url_norm,
        COALESCE(
            eb.payload_channel_id,
            ylu.resolved_channel_id,
            ylh.resolved_channel_id
        ) AS channel_id,
        eb.channel_title,
        eb.confidence_score,
        eb.video_count,
        eb.subscriber_count,
        eb.view_count,
        eb.discovery_method
    FROM exploded_base eb
    LEFT JOIN youtube_lookup_by_url ylu
        ON eb.channel_url_norm = ylu.channel_url_norm
    LEFT JOIN youtube_lookup_by_handle ylh
        ON NULLIF(
            REGEXP_REPLACE(
                SPLIT_PART(eb.channel_url_norm, '/@', 2),
                '[\\?/].*$',
                ''
            ),
            ''
        ) = ylh.channel_handle_norm
),

ranked AS (
    SELECT
        e.*,
        COUNT(*) OVER (PARTITION BY e.channel_url_norm) AS candidate_count,
        ROW_NUMBER() OVER (
            PARTITION BY e.channel_url_norm
            ORDER BY
                e.confidence_score DESC,
                e.video_count DESC,
                e.completeness_score DESC NULLS LAST,
                e.jurisdiction_type,
                e.jurisdiction_id
        ) AS rn
    FROM exploded e
    WHERE e.channel_url_norm IS NOT NULL
      AND e.channel_url_norm != ''
)

SELECT
    channel_url_norm,
    channel_url,
    jurisdiction_id,
    jurisdiction_name,
    state_code,
    state,
    jurisdiction_type,
    geoid,
    jurisdiction_class,
    homepage_url,
    homepage_final_url,
    discovery_source,
    status,
    completeness_score,
    channel_id,
    channel_title,
    confidence_score,
    video_count,
    subscriber_count,
    view_count,
    candidate_count,
    COALESCE(discovery_method, 'derived_from_homepage_youtube_link')::text AS discovery_method,
    CURRENT_TIMESTAMP AS transformed_at
FROM ranked
WHERE rn = 1