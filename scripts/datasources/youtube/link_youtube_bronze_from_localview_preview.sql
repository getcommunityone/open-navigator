-- Preview only: counts and samples for LocalView-based jurisdiction linking (no gold).
-- See link_youtube_bronze_from_localview_apply.sql to write changes.
--
-- Prerequisites:
--   dbt run --select int_events_localview int_localview_jurisdiction_geography
--            int_localview_channel_geography int_jurisdictions int_events_channels

\set ON_ERROR_STOP on

\echo '========== Pass 1: rows int_events_channels could fill on bronze_events_youtube =========='
SELECT
    COUNT(*) AS youtube_rows_to_update_pass1
FROM bronze.bronze_events_youtube y
INNER JOIN intermediate.int_events_channels_registry ec
    ON ec.channel_id = y.channel_id
INNER JOIN intermediate.int_jurisdictions j
    ON j.jurisdiction_id = ec.jurisdiction_id
WHERE ec.jurisdiction_id IS NOT NULL
  AND (
      y.jurisdiction_id IS NULL
      OR BTRIM(y.jurisdiction_id) = ''
      OR lower(BTRIM(y.jurisdiction_id)) = 'unknown'
  );

\echo '========== Pass 2: rows LocalView name-consensus could fill (GEOID path NULL on ec) =========='
WITH lv_consensus AS (
    SELECT
        il.channel_id,
        MAX(lv.state_code) AS state_code,
        MAX(lv.jurisdiction_name) AS jurisdiction_name
    FROM intermediate.int_events_localview il
    INNER JOIN bronze.bronze_events_localview lv
        ON lv.datasource_id = il.datasource_id
       AND lv.datasource = 'localview'
    WHERE il.channel_id IS NOT NULL
      AND BTRIM(COALESCE(il.channel_id, '')) <> ''
      AND lv.state_code IS NOT NULL
      AND BTRIM(COALESCE(lv.jurisdiction_name, '')) <> ''
    GROUP BY il.channel_id
    HAVING COUNT(DISTINCT (lv.state_code, lower(BTRIM(lv.jurisdiction_name)))) = 1
),
juris_name_match AS (
    SELECT
        lc.channel_id,
        MAX(j.jurisdiction_id) AS jurisdiction_id
    FROM lv_consensus lc
    INNER JOIN intermediate.int_jurisdictions j
        ON j.state_code = lc.state_code
       AND lower(BTRIM(j.name)) = lower(BTRIM(lc.jurisdiction_name))
    GROUP BY lc.channel_id
    HAVING COUNT(DISTINCT j.jurisdiction_id) = 1
)
SELECT COUNT(*) AS youtube_rows_to_update_pass2
FROM bronze.bronze_events_youtube y
INNER JOIN juris_name_match jnm ON jnm.channel_id = y.channel_id
LEFT JOIN intermediate.int_events_channels_registry ec ON ec.channel_id = y.channel_id
WHERE ec.jurisdiction_id IS NULL
  AND (
      y.jurisdiction_id IS NULL
      OR BTRIM(y.jurisdiction_id) = ''
      OR lower(BTRIM(y.jurisdiction_id)) = 'unknown'
  );

\echo '========== Sample (up to 20) Pass 1 =========='
SELECT
    y.channel_id,
    MAX(y.jurisdiction_id) AS sample_current_jurisdiction_id,
    MAX(ec.jurisdiction_id) AS new_jurisdiction_id,
    MAX(j.name) AS new_jurisdiction_name,
    MAX(j.state_code) AS state_code
FROM bronze.bronze_events_youtube y
INNER JOIN intermediate.int_events_channels_registry ec
    ON ec.channel_id = y.channel_id
INNER JOIN intermediate.int_jurisdictions j
    ON j.jurisdiction_id = ec.jurisdiction_id
WHERE ec.jurisdiction_id IS NOT NULL
  AND (
      y.jurisdiction_id IS NULL
      OR BTRIM(y.jurisdiction_id) = ''
      OR lower(BTRIM(y.jurisdiction_id)) = 'unknown'
  )
GROUP BY y.channel_id
ORDER BY y.channel_id
LIMIT 20;

\echo '========== Diagnostic: LocalView (state_code, channel_title) with exactly one channel_id =========='
SELECT
    lv.state_code,
    lower(BTRIM(lv.channel_title)) AS channel_title_norm,
    COUNT(DISTINCT il.channel_id) AS distinct_channel_ids,
    MAX(il.channel_id) AS only_channel_id
FROM bronze.bronze_events_localview lv
INNER JOIN intermediate.int_events_localview il
    ON il.datasource_id = lv.datasource_id
   AND lv.datasource = 'localview'
WHERE BTRIM(COALESCE(lv.channel_title, '')) <> ''
  AND il.channel_id IS NOT NULL
  AND BTRIM(COALESCE(il.channel_id, '')) <> ''
GROUP BY lv.state_code, lower(BTRIM(lv.channel_title))
HAVING COUNT(DISTINCT il.channel_id) = 1
ORDER BY lv.state_code, channel_title_norm
LIMIT 30;
