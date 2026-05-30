-- Migration 068: store jurisdiction website URLs linked from YouTube About pages.
--
-- ``jurisdiction_website_back_links`` is the subset of ``external_links`` (plus description
-- URL mentions) whose host matches the jurisdiction ``website_url``.
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/068_add_jurisdiction_website_back_links_youtube.sql

BEGIN;

ALTER TABLE bronze.bronze_jurisdiction_youtube_candidates
    ADD COLUMN IF NOT EXISTS jurisdiction_website_back_links JSONB NOT NULL DEFAULT '[]'::JSONB;

ALTER TABLE bronze.bronze_jurisdiction_youtube
    ADD COLUMN IF NOT EXISTS jurisdiction_website_back_links JSONB NOT NULL DEFAULT '[]'::JSONB;

COMMENT ON COLUMN bronze.bronze_jurisdiction_youtube_candidates.jurisdiction_website_back_links IS
    'JSON array of outbound YouTube About-page URLs matching the jurisdiction website host.';

COMMENT ON COLUMN bronze.bronze_jurisdiction_youtube.jurisdiction_website_back_links IS
    'JSON array of outbound YouTube About-page URLs matching the jurisdiction website host.';

-- Best-effort backfill from existing external_links + website_url host match.
UPDATE bronze.bronze_jurisdiction_youtube y
SET jurisdiction_website_back_links = sub.links
FROM (
    SELECT
        y2.id,
        COALESCE(
            jsonb_agg(DISTINCT link) FILTER (WHERE link IS NOT NULL),
            '[]'::jsonb
        ) AS links
    FROM bronze.bronze_jurisdiction_youtube y2
    CROSS JOIN LATERAL jsonb_array_elements_text(COALESCE(y2.external_links, '[]'::jsonb)) AS link
    WHERE y2.website_url IS NOT NULL
      AND BTRIM(y2.website_url) <> ''
      AND link ~* '^https?://'
      AND regexp_replace(lower(link), '^https?://(www\.)?', '') LIKE
          regexp_replace(lower(y2.website_url), '^https?://(www\.)?', '') || '%'
    GROUP BY y2.id
) sub
WHERE y.id = sub.id;

UPDATE bronze.bronze_jurisdiction_youtube_candidates c
SET jurisdiction_website_back_links = sub.links
FROM (
    SELECT
        c2.id,
        COALESCE(
            jsonb_agg(DISTINCT link) FILTER (WHERE link IS NOT NULL),
            '[]'::jsonb
        ) AS links
    FROM bronze.bronze_jurisdiction_youtube_candidates c2
    CROSS JOIN LATERAL jsonb_array_elements_text(COALESCE(c2.external_links, '[]'::jsonb)) AS link
    WHERE c2.website_url IS NOT NULL
      AND BTRIM(c2.website_url) <> ''
      AND link ~* '^https?://'
      AND regexp_replace(lower(link), '^https?://(www\.)?', '') LIKE
          regexp_replace(lower(c2.website_url), '^https?://(www\.)?', '') || '%'
    GROUP BY c2.id
) sub
WHERE c.id = sub.id;

COMMIT;
