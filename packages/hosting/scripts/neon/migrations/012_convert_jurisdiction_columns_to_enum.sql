-- Migration 012: Convert jurisdiction_type / jurisdiction_id_source from TEXT → ENUM
--               and add missing columns to _wikidata tables.
--
-- Handles three cases:
--   A. Column doesn't exist yet              → ADD COLUMN with enum type
--   B. Column exists as TEXT with CHECK      → drop CHECK by known name, drop DEFAULT,
--                                              retype, restore DEFAULT
--   C. Column already enum type              → no-op
--
-- Idempotent: safe to re-run.

-- ─────────────────────────────────────────────────────────────────────────────
-- Enum types (no-op if already created by migration 011)
-- ─────────────────────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE bronze.jurisdiction_type_enum AS ENUM (
        'state', 'county', 'municipality', 'school_district', 'zcta'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE bronze.jurisdiction_id_source_enum AS ENUM (
        'usps', 'county_fips', 'place_geoid', 'school_district_geoid', 'zip_code'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 1: Drop known CHECK constraints by name (added by old TEXT version of
--         migration 011). DROP CONSTRAINT IF EXISTS is safe if they're already gone.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE bronze.bronze_jurisdictions_states               DROP CONSTRAINT IF EXISTS chk_bjs_jtype;
ALTER TABLE bronze.bronze_jurisdictions_states               DROP CONSTRAINT IF EXISTS chk_bjs_jsrc;
ALTER TABLE bronze.bronze_jurisdictions_counties             DROP CONSTRAINT IF EXISTS chk_bjc_jtype;
ALTER TABLE bronze.bronze_jurisdictions_counties             DROP CONSTRAINT IF EXISTS chk_bjc_jsrc;
ALTER TABLE bronze.bronze_jurisdictions_municipalities       DROP CONSTRAINT IF EXISTS chk_bjm_jtype;
ALTER TABLE bronze.bronze_jurisdictions_municipalities       DROP CONSTRAINT IF EXISTS chk_bjm_jsrc;
ALTER TABLE bronze.bronze_jurisdictions_school_districts     DROP CONSTRAINT IF EXISTS chk_bjsd_jtype;
ALTER TABLE bronze.bronze_jurisdictions_school_districts     DROP CONSTRAINT IF EXISTS chk_bjsd_jsrc;
ALTER TABLE bronze.bronze_jurisdictions_place_zcta           DROP CONSTRAINT IF EXISTS chk_bjpz_jtype;
ALTER TABLE bronze.bronze_jurisdictions_place_zcta           DROP CONSTRAINT IF EXISTS chk_bjpz_jsrc;
ALTER TABLE bronze.bronze_jurisdictions_states_scraped       DROP CONSTRAINT IF EXISTS chk_bjss_jtype;
ALTER TABLE bronze.bronze_jurisdictions_states_scraped       DROP CONSTRAINT IF EXISTS chk_bjss_jsrc;
ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped DROP CONSTRAINT IF EXISTS chk_bjms_jtype;
ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped DROP CONSTRAINT IF EXISTS chk_bjms_jsrc;
ALTER TABLE bronze.bronze_jurisdictions_counties_scraped     DROP CONSTRAINT IF EXISTS chk_bjcs_jtype;
ALTER TABLE bronze.bronze_jurisdictions_counties_scraped     DROP CONSTRAINT IF EXISTS chk_bjcs_jsrc;
ALTER TABLE bronze.bronze_jurisdictions_school_districts_scraped DROP CONSTRAINT IF EXISTS chk_bjsds_jtype;
ALTER TABLE bronze.bronze_jurisdictions_school_districts_scraped DROP CONSTRAINT IF EXISTS chk_bjsds_jsrc;

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 2: For each table either ADD (missing) or retype (TEXT → enum).
--         Wikidata tables may not have these columns at all if they were
--         materialized before migration 011 — ADD COLUMN handles that case.
-- ─────────────────────────────────────────────────────────────────────────────

DO $$ DECLARE rec RECORD; col_type TEXT; BEGIN
    FOR rec IN SELECT * FROM (VALUES
        ('bronze_jurisdictions_states',                    'state',           'usps'),
        ('bronze_jurisdictions_counties',                  'county',          'county_fips'),
        ('bronze_jurisdictions_municipalities',            'municipality',    'place_geoid'),
        ('bronze_jurisdictions_school_districts',          'school_district', 'school_district_geoid'),
        ('bronze_jurisdictions_place_zcta',                'zcta',            'zip_code'),
        ('bronze_jurisdictions_states_scraped',            'state',           'usps'),
        ('bronze_jurisdictions_counties_scraped',          'county',          'county_fips'),
        ('bronze_jurisdictions_municipalities_scraped',    'municipality',    'place_geoid'),
        ('bronze_jurisdictions_school_districts_scraped',  'school_district', 'school_district_geoid'),
        ('bronze_jurisdictions_states_wikidata',           'state',           'usps'),
        ('bronze_jurisdictions_counties_wikidata',         'county',          'county_fips'),
        ('bronze_jurisdictions_municipalities_wikidata',   'municipality',    'place_geoid'),
        ('bronze_jurisdictions_school_districts_wikidata', 'school_district', 'school_district_geoid')
    ) AS t(tbl, jtype, jsrc)
    LOOP
        -- Skip tables that don't exist (wikidata tables may not be materialized yet)
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'bronze' AND table_name = rec.tbl
        ) THEN
            RAISE NOTICE 'Table bronze.% does not exist — skipping', rec.tbl;
            CONTINUE;
        END IF;

        -- ── jurisdiction_type ──────────────────────────────────────────────

        SELECT data_type INTO col_type
        FROM information_schema.columns
        WHERE table_schema = 'bronze'
          AND table_name   = rec.tbl
          AND column_name  = 'jurisdiction_type';

        IF col_type IS NULL THEN
            -- Column missing entirely (old wikidata table)
            EXECUTE format(
                'ALTER TABLE bronze.%I ADD COLUMN jurisdiction_type
                 bronze.jurisdiction_type_enum NOT NULL DEFAULT %L::bronze.jurisdiction_type_enum',
                rec.tbl, rec.jtype
            );
            RAISE NOTICE 'Added %.jurisdiction_type', rec.tbl;

        ELSIF col_type = 'text' THEN
            -- Exists as TEXT — drop default, retype, restore default
            EXECUTE format('ALTER TABLE bronze.%I ALTER COLUMN jurisdiction_type DROP DEFAULT', rec.tbl);
            EXECUTE format(
                'ALTER TABLE bronze.%I ALTER COLUMN jurisdiction_type
                 TYPE bronze.jurisdiction_type_enum
                 USING jurisdiction_type::bronze.jurisdiction_type_enum',
                rec.tbl
            );
            EXECUTE format(
                'ALTER TABLE bronze.%I ALTER COLUMN jurisdiction_type
                 SET DEFAULT %L::bronze.jurisdiction_type_enum',
                rec.tbl, rec.jtype
            );
            RAISE NOTICE 'Converted %.jurisdiction_type TEXT → enum', rec.tbl;
        END IF;

        -- ── jurisdiction_id_source ─────────────────────────────────────────

        SELECT data_type INTO col_type
        FROM information_schema.columns
        WHERE table_schema = 'bronze'
          AND table_name   = rec.tbl
          AND column_name  = 'jurisdiction_id_source';

        IF col_type IS NULL THEN
            EXECUTE format(
                'ALTER TABLE bronze.%I ADD COLUMN jurisdiction_id_source
                 bronze.jurisdiction_id_source_enum NOT NULL DEFAULT %L::bronze.jurisdiction_id_source_enum',
                rec.tbl, rec.jsrc
            );
            RAISE NOTICE 'Added %.jurisdiction_id_source', rec.tbl;

        ELSIF col_type = 'text' THEN
            EXECUTE format('ALTER TABLE bronze.%I ALTER COLUMN jurisdiction_id_source DROP DEFAULT', rec.tbl);
            EXECUTE format(
                'ALTER TABLE bronze.%I ALTER COLUMN jurisdiction_id_source
                 TYPE bronze.jurisdiction_id_source_enum
                 USING jurisdiction_id_source::bronze.jurisdiction_id_source_enum',
                rec.tbl
            );
            EXECUTE format(
                'ALTER TABLE bronze.%I ALTER COLUMN jurisdiction_id_source
                 SET DEFAULT %L::bronze.jurisdiction_id_source_enum',
                rec.tbl, rec.jsrc
            );
            RAISE NOTICE 'Converted %.jurisdiction_id_source TEXT → enum', rec.tbl;
        END IF;

        -- ── jurisdiction_id ────────────────────────────────────────────────
        -- Wikidata tables may also be missing jurisdiction_id if built before
        -- migration 010. Add it as a plain TEXT column (it's computed on the
        -- base tables but stored as TEXT in the denormalized wikidata snapshot).

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'bronze'
              AND table_name   = rec.tbl
              AND column_name  = 'jurisdiction_id'
        ) THEN
            EXECUTE format('ALTER TABLE bronze.%I ADD COLUMN jurisdiction_id TEXT', rec.tbl);
            -- Populate from usps + geoid for wikidata tables
            EXECUTE format(
                'UPDATE bronze.%I SET jurisdiction_id =
                    CASE WHEN %L = ''state'' THEN usps
                         ELSE usps || ''-'' || geoid
                    END',
                rec.tbl, rec.jtype
            );
            RAISE NOTICE 'Added and populated %.jurisdiction_id', rec.tbl;
        END IF;

    END LOOP;
END $$;
