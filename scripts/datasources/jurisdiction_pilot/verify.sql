-- Verification queries for the priority-states scrape batches.
--
-- Run via psql against Neon dev (NEON_DATABASE_URL_DEV):
--     ./scripts/deployment/neon/psql_resolved.sh -f scripts/datasources/jurisdiction_pilot/verify.sql
-- Or pass a specific batch:
--     psql "$NEON_DATABASE_URL_DEV" \
--          -v batch="'<batch-uuid>'" \
--          -f scripts/datasources/jurisdiction_pilot/verify.sql
--
-- If :batch is not set, defaults to "the latest batch present in either bronze table".

\if :{?batch}
\else
\set batch (SELECT scrape_batch_id::text FROM ( \
    SELECT scrape_batch_id, MAX(loaded_at) AS t FROM bronze.bronze_contacts_scraped GROUP BY 1 \
    UNION ALL \
    SELECT scrape_batch_id, MAX(loaded_at) AS t FROM bronze.bronze_jurisdiction_youtube GROUP BY 1 \
) x ORDER BY t DESC LIMIT 1)
\endif

\echo
\echo === Batch in scope ===
SELECT :batch::uuid AS batch_id;

\echo
\echo === Contacts per state ===
SELECT
    state_code,
    COUNT(DISTINCT jurisdiction_id)                AS jurisdictions_with_contacts,
    COUNT(*)                                       AS contact_rows,
    SUM((raw_row->>'is_mayor')::boolean::int)      AS mayor_rows,
    SUM(CASE WHEN email IS NOT NULL THEN 1 END)    AS rows_with_email,
    SUM(CASE WHEN phone IS NOT NULL THEN 1 END)    AS rows_with_phone
FROM bronze.bronze_contacts_scraped
WHERE scrape_batch_id = :batch::uuid
GROUP BY state_code
ORDER BY state_code;

\echo
\echo === YouTube channels per state ===
SELECT
    state_code,
    COUNT(DISTINCT jurisdiction_id)  AS jurisdictions_with_channels,
    COUNT(*)                         AS channel_rows,
    COUNT(DISTINCT youtube_channel_url) AS distinct_channel_urls,
    SUM(video_count)                 AS total_videos
FROM bronze.bronze_jurisdiction_youtube
WHERE scrape_batch_id = :batch::uuid
GROUP BY state_code
ORDER BY state_code;

\echo
\echo === Mayor-flagged contacts (top 50) ===
SELECT
    state_code,
    jurisdiction_id,
    person_name,
    title_or_role,
    email,
    phone,
    source_page_url
FROM bronze.bronze_contacts_scraped
WHERE scrape_batch_id = :batch::uuid
  AND (raw_row->>'is_mayor')::boolean = TRUE
ORDER BY state_code, jurisdiction_id
LIMIT 50;

\echo
\echo === Jurisdiction → website → YouTube map (sample 25) ===
SELECT
    y.state_code,
    y.jurisdiction_id,
    y.website_url,
    y.youtube_channel_url,
    y.channel_title,
    y.video_count,
    y.subscriber_count
FROM bronze.bronze_jurisdiction_youtube y
WHERE y.scrape_batch_id = :batch::uuid
ORDER BY y.video_count DESC NULLS LAST
LIMIT 25;

\echo
\echo === Coverage gap: jurisdictions with website but NO contacts and NO channels ===
WITH targets AS (
    SELECT DISTINCT ON (jurisdiction_id)
        jurisdiction_id,
        state_code,
        COALESCE(NULLIF(btrim(organization_name), ''),
                 NULLIF(btrim(city), ''),
                 jurisdiction_id) AS name,
        btrim(website_url) AS website_url
    FROM intermediate.int_jurisdiction_websites
    WHERE state_code IN ('AL','GA','IN','MA','WA','WI')
      AND jurisdiction_category IN ('municipality','county')
      AND website_url IS NOT NULL AND btrim(website_url) <> ''
    ORDER BY jurisdiction_id, website_record_key
),
ran AS (
    SELECT DISTINCT jurisdiction_id FROM bronze.bronze_contacts_scraped
      WHERE scrape_batch_id = :batch::uuid
    UNION
    SELECT DISTINCT jurisdiction_id FROM bronze.bronze_jurisdiction_youtube
      WHERE scrape_batch_id = :batch::uuid
)
SELECT t.state_code, t.jurisdiction_id, t.name, t.website_url
FROM targets t
LEFT JOIN ran r USING (jurisdiction_id)
WHERE r.jurisdiction_id IS NULL
ORDER BY t.state_code, t.jurisdiction_id
LIMIT 50;

\echo
\echo === Errors recorded in checkpoint file? ===
\echo (Checkpoint is a local JSONL — see data/bronze/jurisdiction_pilot_progress/<batch>.jsonl)
