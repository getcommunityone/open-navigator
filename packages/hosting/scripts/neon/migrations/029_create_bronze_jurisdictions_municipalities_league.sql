-- League of Cities / state municipal league directory rows (cache JSON → bronze).
--
-- Apply (use a real Postgres URL; empty DATABASE_URL makes psql use socket :5432 + your OS user):
--   psql "$OPEN_NAVIGATOR_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/029_create_bronze_jurisdictions_municipalities_league.sql
--   # or local docker-style default from scripts/database/target_database_url.py:
--   psql "postgresql://postgres:${POSTGRES_PASSWORD:-password}@localhost:5433/open_navigator" -v ON_ERROR_STOP=1 -f scripts/deployment/neon/migrations/029_create_bronze_jurisdictions_municipalities_league.sql
--
-- Load:
--   python scripts/datasources/leagueofcities/load_league_city_directories_to_bronze.py
-- Upgrade from raw_city_json (if applicable):
--   psql ... -f scripts/deployment/neon/migrations/030_league_bronze_columns_raw_row.sql
-- Rename state_usps / state_name on older installs:
--   psql ... -f scripts/deployment/neon/migrations/031_rename_league_state_columns.sql

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_jurisdictions_municipalities_league (
    row_key                      TEXT          PRIMARY KEY,
    state_code                   VARCHAR(2)    NOT NULL,
    state                        TEXT,
    league_organization          TEXT,
    league_base_url              TEXT,
    league_state_extracted_at    TIMESTAMPTZ,
    state_extraction_status      TEXT,
    municipality_name            VARCHAR(500)  NOT NULL,
    population_raw               TEXT,
    county                       TEXT,
    mayor                        TEXT,
    website                      TEXT,
    phone                        VARCHAR(120),
    email                        TEXT,
    address                      TEXT,
    municipality_type            TEXT,
    source_url                   TEXT,
    source_kind                  TEXT,
    source_detail                TEXT,
    league_profile_url           TEXT,
    alternate_names              JSONB         NOT NULL DEFAULT '[]'::jsonb,
    municipality_state_usps      VARCHAR(2),
    raw_row                      JSONB         NOT NULL DEFAULT '[]'::jsonb,
    census_geoid                 VARCHAR(7),
    jurisdiction_id              TEXT,
    jurisdiction_match_method    TEXT,
    ingestion_date               TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bjmleague_state
    ON bronze.bronze_jurisdictions_municipalities_league (state_code);

CREATE INDEX IF NOT EXISTS idx_bjmleague_jurisdiction_id
    ON bronze.bronze_jurisdictions_municipalities_league (jurisdiction_id)
    WHERE jurisdiction_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_bjmleague_geoid
    ON bronze.bronze_jurisdictions_municipalities_league (census_geoid)
    WHERE census_geoid IS NOT NULL;

COMMENT ON TABLE bronze.bronze_jurisdictions_municipalities_league IS
    'State municipal league / League-style city directory rows from data/cache/leagueofcities/*/cities.json; '
    'jurisdiction_id is resolved to bronze.bronze_jurisdictions_municipalities when the loader can match '
    'Census place name + state.';

COMMENT ON COLUMN bronze.bronze_jurisdictions_municipalities_league.row_key IS
    'Stable synthetic key (MD5 hex) from municipality state, name, profile URL, and source_detail so re-runs upsert cleanly.';

COMMENT ON COLUMN bronze.bronze_jurisdictions_municipalities_league.municipality_state_usps IS
    'USPS from the city JSON when present; used with municipality_name for Census matching.';

COMMENT ON COLUMN bronze.bronze_jurisdictions_municipalities_league.raw_row IS
    'Source table row as JSON array (scraper-native order); not folded into raw_city_json.';

COMMENT ON COLUMN bronze.bronze_jurisdictions_municipalities_league.jurisdiction_match_method IS
    'place_name_exact | place_name_normalized | place_name_fuzzy_* | website_url_state | alternate_* | unmatched (or NULL if not attempted).';
