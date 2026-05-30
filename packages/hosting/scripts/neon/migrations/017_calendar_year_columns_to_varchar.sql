-- Calendar / tax / filing year labels as VARCHAR(4), not INTEGER, across bronze + public search tables.
-- Apply with: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/017_calendar_year_columns_to_varchar.sql
-- Safe to re-run: each block skips if the column is already character type.

-- ---------------------------------------------------------------------------
-- public (Neon / schema.sql "gold" search tables)
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'contact'
      AND column_name = 'tax_year' AND data_type = 'integer'
  ) THEN
    ALTER TABLE public.contact
      ALTER COLUMN tax_year TYPE VARCHAR(4)
      USING (CASE WHEN tax_year IS NULL THEN NULL ELSE tax_year::text END);
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- bronze.bronze_bills (from dbt bronze_bills_from_ai)
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'bronze' AND table_name = 'bronze_bills'
      AND column_name = 'year' AND data_type = 'integer'
  ) THEN
    ALTER TABLE bronze.bronze_bills
      ALTER COLUMN year TYPE VARCHAR(4)
      USING (CASE WHEN year IS NULL THEN NULL ELSE year::text END);
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- NCCS nonprofit bronze (year labels; org_year_count stays integer)
-- ---------------------------------------------------------------------------

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['bronze_organizations_nonprofits_nccs', 'bronze_organizations_nonprofits_nccs_history']
  LOOP
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'bronze' AND table_name = t
        AND column_name = 'org_fiscal_year' AND data_type = 'integer'
    ) THEN
      EXECUTE format(
        'ALTER TABLE bronze.%I ALTER COLUMN org_fiscal_year TYPE VARCHAR(4) USING (CASE WHEN org_fiscal_year IS NULL THEN NULL ELSE org_fiscal_year::text END)',
        t
      );
    END IF;
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'bronze' AND table_name = t
        AND column_name = 'org_ruling_year' AND data_type = 'integer'
    ) THEN
      EXECUTE format(
        'ALTER TABLE bronze.%I ALTER COLUMN org_ruling_year TYPE VARCHAR(4) USING (CASE WHEN org_ruling_year IS NULL THEN NULL ELSE org_ruling_year::text END)',
        t
      );
    END IF;
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'bronze' AND table_name = t
        AND column_name = 'org_year_first' AND data_type = 'integer'
    ) THEN
      EXECUTE format(
        'ALTER TABLE bronze.%I ALTER COLUMN org_year_first TYPE VARCHAR(4) USING (CASE WHEN org_year_first IS NULL THEN NULL ELSE org_year_first::text END)',
        t
      );
    END IF;
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'bronze' AND table_name = t
        AND column_name = 'org_year_last' AND data_type = 'integer'
    ) THEN
      EXECUTE format(
        'ALTER TABLE bronze.%I ALTER COLUMN org_year_last TYPE VARCHAR(4) USING (CASE WHEN org_year_last IS NULL THEN NULL ELSE org_year_last::text END)',
        t
      );
    END IF;
  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- Census / shapefile vintage year on bronze geographies
-- ---------------------------------------------------------------------------

DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT unnest(ARRAY[
      'bronze_jurisdictions_place_county',
      'bronze_geo_states',
      'bronze_geo_counties',
      'bronze_geo_places',
      'bronze_geo_zcta'
    ]) AS tbl
  LOOP
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'bronze' AND table_name = r.tbl
        AND column_name = 'vintage_year'
        AND data_type IN ('smallint', 'integer', 'bigint')
    ) THEN
      EXECUTE format(
        'ALTER TABLE bronze.%I ALTER COLUMN vintage_year TYPE VARCHAR(4) USING (CASE WHEN vintage_year IS NULL THEN NULL ELSE vintage_year::text END)',
        r.tbl
      );
    END IF;
  END LOOP;
END $$;
