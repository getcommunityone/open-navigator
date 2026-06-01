-- =============================================================================
-- YouTube ↔ jurisdiction coverage (one state, compact)
--
-- Requires: psql -v one_state=GA
--
-- 1) Match rate — int_jurisdictions in state vs (a) exact linked jurisdiction_id union
--    OR (b) GA bronze YouTube jurisdiction_name + type bucket aligned to same int row
-- 1b) Why % can look tiny — bronze YouTube jurisdiction_id keys vs int_jurisdictions
-- 1c) Sample YouTube jurisdiction_id in state missing from int_jurisdictions
-- 2) Bronze YouTube volumes in state
-- 3) LocalView bronze rows in state
-- 4) Top 5 still-unmatched per type (no linked id AND no section-1 name/type proxy) —
--     rank: population → looser name-matched YT activity (videos/.gov/views/subs) → land area
--
-- Linked jurisdiction_ids: int_events_channels, bronze_events_channels JSON,
--   bronze_event_youtube (scalar, non-unknown).
-- =============================================================================

\pset pager off

DROP TABLE IF EXISTS _tmp_yt_covered_jurisdiction;
CREATE TEMP TABLE _tmp_yt_covered_jurisdiction AS
SELECT DISTINCT x.jurisdiction_id
FROM (
    SELECT ec.jurisdiction_id
    FROM intermediate.int_events_channels_registry ec
    WHERE ec.jurisdiction_id IS NOT NULL
      AND BTRIM(ec.jurisdiction_id) <> ''
      AND lower(BTRIM(ec.jurisdiction_id)) <> 'unknown'

    UNION

    SELECT elem->>'jurisdiction_id' AS jurisdiction_id
    FROM intermediate.int_events_channels_registry ec,
    LATERAL jsonb_array_elements(COALESCE(ec.jurisdictions, '[]'::jsonb)) AS elem
    WHERE elem ? 'jurisdiction_id'
      AND BTRIM(COALESCE(elem->>'jurisdiction_id', '')) <> ''
      AND lower(BTRIM(elem->>'jurisdiction_id')) <> 'unknown'

    UNION

    SELECT elem->>'jurisdiction_id' AS jurisdiction_id
    FROM bronze.bronze_events_channels bc,
    LATERAL jsonb_array_elements(COALESCE(bc.jurisdictions, '[]'::jsonb)) AS elem
    WHERE elem ? 'jurisdiction_id'
      AND BTRIM(COALESCE(elem->>'jurisdiction_id', '')) <> ''
      AND lower(BTRIM(elem->>'jurisdiction_id')) <> 'unknown'

    UNION

    SELECT y.jurisdiction_id
    FROM bronze.bronze_event_youtube y
    WHERE y.jurisdiction_id IS NOT NULL
      AND BTRIM(y.jurisdiction_id) <> ''
      AND lower(BTRIM(y.jurisdiction_id)) <> 'unknown'
) x
WHERE x.jurisdiction_id IS NOT NULL;

-- Distinct normalized (name, Census type bucket) signals from bronze YouTube in this state only.
DROP TABLE IF EXISTS _tmp_yt_ga_nm_signal;
CREATE TEMP TABLE _tmp_yt_ga_nm_signal AS
SELECT DISTINCT
    trim(upper(:'one_state')) AS state_code,
    lower(BTRIM(REGEXP_REPLACE(
        REGEXP_REPLACE(COALESCE(y.jurisdiction_name, ''), '\s+', ' ', 'g'),
        '\s+(city|town|village|borough|county|consolidated government|unified government)$',
        '',
        'ig'
    ))) AS name_key,
    CASE
        WHEN lower(BTRIM(COALESCE(y.jurisdiction_type, ''))) ~ 'school' THEN 'school_district'::text
        WHEN lower(BTRIM(COALESCE(y.jurisdiction_type, ''))) ~ 'urban county|metro government|consolidated|unified' THEN 'municipality'::text
        WHEN lower(BTRIM(COALESCE(y.jurisdiction_type, ''))) ~ 'county' THEN 'county'::text
        WHEN lower(BTRIM(COALESCE(y.jurisdiction_type, '')))
             ~ 'city|town|village|borough|municipality|place|cdp' THEN 'municipality'::text
        ELSE NULL::text
    END AS int_jurisdiction_type
FROM bronze.bronze_event_youtube y
WHERE y.state_code = trim(upper(:'one_state'))
  AND y.jurisdiction_name IS NOT NULL
  AND BTRIM(y.jurisdiction_name) <> ''
  AND y.jurisdiction_type IS NOT NULL
  AND BTRIM(y.jurisdiction_type) <> '';

DELETE FROM _tmp_yt_ga_nm_signal WHERE int_jurisdiction_type IS NULL OR name_key = '';

\echo '========== 1) Match rate (exact id + name/type proxy) =========='

WITH jn AS (
    SELECT
        j.jurisdiction_type,
        j.jurisdiction_id,
        j.state_code,
        lower(BTRIM(REGEXP_REPLACE(
            REGEXP_REPLACE(COALESCE(j.name, ''), '\s+', ' ', 'g'),
            '\s+(city|town|village|borough|county|consolidated government|unified government)$',
            '',
            'ig'
        ))) AS name_key
    FROM intermediate.int_jurisdictions j
    WHERE j.jurisdiction_type IN ('county', 'municipality', 'school_district')
      AND j.state_code = trim(upper(:'one_state'))
)
SELECT
    trim(upper(:'one_state')) AS state_code,
    CASE j.jurisdiction_type
        WHEN 'municipality' THEN 'muni'
        WHEN 'county' THEN 'county'
        WHEN 'school_district' THEN 'sd'
    END AS j_type,
    COUNT(*)::bigint AS in_ref,
    COUNT(*) FILTER (WHERE c.jurisdiction_id IS NOT NULL)::bigint AS m_exact,
    COUNT(*) FILTER (
        WHERE c.jurisdiction_id IS NULL
          AND EXISTS (
              SELECT 1
              FROM _tmp_yt_ga_nm_signal s
              WHERE s.state_code = j.state_code
                AND s.int_jurisdiction_type = j.jurisdiction_type
                AND s.name_key = j.name_key
          )
    )::bigint AS m_name,
    COUNT(*) FILTER (
        WHERE c.jurisdiction_id IS NOT NULL
           OR EXISTS (
              SELECT 1
              FROM _tmp_yt_ga_nm_signal s
              WHERE s.state_code = j.state_code
                AND s.int_jurisdiction_type = j.jurisdiction_type
                AND s.name_key = j.name_key
          )
    )::bigint AS m_any,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE c.jurisdiction_id IS NOT NULL
               OR EXISTS (
                  SELECT 1
                  FROM _tmp_yt_ga_nm_signal s
                  WHERE s.state_code = j.state_code
                    AND s.int_jurisdiction_type = j.jurisdiction_type
                    AND s.name_key = j.name_key
              )
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS pct_any,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE c.jurisdiction_id IS NOT NULL) / NULLIF(COUNT(*), 0),
        2
    ) AS pct_id
FROM jn j
LEFT JOIN _tmp_yt_covered_jurisdiction c ON c.jurisdiction_id = j.jurisdiction_id
GROUP BY j.jurisdiction_type
ORDER BY j.jurisdiction_type;

\echo 'm_exact=id link; m_name=name+type only; m_any=union; pct_any/pct_id=% of in_ref.'

\echo ''
\echo '========== 1b) bronze_event_youtube jur_id vs int_jurisdictions =========='

WITH st AS (
    SELECT trim(upper(:'one_state')) AS sc
),
yt_ids AS (
    SELECT DISTINCT y.jurisdiction_id AS jurisdiction_id
    FROM bronze.bronze_event_youtube y
    CROSS JOIN st
    WHERE y.state_code = st.sc
      AND y.jurisdiction_id IS NOT NULL
      AND BTRIM(y.jurisdiction_id) <> ''
      AND lower(BTRIM(y.jurisdiction_id)) <> 'unknown'
),
agg AS (
    SELECT
        st.sc AS state_code,
        (SELECT COUNT(*) FROM yt_ids)::bigint AS n_distinct,
        (
            SELECT COUNT(*)
            FROM yt_ids yt
            WHERE EXISTS (
                SELECT 1
                FROM intermediate.int_jurisdictions j
                WHERE j.jurisdiction_id = yt.jurisdiction_id
                  AND j.state_code = st.sc
            )
        )::bigint AS n_hit_this_state,
        (
            SELECT COUNT(*)
            FROM yt_ids yt
            WHERE NOT EXISTS (
                SELECT 1 FROM intermediate.int_jurisdictions j WHERE j.jurisdiction_id = yt.jurisdiction_id
            )
        )::bigint AS n_missing_table,
        (
            SELECT COUNT(*)
            FROM yt_ids yt
            WHERE EXISTS (
                SELECT 1
                FROM intermediate.int_jurisdictions j
                WHERE j.jurisdiction_id = yt.jurisdiction_id
                  AND j.state_code <> st.sc
            )
        )::bigint AS n_hit_other_state_only
    FROM st
)
SELECT
    x.line AS ln,
    x.what,
    x.n
FROM agg a
CROSS JOIN LATERAL (
    VALUES
        (1, 'distinct jur_id on bronze_event_youtube', a.n_distinct),
        (2, 'those ids exist on int_jurisdictions (this state)', a.n_hit_this_state),
        (3, 'those ids not on int_jurisdictions', a.n_missing_table),
        (4, 'those ids on int_jurisdictions but other state', a.n_hit_other_state_only)
) AS x(line, what, n)
ORDER BY x.line;

\echo ''
\echo '========== 1c) Sample jur_id (bronze_event_youtube) missing from int_jurisdictions =========='

SELECT
    y.jurisdiction_id AS jur_id,
    MAX(y.jurisdiction_name) AS name,
    COUNT(*)::bigint AS vids
FROM bronze.bronze_event_youtube y
WHERE y.state_code = trim(upper(:'one_state'))
  AND y.jurisdiction_id IS NOT NULL
  AND BTRIM(y.jurisdiction_id) <> ''
  AND lower(BTRIM(y.jurisdiction_id)) <> 'unknown'
  AND NOT EXISTS (
      SELECT 1
      FROM intermediate.int_jurisdictions j
      WHERE j.jurisdiction_id = y.jurisdiction_id
  )
GROUP BY y.jurisdiction_id
ORDER BY vids DESC, y.jurisdiction_id
LIMIT 8;

\echo ''
\echo '========== 2) Bronze YouTube in this state (volumes) =========='

SELECT
    trim(upper(:'one_state')) AS state_code,
    COUNT(*)::bigint AS youtube_video_rows,
    COUNT(*) FILTER (
        WHERE y.jurisdiction_id IS NOT NULL
          AND BTRIM(y.jurisdiction_id) <> ''
          AND lower(BTRIM(y.jurisdiction_id)) <> 'unknown'
    )::bigint AS rows_with_jurisdiction_id,
    COUNT(DISTINCT y.channel_id)::bigint AS distinct_channels
FROM bronze.bronze_event_youtube y
WHERE y.state_code = trim(upper(:'one_state'));

\echo ''
\echo '========== 3) LocalView bronze rows in this state =========='

SELECT
    trim(upper(:'one_state')) AS state_code,
    COUNT(*)::bigint AS localview_event_rows
FROM bronze.bronze_events_localview lv
WHERE lv.datasource = 'localview'
  AND lv.state_code = trim(upper(:'one_state'));

\echo ''
\echo '========== 4) Top 5 still-unmatched (no linked id + no sec.1 name/type proxy) — rank: pop → YT signals → area =========='

WITH ref AS (
    SELECT
        j.jurisdiction_id,
        j.jurisdiction_type,
        j.name,
        j.geoid,
        j.state_code,
        j.area_sq_miles
    FROM intermediate.int_jurisdictions j
    WHERE j.jurisdiction_type IN ('county', 'municipality', 'school_district')
      AND j.state_code = trim(upper(:'one_state'))
      AND NOT EXISTS (
          SELECT 1
          FROM _tmp_yt_covered_jurisdiction c
          WHERE c.jurisdiction_id = j.jurisdiction_id
      )
      AND NOT EXISTS (
          SELECT 1
          FROM _tmp_yt_ga_nm_signal s
          WHERE s.state_code = j.state_code
            AND s.int_jurisdiction_type = j.jurisdiction_type
            AND s.name_key = lower(BTRIM(REGEXP_REPLACE(
                REGEXP_REPLACE(COALESCE(j.name, ''), '\s+', ' ', 'g'),
                '\s+(city|town|village|borough|county|consolidated government|unified government)$',
                '',
                'ig'
            )))
      )
),
pop AS (
    SELECT
        r.*,
        (
            SELECT MAX(z.pop)
            FROM (
                SELECT CASE
                    WHEN BTRIM(COALESCE(to_jsonb(js)->>'population', '')) ~ '^[0-9]+$'
                        THEN BTRIM(COALESCE(to_jsonb(js)->>'population', ''))::bigint
                    ELSE NULL::bigint
                END AS pop
                FROM jurisdiction js
                WHERE BTRIM(COALESCE(to_jsonb(js)->>'geoid', '')) = BTRIM(r.geoid)
            ) z
        ) AS population_estimate
    FROM ref r
),
yt_name AS (
    SELECT
        p.*,
        COALESCE(sig.name_match_videos, 0)::bigint AS name_match_youtube_videos,
        COALESCE(sig.name_match_views, 0)::bigint AS name_match_sum_views,
        COALESCE(sig.subscriber_max, 0)::bigint AS name_match_max_subscribers,
        COALESCE(sig.has_gov_external_link, FALSE) AS name_match_gov_external_link
    FROM pop p
    LEFT JOIN LATERAL (
        SELECT
            COUNT(*)::bigint AS name_match_videos,
            SUM(COALESCE(y.view_count, 0))::bigint AS name_match_views,
            MAX(COALESCE(bc.subscriber_count, 0))::bigint AS subscriber_max,
            BOOL_OR(
                COALESCE(bc.channel_external_links::text, '') ILIKE '%.gov%'
            ) AS has_gov_external_link
        FROM bronze.bronze_event_youtube y
        LEFT JOIN bronze.bronze_events_channels bc ON bc.channel_id = y.channel_id
        WHERE y.state_code = p.state_code
          AND lower(BTRIM(REGEXP_REPLACE(COALESCE(y.jurisdiction_name, ''), '\s+', ' ', 'g')))
           = lower(BTRIM(REGEXP_REPLACE(p.name, '\s+', ' ', 'g')))
    ) sig ON TRUE
),
ranked AS (
    SELECT
        y.*,
        ROW_NUMBER() OVER (
            PARTITION BY y.jurisdiction_type
            ORDER BY
                y.population_estimate DESC NULLS LAST,
                (y.name_match_youtube_videos > 5)::int DESC,
                y.name_match_gov_external_link DESC,
                y.name_match_sum_views DESC,
                y.name_match_max_subscribers DESC,
                y.area_sq_miles DESC NULLS LAST,
                y.name
        ) AS rn
    FROM yt_name y
)
SELECT
    jurisdiction_type,
    name,
    jurisdiction_id,
    geoid,
    population_estimate,
    name_match_youtube_videos,
    name_match_gov_external_link,
    name_match_sum_views,
    name_match_max_subscribers,
    ROUND(area_sq_miles::numeric, 2) AS area_sq_miles
FROM ranked
WHERE rn <= 5
ORDER BY jurisdiction_type, rn;

DROP TABLE IF EXISTS _tmp_yt_ga_nm_signal;
DROP TABLE IF EXISTS _tmp_yt_covered_jurisdiction;
