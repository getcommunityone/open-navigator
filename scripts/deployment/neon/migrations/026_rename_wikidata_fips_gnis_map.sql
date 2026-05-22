-- Rename Wikidata FIPS/GNIS lookup table (jurisdiction scope).
-- Dev:  psql "$NEON_DATABASE_URL_DEV" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/026_rename_wikidata_fips_gnis_map.sql
-- Prod: psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/026_rename_wikidata_fips_gnis_map.sql
--
-- wikidata_fips_gnis_map → jurisdiction_wikidata_fips_gnis_map

BEGIN;

ALTER TABLE IF EXISTS public.wikidata_fips_gnis_map RENAME TO jurisdiction_wikidata_fips_gnis_map;

COMMIT;
