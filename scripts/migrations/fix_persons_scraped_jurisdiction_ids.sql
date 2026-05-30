-- Migration: canonicalize legacy generic-prefix jurisdiction_id values in
--            bronze.bronze_persons_scraped.
--
-- Some scraped person rows were written with a generic-typed jurisdiction_id
-- ("{type}_{geoid}") instead of the canonical name-slug form ("{slug}_{geoid}")
-- used everywhere else in that table and in the canonical jurisdictions tables:
--
--     county_55091         -> pepin_55091
--     municipality_1304980 -> baldwin_1304980
--
-- The correct slug is taken from the matching canonical table, joined on the
-- numeric GEOID tail (unique per table):
--     county_<fips>       -> bronze.bronze_jurisdictions_counties
--     municipality_<fips> -> bronze.bronze_jurisdictions_municipalities
--
-- Idempotent: only rows whose id still uses the generic "county_"/"municipality_"
-- prefix are touched, so re-running is a no-op.
--
-- Apply (local dev warehouse):
--     psql "$OPEN_NAVIGATOR_DATABASE_URL" -f scripts/migrations/fix_persons_scraped_jurisdiction_ids.sql

BEGIN;

-- Counties: county_<5-digit-fips> -> <county_slug>_<fips>
UPDATE bronze.bronze_persons_scraped p
SET jurisdiction_id = c.jurisdiction_id
FROM bronze.bronze_jurisdictions_counties c
WHERE p.jurisdiction_id ~ '^county_[0-9]+$'
  AND c.jurisdiction_id ~ ('_' || split_part(p.jurisdiction_id, '_', 2) || '$');

-- Municipalities: municipality_<7-digit-place-fips> -> <place_slug>_<fips>
UPDATE bronze.bronze_persons_scraped p
SET jurisdiction_id = m.jurisdiction_id
FROM bronze.bronze_jurisdictions_municipalities m
WHERE p.jurisdiction_id ~ '^municipality_[0-9]+$'
  AND m.jurisdiction_id ~ ('_' || split_part(p.jurisdiction_id, '_', 2) || '$');

COMMIT;
