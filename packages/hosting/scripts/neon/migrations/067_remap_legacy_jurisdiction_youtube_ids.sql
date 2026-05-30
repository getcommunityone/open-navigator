-- Migration 067: remap legacy municipality_/county_ ids in YouTube channel tables.
-- (064 predates bronze_jurisdiction_youtube_candidates; pilot may write legacy ids
--  until load_jurisdictions / persist canonicalization is deployed.)
--
-- Apply:
--   ./scripts/deployment/neon/psql_resolved.sh -f scripts/deployment/neon/migrations/067_remap_legacy_jurisdiction_youtube_ids.sql

BEGIN;

DO $remap$
DECLARE
    tbl text;
    n bigint;
BEGIN
    FOR tbl IN SELECT unnest(ARRAY[
        'bronze.bronze_jurisdiction_youtube',
        'bronze.bronze_jurisdiction_youtube_candidates'
    ]) LOOP
        -- Drop legacy rows when the canonical id already has the same channel URL.
        EXECUTE format($sql$
            DELETE FROM %s legacy
            USING bronze.bronze_jurisdictions_counties c, %s canonical
            WHERE legacy.jurisdiction_id = 'county_' || c.geoid
              AND canonical.jurisdiction_id = c.jurisdiction_id
              AND canonical.youtube_channel_url = legacy.youtube_channel_url
        $sql$, tbl, tbl);
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE 'county legacy dup delete %: % rows', tbl, n;

        EXECUTE format($sql$
            DELETE FROM %s legacy
            USING bronze.bronze_jurisdictions_municipalities m, %s canonical
            WHERE legacy.jurisdiction_id = 'municipality_' || m.geoid
              AND canonical.jurisdiction_id = m.jurisdiction_id
              AND canonical.youtube_channel_url = legacy.youtube_channel_url
        $sql$, tbl, tbl);
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE 'municipality legacy dup delete %: % rows', tbl, n;

        EXECUTE format($sql$
            UPDATE %s t
            SET jurisdiction_id = c.jurisdiction_id
            FROM bronze.bronze_jurisdictions_counties c
            WHERE t.jurisdiction_id = 'county_' || c.geoid
              AND t.jurisdiction_id IS DISTINCT FROM c.jurisdiction_id
        $sql$, tbl);
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE 'county remap %: % rows', tbl, n;

        EXECUTE format($sql$
            UPDATE %s t
            SET jurisdiction_id = m.jurisdiction_id
            FROM bronze.bronze_jurisdictions_municipalities m
            WHERE t.jurisdiction_id = 'municipality_' || m.geoid
              AND t.jurisdiction_id IS DISTINCT FROM m.jurisdiction_id
        $sql$, tbl);
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE 'municipality remap %: % rows', tbl, n;
    END LOOP;
END;
$remap$;

DELETE FROM bronze.bronze_jurisdiction_youtube a
USING bronze.bronze_jurisdiction_youtube b
WHERE a.jurisdiction_id = b.jurisdiction_id
  AND a.youtube_channel_url = b.youtube_channel_url
  AND a.id < b.id;

DELETE FROM bronze.bronze_jurisdiction_youtube_candidates a
USING bronze.bronze_jurisdiction_youtube_candidates b
WHERE a.scrape_batch_id = b.scrape_batch_id
  AND a.jurisdiction_id = b.jurisdiction_id
  AND a.youtube_channel_url = b.youtube_channel_url
  AND a.id < b.id;

COMMIT;
