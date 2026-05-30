-- Migration 061: jurisdiction_id = {place_slug}_{geoid} (e.g. andalusia_0101708, mobile_01097).
--
-- Replaces migration 010/013 forms (AL-01001, c-AL-01001, municipality_0101852) on county and
-- municipality bronze tables (+ scraped + wikidata FK children). States unchanged (USPS).
-- School districts use the same slug formula for int_jurisdictions consistency.

CREATE OR REPLACE FUNCTION bronze.jurisdiction_place_slug(label text)
RETURNS text
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
  SELECT COALESCE(
    NULLIF(
      LEFT(
        regexp_replace(
          regexp_replace(
            regexp_replace(
              regexp_replace(
                lower(trim(coalesce(label, ''))),
                '^(?:city|town|village|borough|township|county)\s+of\s+',
                '',
                'i'
              ),
              '\s+(?:city|town|village|county|borough|cdp|municipality|township|parish|ccd)\s*$',
              '',
              'i'
            ),
            '[^a-z0-9]+',
            '_',
            'g'
          ),
          '_+',
          '_',
          'g'
        ),
        56
      ),
      ''
    ),
    'unknown'
  );
$$;

CREATE OR REPLACE FUNCTION bronze.jurisdiction_id_from_place(label text, geoid text)
RETURNS text
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
  SELECT bronze.jurisdiction_place_slug(label) || '_' || geoid;
$$;

-- ═════════════════════════════════════════════════════════════════════════════
-- COUNTIES
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE bronze.bronze_jurisdictions_counties_scraped
    DROP CONSTRAINT IF EXISTS fk_bjcs_jurisdiction_id;
DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_counties_wikidata
        DROP CONSTRAINT IF EXISTS fk_bjcw_jurisdiction_id;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

ALTER TABLE bronze.bronze_jurisdictions_counties DROP COLUMN IF EXISTS jurisdiction_id;
ALTER TABLE bronze.bronze_jurisdictions_counties
    ADD COLUMN jurisdiction_id TEXT GENERATED ALWAYS AS (
        bronze.jurisdiction_id_from_place(name, geoid)
    ) STORED;
DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_counties
        ADD CONSTRAINT uq_bjc_jurisdiction_id UNIQUE (jurisdiction_id);
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS idx_bjc_jurisdiction_id ON bronze.bronze_jurisdictions_counties(jurisdiction_id);

ALTER TABLE bronze.bronze_jurisdictions_counties_scraped DROP COLUMN IF EXISTS jurisdiction_id;
ALTER TABLE bronze.bronze_jurisdictions_counties_scraped
    ADD COLUMN jurisdiction_id TEXT;
UPDATE bronze.bronze_jurisdictions_counties_scraped s
    SET jurisdiction_id = c.jurisdiction_id
    FROM bronze.bronze_jurisdictions_counties c
    WHERE c.geoid = s.geoid;
ALTER TABLE bronze.bronze_jurisdictions_counties_scraped
    ADD CONSTRAINT fk_bjcs_jurisdiction_id
    FOREIGN KEY (jurisdiction_id)
    REFERENCES bronze.bronze_jurisdictions_counties(jurisdiction_id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_bjcs_jurisdiction_id ON bronze.bronze_jurisdictions_counties_scraped(jurisdiction_id);

DO $$ BEGIN
    UPDATE bronze.bronze_jurisdictions_counties_wikidata w
        SET jurisdiction_id = c.jurisdiction_id
        FROM bronze.bronze_jurisdictions_counties c
        WHERE c.geoid = w.geoid;
    ALTER TABLE bronze.bronze_jurisdictions_counties_wikidata
        ADD CONSTRAINT fk_bjcw_jurisdiction_id
        FOREIGN KEY (jurisdiction_id)
        REFERENCES bronze.bronze_jurisdictions_counties(jurisdiction_id) ON DELETE CASCADE;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- ═════════════════════════════════════════════════════════════════════════════
-- MUNICIPALITIES
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped
    DROP CONSTRAINT IF EXISTS fk_bjms_jurisdiction_id;
DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_municipalities_wikidata
        DROP CONSTRAINT IF EXISTS fk_bjmw_jurisdiction_id;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

ALTER TABLE bronze.bronze_jurisdictions_municipalities DROP COLUMN IF EXISTS jurisdiction_id;
ALTER TABLE bronze.bronze_jurisdictions_municipalities
    ADD COLUMN jurisdiction_id TEXT GENERATED ALWAYS AS (
        bronze.jurisdiction_id_from_place(name, geoid)
    ) STORED;
DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_municipalities
        ADD CONSTRAINT uq_bjm_jurisdiction_id UNIQUE (jurisdiction_id);
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS idx_bjm_jurisdiction_id ON bronze.bronze_jurisdictions_municipalities(jurisdiction_id);

ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped DROP COLUMN IF EXISTS jurisdiction_id;
ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped
    ADD COLUMN jurisdiction_id TEXT;
UPDATE bronze.bronze_jurisdictions_municipalities_scraped s
    SET jurisdiction_id = m.jurisdiction_id
    FROM bronze.bronze_jurisdictions_municipalities m
    WHERE m.geoid = s.geoid;
ALTER TABLE bronze.bronze_jurisdictions_municipalities_scraped
    ADD CONSTRAINT fk_bjms_jurisdiction_id
    FOREIGN KEY (jurisdiction_id)
    REFERENCES bronze.bronze_jurisdictions_municipalities(jurisdiction_id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_bjms_jurisdiction_id ON bronze.bronze_jurisdictions_municipalities_scraped(jurisdiction_id);

DO $$ BEGIN
    UPDATE bronze.bronze_jurisdictions_municipalities_wikidata w
        SET jurisdiction_id = m.jurisdiction_id
        FROM bronze.bronze_jurisdictions_municipalities m
        WHERE m.geoid = w.geoid;
    ALTER TABLE bronze.bronze_jurisdictions_municipalities_wikidata
        ADD CONSTRAINT fk_bjmw_jurisdiction_id
        FOREIGN KEY (jurisdiction_id)
        REFERENCES bronze.bronze_jurisdictions_municipalities(jurisdiction_id) ON DELETE CASCADE;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- ═════════════════════════════════════════════════════════════════════════════
-- SCHOOL DISTRICTS (int_jurisdictions / public search)
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE bronze.bronze_jurisdictions_school_districts_scraped
    DROP CONSTRAINT IF EXISTS fk_bjsds_jurisdiction_id;
DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_school_districts_wikidata
        DROP CONSTRAINT IF EXISTS fk_bjsdw_jurisdiction_id;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

ALTER TABLE bronze.bronze_jurisdictions_school_districts DROP COLUMN IF EXISTS jurisdiction_id;
ALTER TABLE bronze.bronze_jurisdictions_school_districts
    ADD COLUMN jurisdiction_id TEXT GENERATED ALWAYS AS (
        bronze.jurisdiction_id_from_place(name, geoid)
    ) STORED;
DO $$ BEGIN
    ALTER TABLE bronze.bronze_jurisdictions_school_districts
        ADD CONSTRAINT uq_bjsd_jurisdiction_id UNIQUE (jurisdiction_id);
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS idx_bjsd_jurisdiction_id ON bronze.bronze_jurisdictions_school_districts(jurisdiction_id);

ALTER TABLE bronze.bronze_jurisdictions_school_districts_scraped DROP COLUMN IF EXISTS jurisdiction_id;
ALTER TABLE bronze.bronze_jurisdictions_school_districts_scraped
    ADD COLUMN jurisdiction_id TEXT;
UPDATE bronze.bronze_jurisdictions_school_districts_scraped s
    SET jurisdiction_id = d.jurisdiction_id
    FROM bronze.bronze_jurisdictions_school_districts d
    WHERE d.geoid = s.geoid;
ALTER TABLE bronze.bronze_jurisdictions_school_districts_scraped
    ADD CONSTRAINT fk_bjsds_jurisdiction_id
    FOREIGN KEY (jurisdiction_id)
    REFERENCES bronze.bronze_jurisdictions_school_districts(jurisdiction_id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_bjsds_jurisdiction_id ON bronze.bronze_jurisdictions_school_districts_scraped(jurisdiction_id);

DO $$ BEGIN
    UPDATE bronze.bronze_jurisdictions_school_districts_wikidata w
        SET jurisdiction_id = s.jurisdiction_id
        FROM bronze.bronze_jurisdictions_school_districts s
        WHERE s.geoid = w.geoid;
    ALTER TABLE bronze.bronze_jurisdictions_school_districts_wikidata
        ADD CONSTRAINT fk_bjsdw_jurisdiction_id
        FOREIGN KEY (jurisdiction_id)
        REFERENCES bronze.bronze_jurisdictions_school_districts(jurisdiction_id) ON DELETE CASCADE;
EXCEPTION WHEN undefined_table THEN NULL; END $$;

-- Scraped rows: copy jurisdiction_id from base table on insert/update (no subquery in GENERATED).
CREATE OR REPLACE FUNCTION bronze.trg_set_scraped_jurisdiction_id()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_TABLE_NAME = 'bronze_jurisdictions_counties_scraped' THEN
        SELECT jurisdiction_id INTO NEW.jurisdiction_id
        FROM bronze.bronze_jurisdictions_counties WHERE geoid = NEW.geoid;
    ELSIF TG_TABLE_NAME = 'bronze_jurisdictions_municipalities_scraped' THEN
        SELECT jurisdiction_id INTO NEW.jurisdiction_id
        FROM bronze.bronze_jurisdictions_municipalities WHERE geoid = NEW.geoid;
    ELSIF TG_TABLE_NAME = 'bronze_jurisdictions_school_districts_scraped' THEN
        SELECT jurisdiction_id INTO NEW.jurisdiction_id
        FROM bronze.bronze_jurisdictions_school_districts WHERE geoid = NEW.geoid;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_bjcs_jurisdiction_id ON bronze.bronze_jurisdictions_counties_scraped;
CREATE TRIGGER trg_bjcs_jurisdiction_id
    BEFORE INSERT OR UPDATE OF geoid ON bronze.bronze_jurisdictions_counties_scraped
    FOR EACH ROW EXECUTE FUNCTION bronze.trg_set_scraped_jurisdiction_id();

DROP TRIGGER IF EXISTS trg_bjms_jurisdiction_id ON bronze.bronze_jurisdictions_municipalities_scraped;
CREATE TRIGGER trg_bjms_jurisdiction_id
    BEFORE INSERT OR UPDATE OF geoid ON bronze.bronze_jurisdictions_municipalities_scraped
    FOR EACH ROW EXECUTE FUNCTION bronze.trg_set_scraped_jurisdiction_id();

DROP TRIGGER IF EXISTS trg_bjsds_jurisdiction_id ON bronze.bronze_jurisdictions_school_districts_scraped;
CREATE TRIGGER trg_bjsds_jurisdiction_id
    BEFORE INSERT OR UPDATE OF geoid ON bronze.bronze_jurisdictions_school_districts_scraped
    FOR EACH ROW EXECUTE FUNCTION bronze.trg_set_scraped_jurisdiction_id();
