-- Add municipality_state_usps + raw_row; drop legacy raw_city_json (per-city fields are columns).
-- Safe if 029 already created the new shape (no raw_city_json): adds missing columns, no-op update, DROP IF EXISTS.
--
--   psql "$OPEN_NAVIGATOR_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/030_league_bronze_columns_raw_row.sql

ALTER TABLE bronze.bronze_jurisdictions_municipalities_league
    ADD COLUMN IF NOT EXISTS municipality_state_usps VARCHAR(2);

ALTER TABLE bronze.bronze_jurisdictions_municipalities_league
    ADD COLUMN IF NOT EXISTS raw_row JSONB NOT NULL DEFAULT '[]'::jsonb;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'bronze'
          AND table_name = 'bronze_jurisdictions_municipalities_league'
          AND column_name = 'raw_city_json'
    ) THEN
        EXECUTE $mig$
            UPDATE bronze.bronze_jurisdictions_municipalities_league
            SET
                municipality_state_usps = COALESCE(
                    NULLIF(TRIM(UPPER(raw_city_json->>'state_usps')), ''),
                    municipality_state_usps
                ),
                raw_row = CASE
                    WHEN raw_city_json ? 'raw_row'
                         AND jsonb_typeof(raw_city_json->'raw_row') = 'array'
                    THEN raw_city_json->'raw_row'
                    ELSE raw_row
                END
            WHERE raw_city_json IS NOT NULL
              AND raw_city_json <> '{}'::jsonb
        $mig$;
    END IF;
END$$;

ALTER TABLE bronze.bronze_jurisdictions_municipalities_league
    DROP COLUMN IF EXISTS raw_city_json;
