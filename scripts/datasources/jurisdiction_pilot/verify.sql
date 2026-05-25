-- Verification queries for the priority-states scrape batches.
--
-- Run via psql against Neon dev (NEON_DATABASE_URL_DEV):
--     ./scripts/deployment/neon/psql_resolved.sh -f scripts/datasources/jurisdiction_pilot/verify.sql
-- Or pass a specific batch:
--     psql "$NEON_DATABASE_URL_DEV" \
--          -v batch="'<batch-uuid>'" \
--          -f scripts/datasources/jurisdiction_pilot/verify.sql

\if :{?batch}
\else
\set batch (SELECT scrape_batch_id::text FROM ( \
    SELECT scrape_batch_id, MAX(loaded_at) AS t FROM bronze.bronze_contacts_scraped GROUP BY 1 \
    UNION ALL \
    SELECT scrape_batch_id, MAX(loaded_at) AS t FROM bronze.bronze_jurisdiction_youtube_candidates GROUP BY 1 \
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
\echo === YouTube: candidates vs verified (this batch) ===
SELECT
    'candidates' AS layer,
    state_code,
    COUNT(DISTINCT jurisdiction_id) AS jurisdictions,
    COUNT(*) AS channel_rows,
    COUNT(*) FILTER (WHERE is_verified) AS verified_flagged,
    COUNT(*) FILTER (WHERE NOT is_verified) AS rejected,
    COUNT(DISTINCT rejection_reason) AS distinct_rejection_reasons
FROM bronze.bronze_jurisdiction_youtube_candidates
WHERE scrape_batch_id = :batch::uuid
GROUP BY state_code
UNION ALL
SELECT
    'verified_canonical' AS layer,
    state_code,
    COUNT(DISTINCT jurisdiction_id),
    COUNT(*),
    COUNT(*) FILTER (WHERE is_primary),
  NULL::bigint,
  NULL::bigint
FROM bronze.bronze_jurisdiction_youtube
WHERE scrape_batch_id = :batch::uuid
GROUP BY state_code
ORDER BY layer, state_code;

\echo
\echo === Rejected candidate reasons (top) ===
SELECT
    COALESCE(rejection_reason, '(verified)') AS reason,
    COUNT(*) AS n
FROM bronze.bronze_jurisdiction_youtube_candidates
WHERE scrape_batch_id = :batch::uuid
GROUP BY 1
ORDER BY n DESC
LIMIT 20;

\echo
\echo === YouTube metadata quality (junk titles / missing description / back-links) ===
SELECT
    'verified' AS layer,
    COUNT(*) AS rows,
    COUNT(*) FILTER (
        WHERE LOWER(BTRIM(channel_title)) IN ('home','videos','shorts','live','playlists','community','about')
    ) AS junk_tab_titles,
    COUNT(*) FILTER (
        WHERE channel_description IS NULL OR BTRIM(channel_description) = ''
    ) AS missing_description,
    COUNT(*) FILTER (
        WHERE jsonb_array_length(jurisdiction_website_back_links) > 0
    ) AS has_jurisdiction_back_links
FROM bronze.bronze_jurisdiction_youtube
UNION ALL
SELECT
    'candidates',
    COUNT(*),
    COUNT(*) FILTER (
        WHERE LOWER(BTRIM(channel_title)) IN ('home','videos','shorts','live','playlists','community','about')
    ),
    COUNT(*) FILTER (
        WHERE channel_description IS NULL OR BTRIM(channel_description) = ''
    ),
    COUNT(*) FILTER (
        WHERE jsonb_array_length(jurisdiction_website_back_links) > 0
    )
FROM bronze.bronze_jurisdiction_youtube_candidates;

\echo
\echo === Rows with junk tab titles (sample) ===
SELECT
    'verified' AS layer,
    jurisdiction_id,
    channel_title,
    LEFT(channel_description, 80) AS description_preview,
    jurisdiction_website_back_links,
    youtube_channel_url
FROM bronze.bronze_jurisdiction_youtube
WHERE LOWER(BTRIM(channel_title)) IN ('home','videos','shorts','live','playlists','community','about')
UNION ALL
SELECT
    'candidates',
    jurisdiction_id,
    channel_title,
    LEFT(channel_description, 80),
    jurisdiction_website_back_links,
    youtube_channel_url
FROM bronze.bronze_jurisdiction_youtube_candidates
WHERE LOWER(BTRIM(channel_title)) IN ('home','videos','shorts','live','playlists','community','about')
ORDER BY layer, jurisdiction_id
LIMIT 25;

\echo
\echo === Verified canonical channels (GA counties sample) ===
SELECT
    y.jurisdiction_id,
    y.jurisdiction_type,
    j.name,
    y.channel_title,
    y.youtube_channel_url,
    y.official_meeting_confidence,
    y.source,
    y.is_primary,
    y.back_links_to_jurisdiction_website,
    y.jurisdiction_website_back_links
FROM bronze.bronze_jurisdiction_youtube y
JOIN intermediate.int_jurisdictions j USING (jurisdiction_id)
WHERE j.state_code = 'GA'
  AND y.jurisdiction_type = 'county'
ORDER BY y.jurisdiction_id, y.is_primary DESC, y.official_meeting_confidence DESC NULLS LAST
LIMIT 30;

\echo
\echo === Noise still in candidates only (pattern_match rejects) ===
SELECT
    c.jurisdiction_id,
    c.jurisdiction_type,
    j.name,
    c.channel_title,
    c.youtube_channel_url,
    c.official_meeting_confidence,
    c.rejection_reason
FROM bronze.bronze_jurisdiction_youtube_candidates c
JOIN intermediate.int_jurisdictions j USING (jurisdiction_id)
WHERE c.scrape_batch_id = :batch::uuid
  AND NOT c.is_verified
ORDER BY c.jurisdiction_id
LIMIT 30;

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
\echo === Coverage gap: jurisdictions with website but NO verified YouTube ===
WITH targets AS (
    SELECT DISTINCT ON (jurisdiction_id)
        jurisdiction_id,
        state_code,
        COALESCE(NULLIF(btrim(j.name), ''), jurisdiction_id) AS name,
        btrim(website_url) AS website_url
    FROM intermediate.int_jurisdiction_websites w
    LEFT JOIN intermediate.int_jurisdictions j USING (jurisdiction_id)
    WHERE w.state_code IN ('AL','GA','IN','MA','WA','WI')
      AND w.jurisdiction_category IN ('municipality','county')
      AND w.website_url IS NOT NULL AND btrim(w.website_url) <> ''
    ORDER BY jurisdiction_id, w.website_record_key
),
verified AS (
    SELECT DISTINCT jurisdiction_id FROM bronze.bronze_jurisdiction_youtube
)
SELECT t.state_code, t.jurisdiction_id, t.name, t.website_url
FROM targets t
LEFT JOIN verified v USING (jurisdiction_id)
WHERE v.jurisdiction_id IS NULL
ORDER BY t.state_code, t.jurisdiction_id
LIMIT 50;

\echo
\echo === Checkpoint file ===
\echo (See data/bronze/jurisdiction_pilot_progress/<batch>.jsonl)
