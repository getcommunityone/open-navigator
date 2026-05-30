-- Migration 084: Remap legacy county jurisdiction_id of the form
-- `c-{state_code}-{geoid}` (e.g. c-IN-18175, c-MA-25011, c-WA-53015) to the
-- canonical `{place_slug}_{geoid}` ids generated in bronze.bronze_jurisdictions_counties.
--
-- Background: migration 064 remapped the `county_{geoid}` / `municipality_{geoid}` /
-- `school_district_{geoid}` legacy formats, but the older `c-{state}-{geoid}` county
-- variant — carried in from legacy YouTube source manifests — was never covered.
-- It still appears in bronze.bronze_events_youtube and bronze.bronze_events_text_ai,
-- breaking joins to int_jurisdictions (the API works around it with a defensive
-- `'c-' || state_code || '-' || geoid` OR clause in batch_job_status.py).
--
-- The {geoid} segment is globally unique per county, so the join keys on the
-- extracted geoid; the redundant {state_code} segment is ignored.
-- After applying: rebuild dbt intermediate models (int_jurisdictions, events_text_search, …).

DO $remap$
DECLARE
    tbl text;
    n bigint;
BEGIN
    FOR tbl IN SELECT unnest(ARRAY[
        'bronze.bronze_events_youtube',
        'bronze.bronze_events_text_ai'
    ]) LOOP
        EXECUTE format($sql$
            UPDATE %s t
            SET jurisdiction_id = c.jurisdiction_id
            FROM bronze.bronze_jurisdictions_counties c
            WHERE t.jurisdiction_id ~ '^c-[A-Z]+-.+$'
              AND c.geoid = substring(t.jurisdiction_id from '^c-[A-Z]+-(.+)$')
              AND t.jurisdiction_id IS DISTINCT FROM c.jurisdiction_id
        $sql$, tbl);
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE 'c- county remap %: % rows', tbl, n;
    END LOOP;
END;
$remap$;

-- Verification: no `c-` formatted ids should remain that map to a known county.
DO $verify$
DECLARE
    leftover bigint;
BEGIN
    SELECT count(*) INTO leftover
    FROM (
        SELECT jurisdiction_id FROM bronze.bronze_events_youtube WHERE jurisdiction_id ~ '^c-[A-Z]+-.+$'
        UNION ALL
        SELECT jurisdiction_id FROM bronze.bronze_events_text_ai WHERE jurisdiction_id ~ '^c-[A-Z]+-.+$'
    ) s
    JOIN bronze.bronze_jurisdictions_counties c
      ON c.geoid = substring(s.jurisdiction_id from '^c-[A-Z]+-(.+)$');
    RAISE NOTICE 'remaining mappable c- ids after remap: %', leftover;
END;
$verify$;
