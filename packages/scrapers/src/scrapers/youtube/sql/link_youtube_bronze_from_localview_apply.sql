-- Apply LocalView + dbt intermediate jurisdiction links to bronze (no gold).
-- Run link_youtube_bronze_from_localview_preview.sql first.
--
-- Prerequisites:
--   dbt run --select int_events_localview int_localview_jurisdiction_geography
--            int_localview_channel_geography int_jurisdictions int_events_channels

\set ON_ERROR_STOP on

BEGIN;

\echo '========== Pass 1: bronze.bronze_events_youtube =========='
UPDATE bronze.bronze_events_youtube y
SET
    jurisdiction_id = j.jurisdiction_id,
    jurisdiction_name = j.name,
    jurisdiction_type = j.jurisdiction_type,
    state_code = j.state_code,
    state = j.state,
    last_updated = CURRENT_TIMESTAMP
FROM intermediate.int_events_channels_registry ec
INNER JOIN intermediate.int_jurisdictions j
    ON j.jurisdiction_id = ec.jurisdiction_id
WHERE y.channel_id = ec.channel_id
  AND ec.jurisdiction_id IS NOT NULL
  AND (
      y.jurisdiction_id IS NULL
      OR BTRIM(y.jurisdiction_id) = ''
      OR lower(BTRIM(y.jurisdiction_id)) = 'unknown'
  );

\echo '========== Pass 1: bronze.bronze_events_channels (jurisdictions JSON when empty) =========='
UPDATE bronze.bronze_events_channels bc
SET
    jurisdictions = ec.jurisdictions,
    in_localview = TRUE,
    discovery_method = COALESCE(bc.discovery_method, 'derived_from_localview'),
    last_updated = CURRENT_TIMESTAMP
FROM intermediate.int_events_channels_registry ec
WHERE bc.channel_id = ec.channel_id
  AND ec.jurisdiction_id IS NOT NULL
  AND ec.jurisdictions IS NOT NULL
  AND jsonb_array_length(ec.jurisdictions) > 0
  AND (
      bc.jurisdictions IS NULL
      OR bc.jurisdictions = '[]'::jsonb
  );

\echo '========== Pass 2: bronze.bronze_events_youtube (name consensus; ec.jurisdiction_id NULL) =========='
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
UPDATE bronze.bronze_events_youtube y
SET
    jurisdiction_id = j.jurisdiction_id,
    jurisdiction_name = j.name,
    jurisdiction_type = j.jurisdiction_type,
    state_code = j.state_code,
    state = j.state,
    last_updated = CURRENT_TIMESTAMP
FROM juris_name_match jnm
INNER JOIN intermediate.int_jurisdictions j
    ON j.jurisdiction_id = jnm.jurisdiction_id
LEFT JOIN intermediate.int_events_channels_registry ec ON ec.channel_id = jnm.channel_id
WHERE y.channel_id = jnm.channel_id
  AND ec.jurisdiction_id IS NULL
  AND (
      y.jurisdiction_id IS NULL
      OR BTRIM(y.jurisdiction_id) = ''
      OR lower(BTRIM(y.jurisdiction_id)) = 'unknown'
  );

COMMIT;

\echo '========== Done =========='
