{{ config(
    materialized='table',
    tags=['intermediate', 'youtube', 'channels']
) }}

/*
Intermediate model: derived channel registry.

`bronze_events_channels` is a dbt `source` table; when missing in a dev DB, create it
via loaders or apply the same DDL before `dbt run`. Optional enrichment (title, About links)
comes from that table when populated.

`jurisdictions` JSONB: distinct `intermediate.int_jurisdictions` rows matched via
`int_localview_channel_geography` (place / school district / township / county GEOIDs).
Shape matches Python loaders: jurisdiction_id, jurisdiction_name, state_code, state,
jurisdiction_type, geoid.

`jurisdiction_id` (scalar): first entry of `jurisdiction_ids` (sorted); NULL when geography
did not match `int_jurisdictions` (fix upstream `int_localview_jurisdiction_geography` /
GEOIDs) or when `int_localview_channel_geography` has no row for the channel.

`channel_url`: prefer `bronze_events_youtube.channel_url`; if missing/blank, canonical
`https://www.youtube.com/channel/{channel_id}` so API/UI always have a link.

`channel_title`, `channel_description`, `subscriber_count`, `video_count`, `view_count`,
`channel_external_links`: from `bronze_events_channels` when present (loaders +
`scripts/datasources/youtube/channel_about_links.py` About-tab scrape); otherwise NULL where not joined.
*/

WITH base_channels AS (
    SELECT DISTINCT
        channel_id
    FROM {{ ref('int_events_localview') }}
    WHERE channel_id IS NOT NULL
      AND channel_id != ''
),

youtube_meta AS (
    SELECT
        channel_id,
        MAX(channel_url)  AS channel_url,
        MAX(channel_type) AS channel_type,
        MAX(last_updated) AS last_updated
    FROM {{ source('bronze', 'bronze_events_youtube') }}
    WHERE channel_id IS NOT NULL
      AND channel_id != ''
    GROUP BY channel_id
),

localview_meta AS (
    SELECT
        channel_id,
        MAX(loaded_at) AS loaded_at
    FROM {{ ref('int_events_localview') }}
    WHERE channel_id IS NOT NULL
      AND channel_id != ''
    GROUP BY channel_id
),

channels_bronze AS (
    SELECT
        channel_id,
        MAX(NULLIF(BTRIM(channel_title), '')) AS channel_title,
        MAX(channel_external_links::text)::jsonb AS channel_external_links,
        MAX(subscriber_count) AS subscriber_count,
        MAX(video_count) AS video_count,
        MAX(view_count) AS view_count,
        MAX(channel_description) AS channel_description
    FROM {{ source('bronze', 'bronze_events_channels') }}
    WHERE channel_id IS NOT NULL
      AND channel_id != ''
    GROUP BY channel_id
),

channel_event_state_counts AS (
    SELECT
        channel_id,
        state_code,
        event_count,
        ROW_NUMBER() OVER (
            PARTITION BY channel_id
            ORDER BY event_count DESC, state_code
        ) AS rn
    FROM (
        SELECT
            channel_id,
            state_code,
            COUNT(*) AS event_count
        FROM {{ ref('int_events_localview') }}
        WHERE channel_id IS NOT NULL
          AND channel_id != ''
          AND state_code IS NOT NULL
          AND state_code != ''
        GROUP BY channel_id, state_code
    ) state_counts
),

channel_primary_state AS (
    SELECT
        channel_id,
        state_code AS event_state_code,
        event_count AS event_state_count
    FROM channel_event_state_counts
    WHERE rn = 1
),

title_sources AS (
    SELECT
        bc.channel_id,
        NULLIF(BTRIM(cb.channel_title), '') AS channel_title,
        cb.video_count::BIGINT AS video_count,
        cps.event_state_code,
        cps.event_state_count,
        regexp_replace(lower(NULLIF(BTRIM(cb.channel_title), '')), '[^a-z0-9]+', '', 'g') AS title_compact,
        CASE
            WHEN cb.channel_title ILIKE '%school district%'
              OR cb.channel_title ILIKE '%public schools%'
              OR cb.channel_title ILIKE '%board of education%'
              OR cb.channel_title ILIKE '%school board%'
              OR cb.channel_title ~* '\m(isd|cusd|susd|pusd|usd|csd)\M'
                THEN 'school_district'
            WHEN cb.channel_title ILIKE '%county%'
                THEN 'county'
            WHEN cb.channel_title ILIKE '%township%'
                THEN 'township'
            WHEN cb.channel_title ILIKE '%city%'
              OR cb.channel_title ILIKE '%town%'
              OR cb.channel_title ILIKE '%village%'
              OR cb.channel_title ILIKE '%borough%'
              OR cb.channel_title ILIKE '%municipal%'
                THEN 'municipality'
            WHEN cb.channel_title ILIKE '%state%'
              OR cb.channel_title ILIKE '%commonwealth%'
                THEN 'state'
            ELSE NULL
        END AS inferred_jurisdiction_type,
        (
            cb.channel_title ILIKE '% city %'
            OR cb.channel_title ILIKE 'city %'
            OR cb.channel_title ILIKE '% city'
            OR cb.channel_title ILIKE '% county %'
            OR cb.channel_title ILIKE 'county %'
            OR cb.channel_title ILIKE '% county'
            OR cb.channel_title ILIKE '% school district%'
            OR cb.channel_title ILIKE '% public schools%'
            OR cb.channel_title ILIKE '% board of education%'
            OR cb.channel_title ILIKE '% school board%'
            OR cb.channel_title ILIKE '% township %'
            OR cb.channel_title ILIKE '% township'
            OR cb.channel_title ILIKE '% municipal %'
            OR cb.channel_title ILIKE '% government %'
            OR cb.channel_title ILIKE '% gov %'
        ) AS has_gov_keyword
    FROM base_channels bc
    LEFT JOIN channels_bronze cb ON bc.channel_id = cb.channel_id
    LEFT JOIN channel_primary_state cps ON bc.channel_id = cps.channel_id
    WHERE NULLIF(BTRIM(cb.channel_title), '') IS NOT NULL
),

jurisdiction_catalog AS (
    SELECT
        jurisdiction_id,
        state_code,
        state,
        jurisdiction_type,
        name AS jurisdiction_name,
        regexp_replace(lower(name), '[^a-z0-9]+', '', 'g') AS jurisdiction_name_compact
    FROM {{ ref('int_jurisdictions') }}
    WHERE jurisdiction_type IN ('municipality', 'county', 'school_district', 'township')
),

title_match_candidates AS (
    SELECT
        ts.channel_id,
        jc.jurisdiction_id,
        jc.state_code,
        jc.state,
        jc.jurisdiction_type,
        jc.jurisdiction_name,
        CASE
            WHEN ts.title_compact = jc.jurisdiction_name_compact THEN 0.94
            WHEN ts.title_compact LIKE '%' || jc.jurisdiction_name_compact || '%' THEN 0.90
            WHEN jc.jurisdiction_name_compact LIKE '%' || ts.title_compact || '%' THEN 0.82
            ELSE 0.0
        END
        + CASE WHEN ts.inferred_jurisdiction_type = jc.jurisdiction_type THEN 0.04 ELSE 0.0 END
        + CASE WHEN ts.event_state_code = jc.state_code THEN 0.03 ELSE 0.0 END
        + CASE
            WHEN COALESCE(ts.video_count, 0) >= 500 THEN 0.03
            WHEN COALESCE(ts.video_count, 0) >= 100 THEN 0.025
            WHEN COALESCE(ts.video_count, 0) >= 25 THEN 0.02
            WHEN COALESCE(ts.video_count, 0) >= 10 THEN 0.01
            ELSE 0.0
        END AS match_score
    FROM title_sources ts
    INNER JOIN jurisdiction_catalog jc
        ON (ts.event_state_code IS NULL OR jc.state_code = ts.event_state_code)
       AND (
            ts.title_compact = jc.jurisdiction_name_compact
            OR ts.title_compact LIKE '%' || jc.jurisdiction_name_compact || '%'
            OR jc.jurisdiction_name_compact LIKE '%' || ts.title_compact || '%'
       )
    AND ts.has_gov_keyword
       AND (ts.inferred_jurisdiction_type IS NULL OR ts.inferred_jurisdiction_type = jc.jurisdiction_type)
),

title_best_match AS (
    SELECT
        channel_id,
        jurisdiction_id,
        state_code,
        state,
        jurisdiction_type,
        jurisdiction_name,
        match_score
    FROM (
        SELECT
            tmc.*,
            ROW_NUMBER() OVER (
                PARTITION BY channel_id
                ORDER BY match_score DESC, jurisdiction_id
            ) AS rn,
            LEAD(match_score) OVER (
                PARTITION BY channel_id
                ORDER BY match_score DESC, jurisdiction_id
            ) AS next_score
        FROM title_match_candidates tmc
        WHERE match_score >= 0.95
    ) ranked
    WHERE rn = 1
      AND (next_score IS NULL OR match_score - next_score >= 0.05)
),

title_jurisdictions AS (
    SELECT
        t.channel_id,
        jsonb_build_array(
            jsonb_build_object(
                'jurisdiction_id', t.jurisdiction_id,
                'jurisdiction_name', t.jurisdiction_name,
                'state_code', t.state_code,
                'state', t.state,
                'jurisdiction_type', t.jurisdiction_type,
                'geoid', NULL
            )
        ) AS jurisdictions,
        ARRAY[t.jurisdiction_id] AS jurisdiction_ids,
        t.jurisdiction_id,
        t.state_code,
        t.state,
        t.match_score AS confidence_score
    FROM title_best_match t
),

/*
Expand LocalView channel geography to typed GEOIDs, then resolve canonical
jurisdiction_id (e.g. municipality_0607500) from int_jurisdictions.
*/
channel_geoid_candidates AS (
    SELECT DISTINCT
        lg.channel_id,
        lg.state_code,
        'municipality'::TEXT    AS jurisdiction_type,
        lg.place_geoid::TEXT    AS geoid
    FROM {{ ref('int_localview_channel_geography') }} lg
    WHERE lg.place_geoid IS NOT NULL
      AND BTRIM(lg.place_geoid::TEXT) != ''

    UNION

    SELECT DISTINCT
        lg.channel_id,
        lg.state_code,
        'school_district'::TEXT,
        lg.school_district_geoid::TEXT
    FROM {{ ref('int_localview_channel_geography') }} lg
    WHERE lg.school_district_geoid IS NOT NULL
      AND BTRIM(lg.school_district_geoid::TEXT) != ''

    UNION

    SELECT DISTINCT
        lg.channel_id,
        lg.state_code,
        'township'::TEXT,
        lg.township_geoid::TEXT
    FROM {{ ref('int_localview_channel_geography') }} lg
    WHERE lg.township_geoid IS NOT NULL
      AND BTRIM(lg.township_geoid::TEXT) != ''

    UNION

    SELECT DISTINCT
        lg.channel_id,
        lg.state_code,
        'county'::TEXT,
        lg.primary_county_geoid::TEXT
    FROM {{ ref('int_localview_channel_geography') }} lg
    WHERE lg.primary_county_geoid IS NOT NULL
      AND BTRIM(lg.primary_county_geoid::TEXT) != ''

    UNION

    SELECT DISTINCT
        lg.channel_id,
        lg.state_code,
        'county'::TEXT,
        u.c_geoid::TEXT
    FROM {{ ref('int_localview_channel_geography') }} lg
    CROSS JOIN LATERAL unnest(lg.county_geoids) AS u(c_geoid)
    WHERE lg.county_geoids IS NOT NULL
      AND CARDINALITY(lg.county_geoids) > 0
),

channel_jurisdictions AS (
    SELECT DISTINCT
        cgc.channel_id,
        j.jurisdiction_id,
        j.name              AS jurisdiction_name,
        j.state_code,
        j.state,
        j.jurisdiction_type,
        j.geoid
    FROM channel_geoid_candidates cgc
    INNER JOIN {{ ref('int_jurisdictions') }} j
        ON j.state_code = cgc.state_code
       AND j.geoid = cgc.geoid
       AND j.jurisdiction_type = cgc.jurisdiction_type
),

jurisdictions_by_channel AS (
    SELECT
        channel_id,
        jsonb_agg(
            jsonb_build_object(
                'jurisdiction_id',       jurisdiction_id,
                'jurisdiction_name',     jurisdiction_name,
                'state_code',            state_code,
                'state',                 state,
                'jurisdiction_type',     jurisdiction_type,
                'geoid',                 geoid
            )
            ORDER BY jurisdiction_id
        ) AS jurisdictions,
        array_agg(jurisdiction_id ORDER BY jurisdiction_id) AS jurisdiction_ids,
        array_agg(DISTINCT state_code ORDER BY state_code) AS state_codes,
        array_agg(DISTINCT state ORDER BY state) AS states
    FROM channel_jurisdictions
    GROUP BY channel_id
)

SELECT
    bc.channel_id AS id,
    bc.channel_id,
    COALESCE(
        NULLIF(BTRIM(ym.channel_url), ''),
        'https://www.youtube.com/channel/' || bc.channel_id
    ) AS channel_url,
    bec.channel_title AS channel_title,
    ym.channel_type,
    bec.subscriber_count::BIGINT AS subscriber_count,
    bec.video_count::BIGINT AS video_count,
    bec.view_count::BIGINT AS view_count,
    bec.channel_description,

    bec.channel_external_links,

    -- Source flags (which datasets validate this channel)
    TRUE          AS in_localview,
    (jbc.jurisdictions IS NOT NULL OR tj.jurisdictions IS NOT NULL) AS in_jurisdictions_details,
    FALSE         AS on_public_website,
    FALSE         AS in_wikidata,

    -- Discovery information
    CASE
        WHEN jbc.jurisdictions IS NOT NULL THEN 'derived_from_localview'
        WHEN tj.jurisdictions IS NOT NULL THEN 'derived_from_title_match'
        ELSE 'derived_from_localview'
    END::TEXT AS discovery_method,
    NULL::DATE                    AS discovery_date,
    CASE
        WHEN jbc.jurisdictions IS NOT NULL THEN 0.85::DOUBLE PRECISION
        WHEN tj.jurisdictions IS NOT NULL THEN tj.confidence_score
        ELSE 0.5::DOUBLE PRECISION
    END AS confidence_score,

    -- Jurisdiction associations (JSONB array of resolved int_jurisdictions rows)
    COALESCE(jbc.jurisdictions, tj.jurisdictions) AS jurisdictions,
    COALESCE(jbc.jurisdiction_ids, tj.jurisdiction_ids) AS jurisdiction_ids,
    COALESCE((jbc.jurisdiction_ids)[1], tj.jurisdiction_id)::TEXT AS jurisdiction_id,
    COALESCE((jbc.state_codes)[1], tj.state_code)::TEXT AS state_code,
    COALESCE((jbc.states)[1], tj.state)::TEXT AS state,

    -- Quality indicators
    NULL::BOOLEAN AS is_verified,
    NULL::BOOLEAN AS is_government,
    FALSE         AS flagged_as_junk,
    NULL::TEXT    AS flag_reason,

    -- Timestamps
    lm.loaded_at,
    COALESCE(ym.last_updated, lm.loaded_at) AS last_updated

FROM base_channels bc
LEFT JOIN youtube_meta ym ON bc.channel_id = ym.channel_id
LEFT JOIN localview_meta lm ON bc.channel_id = lm.channel_id
LEFT JOIN channels_bronze bec ON bc.channel_id = bec.channel_id
LEFT JOIN jurisdictions_by_channel jbc ON bc.channel_id = jbc.channel_id
LEFT JOIN title_jurisdictions tj ON bc.channel_id = tj.channel_id
