-- Migration 064: Remap legacy typed jurisdiction_id (county_13017, municipality_0101708, …)
-- to canonical {place_slug}_{geoid} from bronze base tables (migration 061).
--
-- Bronze counties/municipalities already use generated slug_geoid ids; this updates
-- dependent bronze/c1 rows and any tables still keyed by the old strings.
-- After applying: rebuild dbt intermediate models (int_jurisdictions, int_jurisdiction_websites, …).

-- County: county_{geoid} -> bronze.bronze_jurisdictions_counties.jurisdiction_id
DO $remap$
DECLARE
    tbl text;
    n bigint;
BEGIN
    FOR tbl IN SELECT unnest(ARRAY[
        'bronze.bronze_persons_scraped',
        'bronze.bronze_events_youtube',
        'bronze.bronze_events_meetings_counties_scraped',
        'bronze.bronze_jurisdiction_youtube',
        'bronze.bronze_elections_scraped',
        'bronze.bronze_jurisdiction_website_accessibility',
        'bronze.bronze_events_text_ai',
        'bronze.bronze_jurisdictions_county_directory',
        'bronze.bronze_jurisdiction_website_lighthouse'
    ]) LOOP
        EXECUTE format($sql$
            UPDATE %s t
            SET jurisdiction_id = c.jurisdiction_id
            FROM bronze.bronze_jurisdictions_counties c
            WHERE t.jurisdiction_id = 'county_' || c.geoid
              AND t.jurisdiction_id IS DISTINCT FROM c.jurisdiction_id
        $sql$, tbl);
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE 'county remap %: % rows', tbl, n;
    END LOOP;
END;
$remap$;

-- Municipality: municipality_{geoid}
DO $remap$
DECLARE
    tbl text;
    n bigint;
BEGIN
    FOR tbl IN SELECT unnest(ARRAY[
        'bronze.bronze_persons_scraped',
        'bronze.bronze_events_youtube',
        'bronze.bronze_events_meetings_municipalities_scraped',
        'bronze.bronze_jurisdiction_youtube',
        'bronze.bronze_elections_scraped',
        'bronze.bronze_jurisdiction_website_accessibility',
        'bronze.bronze_events_text_ai',
        'bronze.bronze_jurisdictions_municipalities_league'
    ]) LOOP
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

-- School district: school_district_{geoid}
DO $remap$
DECLARE
    tbl text;
    n bigint;
BEGIN
    FOR tbl IN SELECT unnest(ARRAY[
        'bronze.bronze_events_meetings_school_districts_scraped',
        'bronze.bronze_persons_scraped',
        'bronze.bronze_events_youtube'
    ]) LOOP
        BEGIN
            EXECUTE format($sql$
                UPDATE %s t
                SET jurisdiction_id = d.jurisdiction_id
                FROM bronze.bronze_jurisdictions_school_districts d
                WHERE t.jurisdiction_id = 'school_district_' || d.geoid
                  AND t.jurisdiction_id IS DISTINCT FROM d.jurisdiction_id
            $sql$, tbl);
            GET DIAGNOSTICS n = ROW_COUNT;
            RAISE NOTICE 'school_district remap %: % rows', tbl, n;
        EXCEPTION WHEN undefined_table THEN
            RAISE NOTICE 'skip % (no table)', tbl;
        END;
    END LOOP;
END;
$remap$;

-- c1 layer (same join patterns)
UPDATE public.c1_event t
SET jurisdiction_id = c.jurisdiction_id
FROM bronze.bronze_jurisdictions_counties c
WHERE t.jurisdiction_id = 'county_' || c.geoid
  AND t.jurisdiction_id IS DISTINCT FROM c.jurisdiction_id;

UPDATE public.c1_event t
SET jurisdiction_id = m.jurisdiction_id
FROM bronze.bronze_jurisdictions_municipalities m
WHERE t.jurisdiction_id = 'municipality_' || m.geoid
  AND t.jurisdiction_id IS DISTINCT FROM m.jurisdiction_id;

UPDATE public.c1_election t
SET jurisdiction_id = c.jurisdiction_id
FROM bronze.bronze_jurisdictions_counties c
WHERE t.jurisdiction_id = 'county_' || c.geoid
  AND t.jurisdiction_id IS DISTINCT FROM c.jurisdiction_id;

UPDATE public.c1_election t
SET jurisdiction_id = m.jurisdiction_id
FROM bronze.bronze_jurisdictions_municipalities m
WHERE t.jurisdiction_id = 'municipality_' || m.geoid
  AND t.jurisdiction_id IS DISTINCT FROM m.jurisdiction_id;

UPDATE public.c1_division t
SET jurisdiction_id = c.jurisdiction_id
FROM bronze.bronze_jurisdictions_counties c
WHERE t.jurisdiction_id = 'county_' || c.geoid
  AND t.jurisdiction_id IS DISTINCT FROM c.jurisdiction_id;

UPDATE public.c1_division t
SET jurisdiction_id = m.jurisdiction_id
FROM bronze.bronze_jurisdictions_municipalities m
WHERE t.jurisdiction_id = 'municipality_' || m.geoid
  AND t.jurisdiction_id IS DISTINCT FROM m.jurisdiction_id;
